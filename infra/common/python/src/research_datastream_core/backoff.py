"""Wait timing shared by the orchestrators: the pre-launch wait for a run's
inputs and the wait before retrying a failed run. Both are exponential,
``min(base * rate ** n, max)``, tunable through ``run_options``."""

from __future__ import annotations

import math

__all__ = [
    "INPUT_WAIT_DEFAULTS",
    "RETRY_BACKOFF_DEFAULTS",
    "backoff_seconds",
    "input_wait",
    "retry_backoff_seconds",
]

INPUT_WAIT_DEFAULTS = {
    "input_wait_base_s": 60,
    "input_wait_rate": 2,
    "input_wait_max_s": 900,
    "input_wait_timeout_s": 86400,
}

# Spaces out retries of a run whose output never appeared (#391).
RETRY_BACKOFF_DEFAULTS = {
    "retry_backoff_base_s": 1800,
    "retry_backoff_rate": 2,
    "retry_backoff_max_s": 7200,
}


def backoff_seconds(n: int, base: float, rate: float, max_s: float) -> int:
    """``min(base * rate ** n, max_s)`` in whole seconds."""
    return int(min(base * rate ** n, max_s))


def input_wait(run_options: dict, n_checks: int, elapsed_s: float) -> tuple[int, bool]:
    """After ``n_checks`` checks found inputs missing, ``elapsed_s`` since the
    first: return ``(seconds until the next check, timed out)``. The last wait
    is cut short so the final check lands on the deadline.
    """
    o = {**INPUT_WAIT_DEFAULTS, **run_options}
    remaining = o["input_wait_timeout_s"] - elapsed_s
    if remaining <= 0:
        return 0, True
    wait = backoff_seconds(n_checks, o["input_wait_base_s"], o["input_wait_rate"], o["input_wait_max_s"])
    return max(1, min(wait, math.ceil(remaining))), False


def retry_backoff_seconds(retry_attempt: int, run_options: dict) -> int:
    """Wait before the next attempt; ``retry_attempt`` is 0-indexed for the
    attempt that just failed, so the first retry waits ``base * rate``."""
    o = {**RETRY_BACKOFF_DEFAULTS, **run_options}
    return backoff_seconds(
        retry_attempt + 1, o["retry_backoff_base_s"], o["retry_backoff_rate"], o["retry_backoff_max_s"]
    )
