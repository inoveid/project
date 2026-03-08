"""Evaluation service: управление eval cases, runs и запуск оценки."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import EvalCase, EvalResult, EvalRun
from app.schemas.evaluation import (
    EvalCaseCreate,
    EvalCaseUpdate,
    EvalRunCreate,
    JudgeRequest,
    RubricCriterion,
)
from app.services.judge_service import judge_agent_output

logger = logging.getLogger(__name__)


# ── EvalCase CRUD ────────────────────────────────────────────────────────────

async def create_case(db: AsyncSession, data: EvalCaseCreate) -> EvalCase:
    case = EvalCase(
        name=data.name,
        description=data.description,
        agent_role=data.agent_role,
        task_prompt=data.task_prompt,
        context_files=data.context_files,
        rubric=[c.model_dump() for c in data.rubric],
        expected_artifacts=data.expected_artifacts,
        tags=data.tags,
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


async def list_cases(
    db: AsyncSession, agent_role: str | None = None, tag: str | None = None
) -> list[EvalCase]:
    q = select(EvalCase).order_by(EvalCase.created_at.desc())
    if agent_role:
        q = q.where(EvalCase.agent_role == agent_role)
    result = await db.execute(q)
    cases = list(result.scalars().all())
    if tag:
        cases = [c for c in cases if tag in (c.tags or [])]
    return cases


async def get_case(db: AsyncSession, case_id: uuid.UUID) -> EvalCase | None:
    return await db.get(EvalCase, case_id)


async def update_case(
    db: AsyncSession, case_id: uuid.UUID, data: EvalCaseUpdate
) -> EvalCase | None:
    case = await db.get(EvalCase, case_id)
    if not case:
        return None
    update_data = data.model_dump(exclude_unset=True)
    if "rubric" in update_data and update_data["rubric"] is not None:
        update_data["rubric"] = [c.model_dump() for c in data.rubric]
    for key, value in update_data.items():
        setattr(case, key, value)
    await db.commit()
    await db.refresh(case)
    return case


async def delete_case(db: AsyncSession, case_id: uuid.UUID) -> bool:
    case = await db.get(EvalCase, case_id)
    if not case:
        return False
    await db.delete(case)
    await db.commit()
    return True


# ── EvalRun CRUD ─────────────────────────────────────────────────────────────

async def create_run(db: AsyncSession, data: EvalRunCreate) -> EvalRun:
    run = EvalRun(
        name=data.name,
        prompt_version=data.prompt_version,
        prompt_snapshot=data.prompt_snapshot,
        model=data.model,
        metadata_=data.metadata,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def list_runs(db: AsyncSession, prompt_version: str | None = None) -> list[EvalRun]:
    q = select(EvalRun).order_by(EvalRun.created_at.desc())
    if prompt_version:
        q = q.where(EvalRun.prompt_version == prompt_version)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_run(db: AsyncSession, run_id: uuid.UUID) -> EvalRun | None:
    return await db.get(EvalRun, run_id)


async def get_run_results(db: AsyncSession, run_id: uuid.UUID) -> list[EvalResult]:
    q = (
        select(EvalResult)
        .where(EvalResult.run_id == run_id)
        .order_by(EvalResult.created_at)
    )
    result = await db.execute(q)
    return list(result.scalars().all())


# ── Eval Execution ───────────────────────────────────────────────────────────

async def execute_eval_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    case_ids: list[uuid.UUID] | None = None,
    agent_output_provider=None,
) -> EvalRun:
    """Запустить eval run: для каждого кейса вызвать judge и сохранить результат.

    Args:
        db: database session
        run_id: ID ранее созданного run
        case_ids: список кейсов (если None — все кейсы для agent_role)
        agent_output_provider: async callable(case) -> str
            Функция, возвращающая output агента для кейса.
            Если None — используется task_prompt как mock output (для тестирования judge).
    """
    run = await db.get(EvalRun, run_id)
    if not run:
        raise ValueError(f"EvalRun {run_id} not found")

    # Загрузить кейсы
    if case_ids:
        q = select(EvalCase).where(EvalCase.id.in_(case_ids))
    else:
        q = select(EvalCase)
    result = await db.execute(q)
    cases = list(result.scalars().all())

    if not cases:
        raise ValueError("No eval cases found")

    # Обновить статус
    run.status = "running"
    run.total_cases = len(cases)
    run.started_at = datetime.now(timezone.utc)
    await db.commit()

    passed = 0
    failed = 0

    for case in cases:
        try:
            start_time = time.monotonic()

            # Получить output агента
            if agent_output_provider:
                agent_output = await agent_output_provider(case)
            else:
                agent_output = f"[Mock output for eval case: {case.name}]"

            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Собрать rubric из JSONB
            rubric = [RubricCriterion(**c) for c in case.rubric]

            # Вызвать Judge
            judge_request = JudgeRequest(
                agent_output=agent_output,
                task_prompt=case.task_prompt,
                rubric=rubric,
                context_files=case.context_files or {},
                expected_artifacts=case.expected_artifacts or [],
            )

            judge_response, token_usage = await judge_agent_output(
                judge_request, model=run.model
            )

            # Сохранить результат
            eval_result = EvalResult(
                run_id=run.id,
                case_id=case.id,
                agent_output=agent_output,
                verdict=judge_response.verdict,
                score=judge_response.score,
                criteria_scores={
                    cs.name: {"score": cs.score, "reasoning": cs.reasoning}
                    for cs in judge_response.criteria_scores
                },
                judge_reasoning=judge_response.reasoning,
                trajectory={},
                token_usage=token_usage,
                duration_ms=duration_ms,
            )
            db.add(eval_result)

            if judge_response.verdict == "pass":
                passed += 1
            else:
                failed += 1

            logger.info(
                "Case '%s': verdict=%s score=%.3f",
                case.name,
                judge_response.verdict,
                judge_response.score,
            )

        except Exception as e:
            logger.error("Case '%s' failed: %s", case.name, e)
            eval_result = EvalResult(
                run_id=run.id,
                case_id=case.id,
                agent_output=str(e),
                verdict="error",
                score=0.0,
                criteria_scores={},
                judge_reasoning=f"Error during evaluation: {e}",
                trajectory={},
                token_usage={},
            )
            db.add(eval_result)
            failed += 1

    # Обновить run
    run.passed_cases = passed
    run.failed_cases = failed
    run.pass_rate = round(passed / len(cases), 3) if cases else 0.0
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(run)

    logger.info(
        "EvalRun '%s' completed: %d/%d passed (%.1f%%)",
        run.name,
        passed,
        len(cases),
        run.pass_rate * 100,
    )

    return run


# ── Comparison ───────────────────────────────────────────────────────────────

async def compare_runs(
    db: AsyncSession, run_id_a: uuid.UUID, run_id_b: uuid.UUID
) -> dict:
    """Сравнить два eval run по критериям — regression detection."""
    results_a = await get_run_results(db, run_id_a)
    results_b = await get_run_results(db, run_id_b)

    run_a = await get_run(db, run_id_a)
    run_b = await get_run(db, run_id_b)

    # Индексировать по case_id
    by_case_a = {r.case_id: r for r in results_a}
    by_case_b = {r.case_id: r for r in results_b}

    common_cases = set(by_case_a.keys()) & set(by_case_b.keys())

    regressions = []
    improvements = []

    for case_id in common_cases:
        ra = by_case_a[case_id]
        rb = by_case_b[case_id]

        if ra.verdict == "pass" and rb.verdict != "pass":
            regressions.append({
                "case_id": str(case_id),
                "score_a": ra.score,
                "score_b": rb.score,
                "delta": rb.score - ra.score,
            })
        elif ra.verdict != "pass" and rb.verdict == "pass":
            improvements.append({
                "case_id": str(case_id),
                "score_a": ra.score,
                "score_b": rb.score,
                "delta": rb.score - ra.score,
            })

    return {
        "run_a": {"id": str(run_id_a), "prompt_version": run_a.prompt_version if run_a else None,
                   "pass_rate": run_a.pass_rate if run_a else None},
        "run_b": {"id": str(run_id_b), "prompt_version": run_b.prompt_version if run_b else None,
                   "pass_rate": run_b.pass_rate if run_b else None},
        "common_cases": len(common_cases),
        "regressions": regressions,
        "improvements": improvements,
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
    }
