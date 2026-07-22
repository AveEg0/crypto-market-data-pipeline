"""create candles_1m

Revision ID: f2ef4eaa6414
Revises:
Create Date: 2026-07-12 22:44:22.388756

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2ef4eaa6414"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE candles_1m (
        symbol TEXT NOT NULL,
        ts TIMESTAMPTZ NOT NULL,
        open NUMERIC NOT NULL,
        high NUMERIC NOT NULL,
        low NUMERIC NOT NULL,
        close NUMERIC NOT NULL,
        volume NUMERIC NOT NULL,
        PRIMARY KEY (symbol, ts)
        );
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE candles_1m;
    """)
