SYMBOL = "BTCUSDT"


def generate_candles_1m_page(start_ms: int, count: int) -> list[list]:
    page = []
    for i in range(count):
        open_time = start_ms + i * 60_000
        open_price = 60_000 + i * 0.5
        high = 60_500 + i * 15
        low = open_price
        close = high
        volume = 5 * ((0.01 * i) * (i % 2))
        close_time = open_time + 59_999
        quote_asset_volume = volume * (low + high) / 2
        number_of_trades = 3 + i
        taker_buy_base_volume = volume * 0.6
        taker_buy_quote_volume = quote_asset_volume * 0.6
        unused = "0"
        page.append(
            [
                open_time,
                f"{open_price:.8f}",
                f"{high:.8f}",
                f"{low:.8f}",
                f"{close:.8f}",
                f"{volume:.8f}",
                close_time,
                f"{quote_asset_volume:.8f}",
                number_of_trades,
                f"{taker_buy_base_volume:.8f}",
                f"{taker_buy_quote_volume:.8f}",
                unused,
            ]
        )
    return page
