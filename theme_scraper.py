#!/usr/bin/env python3
"""抓取代表股價格，建立PCB、ABF、散熱等細分題材族群資料。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from twse_scraper import NoDataError, TwseClient, number


THEMES = {
    "PCB": ["2313", "2367", "3037", "3044", "4958", "5469", "6191", "8046"],
    "ABF載板": ["3037", "3189", "8046"],
    "散熱": ["2421", "3017", "3324", "3653", "6230"],
    "記憶體": ["2337", "2344", "2408", "4967", "8271"],
    "CCL銅箔基板": ["2383", "6213", "6274"],
    "AI伺服器": ["2317", "2382", "3017", "3231", "6669"],
    "半導體設備": ["2467", "3583", "6196"],
    "IC設計": ["2379", "2454", "3034", "3443", "3661", "5269"],
    "光通訊": ["3450", "4977", "4979", "6442"],
    "網通": ["2345", "2412", "4904", "5388", "6285"],
    "重電": ["1503", "1513", "1519", "1609", "1618"],
    "機器人": ["1590", "2049", "2308", "2359", "2464", "6166"],
}


def stock_day(client: TwseClient, day: str) -> dict[str, dict]:
    payload = client.get("/exchangeReport/MI_INDEX", {
        "date": day.replace("-", ""), "type": "ALLBUT0999",
    })
    wanted = {code for codes in THEMES.values() for code in codes}
    result = {}
    for table in payload.get("tables", []):
        fields = table.get("fields", [])
        if "證券代號" not in fields or "收盤價" not in fields:
            continue
        code_i, name_i, close_i = (fields.index("證券代號"),
                                   fields.index("證券名稱"), fields.index("收盤價"))
        for row in table.get("data", []):
            code = str(row[code_i]).strip()
            if code in wanted and number(row[close_i]) > 0:
                result[code] = {"name": str(row[name_i]).strip(),
                                "close": number(row[close_i])}
        break
    return result


def dates(path: Path, limit: int) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [row["date"] for row in csv.DictReader(handle)][-limit:]


def scrape(market_path: Path, output: Path, limit: int, delay: float) -> int:
    cached: dict[tuple[str, str, str], dict] = {}
    if output.exists():
        with output.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                cached[(row["date"], row["theme"], row["code"])] = row
    client, wanted_dates = TwseClient(delay=delay), dates(market_path, limit)
    for day in wanted_dates:
        if any(key[0] == day for key in cached):
            continue
        try:
            stocks = stock_day(client, day)
            for theme, codes in THEMES.items():
                for code in codes:
                    if code not in stocks:
                        continue
                    cached[(day, theme, code)] = {
                        "date": day, "theme": theme, "code": code,
                        "name": stocks[code]["name"], "close": stocks[code]["close"]}
            print(f"已取得題材族群：{day}")
        except NoDataError:
            print(f"略過尚未發布個股行情：{day}")
    rows = [cached[key] for key in sorted(cached) if key[0] in wanted_dates]
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "date", "theme", "code", "name", "close"])
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, default=Path("market.csv"))
    parser.add_argument("--output", type=Path, default=Path("themes.csv"))
    parser.add_argument("--limit", type=int, default=45)
    parser.add_argument("--delay", type=float, default=.2)
    args = parser.parse_args()
    count = scrape(args.market, args.output, args.limit, args.delay)
    print(f"完成：{args.output}（{count}筆）")


if __name__ == "__main__":
    main()
