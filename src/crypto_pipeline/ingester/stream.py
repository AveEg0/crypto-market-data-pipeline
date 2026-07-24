import asyncio
import json
import time

import structlog
from websockets import ConnectionClosed
from websockets.asyncio.client import connect

from crypto_pipeline.ingester.parse import parse_ws_kline

WS_BASE_URL = "wss://data-stream.binance.vision:443"


class BinanceIngester:
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = [s.upper() for s in symbols]
        self.received = 0
        self.kept = 0
        self.log = structlog.get_logger().bind(symbols=self.symbols)

    async def run(self) -> None:
            await self._stream_klines()


    def _build_url(self) -> str:
        return (
            WS_BASE_URL
            + "/stream?streams="
            + "/".join([f"{s.lower()}@kline_1m" for s in self.symbols])
        )

    async def _stream_klines(self) -> None:
        time0 = time.perf_counter()
        try:
            async with connect(self._build_url()) as ws:
                self.log.info("ws_connected", symbols=self.symbols)
                async for raw_msg in ws:
                    msg = json.loads(raw_msg)
                    event = msg["data"]
                    k = event["k"]
                    self.received += 1
                    self.log.bind(symbol=k["s"]).debug(
                        "kline_received", symbol=k["s"], is_closed=k["x"]
                    )
                    if k["x"]:
                        self.kept += 1
                        candle = parse_ws_kline(event)
                        self.log.info(
                            "candle_kept", symbol=candle.symbol, ts=candle.ts, close=candle.close
                        )
        except asyncio.CancelledError:
            self.log.info(
                "stream_cancelled",
                uptime_s=round(time.perf_counter() - time0, 1)
            )
            raise
        except ConnectionClosed as exc:
            self.log.warning(
                "ws_disconnected",
                reason=type(exc).__name__,
                uptime_s=round(time.perf_counter() - time0, 1),
            )
