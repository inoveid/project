"""replace agent_links with workflows and workflow_edges, add agent canvas fields

Revision ID: 007
Revises: 006
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Create workflows table ---
    op.create_table(
        "workflows",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "starting_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("starting_prompt", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("team_id", "name"),
    )

    # --- Create workflow_edges table ---
    op.create_table(
        "workflow_edges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workflow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("prompt_template", sa.Text(), nullable=True),
        sa.Column("prompt_id", sa.String(100), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_check_constraint(
        "ck_workflow_edges_no_self",
        "workflow_edges",
        "from_agent_id != to_agent_id",
    )
    op.create_index(
        "idx_workflow_edges_workflow_id", "workflow_edges", ["workflow_id"]
    )

    # --- Add canvas fields to agents ---
    op.add_column(
        "agents",
        sa.Column(
            "max_cycles", sa.Integer(), nullable=False, server_default="3"
        ),
    )
    op.add_column(
        "agents",
        sa.Column("position_x", sa.Float(), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("position_y", sa.Float(), nullable=True),
    )

    # --- Drop agent_links table ---
    op.drop_table("agent_links")


def downgrade() -> None:
    # --- Recreate agent_links table ---
    op.create_table(
        "agent_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("link_type", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("from_agent_id", "to_agent_id", "link_type"),
    )
    op.create_check_constraint(
        "ck_agent_links_link_type",
        "agent_links",
        "link_type IN ('handoff', 'review', 'migration_brief')",
    )
    op.create_check_constraint(
        "ck_agent_links_no_self_link",
        "agent_links",
        "from_agent_id != to_agent_id",
    )

    # --- Remove canvas fields from agents ---
    op.drop_column("agents", "position_y")
    op.drop_column("agents", "position_x")
    op.drop_column("agents", "max_cycles")

    # --- Drop new tables ---
    op.drop_index("idx_workflow_edges_workflow_id", table_name="workflow_edges")
    op.drop_table("workflow_edges")
    op.drop_table("workflows")
