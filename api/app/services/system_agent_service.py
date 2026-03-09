from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent

SYSTEM_AGENT_PROMPT = """
Ты — ассистент для управления платформой AI-агентов Agent Console.

Ты можешь:
- Создавать и просматривать бизнесы и продукты
- Создавать и просматривать команды агентов
- Создавать агентов в командах

Используй доступные инструменты для управления платформой.
Отвечай кратко и по делу на русском языке.
После выполнения действия — подтверди что сделал и покажи результат.

Примеры запросов:
- "Создай бизнес My Company"
- "Покажи все продукты бизнеса X"
- "Создай команду разработчиков"
- "Добавь агента Developer в команду Y"
"""


async def seed_system_agent(db: AsyncSession) -> Agent:
    result = await db.execute(select(Agent).where(Agent.is_system.is_(True)))
    existing = result.scalar_one_or_none()
    if existing:
        existing.system_prompt = SYSTEM_AGENT_PROMPT  # обновляем при рестарте
        await db.commit()
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
