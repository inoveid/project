"""Drop agent prompts column, add task error_message, drop edge prompt_id."""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("agents", "prompts")
    op.drop_column("workflow_edges", "prompt_id")
    op.add_column("tasks", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "error_message")
    op.add_column(
        "workflow_edges",
        sa.Column("prompt_id", sa.String(100), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("prompts", sa.JSON(), nullable=False, server_default="[]"),
    )
