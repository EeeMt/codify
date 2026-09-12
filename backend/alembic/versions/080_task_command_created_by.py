"""Widen task_harness_commands.created_by to the User.username width.

Revision ID: 080_task_command_created_by
Revises: 079_task_execution_timeout
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "080_task_command_created_by"
down_revision: Union[str, None] = "079_task_execution_timeout"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "task_harness_commands",
        "created_by",
        existing_type=sa.String(length=64),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "task_harness_commands",
        "created_by",
        existing_type=sa.String(length=255),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
