"""Circuit Breaker pattern for protecting against cascading failures.

Wraps external calls (CLI subprocess, API) and tracks failures.
When failure threshold is reached, switches to OPEN state and
fails fast without making actual calls.

States:
  CLOSED    — normal operation, requests pass through
  OPEN      — requests blocked (fail-fast), waiting for recovery timeout
  HALF_OPEN — one probe request allowed to test recovery
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when circuit is OPEN and requests are blocked."""

    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker is OPEN. Retry after {retry_after:.0f}s"
        )


class CircuitBreaker:
    """Simple circuit breaker with CLOSED → OPEN → HALF_OPEN → CLOSED cycle.

    Args:
        failure_threshold: failures within window to trip the breaker.
        recovery_timeout: seconds to wait in OPEN before moving to HALF_OPEN.
        failure_window: sliding window (seconds) for counting failures.
        half_open_max_calls: probe calls allowed in HALF_OPEN state.
        name: label for logging.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        failure_window: float = 60.0,
        half_open_max_calls: int = 1,
        name: str = "default",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_window = failure_window
        self._half_open_max_calls = half_open_max_calls
        self._name = name

        self._state = CircuitState.CLOSED
        self._failures: list[float] = []  # timestamps of recent failures
        self._opened_at: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        """Current state, accounting for recovery timeout expiry."""
        if self._state == CircuitState.OPEN and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self._recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
        return self._state

    @property
    def failure_count(self) -> int:
        self._prune_old_failures()
        return len(self._failures)

    def check(self) -> None:
        """Check if a request is allowed.  Raises CircuitOpenError if not."""
        current = self.state

        if current == CircuitState.CLOSED:
            return

        if current == CircuitState.OPEN:
            retry_after = self._recovery_timeout - (
                time.monotonic() - (self._opened_at or 0)
            )
            raise CircuitOpenError(max(retry_after, 0))

        if current == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self._half_open_max_calls:
                raise CircuitOpenError(self._recovery_timeout)
            self._half_open_calls += 1

    def record_success(self) -> None:
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            logger.info("[CB:%s] Probe succeeded → CLOSED", self._name)
            self._transition(CircuitState.CLOSED)

    def record_failure(self) -> None:
        """Record a failed call."""
        now = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            logger.warning("[CB:%s] Probe failed → OPEN", self._name)
            self._transition(CircuitState.OPEN)
            return

        if self._state == CircuitState.CLOSED:
            self._failures.append(now)
            self._prune_old_failures()
            if len(self._failures) >= self._failure_threshold:
                logger.warning(
                    "[CB:%s] Failure threshold reached (%d/%d) → OPEN",
                    self._name,
                    len(self._failures),
                    self._failure_threshold,
                )
                self._transition(CircuitState.OPEN)

    def reset(self) -> None:
        """Force-reset to CLOSED (for admin/testing)."""
        self._transition(CircuitState.CLOSED)

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state

        if new_state == CircuitState.CLOSED:
            self._failures.clear()
            self._opened_at = None
            self._half_open_calls = 0
        elif new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

        if old != new_state:
            logger.info("[CB:%s] %s → %s", self._name, old.value, new_state.value)

    def _prune_old_failures(self) -> None:
        cutoff = time.monotonic() - self._failure_window
        self._failures = [t for t in self._failures if t > cutoff]
