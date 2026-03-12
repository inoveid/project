from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings
from app.services.redis_service import init_redis, close_redis
from app.database import async_session
from app.routers import agents, auth, businesses, evaluations, memory, notifications_ws, products, sessions, tasks, teams, workflow_edges, workflows, ws
import app.services.graph_service as graph_svc
from app.services.system_agent_service import seed_system_agent


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])
app.include_router(workflow_edges.router, prefix="/api", tags=["workflow_edges"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(businesses.router, prefix="/api", tags=["businesses"])
app.include_router(products.router, prefix="/api", tags=["products"])
app.include_router(ws.router, prefix="/api/ws", tags=["websocket"])
app.include_router(notifications_ws.router, prefix="/api/ws", tags=["notifications"])
app.include_router(memory.router, prefix="/api", tags=["memory"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(evaluations.router, prefix="/api", tags=["evaluations"])
