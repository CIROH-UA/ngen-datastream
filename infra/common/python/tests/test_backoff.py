"""Tests for the shared wait timing (research_datastream_core.backoff)."""

from research_datastream_core import input_wait, retry_backoff_seconds


def test_input_wait_doubles_to_cap():
    assert [input_wait({}, n, 0)[0] for n in range(7)] == [60, 120, 240, 480, 900, 900, 900]


def test_input_wait_lands_on_deadline_then_times_out():
    assert input_wait({}, 50, 86400 - 100) == (100, False)
    assert input_wait({}, 50, 86400) == (0, True)
    assert input_wait({"input_wait_timeout_s": 600}, 0, 600) == (0, True)


def test_retry_backoff_matches_stopper_defaults():
    # Same schedule the stopper used before moving to core: 1h, 2h, capped at 2h.
    assert [retry_backoff_seconds(a, {}) for a in range(3)] == [3600, 7200, 7200]
    assert retry_backoff_seconds(0, {"retry_backoff_base_s": 10, "retry_backoff_rate": 3}) == 30
