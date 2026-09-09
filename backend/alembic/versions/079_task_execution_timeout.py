"""Freeze the selected peak/off-peak timeout on each Task execution.

Revision ID: 079_task_execution_timeout
Revises: 078_remove_provider_driver
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "079_task_execution_timeout"
down_revision: Union[str, None] = "078_remove_provider_driver"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("execution_timeout_seconds", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_tasks_execution_timeout_seconds",
        "tasks",
        "execution_timeout_seconds IS NULL OR execution_timeout_seconds BETWEEN 60 AND 28800",
    )

    conn = op.get_bind()
    legacy = conn.execute(
        sa.text(
            "SELECT value, value_type FROM system_config "
            "WHERE key = 'task_timeout'"
        )
    ).mappings().first()
    if legacy is not None:
        for key in ("task_timeout_peak_seconds", "task_timeout_off_peak_seconds"):
            exists = conn.execute(
                sa.text("SELECT 1 FROM system_config WHERE key = :key"),
                {"key": key},
            ).first()
            if exists is None:
                conn.execute(
                    sa.text(
                        "INSERT INTO system_config (key, value, value_type, updated_at) "
                        "VALUES (:key, :value, :value_type, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "key": key,
                        "value": legacy["value"],
                        "value_type": legacy["value_type"],
                    },
                )
        conn.execute(sa.text("DELETE FROM system_config WHERE key = 'task_timeout'"))


def downgrade() -> None:
    raise RuntimeError(
        "079_task_execution_timeout is roll-forward-only; restore from backup"
    )
