import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

SERVICE = "app.routers.evaluations.eval_service"


def _make_case(name: str = "crud-endpoint-basic") -> dict:
    return {
        "id": uuid.uuid4(),
        "name": name,
        "description": "Test eval case",
        "agent_role": "developer",
        "task_prompt": "Create a CRUD endpoint",
        "context_files": {},
        "rubric": [{"name": "correctness", "description": "Is it correct?", "weight": 1.0, "pass_threshold": 0.7}],
        "expected_artifacts": ["app/models/product.py"],
        "tags": ["backend", "basic"],
        "created_at": datetime.now(timezone.utc),
    }


def _make_run(name: str = "test-run") -> dict:
    return {
        "id": uuid.uuid4(),
        "name": name,
        "prompt_version": "v1.0",
        "prompt_snapshot": "You are a developer.",
        "model": "claude-sonnet-4-20250514",
        "status": "completed",
        "total_cases": 5,
        "passed_cases": 4,
        "failed_cases": 1,
        "pass_rate": 0.8,
        "metadata_": {},
        "started_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }


def _make_result(run_id: uuid.UUID, case_id: uuid.UUID) -> dict:
    return {
        "id": uuid.uuid4(),
        "run_id": run_id,
        "case_id": case_id,
        "agent_output": "Here is my implementation...",
        "verdict": "pass",
        "score": 0.85,
        "criteria_scores": {"correctness": {"score": 0.85, "reasoning": "Good"}},
        "judge_reasoning": "Overall good quality.",
        "trajectory": {},
        "token_usage": {"input_tokens": 500, "output_tokens": 200},
        "duration_ms": 1500,
        "created_at": datetime.now(timezone.utc),
    }


# ── EvalCase endpoints ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_eval_case(client):
    case = _make_case()
    with patch(f"{SERVICE}.create_case", new_callable=AsyncMock, return_value=case):
        resp = await client.post(
            "/api/eval/cases",
            json={
                "name": "crud-endpoint-basic",
                "description": "Test eval case",
                "task_prompt": "Create a CRUD endpoint",
                "rubric": [{"name": "correctness", "description": "Is it correct?", "weight": 1.0, "pass_threshold": 0.7}],
            },
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "crud-endpoint-basic"


@pytest.mark.asyncio
async def test_list_eval_cases(client):
    cases = [_make_case("case-1"), _make_case("case-2")]
    with patch(f"{SERVICE}.list_cases", new_callable=AsyncMock, return_value=cases):
        resp = await client.get("/api/eval/cases")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_eval_cases_filter_role(client):
    cases = [_make_case()]
    with patch(f"{SERVICE}.list_cases", new_callable=AsyncMock, return_value=cases) as mock:
        resp = await client.get("/api/eval/cases?agent_role=developer")
    assert resp.status_code == 200
    mock.assert_called_once()


@pytest.mark.asyncio
async def test_get_eval_case(client):
    case = _make_case()
    case_id = case["id"]
    with patch(f"{SERVICE}.get_case", new_callable=AsyncMock, return_value=case):
        resp = await client.get(f"/api/eval/cases/{case_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "crud-endpoint-basic"


@pytest.mark.asyncio
async def test_get_eval_case_not_found(client):
    case_id = uuid.uuid4()
    with patch(f"{SERVICE}.get_case", new_callable=AsyncMock, return_value=None):
        resp = await client.get(f"/api/eval/cases/{case_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_eval_case(client):
    case_id = uuid.uuid4()
    with patch(f"{SERVICE}.delete_case", new_callable=AsyncMock, return_value=True):
        resp = await client.delete(f"/api/eval/cases/{case_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_eval_case_not_found(client):
    case_id = uuid.uuid4()
    with patch(f"{SERVICE}.delete_case", new_callable=AsyncMock, return_value=False):
        resp = await client.delete(f"/api/eval/cases/{case_id}")
    assert resp.status_code == 404


# ── EvalRun endpoints ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_eval_run(client):
    run = _make_run()
    with patch(f"{SERVICE}.create_run", new_callable=AsyncMock, return_value=run):
        resp = await client.post(
            "/api/eval/runs",
            json={
                "name": "test-run",
                "prompt_version": "v1.0",
                "prompt_snapshot": "You are a developer.",
            },
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "test-run"


@pytest.mark.asyncio
async def test_list_eval_runs(client):
    runs = [_make_run("run-1"), _make_run("run-2")]
    with patch(f"{SERVICE}.list_runs", new_callable=AsyncMock, return_value=runs):
        resp = await client.get("/api/eval/runs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_get_eval_run(client):
    run = _make_run()
    run_id = run["id"]
    with patch(f"{SERVICE}.get_run", new_callable=AsyncMock, return_value=run):
        resp = await client.get(f"/api/eval/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["prompt_version"] == "v1.0"


@pytest.mark.asyncio
async def test_get_eval_run_not_found(client):
    run_id = uuid.uuid4()
    with patch(f"{SERVICE}.get_run", new_callable=AsyncMock, return_value=None):
        resp = await client.get(f"/api/eval/runs/{run_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_eval_run_results(client):
    run_id = uuid.uuid4()
    case_id = uuid.uuid4()
    results = [_make_result(run_id, case_id)]
    with patch(f"{SERVICE}.get_run_results", new_callable=AsyncMock, return_value=results):
        resp = await client.get(f"/api/eval/runs/{run_id}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["verdict"] == "pass"


# ── Comparison ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compare_eval_runs(client):
    run_a = uuid.uuid4()
    run_b = uuid.uuid4()
    comparison = {
        "run_a": {"id": str(run_a), "prompt_version": "v1.0", "pass_rate": 0.6},
        "run_b": {"id": str(run_b), "prompt_version": "v2.0", "pass_rate": 0.8},
        "common_cases": 5,
        "regressions": [],
        "improvements": [{"case_id": str(uuid.uuid4()), "score_a": 0.3, "score_b": 0.9, "delta": 0.6}],
        "regression_count": 0,
        "improvement_count": 1,
    }
    with patch(f"{SERVICE}.compare_runs", new_callable=AsyncMock, return_value=comparison):
        resp = await client.get(f"/api/eval/compare?run_a={run_a}&run_b={run_b}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["regression_count"] == 0
    assert data["improvement_count"] == 1


# ── Schema validation ────────────────────────────────────────────────────────

def test_rubric_criterion_schema():
    from app.schemas.evaluation import RubricCriterion
    c = RubricCriterion(name="test", description="desc", weight=2.0, pass_threshold=0.8)
    assert c.weight == 2.0
    assert c.pass_threshold == 0.8


def test_eval_case_create_schema():
    from app.schemas.evaluation import EvalCaseCreate, RubricCriterion
    data = EvalCaseCreate(
        name="test",
        description="desc",
        task_prompt="Do something",
        rubric=[RubricCriterion(name="c1", description="d1")],
    )
    assert data.agent_role == "developer"
    assert len(data.rubric) == 1


def test_eval_run_create_schema():
    from app.schemas.evaluation import EvalRunCreate
    data = EvalRunCreate(
        name="run-1",
        prompt_version="v1",
        prompt_snapshot="You are an agent.",
    )
    assert data.model == "claude-sonnet-4-20250514"
    assert data.case_ids == []


# ── Judge service unit tests ─────────────────────────────────────────────────

def test_parse_judge_response():
    from app.services.judge_service import _parse_judge_response
    from app.schemas.evaluation import RubricCriterion

    raw = '''{
        "criteria_scores": [
            {"name": "correctness", "score": 0.9, "reasoning": "Correct implementation"},
            {"name": "style", "score": 0.7, "reasoning": "Acceptable style"}
        ],
        "overall_reasoning": "Good overall quality"
    }'''

    rubric = [
        RubricCriterion(name="correctness", description="Is it correct?", weight=2.0, pass_threshold=0.7),
        RubricCriterion(name="style", description="Good style?", weight=1.0, pass_threshold=0.6),
    ]

    response = _parse_judge_response(raw, rubric)
    assert response.verdict == "pass"
    assert len(response.criteria_scores) == 2
    assert response.score > 0.8  # weighted avg: (0.9*2 + 0.7*1) / 3 ≈ 0.833


def test_parse_judge_response_fail():
    from app.services.judge_service import _parse_judge_response
    from app.schemas.evaluation import RubricCriterion

    raw = '''{
        "criteria_scores": [
            {"name": "correctness", "score": 0.3, "reasoning": "Incorrect"}
        ],
        "overall_reasoning": "Failed"
    }'''

    rubric = [
        RubricCriterion(name="correctness", description="desc", weight=1.0, pass_threshold=0.7),
    ]

    response = _parse_judge_response(raw, rubric)
    assert response.verdict == "fail"
    assert response.score == 0.3


def test_parse_judge_response_markdown_fences():
    from app.services.judge_service import _parse_judge_response
    from app.schemas.evaluation import RubricCriterion

    raw = '''```json
{
    "criteria_scores": [
        {"name": "test", "score": 0.8, "reasoning": "OK"}
    ],
    "overall_reasoning": "Fine"
}
```'''

    rubric = [RubricCriterion(name="test", description="d", weight=1.0, pass_threshold=0.5)]
    response = _parse_judge_response(raw, rubric)
    assert response.verdict == "pass"
    assert response.score == 0.8
