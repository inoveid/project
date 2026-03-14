"""Add isolation_mode to workflows

Revision ID: 014
Revises: 013
Create Date: 2026-03-14
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("isolation_mode", sa.String(20), nullable=False, server_default="none"))


def downgrade() -> None:
    op.drop_column("workflows", "isolation_mode")
