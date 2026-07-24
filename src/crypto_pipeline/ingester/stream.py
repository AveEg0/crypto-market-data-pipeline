import json

from websockets.asyncio.client import connect

from crypto_pipeline.ingester.parse import parse_ws_kline

WS_BASE_URL = "wss://data-stream.binance.vision:443"


class BinanceIngester:
    def __init__(self, symbols: list[str]) -> None:
        self.symbols = [s.upper() for s in symbols]
        self.received = 0
        self.kept = 0

    async def run(self) -> None:
        await self._stream_klines()

    def _build_url(self) -> str:
        return (
            WS_BASE_URL
            + "/stream?streams="
            + "/".join([f"{s.lower()}@kline_1m" for s in self.symbols])
        )

    async def _stream_klines(self) -> None:
        async with connect(self._build_url()) as ws:
            async for raw_msg in ws:
                msg = json.loads(raw_msg)
                event = msg["data"]
                k = event["k"]
                self.received += 1
                if k["x"]:
                    self.kept += 1
                    candle = parse_ws_kline(event)
                    print(
                        f"candle kept: {candle.symbol}, open time: {candle.ts}, "
                        f"close: {candle.close}\n received: {self.received}, kept: {self.kept}"
                    )
