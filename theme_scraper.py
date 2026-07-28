#!/usr/bin/env python3
"""抓取代表股價格，建立PCB、ABF、散熱等細分題材族群資料。"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from twse_scraper import NoDataError, TwseClient, number


THEMES = {
    "水泥": ["1101", "1102", "1103", "1104"],
    "食品製造": ["1201", "1203", "1210", "1215", "1227", "1231"],
    "飲料食品": ["1216", "1217", "1218", "1234", "1235", "1256"],
    "油脂飼料": ["1210", "1219", "1225", "1229", "1232", "1702"],
    "塑化": ["1301", "1303", "1304", "1305", "1308", "1314"],
    "塑膠加工": ["1307", "1315", "1323", "1324", "1325", "1337", "1341",
                 "4306"],
    "石化原料": ["1309", "1310", "1312", "1313", "1321", "1326"],
    "機能紡織": ["1402", "1476", "1477", "4438"],
    "聚酯尼龍": ["1409", "1440", "1444", "1447", "1455"],
    "織布染整": ["1410", "1413", "1434", "1460", "1463", "1464", "1466",
                 "1474"],
    "成衣製鞋": ["1417", "1451", "1473", "4414", "4439", "4441"],
    "電線電纜": ["1605", "1608", "1609", "1612", "1618"],
    "生技製藥": ["1701", "1707", "1720", "1760", "1789"],
    "醫療器材": ["4104", "4133", "4736", "6491"],
    "原料藥CDMO": ["1762", "4119", "4746", "6472"],
    "生物新藥": ["4142", "6446", "6541", "6550", "6589", "6598", "6657",
                 "6794", "6838", "6885", "6919"],
    "醫美保健": ["1731", "1783", "1786", "4137", "4190", "6666"],
    "眼科視覺": ["4108", "4737", "4771", "6782"],
    "特用化學": ["1711", "1723", "1773", "4763"],
    "基礎化學肥料": ["1708", "1709", "1710", "1712", "1713", "1714",
                     "1718", "1722"],
    "塗料接著劑": ["1717", "1726", "1727", "1735", "1776", "4720", "4722",
                   "4766"],
    "玻璃陶瓷": ["1802", "1806", "1809", "1810"],
    "造紙": ["1904", "1905", "1907"],
    "鋼鐵": ["2002", "2006", "2014", "2027", "2031"],
    "不鏽鋼特殊鋼": ["2023", "2029", "2030", "2034", "2069"],
    "鋼構工程": ["2013", "2211", "5538", "9958"],
    "扣件線材": ["2012", "2027", "2033", "5007"],
    "輪胎橡膠": ["2101", "2103", "2105", "2106"],
    "汽車整車": ["2201", "2204", "2207"],
    "汽車零組件": ["1319", "1521", "1536", "2227", "2231", "4551"],
    "汽車照明": ["1522", "3346", "3717", "6605"],
    "電動車零組件": ["1533", "2231", "2258", "2497"],
    "汽車精密件": ["1563", "2233", "2250", "4569", "4581", "7732"],
    "PCB": ["2313", "2355", "2367", "2368", "3037", "3044", "3715", "4927",
            "4958", "5469", "6191", "8046", "8213"],
    "ABF載板": ["3037", "3189", "8046"],
    "散熱": ["2421", "3017", "3324", "3653", "6230"],
    "記憶體": ["2337", "2344", "2408", "4967", "8271"],
    "CCL銅箔基板": ["2383", "6213", "6274"],
    "玻纖布": ["1802", "1815", "5340"],
    "TGV玻璃基板": ["1802", "2409", "2467", "3019", "3167", "3362",
                    "3455", "3481", "3563", "6207", "6438"],
    "AI伺服器": ["2308", "2317", "2382", "3017", "3231", "3706", "6414",
                 "6669", "8210"],
    "半導體設備": ["2467", "3583", "6196"],
    "晶圓代工": ["2303", "2330", "2342", "6770"],
    "封裝測試": ["2329", "2441", "2449", "3711", "6239", "6257", "6271",
                 "6451", "6525", "8110", "8131", "8150"],
    "矽晶圓": ["3016", "3532", "6182", "6488", "8028"],
    "功率半導體": ["2340", "2434", "2481", "5285", "6573", "8261"],
    "IC設計": ["2379", "2454", "3034", "3443", "3661", "5269"],
    "光通訊": ["3450", "4977", "4979", "6442"],
    "網通": ["2345", "2412", "4904", "5388", "6285"],
    "面板": ["2409", "3481", "6116"],
    "LED光電": ["2393", "2499", "3031", "3596", "3714"],
    "光學鏡頭": ["3008", "3406", "3504"],
    "被動元件": ["2327", "2375", "2428", "2472", "2478", "2492", "3026",
                 "6173", "6449"],
    "石英元件": ["2484", "3042", "6792", "8182"],
    "連接器線材": ["2328", "2392", "3003", "3023", "3533", "3665", "6197",
                   "6279"],
    "電源供應": ["2308", "3015", "6282", "6409", "6412"],
    "半導體通路": ["2347", "3036", "3702", "8112"],
    "資安": ["6690", "6811"],
    "系統整合": ["2427", "2480", "3029", "6214"],
    "電子檢測": ["2360", "3130", "3563"],
    "設備工程": ["2404", "2423", "2467", "3030", "3583", "4585", "6139",
                 "6192", "6196", "6215", "6438", "6658", "6691", "7631"],
    "重電": ["1503", "1513", "1519", "1609", "1618"],
    "工具機": ["1528", "1530", "1531", "1540", "1583", "4526", "6606",
               "7750"],
    "傳動元件": ["1597", "4540", "4576", "8374"],
    "工業工具": ["1515", "1527", "1539", "1541", "1558"],
    "機器人": ["1590", "2049", "2359", "2464", "3665", "4585", "6166",
               "6215"],
    "貨櫃航運": ["2603", "2609", "2615"],
    "散裝航運": ["2605", "2612", "2617", "2637"],
    "航空": ["2610", "2618", "2646"],
    "航太造船": ["2208", "2630", "2634", "2645", "6753"],
    "物流港口": ["2607", "2611", "2613", "2636", "2642", "5607", "8367"],
    "營建": ["2501", "2520", "2542", "2548", "2608"],
    "建設開發": ["1436", "1438", "1442", "1808", "2442", "2505", "2509",
                 "2511", "2524", "2527", "2528", "2534", "2536", "2537",
                 "2538", "2539", "2540", "2545", "2547", "2923", "3056",
                 "3266", "5519", "5522", "5525", "5531", "5533", "5534",
                 "6177", "9906", "9946"],
    "工程承攬": ["1472", "2515", "2516", "2543", "2546", "2597", "3703",
                 "5515", "5521"],
    "飯店餐旅": ["2704", "2707", "2712", "2727"],
    "飯店住宿": ["2701", "2702", "2705", "2706", "2722", "2739", "2748"],
    "連鎖餐飲": ["2723", "2753", "7705", "8940"],
    "旅行休閒": ["2731", "5706", "9943"],
    "金控銀行": ["2880", "2881", "2882", "2884", "2886"],
    "銀行": ["2801", "2812", "2834", "2836", "2838", "2845", "2849",
             "2897", "5876", "5880"],
    "證券期貨": ["2855", "6005", "6024"],
    "保險": ["2823", "2851", "2867"],
    "百貨零售": ["2903", "2912", "5907", "8454"],
    "服飾通路": ["2906", "2911", "2929", "5906", "8429", "8443"],
    "生活零售": ["2901", "2905", "2910", "2945", "6281"],
    "石化能源": ["1301", "1303", "1314", "6505", "8926"],
    "太陽能": ["3576", "6443", "6477", "6806"],
    "環保": ["6803", "8341"],
    "風力發電": ["2072", "3708", "7786"],
    "環保處理": ["5292", "6581", "6641", "6771", "6923", "6944", "6947",
                 "8422", "8438", "8473", "8476", "9930", "9955"],
    "能源服務": ["6869", "6873", "6994", "7740"],
    "雲端服務": ["3045", "4994", "8454"],
    "自行車": ["9914", "9921"],
    "運動健身": ["1598", "1736", "8462", "9904"],
    "居家生活": ["2908", "8464", "9934"],
    "其他綜合": ["9907", "9911", "9924", "9933"],
}
TAXONOMY_VERSION = "2026-07-28.4"

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
    missing = wanted - set(result)
    if missing:
        result.update(tpex_stock_day(day, missing, client.delay))
    return result


def parse_tpex_stock_day(payload: dict, wanted: set[str]) -> dict[str, dict]:
    result = {}
    for table in payload.get("tables", []):
        fields = [str(field).replace("<br>", "").strip()
                  for field in table.get("fields", [])]
        if not {"代號", "名稱", "收盤"}.issubset(fields):
            continue
        code_i, name_i, close_i = (fields.index("代號"), fields.index("名稱"),
                                   fields.index("收盤"))
        for row in table.get("data", []):
            code = str(row[code_i]).strip()
            if code not in wanted:
                continue
            try:
                close = number(row[close_i])
            except ValueError:
                continue
            if close > 0:
                result[code] = {"name": str(row[name_i]).strip(), "close": close}
        break
    return result


def tpex_stock_day(day: str, wanted: set[str], delay: float) -> dict[str, dict]:
    query = urlencode({"date": day.replace("-", "/"), "type": "AL",
                       "response": "json"})
    url = f"https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?{query}"
    request = Request(url, headers={"User-Agent": "twse-risk-score/1.0",
                                    "Accept": "application/json"})
    error = None
    for attempt in range(3):
        try:
            if delay:
                time.sleep(delay)
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8-sig"))
            return parse_tpex_stock_day(payload, wanted)
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"櫃買中心行情請求失敗：{url}：{error}") from error


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
        current_taxonomy = any(
            key[0] == day and row.get("taxonomy_version") == TAXONOMY_VERSION
            for key, row in cached.items())
        if current_taxonomy and set(themes).issubset(cached_themes):
            continue
        try:
            stocks = stock_day(client, day, themes)
            for theme, codes in themes.items():
                for code in codes:
                    if code not in stocks:
                        continue
                    cached[(day, theme, code)] = {
                        "date": day, "theme": theme, "code": code,
                        "name": stocks[code]["name"], "close": stocks[code]["close"],
                        "taxonomy_version": TAXONOMY_VERSION}
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
            "date", "theme", "code", "name", "close", "taxonomy_version"])
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
