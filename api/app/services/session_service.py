from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent
from app.models.session import Message, Session
from app.schemas.session import SessionCreate


class SessionNotFoundError(Exception):
    pass


class AgentNotFoundError(Exception):
    pass


async def create_session(db: AsyncSession, data: SessionCreate) -> Session:
    agent = await db.get(Agent, data.agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {data.agent_id} not found")

    session = Session(agent_id=data.agent_id, status="active")
    db.add(session)
    await db.commit()
    await db.refresh(session, attribute_names=["messages"])
    return session


async def get_sessions(
    db: AsyncSession,
    task_id: uuid.UUID | None = None,
) -> list[dict]:
    stmt = (
        select(Session, Agent.name.label("agent_name"))
        .join(Agent, Session.agent_id == Agent.id)
        .order_by(Session.created_at.desc())
    )
    if task_id is not None:
        stmt = stmt.where(Session.task_id == task_id)
    else:
        stmt = stmt.where(Session.status == "active")
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": session.id,
            "agent_id": session.agent_id,
            "agent_name": agent_name,
            "status": session.status,
            "created_at": session.created_at,
            "stopped_at": session.stopped_at,
        }
        for session, agent_name in rows
    ]


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> Session:
    stmt = (
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.messages), selectinload(Session.agent))
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")
    return session


async def stop_session(db: AsyncSession, session_id: uuid.UUID) -> Session:
    session = await get_session(db, session_id)
    session.status = "stopped"
    session.stopped_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)
    return session


async def add_message(
    db: AsyncSession,
    session_id: uuid.UUID,
    role: str,
    content: str,
    tool_uses: list[dict] | None = None,
) -> Message:
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        tool_uses=tool_uses,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
