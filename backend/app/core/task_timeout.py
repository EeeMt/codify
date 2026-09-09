"""Peak/off-peak task timeout selection and frozen execution deadlines."""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

TASK_TIMEOUT_MIN_SECONDS = 60
TASK_TIMEOUT_MAX_SECONDS = 28_800
TASK_TIMEOUT_TIMEZONE = "Asia/Shanghai"
_TASK_TIMEOUT_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
_BUSINESS_TIMEZONE = ZoneInfo(TASK_TIMEOUT_TIMEZONE)


class TaskTimeoutError(ValueError):
    """Raised when a task timeout snapshot or policy is invalid."""


def parse_hhmm(value: object) -> time:
    """Parse a strict zero-padded 24-hour ``HH:mm`` value."""
    if not isinstance(value, str) or not _TASK_TIMEOUT_TIME_RE.fullmatch(value):
        raise ValueError("task timeout window values must use strict HH:mm format")
    hour, minute = (int(part) for part in value.split(":"))
    return time(hour=hour, minute=minute)


def validate_timeout_seconds(value: object, *, field_name: str = "task timeout") -> int:
    """Validate one task timeout value without accepting booleans as integers."""
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < TASK_TIMEOUT_MIN_SECONDS
        or value > TASK_TIMEOUT_MAX_SECONDS
    ):
        raise ValueError(
            f"{field_name} must be between {TASK_TIMEOUT_MIN_SECONDS} and "
            f"{TASK_TIMEOUT_MAX_SECONDS} seconds"
        )
    return value


def validate_timeout_window(start: object, end: object) -> tuple[time, time]:
    """Validate a daily timeout window and reject an empty full-day boundary."""
    start_time = parse_hhmm(start)
    end_time = parse_hhmm(end)
    if start_time == end_time:
        raise ValueError("task timeout peak start and end must be different")
    return start_time, end_time


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_peak_time(utc_at: datetime, start: object, end: object) -> bool:
    """Return whether a UTC instant is inside the half-open peak window."""
    start_time, end_time = validate_timeout_window(start, end)
    local_time = _as_utc(utc_at).astimezone(_BUSINESS_TIMEZONE).time().replace(
        second=0,
        microsecond=0,
    )
    if start_time < end_time:
        return start_time <= local_time < end_time
    return local_time >= start_time or local_time < end_time


def select_task_timeout(settings: Any, utc_at: datetime) -> tuple[str, int]:
    """Select the immutable timeout tier for a task claim instant."""
    peak_seconds = validate_timeout_seconds(
        getattr(settings, "task_timeout_peak_seconds", None),
        field_name="task_timeout_peak_seconds",
    )
    off_peak_seconds = validate_timeout_seconds(
        getattr(settings, "task_timeout_off_peak_seconds", None),
        field_name="task_timeout_off_peak_seconds",
    )
    peak = is_peak_time(
        utc_at,
        getattr(settings, "task_timeout_peak_start", None),
        getattr(settings, "task_timeout_peak_end", None),
    )
    return ("peak", peak_seconds) if peak else ("off-peak", off_peak_seconds)


def resolve_task_timeout_seconds(settings: Any, utc_at: datetime) -> int:
    """Return only the selected timeout seconds for callers that need the value."""
    return select_task_timeout(settings, utc_at)[1]


def frozen_task_timeout_seconds(task: Any) -> int:
    """Read and validate the timeout frozen on a Task execution."""
    try:
        return validate_timeout_seconds(
            getattr(task, "execution_timeout_seconds", None),
            field_name=f"Task {getattr(task, 'id', '?')} execution_timeout_seconds",
        )
    except ValueError as exc:
        if isinstance(exc, TaskTimeoutError):
            raise
        raise TaskTimeoutError(str(exc)) from exc


def execution_deadline_at(started_at: datetime, timeout_seconds: int) -> datetime:
    """Calculate the derived UTC deadline from the persisted start and timeout."""
    return _as_utc(started_at) + timedelta(seconds=timeout_seconds)


def remaining_timeout_seconds(
    started_at: datetime,
    timeout_seconds: int,
    now: datetime | None = None,
) -> int:
    """Return the ceiling of the frozen deadline minus the current UTC time."""
    current = _as_utc(now or datetime.now(UTC))
    return math.ceil((execution_deadline_at(started_at, timeout_seconds) - current).total_seconds())
