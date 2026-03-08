import pytest

from app.services.budget import (
    BudgetExceededError,
    BudgetLevel,
    BudgetTracker,
    SessionBudget,
    compute_cost,
)


@pytest.fixture
def tracker():
    return BudgetTracker(default_session_limit=1.0)


def test_compute_cost_from_reported():
    cost = compute_cost(1000, 500, reported_cost=0.05)
    assert cost == 0.05


def test_compute_cost_from_tokens():
    # default pricing: input=3.0/1M, output=15.0/1M
    cost = compute_cost(1_000_000, 100_000)
    assert cost == pytest.approx(3.0 + 1.5)


def test_compute_cost_known_model():
    cost = compute_cost(
        1_000_000, 1_000_000,
        model="claude-opus-4-20250514",
    )
    # input: 15.0, output: 75.0
    assert cost == pytest.approx(15.0 + 75.0)


def test_compute_cost_zero_reported_falls_back_to_tokens():
    cost = compute_cost(1_000_000, 0, reported_cost=0.0)
    assert cost == pytest.approx(3.0)


def test_session_budget_levels():
    b = SessionBudget(limit_usd=1.0, spent_usd=0.5)
    assert b.level == BudgetLevel.OK

    b.spent_usd = 0.8
    assert b.level == BudgetLevel.WARNING

    b.spent_usd = 1.0
    assert b.level == BudgetLevel.CRITICAL


def test_session_budget_remaining():
    b = SessionBudget(limit_usd=2.0, spent_usd=1.5)
    assert b.remaining_usd == pytest.approx(0.5)


def test_tracker_start_and_get(tracker):
    tracker.start_session("s1")
    budget = tracker.get_budget("s1")
    assert budget is not None
    assert budget.limit_usd == 1.0
    assert budget.spent_usd == 0.0


def test_tracker_custom_limit(tracker):
    tracker.start_session("s1", limit_usd=5.0)
    assert tracker.get_budget("s1").limit_usd == 5.0


def test_tracker_check_budget_ok(tracker):
    tracker.start_session("s1")
    tracker.check_budget("s1")  # should not raise


def test_tracker_check_budget_exceeded(tracker):
    tracker.start_session("s1", limit_usd=0.001)
    tracker.record_usage("s1", input_tokens=1_000_000, output_tokens=0)
    with pytest.raises(BudgetExceededError):
        tracker.check_budget("s1")


def test_tracker_record_usage_accumulates(tracker):
    tracker.start_session("s1")
    tracker.record_usage("s1", input_tokens=100, output_tokens=50, reported_cost=0.01)
    tracker.record_usage("s1", input_tokens=200, output_tokens=100, reported_cost=0.02)

    budget = tracker.get_budget("s1")
    assert budget.spent_usd == pytest.approx(0.03)
    assert budget.total_input_tokens == 300
    assert budget.total_output_tokens == 150
    assert budget.call_count == 2


def test_tracker_warning_event(tracker):
    tracker.start_session("s1", limit_usd=0.10)

    # Spend 85% of budget
    event = tracker.record_usage("s1", input_tokens=0, output_tokens=0, reported_cost=0.085)
    assert event is not None
    assert event["type"] == "budget_warning"
    assert event["level"] == "warning"


def test_tracker_warning_emitted_once(tracker):
    tracker.start_session("s1", limit_usd=0.10)

    tracker.record_usage("s1", input_tokens=0, output_tokens=0, reported_cost=0.085)
    # Second call at same level should not emit again
    event = tracker.record_usage("s1", input_tokens=0, output_tokens=0, reported_cost=0.005)
    # This might be critical (0.09/0.10 = 90%) — still warning, not critical yet
    # It should be None because warning was already emitted
    assert event is None


def test_tracker_critical_event(tracker):
    tracker.start_session("s1", limit_usd=0.01)

    event = tracker.record_usage("s1", input_tokens=0, output_tokens=0, reported_cost=0.015)
    assert event is not None
    assert event["type"] == "budget_exceeded"
    assert event["level"] == "critical"


def test_tracker_no_event_when_ok(tracker):
    tracker.start_session("s1", limit_usd=100.0)
    event = tracker.record_usage("s1", input_tokens=1000, output_tokens=500, reported_cost=0.01)
    assert event is None


def test_tracker_unknown_session_returns_none(tracker):
    event = tracker.record_usage("unknown", input_tokens=100, output_tokens=50)
    assert event is None


def test_tracker_check_unknown_session_ok(tracker):
    tracker.check_budget("unknown")  # should not raise


def test_tracker_remove_session(tracker):
    tracker.start_session("s1")
    removed = tracker.remove_session("s1")
    assert removed is not None
    assert tracker.get_budget("s1") is None


def test_budget_exceeded_error_attributes():
    err = BudgetExceededError(spent=1.5, limit=1.0)
    assert err.spent == 1.5
    assert err.limit == 1.0
    assert "1.5" in str(err)
