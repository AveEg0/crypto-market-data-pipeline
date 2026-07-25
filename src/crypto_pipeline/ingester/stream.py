import asyncio
import json
import random
import time
from datetime import datetime

import structlog
from websockets import ConnectionClosed
from websockets.asyncio.client import connect

from crypto_pipeline.backfill.db import insert_candles
from crypto_pipeline.common.models import Candle
from crypto_pipeline.ingester.parse import parse_ws_kline

WS_BASE_URL = "wss://data-stream.binance.vision:443"
BACKOFF_BASE_S = 5
BACKOFF_MAX_S = 60
HEALTHY_UPTIME_S = 60
STALE_TIMEOUT_S = 60  # ~30 msg/min/symbol expected; 90s = 3× the worst tolerable gap


class BinanceIngester:
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = [s.upper() for s in symbols]
        self.received = 0
        self.kept = 0
        self.stored = 0
        self._last_ts: dict[str, datetime] = {}
        self._reconnected: dict[str, bool] = dict.fromkeys(self.symbols, False)
        self.log = structlog.get_logger().bind(symbols=self.symbols)

    async def run(self) -> None:
        delay = BACKOFF_BASE_S
        try:
            while True:
                started = time.perf_counter()
                try:
                    await self._connect_and_stream()
                except (ConnectionClosed, OSError, TimeoutError) as exc:
                    uptime = time.perf_counter() - started
                    if uptime >= HEALTHY_UPTIME_S:
                        delay = BACKOFF_BASE_S
                    self.log.warning(
                        "ws_reconnect_scheduled",
                        reason=type(exc).__name__,
                        uptime_s=round(uptime, 1),
                        delay_s=round(delay, 1),
                    )
                    await asyncio.sleep(delay * random.uniform(0.5, 1.5))
                    delay = min(delay * 2, BACKOFF_MAX_S)
        except asyncio.CancelledError:
            self.log.info("stream_cancelled")
            raise

    def _build_url(self) -> str:
        return (
            WS_BASE_URL
            + "/stream?streams="
            + "/".join([f"{s.lower()}@kline_1m" for s in self.symbols])
        )

    async def _connect_and_stream(self) -> None:
        async with connect(self._build_url()) as ws:
            self.log.info("ws_connected", symbols=self.symbols)
            self._reconnected = dict.fromkeys(self.symbols, True)
            while True:
                async with asyncio.timeout(STALE_TIMEOUT_S):
                    raw_msg = await ws.recv()
                await self._handle_msg(json.loads(raw_msg))

    async def _handle_msg(self, msg: dict) -> None:
        event = msg["data"]
        k = event["k"]
        self.received += 1
        self.log.bind(symbol=k["s"]).debug("kline_received", symbol=k["s"], is_closed=k["x"])
        if k["x"]:
            self.kept += 1
            try:
                candle = parse_ws_kline(event)
            except ValueError:
                self.log.error("candle_parse_failed", raw=event, exc_info=True)
                return
            if self._reconnected.get(candle.symbol):
                self._detect_gap(candle)
                self._reconnected[candle.symbol] = False
            try:
                inserted = await asyncio.to_thread(insert_candles, [candle])
                self.stored += inserted
                self._last_ts[candle.symbol] = candle.ts
                self.log.info(
                    "candle_stored",
                    symbol=candle.symbol,
                    ts=candle.ts,
                    close=candle.close,
                    inserted=inserted,
                )
            except Exception:  # noqa: BLE001 log error and continue
                self.log.error("db_write_failed", symbol=candle.symbol, ts=candle.ts, exc_info=True)


    def _detect_gap(self, candle: Candle) -> None:
        last_ts = self._last_ts.get(candle.symbol)
        if last_ts is None:
            return
        missing = int((candle.ts - last_ts).total_seconds() / 60) - 1
        if missing <= 0:
            return
        self.log.warning(
            "candle_gap_detected",
            symbol=candle.symbol,
            gap_from=last_ts,
            gap_to=candle.ts,
            missing_min=missing,
        )