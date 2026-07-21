#!/usr/bin/env python3
"""為歷史市場CSV逐日補算融資維持率與集中結構，可中斷續抓。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from twse_scraper import FIELDS, OUTPUT_FIELDS, STRUCTURE_FIELDS, TwseClient, market_margin_metrics, number


def load_rows(path: Path) -> list[dict[str, float | str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = []
        for raw in csv.DictReader(f):
            rows.append({key: (raw.get(key, "") if key == "date" else number(raw.get(key, "")))
                         for key in OUTPUT_FIELDS})
        return rows


def save(path: Path, rows: list[dict[str, float | str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?", default=Path("market_history.csv"))
    parser.add_argument("--delay", type=float, default=.25)
    parser.add_argument("--checkpoint", type=int, default=5)
    args = parser.parse_args()
    rows = load_rows(args.csv)
    client = TwseClient(delay=args.delay)
    completed = 0
    for index, row in enumerate(rows, 1):
        if all(float(row.get(key, 0) or 0) > 0 for key in STRUCTURE_FIELDS):
            continue
        metrics = market_margin_metrics(client, str(row["date"]), float(row["margin_balance"]))
        row.update({key: round(value, 4) for key, value in metrics.items()})
        completed += 1
        print(f"[{index}/{len(rows)}] 結構已補齊 {row['date']}")
        if completed % args.checkpoint == 0:
            save(args.csv, rows)
    save(args.csv, rows)
    print(f"完成：新增 {completed} 日，{args.csv}")


if __name__ == "__main__":
    main()
