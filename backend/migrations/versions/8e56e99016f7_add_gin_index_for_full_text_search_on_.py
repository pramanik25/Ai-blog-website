"""Add GIN index for full-text search on articles

Revision ID: 8e56e99016f7
Revises: ab193c4b1e3f
Create Date: 2025-09-14 01:40:35.902884

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e56e99016f7'
down_revision = 'ab193c4b1e3f'
branch_labels = None
depends_on = None


def upgrade():
    # Create the GIN index on the title and content columns
    op.execute("""
        CREATE INDEX idx_article_content_fts
        ON article
        USING GIN (to_tsvector('english', title || ' ' || content));
    """)


def downgrade():
    # Remove the index if we ever need to reverse the migration
    op.execute("DROP INDEX idx_article_content_fts;")
