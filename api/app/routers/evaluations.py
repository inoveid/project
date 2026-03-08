import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.database import get_db
from app.schemas.evaluation import (
    EvalCaseCreate,
    EvalCaseRead,
    EvalCaseUpdate,
    EvalRunCreate,
    EvalRunRead,
    EvalRunSummary,
    EvalResultRead,
)
from app.services import eval_service

router = APIRouter()


# ── EvalCase endpoints ───────────────────────────────────────────────────────

@router.post("/eval/cases", response_model=EvalCaseRead, status_code=201)
async def create_eval_case(body: EvalCaseCreate, db: AsyncSession = Depends(get_db)):
    case = await eval_service.create_case(db, body)
    return case


@router.get("/eval/cases", response_model=list[EvalCaseRead])
async def list_eval_cases(
    agent_role: str | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await eval_service.list_cases(db, agent_role=agent_role, tag=tag)


@router.get("/eval/cases/{case_id}", response_model=EvalCaseRead)
async def get_eval_case(case_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    case = await eval_service.get_case(db, case_id)
    if not case:
        raise HTTPException(404, "Eval case not found")
    return case


@router.patch("/eval/cases/{case_id}", response_model=EvalCaseRead)
async def update_eval_case(
    case_id: uuid.UUID, body: EvalCaseUpdate, db: AsyncSession = Depends(get_db)
):
    case = await eval_service.update_case(db, case_id, body)
    if not case:
        raise HTTPException(404, "Eval case not found")
    return case


@router.delete("/eval/cases/{case_id}", status_code=204)
async def delete_eval_case(case_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await eval_service.delete_case(db, case_id)
    if not deleted:
        raise HTTPException(404, "Eval case not found")


# ── EvalRun endpoints ────────────────────────────────────────────────────────

@router.post("/eval/runs", response_model=EvalRunSummary, status_code=201)
async def create_eval_run(
    body: EvalRunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Создать и запустить eval run в фоне."""
    run = await eval_service.create_run(db, body)
    case_ids = body.case_ids or None

    async def _run_eval():
        from app.database import async_session
        async with async_session() as session:
            try:
                await eval_service.execute_eval_run(session, run.id, case_ids=case_ids)
            except Exception:
                logger.exception("Eval run %s failed", run.id)
                try:
                    from app.models.evaluation import EvalRun
                    run_obj = await session.get(EvalRun, run.id)
                    if run_obj and run_obj.status == "running":
                        run_obj.status = "failed"
                        await session.commit()
                except Exception:
                    logger.exception("Failed to mark eval run %s as failed", run.id)

    background_tasks.add_task(_run_eval)
    return run


@router.get("/eval/runs", response_model=list[EvalRunSummary])
async def list_eval_runs(
    prompt_version: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    return await eval_service.list_runs(db, prompt_version=prompt_version)


@router.get("/eval/runs/{run_id}", response_model=EvalRunRead)
async def get_eval_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run = await eval_service.get_run(db, run_id)
    if not run:
        raise HTTPException(404, "Eval run not found")
    return run


@router.get("/eval/runs/{run_id}/results", response_model=list[EvalResultRead])
async def get_eval_run_results(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await eval_service.get_run_results(db, run_id)


# ── Comparison ───────────────────────────────────────────────────────────────

@router.get("/eval/compare")
async def compare_eval_runs(
    run_a: uuid.UUID,
    run_b: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Сравнить два eval run — regression detection."""
    return await eval_service.compare_runs(db, run_a, run_b)
