"""Safety contracts for the roll-forward-only task-timeout migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest import mock

import pytest


def _load_079():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/079_task_execution_timeout.py"
    spec = importlib.util.spec_from_file_location("migration_079", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_079_adds_nullable_timeout_column_and_range_check():
    module = _load_079()
    with mock.patch("alembic.op.add_column") as add_column, mock.patch(
        "alembic.op.create_check_constraint"
    ) as create_check, mock.patch("alembic.op.get_bind") as get_bind:
        legacy = mock.Mock()
        legacy.mappings.return_value.first.return_value = None
        get_bind.return_value.execute.return_value = legacy

        module.upgrade()

    column = add_column.call_args.args[1]
    assert add_column.call_args.args[0] == "tasks"
    assert column.name == "execution_timeout_seconds"
    assert column.nullable is True
    create_check.assert_called_once_with(
        "ck_tasks_execution_timeout_seconds",
        "tasks",
        "execution_timeout_seconds IS NULL OR execution_timeout_seconds BETWEEN 60 AND 28800",
    )


def test_079_copies_legacy_override_to_both_tiers_and_deletes_old_key():
    module = _load_079()
    legacy = mock.Mock()
    legacy.mappings.return_value.first.return_value = {"value": "900", "value_type": "int"}
    missing = mock.Mock()
    missing.first.return_value = None
    conn = mock.Mock()
    conn.execute.side_effect = [legacy, missing, mock.Mock(), missing, mock.Mock(), mock.Mock()]

    with mock.patch("alembic.op.add_column"), mock.patch(
        "alembic.op.create_check_constraint"
    ), mock.patch("alembic.op.get_bind", return_value=conn):
        module.upgrade()

    executed_sql = [str(call.args[0]) for call in conn.execute.call_args_list]
    assert any("SELECT value, value_type" in sql for sql in executed_sql)
    assert sum("INSERT INTO system_config" in sql for sql in executed_sql) == 2
    assert any("DELETE FROM system_config" in sql for sql in executed_sql)
    insert_params = [
        call.args[1]
        for call in conn.execute.call_args_list
        if "INSERT INTO system_config" in str(call.args[0])
    ]
    assert {params["key"] for params in insert_params} == {
        "task_timeout_peak_seconds",
        "task_timeout_off_peak_seconds",
    }
    assert all(params["value"] == "900" for params in insert_params)


def test_079_downgrade_is_explicitly_refused():
    module = _load_079()
    with pytest.raises(RuntimeError, match="roll-forward-only"):
        module.downgrade()


def test_079_follows_078_in_the_migration_chain():
    module = _load_079()
    assert module.down_revision == "078_remove_provider_driver"
