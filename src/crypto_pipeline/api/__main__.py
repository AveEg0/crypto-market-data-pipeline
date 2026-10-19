import asyncio
import sys

import uvicorn

from crypto_pipeline.api.config import HOST, PORT


def loop_factory() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def main() -> int:
    config = uvicorn.Config("crypto_pipeline.api.app:app", host=HOST, port=PORT, loop="none")
    server = uvicorn.Server(config)
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        runner.run(server.serve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
