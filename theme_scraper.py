#!/usr/bin/env python3
"""抓取代表股價格，建立PCB、ABF、散熱等細分題材族群資料。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from twse_scraper import NoDataError, TwseClient, number


THEMES = {
    "水泥": ["1101", "1102", "1103", "1104"],
    "食品製造": ["1201", "1203", "1210", "1215", "1227", "1231"],
    "塑化": ["1301", "1303", "1304", "1305", "1308", "1314"],
    "機能紡織": ["1402", "1476", "1477", "4438"],
    "電線電纜": ["1605", "1608", "1609", "1612", "1618"],
    "生技製藥": ["1701", "1707", "1720", "1760", "1789"],
    "醫療器材": ["4104", "4133", "4736", "6491"],
    "特用化學": ["1711", "1723", "1773", "4763"],
    "玻璃陶瓷": ["1802", "1806", "1809", "1810"],
    "造紙": ["1904", "1905", "1907"],
    "鋼鐵": ["2002", "2006", "2014", "2027", "2031"],
    "輪胎橡膠": ["2101", "2103", "2105", "2106"],
    "汽車整車": ["2201", "2204", "2207"],
    "汽車零組件": ["1319", "1521", "1536", "2227", "2231", "4551"],
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
    "面板": ["2409", "3481", "6116"],
    "LED光電": ["2393", "2499", "3031", "3596", "3714"],
    "光學鏡頭": ["3008", "3406", "3504"],
    "被動元件": ["2327", "2492", "3026", "6173"],
    "半導體通路": ["2347", "3036", "3702", "8112"],
    "資安": ["6690", "6811"],
    "系統整合": ["2427", "2480", "3029", "6214"],
    "電子檢測": ["2360", "3130", "3563"],
    "設備工程": ["2404", "2423", "2467", "3030", "3583", "4585", "6139",
                 "6192", "6196", "6215", "6438", "6658", "6691", "7631"],
    "重電": ["1503", "1513", "1519", "1609", "1618"],
    "機器人": ["1590", "2049", "2308", "2359", "2464", "6166"],
    "貨櫃航運": ["2603", "2609", "2615"],
    "散裝航運": ["2605", "2612", "2617", "2637"],
    "航空": ["2610", "2618", "2646"],
    "營建": ["2501", "2520", "2542", "2548", "2608"],
    "飯店餐旅": ["2704", "2707", "2712", "2727"],
    "金控銀行": ["2880", "2881", "2882", "2884", "2886"],
    "保險": ["2823", "2851", "2867"],
    "百貨零售": ["2903", "2912", "5907", "8454"],
    "石化能源": ["1301", "1303", "1314", "6505", "8926"],
    "太陽能": ["3576", "6443", "6477", "6806"],
    "環保": ["6803", "8341"],
    "雲端服務": ["3045", "4994", "8454"],
    "自行車": ["9914", "9921"],
    "運動健身": ["1598", "1736", "8462", "9904"],
    "居家生活": ["2908", "8464", "9934"],
    "其他綜合": ["9907", "9911", "9924", "9933"],
}

INDUSTRY_NAMES = {
    "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙",
    "10": "鋼鐵", "11": "橡膠", "12": "汽車", "14": "建材營造",
    "15": "航運", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨",
    "20": "其他", "21": "化學", "22": "生技醫療", "23": "油電燃氣",
    "24": "半導體", "25": "電腦及週邊設備", "26": "光電",
    "27": "通信網路", "28": "電子零組件", "29": "電子通路",
    "30": "資訊服務", "31": "其他電子", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活",
    "91": "其他",
}


def complete_themes(client: TwseClient) -> dict[str, list[str]]:
    """保留題材代表股，並讓其餘上市公司進入官方產業的其他族群。"""
    themes = {name: list(codes) for name, codes in THEMES.items()}
    curated = {code for codes in themes.values() for code in codes}
    profiles = client.get_openapi("/opendata/t187ap03_L")
    for profile in profiles:
        code = str(profile.get("公司代號", "")).strip()
        industry = str(profile.get("產業別", "")).strip()
        if not (len(code) == 4 and code.isdigit()) or code in curated:
            continue
        industry_name = INDUSTRY_NAMES.get(industry, "其他")
        fallback = "其他上市" if industry_name == "其他" else f"{industry_name}其他"
        themes.setdefault(fallback, []).append(code)
    return themes


def stock_day(client: TwseClient, day: str,
              themes: dict[str, list[str]]) -> dict[str, dict]:
    payload = client.get("/exchangeReport/MI_INDEX", {
        "date": day.replace("-", ""), "type": "ALLBUT0999",
    })
    wanted = {code for codes in themes.values() for code in codes}
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
    themes = complete_themes(client)
    for day in wanted_dates:
        cached_themes = {key[1] for key in cached if key[0] == day}
        if set(themes).issubset(cached_themes):
            continue
        try:
            stocks = stock_day(client, day, themes)
            for theme, codes in themes.items():
                for code in codes:
                    if code not in stocks:
                        continue
                    cached[(day, theme, code)] = {
                        "date": day, "theme": theme, "code": code,
                        "name": stocks[code]["name"], "close": stocks[code]["close"]}
            print(f"已取得題材族群：{day}")
        except NoDataError:
            print(f"略過尚未發布個股行情：{day}")
    # 只保留現行分類的成分，避免股票改組後仍殘留在舊族群。
    valid_memberships = {(theme, code) for theme, codes in themes.items()
                         for code in codes}
    rows = [cached[key] for key in sorted(cached)
            if key[0] in wanted_dates and (key[1], key[2]) in valid_memberships]
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
