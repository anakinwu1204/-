#!/usr/bin/env python3
"""回測做多提醒：訊號後一交易日收盤進場，預設持有十個交易日。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean, median

from risk_score import calculate, load_csv


def signal_flags(score) -> dict[str, bool]:
    m = score.metrics
    above = m["distance_ma60_pct"] > 0
    rising = m["ma60_slope_20d_pct"] > 0
    return {
        "strong": score.total <= 30,
        "ready": score.total <= 35 and above and rising,
        "pullback": (score.total <= 45 and above and rising
                     and -5 <= m["return_20d_pct"] <= 8),
    }


def summarize(trades: list[dict]) -> dict:
    returns = [trade["return_pct"] for trade in trades]
    drawdowns = [trade["max_drawdown_pct"] for trade in trades]
    gains = sum(value for value in returns if value > 0)
    losses = -sum(value for value in returns if value < 0)
    return {
        "trades": len(trades),
        "win_rate_pct": round(sum(value > 0 for value in returns) / len(returns) * 100, 2),
        "avg_return_pct": round(fmean(returns), 3),
        "median_return_pct": round(median(returns), 3),
        "avg_max_drawdown_pct": round(fmean(drawdowns), 3),
        "profit_factor": round(gains / losses, 2) if losses else None,
    }


def run(rows: list[dict[str, float | str]], holding_days: int = 10) -> dict:
    closes = [float(row["close"]) for row in rows]
    dates = [str(row["date"]) for row in rows]
    candidates = []
    exit_offset = holding_days + 1
    for i in range(119, len(rows) - exit_offset):
        score = calculate(rows[:i + 1])
        flags = signal_flags(score)
        if not any(flags.values()):
            continue
        path = closes[i + 1:i + exit_offset + 1]
        peak, worst = path[0], 0.0
        for close in path[1:]:
            peak = max(peak, close)
            worst = max(worst, (peak - close) / peak * 100)
        candidates.append({
            "signal_index": i, "signal_date": dates[i], "entry_date": dates[i + 1],
            "exit_date": dates[i + exit_offset], "signal": "strong" if flags["strong"] else
            "ready" if flags["ready"] else "pullback",
            "return_pct": round((path[-1] / path[0] - 1) * 100, 4),
            "max_drawdown_pct": round(worst, 4),
        })

    # 訊號可連續發生；正式策略在前一筆出場前不重複進場。
    independent, last_exit_index = [], -1
    for trade in candidates:
        if trade["signal_index"] < last_exit_index:
            continue
        independent.append(trade)
        last_exit_index = trade["signal_index"] + exit_offset
    strong_candidates = [trade for trade in candidates if trade["signal"] == "strong"]
    strong_independent, last_exit_index = [], -1
    for trade in strong_candidates:
        if trade["signal_index"] < last_exit_index:
            continue
        strong_independent.append(trade)
        last_exit_index = trade["signal_index"] + exit_offset
    return {
        "data_start": dates[0], "data_end": dates[-1], "holding_trading_days": holding_days,
        "execution": f"訊號日收盤後確認；下一交易日收盤進場；第{holding_days}個交易日收盤出場",
        "all_signal_observations": summarize(candidates),
        "non_overlapping_trades": summarize(independent),
        "strong_non_overlapping_trades": summarize(strong_independent),
        "trades": independent,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?", default=Path("market_history.csv"))
    parser.add_argument("--report", type=Path, default=Path("long_entry_backtest_report.json"))
    parser.add_argument("--holding-days", type=int, default=10)
    args = parser.parse_args()
    if args.holding_days < 1:
        parser.error("holding-days 必須大於 0")
    report = run(load_csv(args.csv), args.holding_days)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "trades"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
