import asyncio
import sys
import time

import structlog

from crypto_pipeline.common.logging import configure_logging
from crypto_pipeline.writer.consumer import WriterConsumer


def main() -> int:
    time0 = time.perf_counter()
    configure_logging()
    log = structlog.get_logger()
    writer = WriterConsumer()
    try:
        asyncio.run(writer.run())
    except KeyboardInterrupt:
        log.info("interrupt_received")
    finally:
        log.info(
            "writer_stopped",
            written=writer.written,
            uptime_s=round(time.perf_counter() - time0, 1),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
