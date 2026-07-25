#!/usr/bin/env python3
"""Walk-forward 回測台股風險分數對未來 5/20 日最大回撤的區辨力。"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from statistics import fmean, median

from risk_score import calculate, load_csv


def future_max_drawdown(closes: list[float], start: int, horizon: int) -> float:
    """從當日收盤開始，未來 horizon 個交易日內的最大 peak-to-trough 回撤（%）。"""
    window = closes[start:min(len(closes), start + horizon + 1)]
    peak, worst = window[0], 0.0
    for close in window[1:]:
        peak = max(peak, close)
        worst = max(worst, (peak - close) / peak * 100)
    return worst


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            result[order[k]] = rank
        i = j + 1
    return result


def correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mx, my = fmean(xs), fmean(ys)
    dx, dy = [x - mx for x in xs], [y - my for y in ys]
    denominator = sum(x * x for x in dx) ** .5 * sum(y * y for y in dy) ** .5
    return None if denominator == 0 else sum(x * y for x, y in zip(dx, dy)) / denominator


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * p
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def bucket(score: float) -> str:
    if score < 40:
        return "10–39.9 低風險"
    if score < 60:
        return "40–59.9 中低風險"
    if score < 80:
        return "60–79.9 中高風險"
    return "80–100 高風險"


def supervised_thresholds(records: list[dict], key: str) -> dict | None:
    """以前70%樣本選三個分界，後30%只驗證；不以驗證集調參。"""
    valid = [r for r in records if r[key] != ""]
    if len(valid) < 40:
        return None
    split = max(1, int(len(valid) * .70))
    train, validation = valid[:split], valid[split:]
    candidates = sorted(set(round(percentile([float(r["score"]) for r in train], p / 100), 1)
                            for p in range(15, 90, 5)))
    minimum = max(5, int(len(train) * .08))
    best = None
    for a_i in range(len(candidates)):
        for b_i in range(a_i + 1, len(candidates)):
            for c_i in range(b_i + 1, len(candidates)):
                cuts = (candidates[a_i], candidates[b_i], candidates[c_i])
                groups = [[], [], [], []]
                for row in train:
                    score, target = float(row["score"]), float(row[key])
                    group = 0 if score < cuts[0] else 1 if score < cuts[1] else 2 if score < cuts[2] else 3
                    groups[group].append(target)
                if any(len(group) < minimum for group in groups):
                    continue
                means = [fmean(group) for group in groups]
                within = sum(sum((value - fmean(group)) ** 2 for value in group) for group in groups) / len(train)
                # 風險分數由低至高時，平均回撤應遞增；違反單調性給予強懲罰。
                violation = sum(max(0, means[i] - means[i + 1]) ** 2 for i in range(3)) * 10
                objective = within + violation
                if best is None or objective < best[0]:
                    best = (objective, cuts, means, [len(group) for group in groups])
    if best is None:
        return None
    _, cuts, train_means, train_counts = best

    def summarize(sample: list[dict]) -> list[dict]:
        groups = [[], [], [], []]
        for row in sample:
            score = float(row["score"])
            group = 0 if score < cuts[0] else 1 if score < cuts[1] else 2 if score < cuts[2] else 3
            groups[group].append(float(row[key]))
        return [{"samples": len(group), "avg_mdd_pct": round(fmean(group), 3) if group else None,
                 "p90_mdd_pct": round(percentile(group, .9), 3) if group else None}
                for group in groups]
    return {"train_samples": len(train), "validation_samples": len(validation),
            "suggested_thresholds": list(cuts),
            "train_avg_mdd_pct": [round(value, 3) for value in train_means],
            "train_bucket_samples": train_counts,
            "validation_buckets_low_to_high_score": summarize(validation)}


def validate_rows(rows: list[dict[str, float | str]]) -> list[str]:
    warnings = []
    dates = [str(row["date"]) for row in rows]
    if len(set(dates)) != len(dates):
        raise ValueError("資料含重複日期")
    for row in rows:
        if min(float(row[k]) for k in ("close", "volume", "margin_balance", "turnover_value")) <= 0:
            raise ValueError(f"{row['date']} 含非正數的價格、量、融資或成交值")
        net = sum(abs(float(row[k])) for k in ("foreign_net", "investment_trust_net", "dealer_net"))
        if net > float(row["turnover_value"]) * 1.5:
            warnings.append(f"{row['date']} 法人金額可能與成交值單位不同")
    return warnings


def run_backtest(rows: list[dict[str, float | str]]) -> tuple[list[dict], dict]:
    warnings = validate_rows(rows)
    closes = [float(row["close"]) for row in rows]
    records = []
    for i in range(119, len(rows) - 5):
        score = calculate(rows[:i + 1])
        record = {"date": score.date, "score": score.total,
                  "technical": score.technical, "volume": score.volume,
                  "margin": score.margin, "institutional": score.institutional,
                  "mdd_5d_pct": round(future_max_drawdown(closes, i, 5), 4),
                  "mdd_20d_pct": ""}
        if i + 20 < len(rows):
            record["mdd_20d_pct"] = round(future_max_drawdown(closes, i, 20), 4)
        records.append(record)

    summaries = {}
    for horizon in (5, 20):
        key = f"mdd_{horizon}d_pct"
        valid = [r for r in records if r[key] != ""]
        groups = []
        for label in ("10–39.9 低風險", "40–59.9 中低風險", "60–79.9 中高風險", "80–100 高風險"):
            values = [float(r[key]) for r in valid if bucket(float(r["score"])) == label]
            groups.append({"bucket": label, "samples": len(values),
                           "avg_mdd_pct": round(fmean(values), 3) if values else None,
                           "median_mdd_pct": round(median(values), 3) if values else None,
                           "p90_mdd_pct": round(percentile(values, .9), 3) if values else None})
        rho = correlation(ranks([float(r["score"]) for r in valid]),
                          ranks([float(r[key]) for r in valid]))
        summaries[f"{horizon}d"] = {"samples": len(valid),
                                     "spearman_score_vs_mdd": round(rho, 4) if rho is not None else None,
                                     "buckets": groups}
    span_days = (date.fromisoformat(str(rows[-1]["date"])) -
                 date.fromisoformat(str(rows[0]["date"]))).days
    if len(rows) < 500 or span_days < 730:
        warnings.append("樣本未涵蓋至少兩年／500 個交易日，不宜據此正式校準門檻")
    report = {"data_start": rows[0]["date"], "data_end": rows[-1]["date"],
              "trading_days": len(rows), "calendar_days": span_days,
              "method": "expanding-window；每期僅使用當時及以前資料",
              "interpretation": "分數愈高應對應愈大回撤，因此 Spearman 係數預期為正",
              "warnings": warnings, "results": summaries}
    calibration = supervised_thresholds(records, "mdd_20d_pct")
    report["calibration_20d"] = calibration
    if calibration is None:
        report["warnings"].append("完整20日樣本少於40筆，未產生監督式門檻建議")
    return records, report


def write_records(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]) if records else [])
        if records:
            writer.writeheader()
            writer.writerows(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?", default=Path("market.csv"))
    parser.add_argument("--daily-output", type=Path, default=Path("backtest_daily.csv"))
    parser.add_argument("--report", type=Path, default=Path("backtest_report.json"))
    args = parser.parse_args()
    records, report = run_backtest(load_csv(args.csv))
    write_records(args.daily_output, records)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"逐日結果：{args.daily_output}\n報告：{args.report}")


if __name__ == "__main__":
    main()
