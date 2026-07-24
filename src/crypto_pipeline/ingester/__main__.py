import argparse
import asyncio
import sys

from crypto_pipeline.ingester.stream import BinanceIngester


def main() -> int:
    args = _parse_args()
    ingester = BinanceIngester(args.symbol)
    try:
        asyncio.run(ingester.run())
    finally:
        print(f"total: received = {ingester.received}, kept = {ingester.kept}")
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
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
