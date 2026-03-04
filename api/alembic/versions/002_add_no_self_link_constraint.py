"""add no self-link constraint to agent_links

Revision ID: 002
Revises: 001
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_agent_links_no_self_link",
        "agent_links",
        "from_agent_id != to_agent_id",
    )


def downgrade() -> None:
    op.drop_constraint("ck_agent_links_no_self_link", "agent_links", type_="check")
