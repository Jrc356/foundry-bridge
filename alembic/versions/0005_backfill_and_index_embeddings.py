"""Backfill embeddings and create HNSW indexes

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-22

Ordering rationale: run the backfill UPDATE first, then create HNSW indexes over the
complete dataset. Building the index after the bulk write produces a higher-quality
approximation graph than building it first and inserting rows one-by-one.
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

VECTOR_DIM = 768
MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"

# (table, sql_content_expression) — evaluated server-side to build the embedding text.
# These expressions MUST produce the same string as the Python lambdas in db.embed_unembedded_rows
# and db._write_embeddings_for_pipeline_result so that migrated rows are comparable to live rows.
SEARCHABLE_TABLES = (
    ("entities",       "'[' || entity_type || '] ' || name || ': ' || COALESCE(description, '')"),
    ("threads",
     "CASE WHEN is_resolved AND resolution IS NOT NULL"
     " THEN text || ' \u2014 Resolution: ' || resolution ELSE text END"),
    ("events",         "text"),
    ("notes",          "summary"),
    ("decisions",      "'Decision by ' || COALESCE(made_by, '') || ': ' || decision"),
    ("loot",           "'Loot acquired by ' || COALESCE(acquired_by, '') || ': ' || item_name"),
    ("combat_updates", "'Combat encounter: ' || encounter || ' — Outcome: ' || outcome"),
)


def upgrade() -> None:
    import os
    os.environ.setdefault("FASTEMBED_CACHE_PATH", "/app/.cache/fastembed")

    try:
        from fastembed import TextEmbedding
    except ImportError as e:
        raise RuntimeError(
            "fastembed package is required for migration 0005. "
            "Install it with: pip install 'fastembed>=0.7'"
        ) from e

    model = TextEmbedding(model_name=MODEL_NAME)
    bind = op.get_bind()

    # Step 1: Backfill — bulk write ALL embeddings first
    for table, content_expr in SEARCHABLE_TABLES:
        rows = bind.execute(
            sa.text(f"SELECT id, {content_expr} AS content FROM {table}")
        ).fetchall()
        if not rows:
            continue
        texts = ["search_document: " + row.content for row in rows]
        vecs = [v.tolist() for v in model.embed(texts)]
        for row, vec in zip(rows, vecs):
            vec_str = "[" + ",".join(str(x) for x in vec) + "]"
            bind.execute(
                sa.text(f"UPDATE {table} SET embedding = :vec WHERE id = :id"),
                {"vec": vec_str, "id": row.id},
            )

    # Step 2: Create HNSW indexes AFTER backfill — index is built over the complete
    # dataset, giving a higher-quality graph vs. building before bulk insert.
    for table, _ in SEARCHABLE_TABLES:
        bind.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS {table}_embedding_hnsw_idx "
            f"ON {table} USING hnsw (embedding vector_cosine_ops) "
            f"WITH (m=16, ef_construction=64)"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    for table, _ in SEARCHABLE_TABLES:
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {table}_embedding_hnsw_idx"))
    # Embedding columns are dropped by 0004's downgrade; 0005 downgrade only removes indexes.
