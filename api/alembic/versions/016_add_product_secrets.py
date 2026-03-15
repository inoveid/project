"""Add product_secrets table

Revision ID: 016
Revises: 015
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "016"
down_revision = "015"


def upgrade() -> None:
    op.create_table(
        "product_secrets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("product_id", "key"),
    )
    op.create_index("idx_product_secrets_product_id", "product_secrets", ["product_id"])


def downgrade() -> None:
    op.drop_index("idx_product_secrets_product_id")
    op.drop_table("product_secrets")
