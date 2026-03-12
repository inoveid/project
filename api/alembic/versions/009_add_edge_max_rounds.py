"""Add max_rounds to workflow_edges."""

revision = "009"
down_revision = "008_add_agent_can_complete_task"

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "workflow_edges",
        sa.Column(
            "max_rounds",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
    )


def downgrade() -> None:
    op.drop_column("workflow_edges", "max_rounds")
