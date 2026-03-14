"""Token budget tracking and cost enforcement.

Tracks token usage and cost per session. Emits warning/critical events
when budget thresholds are reached. Supports HITL gate on budget exhaustion.

Budget hierarchy:
  system  → total daily spend cap
  session → per-session spend cap (one WebSocket conversation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (USD) — update when models change
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-haiku-4-20250506": {"input": 0.80, "output": 4.0},
}

# Fallback pricing if model is unknown
DEFAULT_PRICING = {"input": 3.0, "output": 15.0}


class BudgetLevel(str, Enum):
    OK = "ok"
    WARNING = "warning"      # 80% spent
    CRITICAL = "critical"    # 100% spent


class BudgetExceededError(Exception):
    """Raised when session budget is exhausted (hard limit)."""

    def __init__(self, spent: float, limit: float) -> None:
        self.spent = spent
        self.limit = limit
        super().__init__(
            f"Budget exceeded: ${spent:.4f} / ${limit:.4f}"
        )


@dataclass
class UsageRecord:
    """Single LLM call usage."""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass
class SessionBudget:
    """Tracks budget for one session."""
    limit_usd: float
    spent_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    call_count: int = 0
    max_tokens: int = 0
    _warned: bool = field(default=False, repr=False)

    @property
    def remaining_usd(self) -> float:
        return max(self.limit_usd - self.spent_usd, 0)

    @property
    def usage_ratio(self) -> float:
        if self.limit_usd <= 0:
            return 0.0
        return self.spent_usd / self.limit_usd

    @property
    def level(self) -> BudgetLevel:
        ratio = self.usage_ratio
        if ratio >= 1.0:
            return BudgetLevel.CRITICAL
        if ratio >= 0.8:
            return BudgetLevel.WARNING
        return BudgetLevel.OK


def compute_cost(
    input_tokens: int,
    output_tokens: int,
    model: Optional[str] = None,
    reported_cost: Optional[float] = None,
) -> float:
    """Compute cost for a single LLM call.

    If the API/CLI reports cost_usd, use that directly.
    Otherwise estimate from token counts and model pricing.
    """
    if reported_cost is not None and reported_cost > 0:
        return reported_cost

    pricing = MODEL_PRICING.get(model or "", DEFAULT_PRICING)
    cost = (
        input_tokens * pricing["input"] / 1_000_000
        + output_tokens * pricing["output"] / 1_000_000
    )
    return cost


class BudgetTracker:
    """Manages budgets across sessions.

    Args:
        default_session_limit: default $ limit per session.
        warning_threshold: ratio (0-1) at which to emit WARNING.
    """

    def __init__(
        self,
        default_session_limit: float = 2.0,
        warning_threshold: float = 0.8,
    ) -> None:
        self._default_limit = default_session_limit
        self._warning_threshold = warning_threshold
        self._sessions: dict[str, SessionBudget] = {}

    def start_session(
        self, session_id: str, limit_usd: Optional[float] = None,
        max_tokens: int = 0,
    ) -> None:
        self._sessions[session_id] = SessionBudget(
            limit_usd=limit_usd if limit_usd is not None else self._default_limit,
            max_tokens=max_tokens,
        )

    def get_budget(self, session_id: str) -> Optional[SessionBudget]:
        return self._sessions.get(session_id)

    def check_budget(self, session_id: str) -> None:
        """Pre-flight check: raise if budget or token limit exhausted."""
        budget = self._sessions.get(session_id)
        if not budget:
            return
        if budget.max_tokens > 0:
            total = budget.total_input_tokens + budget.total_output_tokens
            if total >= budget.max_tokens:
                raise BudgetExceededError(total, budget.max_tokens)
        if budget.level == BudgetLevel.CRITICAL:
            raise BudgetExceededError(budget.spent_usd, budget.limit_usd)

    def record_usage(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
        model: Optional[str] = None,
        reported_cost: Optional[float] = None,
    ) -> Optional[dict]:
        """Record usage after an LLM call. Returns budget event if threshold crossed."""
        budget = self._sessions.get(session_id)
        if not budget:
            return None

        cost = compute_cost(input_tokens, output_tokens, model, reported_cost)
        budget.spent_usd += cost
        budget.total_input_tokens += input_tokens
        budget.total_output_tokens += output_tokens
        budget.call_count += 1

        logger.info(
            "[Budget:%s] call #%d: +$%.4f (total: $%.4f / $%.4f)",
            session_id[:8],
            budget.call_count,
            cost,
            budget.spent_usd,
            budget.limit_usd,
        )

        level = budget.level

        if level == BudgetLevel.CRITICAL:
            logger.warning(
                "[Budget:%s] CRITICAL — budget exhausted ($%.4f / $%.4f)",
                session_id[:8],
                budget.spent_usd,
                budget.limit_usd,
            )
            return {
                "type": "budget_exceeded",
                "level": "critical",
                "spent_usd": round(budget.spent_usd, 4),
                "limit_usd": round(budget.limit_usd, 4),
                "call_count": budget.call_count,
                "total_tokens": budget.total_input_tokens + budget.total_output_tokens,
                "max_tokens": budget.max_tokens,
            }

        if level == BudgetLevel.WARNING and not budget._warned:
            budget._warned = True
            logger.warning(
                "[Budget:%s] WARNING — %.0f%% of budget used ($%.4f / $%.4f)",
                session_id[:8],
                budget.usage_ratio * 100,
                budget.spent_usd,
                budget.limit_usd,
            )
            return {
                "type": "budget_warning",
                "level": "warning",
                "spent_usd": round(budget.spent_usd, 4),
                "limit_usd": round(budget.limit_usd, 4),
                "usage_percent": round(budget.usage_ratio * 100, 1),
                "total_tokens": budget.total_input_tokens + budget.total_output_tokens,
                "max_tokens": budget.max_tokens,
            }

        return None

    def remove_session(self, session_id: str) -> Optional[SessionBudget]:
        return self._sessions.pop(session_id, None)
