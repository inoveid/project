"""add sub_agent_templates to agents + parent_session_id to sessions

Revision ID: 012
Revises: 011
Create Date: 2026-03-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Agent: add sub_agent_templates JSONB column
    op.add_column(
        "agents",
        sa.Column(
            "sub_agent_templates",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )

    # Session: add parent_session_id + depth
    op.add_column(
        "sessions",
        sa.Column(
            "parent_session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "sessions",
        sa.Column(
            "depth",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("sessions", "depth")
    op.drop_column("sessions", "parent_session_id")
    op.drop_column("agents", "sub_agent_templates")
