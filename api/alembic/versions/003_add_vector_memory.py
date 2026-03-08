"""add vector memory

Revision ID: 002
Revises: 001
Create Date: 2026-03-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 512  # voyage-3-lite


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Episodic memory — история выполненных задач
    op.create_table(
        "episodic_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(50), nullable=True),   # e.g. "TASK-007"
        sa.Column("summary", sa.Text(), nullable=False),       # краткое описание задачи
        sa.Column("outcome", sa.Text(), nullable=False),       # что получилось / решение
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_episodic_memory_team_id", "episodic_memory", ["team_id"])
    op.execute("""
        CREATE INDEX idx_episodic_memory_embedding
        ON episodic_memory
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # Semantic memory — архитектурные решения (ADR), соглашения
    op.create_table(
        "semantic_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("team_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),      # "adr" | "convention" | "pattern"
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "kind IN ('adr', 'convention', 'pattern')",
            name="ck_semantic_memory_kind",
        ),
    )
    op.create_index("idx_semantic_memory_team_id", "semantic_memory", ["team_id"])
    op.execute("""
        CREATE INDEX idx_semantic_memory_embedding
        ON semantic_memory
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.drop_table("semantic_memory")
    op.drop_table("episodic_memory")
    op.execute("DROP EXTENSION IF EXISTS vector")
