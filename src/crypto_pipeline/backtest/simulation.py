from decimal import ROUND_DOWN, Decimal

import pandas as pd

from crypto_pipeline.backtest.contracts import (
    FEE_DEFAULT,
    INDEX,
    SLIPPAGE_DEFAULT,
    Column,
    PreparedData,
    SimulationResult,
    TradeRecord,
)


def simulate(
    position: pd.Series,
    prepared_data: PreparedData,
    initial_capital: Decimal,
    fee_rate: Decimal = FEE_DEFAULT,
    slippage: Decimal = SLIPPAGE_DEFAULT,
) -> SimulationResult:
    df = prepared_data.df
    prices = prepared_data.prices
    cash = initial_capital
    quantity = Decimal(0)
    changes = position.diff()
    trades = []
    cash_at_entry = initial_capital
    total_fees = Decimal(0)
    entry_ts = None
    entry_price = None
    entry_fee = Decimal(0)
    curve_list = [
        (df.index[0], initial_capital, quantity),
    ]
    is_open = False
    for ts, change in changes.items():
        if change == 1:
            quantity, entry_fee = execute_buy(cash, prices[ts], slippage, fee_rate)
            entry_ts = ts
            entry_price = prices[ts]
            cash_at_entry = cash
            cash = Decimal(0)
            is_open = True
            total_fees += entry_fee
            curve_list.append((ts, cash, quantity))
        elif change == -1:
            cash, fee = execute_sell(quantity, prices[ts], slippage, fee_rate)
            pnl = cash - cash_at_entry
            fees = entry_fee + fee
            total_fees += fee
            quantity = Decimal(0)
            entry_fee = Decimal(0)
            is_open = False
            trades.append(
                TradeRecord(
                    entry_ts=entry_ts,
                    entry_price=entry_price,
                    fees=fees,
                    exit_ts=ts,
                    exit_price=prices[ts],
                    pnl=pnl,
                )
            )
            curve_list.append((ts, cash, quantity))

    if is_open:
        trades.append(
            TradeRecord(
                entry_ts=entry_ts,
                entry_price=entry_price,
                fees=entry_fee,
                exit_ts=None,
                exit_price=None,
                pnl=None,
            )
        )

    final_cash = cash + quantity * prepared_data.final_close

    states = pd.DataFrame(curve_list, columns=[INDEX, Column.CASH, Column.QUANTITY])
    states = states.set_index(INDEX)
    states = states.reindex(df.index)
    states = states.ffill()

    equity = (
        states[Column.CASH].astype("float64")
        + states[Column.QUANTITY].astype("float64") * df[Column.CLOSE]
    )

    return SimulationResult(
        trades=trades, final_cash=final_cash, equity_curve=equity, total_fees=total_fees
    )


def execute_buy(
    cash: Decimal, price: Decimal, slippage: Decimal, fee_rate: Decimal
) -> tuple[Decimal, Decimal]:
    buy_fill = price * (1 + slippage)
    fee = cash * fee_rate
    spend = cash - fee
    quantity = (spend / buy_fill).quantize(Decimal("1e-8"), rounding=ROUND_DOWN)
    return quantity, fee


def execute_sell(
    quantity: Decimal, price: Decimal, slippage: Decimal, fee_rate: Decimal
) -> tuple[Decimal, Decimal]:
    sell_fill = price * (1 - slippage)
    sell_equity = quantity * sell_fill
    fee = sell_equity * fee_rate
    cash = sell_equity - fee
    return cash, fee
