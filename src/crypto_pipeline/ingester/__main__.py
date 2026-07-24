import argparse
import asyncio
import sys
import time

import structlog

from crypto_pipeline.common.logging import configure_logging
from crypto_pipeline.ingester.stream import BinanceIngester


def main() -> int:
    time0 = time.perf_counter()
    args = _parse_args()
    configure_logging(json_logs=args.log_json)
    log = structlog.get_logger()
    ingester = BinanceIngester(args.symbol)
    try:
        asyncio.run(ingester.run())
    except KeyboardInterrupt:
        log.info("interrupt_received")
    finally:
        log.info(
            "ingester_stopped",
            received=ingester.received,
            kept=ingester.kept,
            uptime_s=round(time.perf_counter() - time0, 1),
        )
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crypto_pipeline.ingester",
        description="Ingest 1m candles from Binance via ws connection",
    )
    parser.add_argument(
        "--symbol",
        required=True,
        nargs="+",
        help="one or more trading pairs, e.g. 'BTCUSDT ETHUSDT'",
    )
    parser.add_argument("--log-json", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
