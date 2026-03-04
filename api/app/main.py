from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import agents, agent_links, sessions, teams, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Agent Console API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router, prefix="/api/teams", tags=["teams"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(agent_links.router, prefix="/api", tags=["agent_links"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(ws.router, prefix="/api/ws", tags=["websocket"])
