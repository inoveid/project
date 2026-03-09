from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

SYSTEM_AGENT_PROMPT = """
Ты — ассистент для управления платформой AI-агентов Agent Console.
Ты можешь создавать и управлять бизнесами, продуктами, командами и агентами.
Отвечай кратко и по делу. Для управления платформой используй доступные инструменты.
"""


async def seed_system_agent(db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).where(Agent.is_system == True))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    agent = Agent(
        name="Assistant",
        is_system=True,
        system_prompt=SYSTEM_AGENT_PROMPT,
        config={"allowed_tools": ["Bash"]},
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent
