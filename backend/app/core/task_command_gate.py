"""Durable control-gate transitions shared by projector and lifecycle paths."""

from __future__ import annotations

import json

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.task_harness_commands import (
    command_projection_fields,
    public_rejection,
    write_command_outcome_unknown,
    write_command_rejection,
)
from app.core.utcnow import utcnow
from app.models import Task, TaskHarnessAttempt, TaskHarnessCommand, TaskLog, TaskStatus


async def begin_control_drain(db: AsyncSession, *, attempt: TaskHarnessAttempt) -> bool:
    """CAS accepting/starting -> closing when Pi reports ``agent_settled``."""
    if attempt.control_state not in {"accepting", "starting"}:
        return False
    attempt.control_state = "closing"
    await db.flush()
    return True


async def reopen_control_after_native_turn_start(
    db: AsyncSession, *, attempt: TaskHarnessAttempt, command_id: str | None, native_id: str | None
) -> bool:
    """CAS closing -> accepting only after Pi reports a new native turn.

    A follow-up ACK is merely queue admission.  The correlated translator
    diagnostic is the first proof Pi actually began the continuation.
    """
    result = await db.execute(
        update(TaskHarnessAttempt)
        .where(
            TaskHarnessAttempt.attempt_id == attempt.attempt_id,
            TaskHarnessAttempt.control_state == "closing",
            TaskHarnessAttempt.awaiting_follow_up_turn.is_(True),
            TaskHarnessAttempt.force_close_requested.is_(False),
            TaskHarnessAttempt.pending_follow_up_command_id == command_id,
            TaskHarnessAttempt.pending_follow_up_native_id == native_id,
            TaskHarnessAttempt.task_id == Task.id,
            Task.status == TaskStatus.RUNNING,
        )
        .values(control_state="accepting", awaiting_follow_up_turn=False,
                pending_follow_up_command_id=None, pending_follow_up_native_id=None)
    )
    if result.rowcount:
        attempt.control_state = "accepting"
        attempt.awaiting_follow_up_turn = False
        attempt.pending_follow_up_command_id = None
        attempt.pending_follow_up_native_id = None
        attempt.force_close_requested = False
        await db.flush()
        return True
    return False


def _add_rejected_command_log(
    db: AsyncSession,
    command: TaskHarnessCommand,
    *,
    rejection_code: str,
    occurred_at,
) -> None:
    """Project one locally rejected command into the visible event stream.

    A command the backend rejects before dispatch never reaches the Harness, so
    there is no native ACK event to carry it; the product event stream is the
    only place a viewer can see the rejection (plan §7). The reason is the
    public, non-diagnostic projection of the persisted rejection code.
    """
    public_code, public_message = public_rejection(rejection_code)
    db.add(
        TaskLog(
            task_id=command.task_id,
            log_level="WARNING",
            message="",
            log_type="control_event",
            log_metadata=json.dumps(
                {
                    "type": "control.command.rejected",
                    **command_projection_fields(command),
                    "rejection_code": public_code,
                    "rejection_message": public_message,
                    "rejected_at": occurred_at.isoformat(),
                },
                ensure_ascii=False,
            ),
        )
    )


async def close_control_gate(db: AsyncSession, *, attempt: TaskHarnessAttempt, reason: str) -> None:
    """Close an attempt and deterministically reject commands never sent."""
    attempt.control_state = "closed"
    attempt.awaiting_follow_up_turn = False
    attempt.pending_follow_up_command_id = None
    attempt.pending_follow_up_native_id = None
    attempt.force_close_requested = False
    pending = list(
        (
            await db.execute(
                select(TaskHarnessCommand)
                .where(
                    TaskHarnessCommand.attempt_id == attempt.attempt_id,
                    TaskHarnessCommand.status == "queued",
                )
                .with_for_update()
            )
        ).scalars()
    )
    now = utcnow()
    for command in pending:
        rejected = await write_command_rejection(
            db,
            command_id=command.command_id,
            rejection_code="control_gate_closed",
            rejection_message=reason,
            rejected_at=now,
        )
        if rejected:
            _add_rejected_command_log(
                db, command, rejection_code="control_gate_closed", occurred_at=now
            )
    dispatching = list(
        (
            await db.execute(
                select(TaskHarnessCommand)
                .where(
                    TaskHarnessCommand.attempt_id == attempt.attempt_id,
                    TaskHarnessCommand.status == "dispatching",
                )
                .with_for_update()
            )
        ).scalars()
    )
    for command in dispatching:
        changed = await write_command_outcome_unknown(
            db,
            command_id=command.command_id,
            message="control gate closed before native delivery outcome was known",
            occurred_at=now,
        )
        if changed:
            db.add(
                TaskLog(
                    task_id=command.task_id,
                    log_level="WARNING",
                    message="",
                    log_type="control_event",
                    log_metadata=json.dumps(
                        {
                            "type": "control.command.outcome_unknown",
                            **command_projection_fields(command),
                            "code": "delivery_outcome_unknown",
                        },
                        ensure_ascii=False,
                    ),
                )
            )
    await db.flush()


async def request_force_close_after_unknown_follow_up(
    db: AsyncSession,
    *,
    attempt: TaskHarnessAttempt,
    command_id: str,
    native_id: str | None,
    reason: str,
) -> bool:
    """Retain closing until the pump's owner close IPC has ACKed."""
    result = await db.execute(
        update(TaskHarnessAttempt)
        .where(
            TaskHarnessAttempt.attempt_id == attempt.attempt_id,
            TaskHarnessAttempt.task_id == Task.id,
            Task.status == TaskStatus.RUNNING,
            TaskHarnessAttempt.control_state == "closing",
            TaskHarnessAttempt.pending_follow_up_command_id == command_id,
            TaskHarnessAttempt.pending_follow_up_native_id == native_id,
        )
        .values(
            awaiting_follow_up_turn=False,
            pending_follow_up_command_id=None,
            pending_follow_up_native_id=None,
            force_close_requested=True,
        )
    )
    if not result.rowcount:
        return False
    attempt.awaiting_follow_up_turn = False
    attempt.pending_follow_up_command_id = None
    attempt.pending_follow_up_native_id = None
    attempt.force_close_requested = True
    pending = list(
        (
            await db.execute(
                select(TaskHarnessCommand)
                .where(
                    TaskHarnessCommand.attempt_id == attempt.attempt_id,
                    TaskHarnessCommand.status == "queued",
                )
                .with_for_update()
            )
        ).scalars()
    )
    now = utcnow()
    for command in pending:
        rejected = await write_command_rejection(
            db,
            command_id=command.command_id,
            rejection_code="control_gate_closed",
            rejection_message=reason,
            rejected_at=now,
        )
        if rejected:
            _add_rejected_command_log(
                db, command, rejection_code="control_gate_closed", occurred_at=now
            )
    await db.flush()
    return True


async def close_task_control_gates(db: AsyncSession, *, task_id: int, reason: str) -> None:
    """Terminal/cancel safety net for paths without a final canonical record."""
    attempts = list(
        (
            await db.execute(
                select(TaskHarnessAttempt)
                .where(
                    TaskHarnessAttempt.task_id == task_id,
                    TaskHarnessAttempt.control_state.in_(("starting", "accepting", "closing")),
                )
                .with_for_update()
            )
        ).scalars()
    )
    for attempt in attempts:
        await close_control_gate(db, attempt=attempt, reason=reason)
