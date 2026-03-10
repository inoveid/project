"""add tasks, session_task_id, agent_prompts

Revision ID: 006
Revises: 005
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="backlog",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_check_constraint(
        "ck_tasks_status",
        "tasks",
        "status IN ('backlog', 'in_progress', 'awaiting_user', 'done', 'error')",
    )
    op.create_index("idx_tasks_product_id", "tasks", ["product_id"])
    op.create_index("idx_tasks_team_id", "tasks", ["team_id"])

    op.add_column(
        "sessions",
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_sessions_task_id", "sessions", ["task_id"])

    op.add_column(
        "agents",
        sa.Column(
            "prompts",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "prompts")
    op.drop_index("idx_sessions_task_id", table_name="sessions")
    op.drop_column("sessions", "task_id")
    op.drop_index("idx_tasks_team_id", table_name="tasks")
    op.drop_index("idx_tasks_product_id", table_name="tasks")
    op.drop_table("tasks")
