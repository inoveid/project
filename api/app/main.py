from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings
from app.routers import agents, agent_links, auth, evaluations, memory, sessions, teams, workspaces, ws
import app.services.graph_service as graph_svc


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Преобразовать asyncpg URL → psycopg3 URL для AsyncPostgresSaver
    postgres_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    # async with держит connection pool живым на время работы приложения
    async with AsyncPostgresSaver.from_conn_string(postgres_url) as checkpointer:
        # Создать таблицы checkpointer (langgraph_checkpoints, langgraph_writes, ...)
        await checkpointer.setup()
        # Скомпилировать граф с checkpointer и сохранить в module-level singleton
        graph_svc._compiled_graph = graph_svc.build_graph(checkpointer)
        yield


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
app.include_router(agent_links.router, prefix="/api", tags=["agent_links"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])
app.include_router(ws.router, prefix="/api/ws", tags=["websocket"])
app.include_router(memory.router, prefix="/api", tags=["memory"])
app.include_router(evaluations.router, prefix="/api", tags=["evaluations"])
