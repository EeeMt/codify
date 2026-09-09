"""Unit tests for peak/off-peak task timeout selection."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.task_timeout import (
    execution_deadline_at,
    is_peak_time,
    remaining_timeout_seconds,
    select_task_timeout,
    validate_timeout_seconds,
    validate_timeout_window,
)

SETTINGS = SimpleNamespace(
    task_timeout_peak_seconds=1_800,
    task_timeout_off_peak_seconds=3_600,
    task_timeout_peak_start="09:00",
    task_timeout_peak_end="18:00",
)


def utc(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 9, 9, hour, minute, second, tzinfo=UTC)


def test_ordinary_window_uses_half_open_boundaries_in_business_timezone() -> None:
    assert select_task_timeout(SETTINGS, utc(0, 59))[0] == "off-peak"  # 08:59 Shanghai
    assert select_task_timeout(SETTINGS, utc(1, 0)) == ("peak", 1_800)
    assert select_task_timeout(SETTINGS, utc(9, 59)) == ("peak", 1_800)
    assert select_task_timeout(SETTINGS, utc(10, 0)) == ("off-peak", 3_600)


def test_cross_midnight_window_includes_late_evening_and_early_morning() -> None:
    settings = SimpleNamespace(
        task_timeout_peak_seconds=60,
        task_timeout_off_peak_seconds=120,
        task_timeout_peak_start="22:00",
        task_timeout_peak_end="06:00",
    )

    assert is_peak_time(utc(14, 0), settings.task_timeout_peak_start, settings.task_timeout_peak_end)
    assert is_peak_time(utc(21, 59), settings.task_timeout_peak_start, settings.task_timeout_peak_end)
    assert not is_peak_time(utc(22, 0), settings.task_timeout_peak_start, settings.task_timeout_peak_end)
    assert not is_peak_time(utc(6, 0), settings.task_timeout_peak_start, settings.task_timeout_peak_end)


@pytest.mark.parametrize("value", [True, False, 59, 28_801])
def test_timeout_seconds_reject_boolean_and_out_of_range_values(value: object) -> None:
    with pytest.raises(ValueError):
        validate_timeout_seconds(value)


@pytest.mark.parametrize(
    ("start", "end"),
    [("09:0", "18:00"), ("24:00", "18:00"), ("09:00:00", "18:00"), ("09:00", "09:00")],
)
def test_timeout_window_rejects_invalid_format_and_empty_window(start: str, end: str) -> None:
    with pytest.raises(ValueError):
        validate_timeout_window(start, end)


def test_remaining_timeout_uses_frozen_deadline_and_ceiling() -> None:
    started_at = datetime(2026, 9, 9, 1, 0, tzinfo=UTC)
    now = datetime(2026, 9, 9, 1, 0, 0, 100_000, tzinfo=UTC)

    assert execution_deadline_at(started_at, 60) == datetime(
        2026, 9, 9, 1, 1, tzinfo=UTC
    )
    assert remaining_timeout_seconds(started_at, 60, now) == 60
    assert remaining_timeout_seconds(started_at, 60, execution_deadline_at(started_at, 60)) == 0
