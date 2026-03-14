"""Add auto_merge to workflows

Revision ID: 015
Revises: 014
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"


def upgrade() -> None:
    op.add_column("workflows", sa.Column("auto_merge", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("workflows", "auto_merge")
