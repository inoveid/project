import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings
from app.services.redis_service import init_redis, close_redis
from app.database import async_session
from app.routers import agents, auth, businesses, evaluations, memory, notifications_ws, products, sessions, specs, tasks, teams, terminal_ws, workflow_edges, workflows, ws
import app.services.graph_service as graph_svc
from app.services.system_agent_service import seed_system_agent
from app.services.auth_user_service import get_current_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Redis
    await init_redis()

    # Преобразовать asyncpg URL → psycopg3 URL для AsyncPostgresSaver
    postgres_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    # async with держит connection pool живым на время работы приложения
    async with AsyncPostgresSaver.from_conn_string(postgres_url) as checkpointer:
        # Создать таблицы checkpointer (langgraph_checkpoints, langgraph_writes, ...)
        await checkpointer.setup()
        # Скомпилировать граф с checkpointer и сохранить в module-level singleton
        graph_svc._compiled_graph = graph_svc.build_graph(checkpointer)
        async with async_session() as db:
            await seed_system_agent(db)
        yield
    # Cleanup
    await close_redis()


app = FastAPI(title="Agent Console API", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth — public (no JWT required)
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

# Protected routes — require JWT
_auth = [Depends(get_current_user)]

app.include_router(teams.router, prefix="/api/teams", tags=["teams"], dependencies=_auth)
app.include_router(agents.router, prefix="/api", tags=["agents"], dependencies=_auth)
app.include_router(workflows.router, prefix="/api", tags=["workflows"], dependencies=_auth)
app.include_router(workflow_edges.router, prefix="/api", tags=["workflow_edges"], dependencies=_auth)
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"], dependencies=_auth)
app.include_router(businesses.router, prefix="/api", tags=["businesses"], dependencies=_auth)
app.include_router(products.router, prefix="/api", tags=["products"], dependencies=_auth)
app.include_router(memory.router, prefix="/api", tags=["memory"], dependencies=_auth)
app.include_router(tasks.router, prefix="/api", tags=["tasks"], dependencies=_auth)
app.include_router(evaluations.router, prefix="/api", tags=["evaluations"], dependencies=_auth)
app.include_router(specs.router, prefix="/api", tags=["specs"], dependencies=_auth)

# WebSocket — без JWT (используют session-based auth при необходимости)
app.include_router(ws.router, prefix="/api/ws", tags=["websocket"])
app.include_router(notifications_ws.router, prefix="/api/ws", tags=["notifications"])
app.include_router(terminal_ws.router, prefix="/api/ws", tags=["terminal"])
