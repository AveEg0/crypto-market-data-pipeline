import asyncio
import json
import signal
from decimal import InvalidOperation

import structlog
from aiokafka import AIOKafkaConsumer

from crypto_pipeline.common.config import CANDLES_TOPIC, get_kafka_bootstrap
from crypto_pipeline.common.parse import parse_kafka_candle
from crypto_pipeline.writer.db import insert_candles

RETRY_DELAY_S = 5


class WriterConsumer:
    def __init__(self) -> None:
        self.written = 0
        self._consumer: AIOKafkaConsumer | None = None
        self.log = structlog.get_logger()

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        task = asyncio.current_task(loop=loop)

        def _request_stop() -> None:
            self.log.info("writer_request_stop")
            task.cancel()

        try:
            loop.add_signal_handler(signal.SIGTERM, _request_stop)
            loop.add_signal_handler(signal.SIGINT, _request_stop)
        except NotImplementedError:
            pass
        async with AIOKafkaConsumer(
            CANDLES_TOPIC,
            bootstrap_servers=get_kafka_bootstrap(),
            group_id="writers",
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        ) as self._consumer:
            while True:
                batches = await self._consumer.getmany(timeout_ms=1000, max_records=500)
                if not batches:
                    continue
                candles = []
                for messages in batches.values():
                    for msg in messages:
                        try:
                            candles.append(parse_kafka_candle(msg.value))
                        except (
                            ValueError,
                            TypeError,
                            KeyError,
                            InvalidOperation,
                            json.decoder.JSONDecodeError,
                        ):
                            self.log.error(
                                "deserialize_failed",
                                partition=msg.partition,
                                offset=msg.offset,
                                raw=msg.value,
                                exc_info=True,
                            )
                if candles:
                    try:
                        inserted = await asyncio.to_thread(insert_candles, candles)
                    except Exception:
                        self.log.error("db_write_failed", count=len(candles), exc_info=True)
                        await self._consumer.seek_to_committed()
                        await asyncio.sleep(RETRY_DELAY_S)
                        continue
                    await self._consumer.commit()
                    self.written += inserted
                    self.log.info(
                        "batch_written",
                        count=len(candles),
                        inserted=inserted,
                    )
