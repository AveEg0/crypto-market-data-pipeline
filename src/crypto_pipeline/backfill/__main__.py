import argparse
import sys
import time
from datetime import UTC, datetime, timedelta

import structlog

from crypto_pipeline.backfill.fetch import fetch_range, make_client
from crypto_pipeline.common.logging import configure_logging
from crypto_pipeline.writer.db import insert_candles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crypto_pipeline.backfill",
        description="Fetch historical 1m candles from Binance into Postgres",
    )
    parser.add_argument(
        "--symbol",
        required=True,
        nargs="+",
        help="one or more trading pairs, e.g. 'BTCUSDT ETHUSDT'",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, default=1, help="fetch the last N days, default is 1")
    group.add_argument(
        "--start", type=str, help="ISO start (UTC if no offset given), e.g. 2026-07-01"
    )
    parser.add_argument(
        "--end", type=str, help="ISO end (UTC if no offset given), e.g. 2026-07-01, default: now"
    )
    # --days + --end = "N days ending at X", compatible, useful for chunked historical backfills
    parser.add_argument("--dry-run", action="store_true", help="dry run")
    parser.add_argument("--log-json", action="store_true")
    return parser.parse_args()


def resolve_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    end = _parse_iso(args.end) if args.end else datetime.now(UTC)
    if args.start:
        start = _parse_iso(args.start)
    else:
        days = args.days
        start = end - timedelta(days=days)
    if start >= end:
        raise ValueError(f"start {start} and end {end} are not valid: start >= end")
    return start, end


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    else:
        dt = dt.astimezone(UTC)
    return dt


def main() -> int:
    time0 = time.perf_counter()
    args = parse_args()
    configure_logging(json_logs=args.log_json)
    log = structlog.get_logger()
    try:
        start, end = resolve_range(args)
    except ValueError:
        log.error("value_error", exc_info=True)
        return 2
    failures: list[tuple[str, Exception]] = []
    total_fetched = total_inserted = 0
    with make_client() as client:
        for symbol in [s.upper() for s in args.symbol]:
            try:
                log.info("backfill_for_symbol_started", symbol=symbol, start=start, end=end)
                time0_symbol = time.perf_counter()
                candles = fetch_range(client, symbol, start, end)
                total_fetched += len(candles)
                if not args.dry_run:
                    total_inserted += insert_candles(candles)
                log.info(
                    "backfill_for_symbol_ended",
                    symbol=symbol,
                    uptime_s=round((time.perf_counter() - time0_symbol), 1),
                )
            except Exception as e:
                failures.append((symbol, e))
                log.error("symbol_failed", symbol=symbol, exc_info=True)
    log.info(
        "backfill_summary",
        fetched=total_fetched,
        inserted=total_inserted,
        uptime=round((time.perf_counter() - time0), 1),
    )
    if failures:
        log.error(
            "backfill_failures",
            number_of_failure=len(failures),
            failed_list=[", ".join(s for s, _ in failures)],
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
