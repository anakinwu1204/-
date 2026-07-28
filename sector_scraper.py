#!/usr/bin/env python3
"""抓取證交所產業類股指數，供族群盤勢分析頁使用。"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from twse_scraper import NoDataError, TwseClient, number


SECTORS = {
    "水泥類指數", "食品類指數", "塑膠類指數", "紡織纖維類指數",
    "電機機械類指數", "電器電纜類指數", "化學生技醫療類指數",
    "化學類指數", "生技醫療類指數", "玻璃陶瓷類指數", "造紙類指數",
    "鋼鐵類指數", "橡膠類指數", "汽車類指數", "半導體類指數",
    "電腦及週邊設備類指數", "光電類指數", "通信網路類指數",
    "電子零組件類指數", "電子通路類指數", "資訊服務類指數",
    "其他電子類指數", "建材營造類指數", "航運類指數",
    "觀光餐旅類指數", "金融保險類指數", "貿易百貨類指數",
    "油電燃氣類指數", "綠能環保類指數", "數位雲端類指數",
    "運動休閒類指數", "居家生活類指數", "其他類指數",
}


def sector_day(client: TwseClient, day: str) -> list[dict[str, float | str]]:
    payload = client.get("/exchangeReport/MI_INDEX", {
        "date": day.replace("-", ""), "type": "IND",
    })
    table = payload.get("tables", [])[0]
    fields = table.get("fields", [])
    name_i, close_i, return_i = (fields.index("指數"), fields.index("收盤指數"),
                                 fields.index("漲跌百分比(%)"))
    return [{"date": day, "sector": str(row[name_i]).removesuffix("類指數"),
             "close": number(row[close_i]), "daily_return_pct": number(row[return_i])}
            for row in table.get("data", []) if row[name_i] in SECTORS]


def market_dates(path: Path, limit: int) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        dates = [row["date"] for row in csv.DictReader(handle)]
    return dates[-limit:]


def scrape(market_path: Path, output: Path, limit: int, delay: float) -> int:
    cached: dict[tuple[str, str], dict] = {}
    if output.exists():
        with output.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                cached[(row["date"], row["sector"])] = row
    client = TwseClient(delay=delay)
    wanted = market_dates(market_path, limit)
    complete_days = {day for day in wanted
                     if sum(key[0] == day for key in cached) >= len(SECTORS)}
    for day in wanted:
        if day in complete_days:
            continue
        try:
            for row in sector_day(client, day):
                cached[(day, str(row["sector"]))] = row
            print(f"已取得產業指數：{day}")
        except NoDataError:
            print(f"略過尚未發布產業指數：{day}")
    rows = [cached[key] for key in sorted(cached) if key[0] in wanted]
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "date", "sector", "close", "daily_return_pct"])
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, default=Path("market.csv"))
    parser.add_argument("--output", type=Path, default=Path("sectors.csv"))
    parser.add_argument("--limit", type=int, default=45)
    parser.add_argument("--delay", type=float, default=.2)
    args = parser.parse_args()
    count = scrape(args.market, args.output, args.limit, args.delay)
    print(f"完成：{args.output}（{count}筆）")


if __name__ == "__main__":
    main()
