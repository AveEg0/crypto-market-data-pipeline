import asyncio
import json
import random
import signal
import time
from asyncio import CancelledError
from datetime import datetime, timedelta

import structlog
from aiokafka import AIOKafkaProducer
from websockets import ConnectionClosed
from websockets.asyncio.client import connect

from crypto_pipeline.backfill.fetch import fetch_range, make_client
from crypto_pipeline.common.config import CANDLES_TOPIC, get_kafka_bootstrap
from crypto_pipeline.common.models import Candle
from crypto_pipeline.common.parse import candle_to_json, parse_ws_candle

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
        self.published = 0
        self._last_ts: dict[str, datetime] = {}
        self._reconnected: dict[str, bool] = dict.fromkeys(self.symbols, False)
        self._producer: AIOKafkaProducer | None = None
        self.log = structlog.get_logger().bind(symbols=self.symbols)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        task = asyncio.current_task(loop=loop)

        def _request_stop() -> None:
            self.log.info("ingester_request_stop")
            task.cancel()

        try:
            loop.add_signal_handler(signal.SIGTERM, _request_stop)
            loop.add_signal_handler(signal.SIGINT, _request_stop)
        except NotImplementedError:
            pass
        delay = BACKOFF_BASE_S
        async with AIOKafkaProducer(bootstrap_servers=get_kafka_bootstrap()) as self._producer:
            try:
                while True:
                    started = time.perf_counter()
                    try:
                        await self._connect_and_stream()
                    except CancelledError:
                        raise
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
            except CancelledError:
                self.log.info("stream_cancelled")
                raise

    def _build_url(self) -> str:
        return (
            WS_BASE_URL
            + "/stream?streams="
            + "/".join([f"{s.lower()}@kline_1m" for s in self.symbols])
        )

    async def _connect_and_stream(self) -> None:
        ws = await connect(self._build_url())
        try:
            self.log.info("ws_connected", symbols=self.symbols)
            self._reconnected = dict.fromkeys(self.symbols, True)
            while True:
                try:
                    async with asyncio.timeout(STALE_TIMEOUT_S):
                        raw_msg = await ws.recv()
                except TimeoutError:
                    self.log.info("run_caught_timeout")
                    raise
                await self._handle_msg(json.loads(raw_msg))
        except CancelledError:
            raise
        except (ConnectionClosed, OSError, TimeoutError):
            try:
                async with asyncio.timeout(2):
                    await ws.close()
                    self.log.info("ws_closed_for_reconnect")
            except (TimeoutError, ConnectionClosed, OSError):
                pass
            raise

    async def _handle_msg(self, msg: dict) -> None:
        event = msg["data"]
        k = event["k"]
        self.received += 1
        self.log.bind(symbol=k["s"]).debug("candle_received", symbol=k["s"], is_closed=k["x"])
        if k["x"]:
            self.kept += 1
            try:
                candle = parse_ws_candle(event)
            except ValueError:
                self.log.error("candle_parse_failed", raw=event, exc_info=True)
                return
            if self._reconnected.get(candle.symbol):
                await self._heal_gap(candle)
                self._reconnected[candle.symbol] = False
            await self._publish(candle)

    async def _heal_gap(self, candle: Candle) -> None:
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
        with make_client() as client:
            try:
                candles = await asyncio.to_thread(
                    fetch_range,
                    client,
                    candle.symbol,
                    last_ts + timedelta(minutes=1),
                    candle.ts,
                )
                for c in candles:
                    await self._publish(c)
                self.log.info(
                    "candle_gap_healed",
                    symbol=candle.symbol,
                    missing_min=missing,
                    start=last_ts,
                    end=candle.ts,
                )
                self.kept += len(candles)
            except Exception:  # noqa: BLE001 log error and continue
                self.log.error(
                    "heal_gap_failed",
                    symbol=candle.symbol,
                    missing_min=missing,
                    start=last_ts,
                    end=candle.ts,
                    exc_info=True,
                )

    async def _publish(self, candle: Candle) -> None:
        try:
            meta = await self._producer.send_and_wait(
                topic=CANDLES_TOPIC,
                value=candle_to_json(candle),
                key=candle.symbol.encode(),
            )
            self.published += 1
            last = self._last_ts.get(candle.symbol)
            if last is None or last < candle.ts:
                self._last_ts[candle.symbol] = candle.ts
            self.log.info(
                "candle_published",
                symbol=candle.symbol,
                ts=candle.ts,
                close=candle.close,
                partition=meta.partition,
                offset=meta.offset,
            )
        except Exception:  # noqa: BLE001 log error and continue
            self.log.error(
                "kafka_publish_failed", symbol=candle.symbol, ts=candle.ts, exc_info=True
            )
