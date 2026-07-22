from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from crypto_pipeline.backfill.fetch import (
    BASE_URL,
    IP_USED_WEIGHT_HEADER,
    MIN_IN_EPOCH,
    QUERY_LIMIT,
    fetch_range,
    last_complete_minute_ms,
    make_client,
)
from tests.conftest import SYMBOL, generate_candles_1m_page


@pytest.mark.parametrize(
    ("now", "expected_ms"),
    [
        (datetime(2026, 7, 22, 5, 29, 40, 5, tzinfo=UTC), 1784698080000),
        (datetime(2026, 7, 22, 5, 29, tzinfo=UTC), 1784698080000),
        (datetime(2026, 7, 22, 5, 29, 0, 1, tzinfo=UTC), 1784698080000),
    ],
)
def test_last_complete_minute_ms(now: datetime, expected_ms: int) -> None:
    assert last_complete_minute_ms(now) == expected_ms


def test_fetch_call_termination_if_page_not_full() -> None:
    count = 10
    start = datetime(2026, 7, 2, 5, 29, 40, 5, tzinfo=UTC)
    start_ms = int(start.timestamp() * 1000)
    page1 = generate_candles_1m_page(start_ms, QUERY_LIMIT)
    page2 = generate_candles_1m_page(page1[-1][0] + MIN_IN_EPOCH, count)
    end = datetime.fromtimestamp(
        ((len(page1) + len(page2)) * MIN_IN_EPOCH + MIN_IN_EPOCH + start_ms) / 1000
    ).astimezone(UTC)
    headers = {IP_USED_WEIGHT_HEADER: "2"}
    with respx.mock:
        route = respx.get(BASE_URL).mock(
            side_effect=[
                httpx.Response(200, json=page1, headers=headers),
                httpx.Response(200, json=page2, headers=headers),
            ]
        )
        with make_client() as client:
            candles = fetch_range(client, SYMBOL, start, end)
    assert len(candles) == QUERY_LIMIT + count
    assert route.call_count == 2
    assert int(route.calls[1].request.url.params["startTime"]) == page1[-1][0] + MIN_IN_EPOCH
    assert len({c.ts for c in candles}) == QUERY_LIMIT + count
    assert int(route.calls[0].request.url.params["startTime"]) == start_ms


def test_fetch_exactly_one_call_if_page_not_full() -> None:
    count = QUERY_LIMIT - 10
    start = datetime(2026, 7, 2, 5, 29, 40, 5, tzinfo=UTC)
    start_ms = int(start.timestamp() * 1000)
    page = generate_candles_1m_page(start_ms, count)
    end = datetime.fromtimestamp(
        (len(page) * MIN_IN_EPOCH + MIN_IN_EPOCH + start_ms) / 1000
    ).astimezone(UTC)
    with respx.mock:
        route = respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=page, headers={IP_USED_WEIGHT_HEADER: "2"})
        )
        with make_client() as client:
            candles = fetch_range(client, SYMBOL, start, end)
    assert len(candles) == count
    assert route.call_count == 1
    assert len({c.ts for c in candles}) == count
    assert int(route.calls[0].request.url.params["startTime"]) == start_ms


def test_fetch_return_empty_list() -> None:
    start = datetime(2026, 7, 2, 5, 29, 40, 5, tzinfo=UTC)
    end = start + timedelta(days=1)
    with respx.mock:
        route = respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=[], headers={IP_USED_WEIGHT_HEADER: "2"})
        )
        with make_client() as client:
            candles = fetch_range(client, SYMBOL, start, end)
    assert route.call_count == 1
    assert candles == []


def test_fetch_fires_exp_on_newer_candles_than_set() -> None:
    start = datetime(2026, 7, 2, 5, 29, 40, 5, tzinfo=UTC)
    end = start + timedelta(minutes=3)
    start_ms = int(start.timestamp() * 1000)
    page = generate_candles_1m_page(start_ms, 10)
    with respx.mock:
        respx.get(BASE_URL).mock(
            return_value=httpx.Response(200, json=page, headers={IP_USED_WEIGHT_HEADER: "2"})
        )
        with make_client() as client:
            with pytest.raises(RuntimeError, match="in-progress"):
                fetch_range(client, SYMBOL, start, end)
