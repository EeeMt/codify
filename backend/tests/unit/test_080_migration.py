"""CMD-04: a command's ``created_by`` must hold a full ``User.username``.

``User.username`` is ``String(255)`` (self-hosted GitLab/OIDC usernames reach
that width), while ``task_harness_commands.created_by`` was created as
``String(64)`` by 074 — long usernames made every command PUT fail on the
database. The model declaration and migration 080 must agree on 255.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.models import TaskHarnessCommand, User


def _load_080():
    versions = Path(__file__).resolve().parents[2] / "alembic/versions"
    matches = sorted(versions.glob("080_*.py"))
    assert len(matches) == 1, matches
    spec = importlib.util.spec_from_file_location("migration_080", matches[0])
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_080_widens_created_by_to_the_username_width():
    module = _load_080()
    with mock.patch("alembic.op.alter_column") as alter_column:
        module.upgrade()

    table, column = alter_column.call_args.args[:2]
    assert (table, column) == ("task_harness_commands", "created_by")
    assert alter_column.call_args.kwargs["type_"].length == 255
    assert alter_column.call_args.kwargs["existing_type"].length == 64
    assert alter_column.call_args.kwargs["existing_nullable"] is False


def test_080_downgrade_restores_the_previous_width():
    module = _load_080()
    with mock.patch("alembic.op.alter_column") as alter_column:
        module.downgrade()

    assert alter_column.call_args.kwargs["type_"].length == 64
    assert alter_column.call_args.kwargs["existing_type"].length == 255


def test_080_follows_079_in_the_migration_chain():
    module = _load_080()
    assert module.revision.startswith("080_")
    assert len(module.revision) <= 32  # alembic_version.version_num is VARCHAR(32)
    assert module.down_revision == "079_task_execution_timeout"


async def test_command_orm_round_trips_a_full_width_username():
    """The row the ORM writes must fit the username the request carries."""
    username = "u" * 255
    assert User.__table__.c.username.type.length == 255
    assert TaskHarnessCommand.__table__.c.created_by.type.length == 255

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(lambda conn: TaskHarnessCommand.__table__.create(conn))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            session.add(
                TaskHarnessCommand(
                    command_id="cmd-1",
                    task_id=1,
                    attempt_id="attempt-1",
                    sequence_no=1,
                    command_type="steer",
                    payload={"text": "go"},
                    payload_digest="d" * 64,
                    status="queued",
                    created_by=username,
                )
            )
            await session.commit()

        async with session_factory() as session:
            stored = await session.get(TaskHarnessCommand, "cmd-1")
            assert stored is not None
            assert stored.created_by == username
    finally:
        await engine.dispose()
