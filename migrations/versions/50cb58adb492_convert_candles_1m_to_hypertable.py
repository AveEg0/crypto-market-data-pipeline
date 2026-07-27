"""convert candles_1m to hypertable

Revision ID: 50cb58adb492
Revises: f2ef4eaa6414
Create Date: 2026-07-26 19:54:20.586863

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "50cb58adb492"
down_revision: str | Sequence[str] | None = "f2ef4eaa6414"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    op.execute(
        "SELECT create_hypertable('candles_1m', 'ts', "
        "chunk_time_interval => INTERVAL '7 days', migrate_data => true)"
    )


def downgrade() -> None:
    # preserve data across the hypertable -> plain-table reversion
    op.execute("CREATE TEMP TABLE candles_1m_backup AS SELECT * FROM candles_1m")
    op.execute("DROP TABLE candles_1m")
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
        )
    """)
    op.execute("INSERT INTO candles_1m SELECT * FROM candles_1m_backup")
    # temp table drops automatically at session end
