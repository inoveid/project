import time
from unittest.mock import patch

import pytest

from app.services.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)


@pytest.fixture
def breaker():
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=5.0,
        failure_window=60.0,
        name="test",
    )


def test_initial_state_is_closed(breaker):
    assert breaker.state == CircuitState.CLOSED


def test_check_passes_when_closed(breaker):
    breaker.check()  # should not raise


def test_failures_below_threshold_keep_closed(breaker):
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    breaker.check()  # still passes


def test_failures_at_threshold_trip_to_open(breaker):
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_check_raises_when_open(breaker):
    for _ in range(3):
        breaker.record_failure()
    with pytest.raises(CircuitOpenError) as exc_info:
        breaker.check()
    assert exc_info.value.retry_after > 0


def test_open_transitions_to_half_open_after_timeout(breaker):
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Simulate time passing beyond recovery_timeout
    breaker._opened_at = time.monotonic() - 6.0
    assert breaker.state == CircuitState.HALF_OPEN


def test_half_open_allows_one_probe(breaker):
    for _ in range(3):
        breaker.record_failure()
    breaker._opened_at = time.monotonic() - 6.0

    breaker.check()  # first probe allowed


def test_half_open_blocks_second_probe(breaker):
    breaker._half_open_max_calls = 1
    for _ in range(3):
        breaker.record_failure()
    breaker._opened_at = time.monotonic() - 6.0

    breaker.check()  # first probe
    with pytest.raises(CircuitOpenError):
        breaker.check()  # second blocked


def test_half_open_success_transitions_to_closed(breaker):
    for _ in range(3):
        breaker.record_failure()
    breaker._opened_at = time.monotonic() - 6.0
    breaker.check()  # enter half_open, allow probe

    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED
    breaker.check()  # should pass


def test_half_open_failure_transitions_to_open(breaker):
    for _ in range(3):
        breaker.record_failure()
    breaker._opened_at = time.monotonic() - 6.0
    breaker.check()

    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_success_in_closed_does_not_change_state(breaker):
    breaker.record_success()
    assert breaker.state == CircuitState.CLOSED


def test_old_failures_are_pruned(breaker):
    """Failures outside the window should not count."""
    breaker._failure_window = 2.0

    # Add failures "in the past" by directly manipulating timestamps
    old_time = time.monotonic() - 10.0
    breaker._failures = [old_time, old_time, old_time]

    # Old failures are pruned, so state remains CLOSED
    assert breaker.failure_count == 0
    assert breaker.state == CircuitState.CLOSED


def test_reset_returns_to_closed(breaker):
    for _ in range(3):
        breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    breaker.reset()
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
    breaker.check()  # should pass


def test_circuit_open_error_has_retry_after():
    err = CircuitOpenError(retry_after=15.0)
    assert err.retry_after == 15.0
    assert "15" in str(err)
