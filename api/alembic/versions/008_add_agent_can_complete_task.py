"""Add can_complete_task to agents

Revision ID: 008
Revises: 007_replace_agent_links_with_workflows
"""
from alembic import op
import sqlalchemy as sa

revision = "008_add_agent_can_complete_task"
down_revision = "007_replace_agent_links_with_workflows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "can_complete_task",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "can_complete_task")
