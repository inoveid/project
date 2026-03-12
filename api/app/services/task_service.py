import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.workflow import Workflow
from app.models.session import Session, Message
from app.schemas.task import TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)

VALID_TRANSITIONS: dict[str, list[str]] = {
    "backlog": ["in_progress"],
    "in_progress": ["awaiting_user", "done", "error"],
    "awaiting_user": ["in_progress", "error"],
    "done": ["in_progress"],
    "error": ["in_progress"],
}

REQUIRED_FOR_IN_PROGRESS = [
    "title",
    "description",
    "product_id",
    "team_id",
    "workflow_id",
]


async def create_task(db: AsyncSession, data: TaskCreate) -> Task:
    task = Task(
        title=data.title,
        description=data.description,
        product_id=data.product_id,
        team_id=data.team_id,
        workflow_id=data.workflow_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_tasks(db: AsyncSession, product_id: uuid.UUID) -> list[Task]:
    stmt = (
        select(Task)
        .where(Task.product_id == product_id)
        .order_by(Task.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task:
    stmt = select(Task).where(Task.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def update_task(
    db: AsyncSession, task_id: uuid.UUID, data: TaskUpdate
) -> Task:
    task = await get_task(db, task_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task_id: uuid.UUID) -> None:
    task = await get_task(db, task_id)
    await db.delete(task)
    await db.commit()


async def update_task_status(
    db: AsyncSession, task_id: uuid.UUID, new_status: str
) -> Task:
    task = await get_task(db, task_id)
    current_status = task.status

    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid transition: {current_status} -> {new_status}",
        )

    if new_status == "in_progress" and current_status == "backlog":
        missing = [
            f for f in REQUIRED_FOR_IN_PROGRESS if not getattr(task, f)
        ]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Required fields missing: {', '.join(missing)}",
            )

    task.status = new_status
    await db.commit()
    await db.refresh(task)

    # Auto-create session for starting agent when task starts
    if new_status == "in_progress" and current_status == "backlog" and task.workflow_id:
        try:
            workflow = await db.get(Workflow, task.workflow_id)
            if workflow:
                # Resolve starting prompt with task variables
                prompt = workflow.starting_prompt
                prompt = prompt.replace("{{task_title}}", task.title or "")
                prompt = prompt.replace("{{task_description}}", task.description or "")

                session = Session(
                    agent_id=workflow.starting_agent_id,
                    task_id=task.id,
                    status="active",
                )
                db.add(session)
                await db.flush()

                if prompt:
                    message = Message(
                        session_id=session.id,
                        role="user",
                        content=prompt,
                    )
                    db.add(message)

                await db.commit()
                logger.info("Auto-created session %s for task %s (agent %s)", session.id, task.id, workflow.starting_agent_id)
        except Exception:
            logger.exception("Failed to auto-create session for task %s", task.id)

    return task
