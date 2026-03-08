import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── EvalCase ─────────────────────────────────────────────────────────────────

class RubricCriterion(BaseModel):
    name: str
    description: str
    weight: float = Field(default=1.0, ge=0)
    pass_threshold: float = Field(default=0.7, ge=0, le=1)


class EvalCaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    agent_role: str = Field(default="developer", max_length=100)
    task_prompt: str = Field(..., min_length=1)
    context_files: dict[str, str] = Field(default_factory=dict)
    rubric: list[RubricCriterion]
    expected_artifacts: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class EvalCaseUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    task_prompt: Optional[str] = None
    context_files: Optional[dict[str, str]] = None
    rubric: Optional[list[RubricCriterion]] = None
    expected_artifacts: Optional[list[str]] = None
    tags: Optional[list[str]] = None


class EvalCaseRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    agent_role: str
    task_prompt: str
    context_files: dict
    rubric: list[dict]
    expected_artifacts: list
    tags: list
    created_at: datetime

    model_config = {"from_attributes": True}


# ── EvalRun ──────────────────────────────────────────────────────────────────

class EvalRunCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    prompt_version: str = Field(..., min_length=1, max_length=100)
    prompt_snapshot: str = Field(..., min_length=1)
    model: str = Field(default="claude-sonnet-4-20250514", max_length=100)
    case_ids: list[uuid.UUID] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class EvalRunRead(BaseModel):
    id: uuid.UUID
    name: str
    prompt_version: str
    prompt_snapshot: str
    model: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: Optional[float]
    metadata_: dict = Field(alias="metadata_")
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class EvalRunSummary(BaseModel):
    id: uuid.UUID
    name: str
    prompt_version: str
    model: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── EvalResult ───────────────────────────────────────────────────────────────

class CriterionScore(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    reasoning: str


class EvalResultRead(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    case_id: uuid.UUID
    agent_output: str
    verdict: str
    score: float
    criteria_scores: dict
    judge_reasoning: str
    trajectory: dict
    token_usage: dict
    duration_ms: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvalResultWithCase(EvalResultRead):
    case_name: str
    case_description: str


# ── Judge input/output ───────────────────────────────────────────────────────

class JudgeRequest(BaseModel):
    agent_output: str
    task_prompt: str
    rubric: list[RubricCriterion]
    context_files: dict[str, str] = Field(default_factory=dict)
    expected_artifacts: list[str] = Field(default_factory=list)


class JudgeResponse(BaseModel):
    verdict: str  # pass | fail
    score: float = Field(ge=0, le=1)
    criteria_scores: list[CriterionScore]
    reasoning: str
