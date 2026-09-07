import argparse
import sys
from decimal import Decimal

import pandas as pd
import structlog

from crypto_pipeline.backtest.contracts import (
    FEE_DEFAULT,
    SLIPPAGE_DEFAULT,
    BacktestMetrics,
    SweepResult,
)
from crypto_pipeline.backtest.runner import run_backtest
from crypto_pipeline.backtest.sweep import run_sweep
from crypto_pipeline.common.db import read_candles
from crypto_pipeline.common.logging import configure_logging
from crypto_pipeline.common.models import Candle
from crypto_pipeline.common.parse import resolve_range


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crypto_pipeline.backtest",
        description="Backtest trading strategies",
    )
    parser.add_argument(
        "--symbol",
        required=True,
        nargs="+",
        help="one or more trading pairs, e.g. 'BTCUSDT ETHUSDT'",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--days", type=int, default=1, help="the last N days, default is 1")
    group.add_argument(
        "--start", type=str, help="ISO start (UTC if no offset given), e.g. 2026-07-01"
    )
    parser.add_argument(
        "--end", type=str, help="ISO end (UTC if no offset given), e.g. 2026-07-01, default: now"
    )
    # --days + --end = "N days ending at X", compatible, useful for chunked historical backfills
    parser.add_argument("--initial-capital", type=Decimal, required=True, help="initial capital")
    parser.add_argument("--fast", type=int, default=5, help="the size of the fast window for sma")
    parser.add_argument("--slow", type=int, default=20, help="the size of the slow window for sma")
    parser.add_argument("--fee-rate", type=Decimal, default=FEE_DEFAULT, help="trade fee rate")
    parser.add_argument("--slippage", type=Decimal, default=SLIPPAGE_DEFAULT, help="trade slippage")
    parser.add_argument("--allow-gaps", action="store_true", default=False, help="allow gaps")
    parser.add_argument("--sweep", action="store_true", default=False, help="sweep run")
    parser.add_argument("--sweep-ratio", type=float, default=0.7, help="ratio of sweep run")
    parser.add_argument("--log-json", action="store_true")
    return parser.parse_args()


# interval hardcoded to 1m, to add different intervals - add arg, write resolve interval
def main() -> int:
    args = _parse_args()
    configure_logging(json_logs=args.log_json)
    log = structlog.get_logger()
    try:
        start, end = resolve_range(args)
    except ValueError:
        log.error("value_error", exc_info=True)
        return 2
    failures: list[tuple[str, Exception]] = []

    formatted_metrics_list = []
    for symbol in [s.upper() for s in args.symbol]:
        try:
            candles = read_candles(symbol, start, end)
            if not candles:
                log.warning("no candles found", symbol=symbol, exc_info=True)
                continue
            if args.sweep:
                metrics = run_sweep(
                    candles=candles,
                    interval=pd.Timedelta(minutes=1),
                    initial_capital=args.initial_capital,
                    ratio=args.sweep_ratio,
                    fee_rate=args.fee_rate,
                    slippage=args.slippage,
                    allow_gaps=args.allow_gaps,
                )
                metrics = format_sweep(metrics)
            else:
                metrics = run_backtest(
                    candles=candles,
                    interval=pd.Timedelta(minutes=1),
                    initial_capital=args.initial_capital,
                    fast_window=args.fast,
                    slow_window=args.slow,
                    fee_rate=args.fee_rate,
                    slippage=args.slippage,
                    allow_gaps=args.allow_gaps,
                )
                metrics = format_metrics(metrics, args.fast, args.slow)
            formatted_metrics_list.append(metrics)
        except Exception as e:
            failures.append((symbol, e))
            log.error("symbol_failed", symbol=symbol, exc_info=True)
    for m in formatted_metrics_list:
        print(m)
    if failures:
        log.error(
            "backtest_failures",
            number_of_failure=len(failures),
            failed_list=[", ".join(s for s, _ in failures)],
        )
    return 1 if failures else 0


def _fmt_money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):,}"


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:+.2f}%"


def _fmt_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def format_metrics(m: BacktestMetrics, fast: int, slow: int) -> str:
    info = m.frame_info
    strategy_pnl = m.final_equity - m.initial_capital
    bh_pnl = m.buy_and_hold_final_equity - m.initial_capital
    verdict = (
        "strategy beat buy-and-hold"
        if m.final_equity > m.buy_and_hold_final_equity
        else "buy-and-hold won"
    )

    lines = [
        "",
        f"  {info.symbol}  ·  SMA {fast}/{slow}  ·  {info.interval.resolution_string} candles",
        f"  {info.start_ts:%Y-%m-%d %H:%M} → {info.end_ts:%Y-%m-%d %H:%M} UTC"
        f"   ({info.candle_count:,} candles, {info.gap_count} gaps)",
        "",
        f"  {'':<22}{'STRATEGY':>16}{'BUY & HOLD':>16}",
        f"  {'-' * 54}",
        f"  {'final equity':<22}{_fmt_money(m.final_equity):>16}"
        f"{_fmt_money(m.buy_and_hold_final_equity):>16}",
        f"  {'profit / loss':<22}{_fmt_money(strategy_pnl):>16}{_fmt_money(bh_pnl):>16}",
        f"  {'total return':<22}{_fmt_pct(m.total_return):>16}"
        f"{_fmt_pct(m.buy_and_hold_total_return):>16}",
        "",
        f"  {'trades':<22}{m.trade_count:>16,}",
        f"  {'win rate':<22}{_fmt_pct(m.win_rate):>16}",
        f"  {'fees paid':<22}{_fmt_money(m.fees_paid):>16}",
        f"  {'max drawdown':<22}{_fmt_pct(m.max_drawdown):>16}",
        f"  {'sharpe (annualized)':<22}{_fmt_ratio(m.sharpe):>16}",
        "",
        f"  starting capital {_fmt_money(m.initial_capital)}  ·  {verdict}",
        "",
    ]
    return "\n".join(lines)


def split_chronological(
    candles: list[Candle], ratio: float = 0.7
) -> tuple[list[Candle], list[Candle]]:
    split_index = int(len(candles) * ratio)
    return candles[:split_index], candles[split_index:]


def format_sweep(result: SweepResult) -> str:
    lines = [
        "",
        "  IN-SAMPLE SWEEP (parameters tuned here)",
        f"  {'fast/slow':<16}{'return':>12}{'sharpe':>10}{'trades':>9}{'max dd':>10}",
        f"  {'-' * 57}",
    ]
    for fast, slow, m in result.ranked_in_sample:
        marker = " *" if (fast, slow) == (result.fast_window, result.slow_window) else "  "
        lines.append(
            f"  {f'{fast}/{slow}':<16}{_fmt_pct(m.total_return):>12}"
            f"{_fmt_ratio(m.sharpe):>10}{m.trade_count:>9,}{_fmt_pct(m.max_drawdown):>10}{marker}"
        )

    is_m, oos_m = result.in_sample, result.out_of_sample
    lines += [
        "",
        f"  SELECTED: SMA {result.fast_window}/{result.slow_window}  (best in-sample Sharpe)",
        "",
        f"  {'':<22}{'IN-SAMPLE':>16}{'OUT-OF-SAMPLE':>16}",
        f"  {'-' * 54}",
        f"  {'total return':<22}{_fmt_pct(is_m.total_return):>16}"
        f"{_fmt_pct(oos_m.total_return):>16}",
        f"  {'buy & hold return':<22}{_fmt_pct(is_m.buy_and_hold_total_return):>16}"
        f"{_fmt_pct(oos_m.buy_and_hold_total_return):>16}",
        f"  {'sharpe':<22}{_fmt_ratio(is_m.sharpe):>16}{_fmt_ratio(oos_m.sharpe):>16}",
        f"  {'max drawdown':<22}{_fmt_pct(is_m.max_drawdown):>16}"
        f"{_fmt_pct(oos_m.max_drawdown):>16}",
        f"  {'trades':<22}{is_m.trade_count:>16,}{oos_m.trade_count:>16,}",
        f"  {'win rate':<22}{_fmt_pct(is_m.win_rate):>16}{_fmt_pct(oos_m.win_rate):>16}",
        f"  {'fees paid':<22}{_fmt_money(is_m.fees_paid):>16}{_fmt_money(oos_m.fees_paid):>16}",
        "",
        f"  {is_m.frame_info.candle_count:,} candles in-sample"
        f"  ·  {oos_m.frame_info.candle_count:,} out-of-sample",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
