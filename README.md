# Crypto Market Data Pipeline

A self-hosted system that ingests live 1-minute crypto candles from Binance, streams them through
Redpanda into PostgreSQL/TimescaleDB, and backtests trading strategies on the accumulated history.

## What this is

A learning and portfolio project, built to production-quality standards — exact numeric types,
versioned migrations, idempotent writes, structured logging, graceful shutdown, resilience to
upstream and downstream failure — but deliberately not production *scope*.

It does not place orders, hold keys, or touch real money. The backtester simulates trades on
historical data and reports what would have happened, including costs.

## Architecture

```
Binance WebSocket  →  ingester  →  Redpanda  →  writer  →  TimescaleDB  →  backtester
Binance REST       →  backfill  ──────────────────────────↗
```

The ingester also heals gaps: when it detects missing minutes after a reconnect, it fetches them
over REST and produces them to the topic, so recovered data takes the same path as live data.

TODO: mermaid diagram.

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Package manager | uv |
| HTTP / WebSocket | httpx, websockets |
| Broker | Redpanda (Kafka API), aiokafka client |
| Database | PostgreSQL 16 + TimescaleDB |
| DB driver | psycopg 3, raw SQL |
| Migrations | Alembic |
| Analytics | pandas |
| Logging | structlog, JSON to stdout |
| Tests / lint | pytest, respx, ruff |
| Orchestration | Docker Compose |

## Quick start

Requires Docker and uv.

```bash
cp .env.example .env    # fill in POSTGRES_* and DATABASE_URL
docker compose up
```

This starts TimescaleDB, Redpanda, the Redpanda Console, runs migrations as a one-shot job, then
brings up the ingester and writer. Live candles begin flowing within a minute. The console is at
`http://127.0.0.1:8080`.

To load historical data:

```bash
uv run --env-file .env python -m crypto_pipeline.backfill --symbol BTCUSDT --start 2026-07-01
```

To backtest an SMA crossover on what's stored:

```bash
uv run --env-file .env python -m crypto_pipeline.backtest \
  --symbol BTCUSDT --start 2026-07-01 --initial-capital 10000 --fast 500 --slow 2000
```

Add `--sweep` to run a parameter sweep with an in-sample/out-of-sample split instead of a single
backtest.

## Components

**ingester** — Connects to the Binance WebSocket stream, keeps only closed candles, and produces
them to the `candles.1m` topic keyed by symbol. Reconnects with exponential backoff and jitter,
detects a stalled stream by timeout, detects gaps after reconnect and heals them over REST, and
shuts down cleanly on SIGTERM.

**writer** — Consumes the topic in batches, inserts them into Postgres, and only then commits its
offsets. Skips malformed messages rather than crash-looping on them, and on a database outage seeks
back to the last committed offset and retries — the topic acts as the buffer.

**backfill** — Paginated REST fetching of historical candles, rate-limit aware. Provides a library 
function (`fetch_range`) used by both the CLI and the ingester's heal path.

**backtest** — A pure library: candles in, metrics out. No I/O, no async, no service. The CLI is a
thin adapter that reads from the database and calls it.

**common** — Shared configuration accessors, the `Candle` model, parsers for each wire format, and
database access.

## Data model

One table, `candles_1m`:

| column | type |
|---|---|
| symbol | `TEXT NOT NULL` |
| ts | `TIMESTAMPTZ NOT NULL` |
| open, high, low, close, volume | `NUMERIC NOT NULL` |

Primary key is `(symbol, ts)` — the natural identity of a candle, and what makes the insert
idempotent. No surrogate id, no derived columns. The table is a TimescaleDB hypertable partitioned
on `ts`.

## Design decisions

- **Money is `Decimal`, constructed from source strings.** Never `Decimal(float)`. Float is banned
  in accounting.
- **UTC everywhere.** `TIMESTAMPTZ` at rest, timezone-aware datetime in Python, epoch conversion
  once at the boundary. Naive datetime are banned project-wide.
- **No ORM.** Raw SQL over psycopg 3. The data is append-only and relationship-free, and the write
  path depends on Postgres-specific `COPY` and `ON CONFLICT`.
- **Idempotent inserts.** Bulk `COPY` into a staging table, then a single
  `INSERT … SELECT … ON CONFLICT DO NOTHING`. Replaying the topic inserts nothing new.
- **Only finalized candles enter the system.** The in-progress candle is filtered out at both
  boundaries. Because the insert is first-writer-wins, a stored partial candle would be a permanent
  lie.
- **At-least-once delivery plus idempotency.** Offsets are committed after the write, never before.
- **Migrations from day one**, immutable once committed. The hypertable migration has a
  data-preserving downgrade.
- **Configuration through the environment.** Required values raise on startup rather than defaulting
  to something plausible.
- **In the backtester, `Decimal` for the ledger and float64 for statistics.** Fills, fees, cash and
  PnL are exact. Returns, Sharpe and drawdown are derived statistics - inexact in any number 
  system - so they are computed in float, where the error is orders of magnitude smaller than 
  the modeling error already introduced by the cost assumptions.

## Backtester

Takes a list of candles and returns a single metrics object: final equity, total return, max
drawdown, annualized Sharpe, win rate, trade count, fees paid, and a buy-and-hold benchmark. The
strategy is an SMA crossover — long when the fast average is above the slow one, flat otherwise.

Costs are modeled on every fill: a taker fee on the notional, and slippage applied adversely to the
fill price in both directions. The buy-and-hold benchmark runs through the same execution and cost
model, so the comparison is net of costs on both sides.

Things worth knowing about the numbers it produces:

- A signal computed from candle *t* fills at candle *t+1*'s open. The last candle can therefore never
  be traded on, which is the honest cost of not looking ahead.
- Annualized Sharpe relies on assumptions about return independence and stable variance. 
  Crypto returns are fat-tailed and autocorrelated, so the figure flatters strategies. 
  It is reported because it is the standard metric, not because the assumption holds.
- The in-sample/out-of-sample split is chronological, never shuffled — shuffling a time series
  leaks future data into the training set. Parameters are chosen on the in-sample segment and
  evaluated once on the out-of-sample segment.
- An open position at the end of a run is marked to the final close. No fees and no slippage are
  applied, because marking to market is a valuation and not a sale.
- Every metric has a hand-computed test fixture — expected values were worked out on paper, not
  produced by running the code.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```

TODO: CI.

## Not built yet

- REST API (FastAPI) exposing candles, stats, and backtests
- Dashboard
- Continuous integration

## Out of scope

Live trading, real money, machine-learning prediction, and user accounts. These are not planned.

## License

See [LICENSE](LICENSE).
