#!/usr/bin/env python3
"""從臺灣證券交易所官方網站建立大盤風險模型所需的 CSV。"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://www.twse.com.tw"
FIELDS = ["date", "close", "volume", "margin_balance", "turnover_value",
          "foreign_net", "investment_trust_net", "dealer_net"]
STRUCTURE_FIELDS = ["margin_maintenance_pct", "margin_top10_concentration_pct",
                    "margin_hhi", "margin_top3_industry_concentration_pct",
                    "short_margin_ratio_pct", "high_margin_cap_exposure_pct"]
OUTPUT_FIELDS = FIELDS + STRUCTURE_FIELDS


class NoDataError(RuntimeError):
    """證交所端點尚未發布該日期資料。"""


def number(value: str) -> float:
    text = str(value).replace(",", "").strip()
    return float(text) if text not in {"", "--"} else 0.0


def roc_date(value: str) -> str:
    year, month, day = (int(part) for part in value.split("/"))
    return f"{year + 1911:04d}-{month:02d}-{day:02d}"


class TwseClient:
    def __init__(self, delay: float = 0.2, retries: int = 3) -> None:
        self.delay = delay
        self.retries = retries
        self._company_profiles: list[dict] | None = None

    def get(self, path: str, params: dict[str, str]) -> dict:
        url = f"{BASE_URL}{path}?{urlencode({**params, 'response': 'json'})}"
        request = Request(url, headers={
            "User-Agent": "twse-risk-score/1.0 (personal research)",
            "Accept": "application/json",
        })
        error: Exception | None = None
        for attempt in range(self.retries):
            try:
                if self.delay:
                    time.sleep(self.delay + random.uniform(0, self.delay / 3))
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8-sig"))
                if payload.get("stat") != "OK":
                    # 「沒有符合條件的資料」常發生於當日不同報表發布時間差，
                    # 不是暫時性網路錯誤，不需要重試。
                    raise NoDataError(str(payload.get("stat") or "查無資料"))
                return payload
            except NoDataError:
                raise
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                error = exc
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"TWSE 請求失敗：{url}：{error}") from error

    def get_openapi(self, path: str) -> list[dict]:
        if path == "/opendata/t187ap03_L" and self._company_profiles is not None:
            return self._company_profiles
        url = f"https://openapi.twse.com.tw/v1{path}"
        request = Request(url, headers={"User-Agent": "twse-risk-score/1.0",
                                        "Accept": "application/json"})
        error: Exception | None = None
        for attempt in range(self.retries):
            try:
                if self.delay:
                    time.sleep(self.delay)
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8-sig"))
                if not isinstance(payload, list):
                    raise RuntimeError("OpenAPI 回傳格式非陣列")
                if path == "/opendata/t187ap03_L":
                    self._company_profiles = payload
                return payload
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                error = exc
                if attempt + 1 < self.retries:
                    time.sleep(2 ** attempt)
        raise RuntimeError(f"TWSE OpenAPI 請求失敗：{url}：{error}") from error


def market_month(client: TwseClient, month: date) -> list[dict[str, float | str]]:
    payload = client.get("/exchangeReport/FMTQIK", {"date": month.strftime("%Y%m01")})
    fields = payload.get("fields", [])
    aliases = {
        "date": "日期", "volume": "成交股數", "turnover_value": "成交金額",
        "close": "發行量加權股價指數",
    }
    try:
        indexes = {key: fields.index(label) for key, label in aliases.items()}
    except ValueError as exc:
        raise ValueError(f"FMTQIK 欄位格式已改變：{fields}") from exc
    return [{
        "date": roc_date(row[indexes["date"]]),
        "close": number(row[indexes["close"]]),
        "volume": number(row[indexes["volume"]]),
        "turnover_value": number(row[indexes["turnover_value"]]),
    } for row in payload.get("data", [])]


def margin_balance(client: TwseClient, day: str) -> float:
    payload = client.get("/exchangeReport/MI_MARGN", {
        "date": day.replace("-", ""), "selectType": "MS",
    })
    for table in payload.get("tables", []):
        fields = table.get("fields", [])
        if "項目" not in fields or "今日餘額" not in fields:
            continue
        item_i, balance_i = fields.index("項目"), fields.index("今日餘額")
        for row in table.get("data", []):
            if "融資金額" in row[item_i]:
                return number(row[balance_i]) * 1000  # 官方欄位單位為仟元
    raise ValueError(f"{day} 找不到融資金額今日餘額")


def market_margin_metrics(client: TwseClient, day: str,
                          total_margin_amount: float) -> dict[str, float]:
    """以個股資券、價格與股本估算集中市場槓桿結構。"""
    compact = day.replace("-", "")
    margin_payload = client.get("/exchangeReport/MI_MARGN", {
        "date": compact, "selectType": "ALL",
    })
    balances: dict[str, float] = {}
    shorts: dict[str, float] = {}
    for table in margin_payload.get("tables", []):
        fields = table.get("fields", [])
        if fields[:2] != ["代號", "名稱"] or fields.count("今日餘額") < 2:
            continue
        # 第一個「今日餘額」屬融資，數值單位為交易單位（通常 1,000 股）。
        balance_i = fields.index("今日餘額")
        short_i = fields.index("今日餘額", balance_i + 1)
        for row in table.get("data", []):
            balances[str(row[0]).strip()] = number(row[balance_i])
            shorts[str(row[0]).strip()] = number(row[short_i])
        break
    price_payload = client.get("/exchangeReport/MI_INDEX", {
        "date": compact, "type": "ALLBUT0999",
    })
    prices: dict[str, float] = {}
    for table in price_payload.get("tables", []):
        fields = table.get("fields", [])
        if "證券代號" in fields and "收盤價" in fields:
            code_i, close_i = fields.index("證券代號"), fields.index("收盤價")
            for row in table.get("data", []):
                prices[str(row[code_i]).strip()] = number(row[close_i])
    if not balances or not prices or total_margin_amount <= 0:
        raise ValueError(f"{day} 無法取得維持率所需的個股明細")
    market_values = {code: units * 1000 * prices.get(code, 0.0)
                     for code, units in balances.items() if prices.get(code, 0) > 0}
    collateral_value = sum(market_values.values())
    shares = [value / collateral_value for value in market_values.values()
              if collateral_value > 0]
    top10 = sum(sorted(shares, reverse=True)[:10]) * 100
    hhi = sum(weight * weight for weight in shares) * 10_000

    profiles = client.get_openapi("/opendata/t187ap03_L")
    company = {str(item.get("公司代號", "")).strip(): item for item in profiles}
    industry_values: dict[str, float] = {}
    mapped_value = 0.0
    high_cap_value = 0.0
    for code, value in market_values.items():
        profile = company.get(code)
        if not profile:
            continue  # ETF、ETN 等不具上市公司產業與股本欄位
        mapped_value += value
        industry = str(profile.get("產業別", "未知")).strip()
        industry_values[industry] = industry_values.get(industry, 0.0) + value
        issued = number(str(profile.get("已發行普通股數或TDR原股發行股數", "0")))
        if issued > 0 and balances.get(code, 0) * 1000 / issued >= .10:
            high_cap_value += value
    top3_industry = (sum(sorted(industry_values.values(), reverse=True)[:3]) /
                     mapped_value * 100 if mapped_value else 0.0)
    high_cap_exposure = high_cap_value / mapped_value * 100 if mapped_value else 0.0
    total_margin_units = sum(balances.values())
    short_margin_ratio = (sum(shorts.values()) / total_margin_units * 100
                          if total_margin_units else 0.0)
    return {"margin_maintenance_pct": collateral_value / total_margin_amount * 100,
            "margin_top10_concentration_pct": top10, "margin_hhi": hhi,
            "margin_top3_industry_concentration_pct": top3_industry,
            "short_margin_ratio_pct": short_margin_ratio,
            "high_margin_cap_exposure_pct": high_cap_exposure}


def market_margin_maintenance(client: TwseClient, day: str,
                              total_margin_amount: float) -> float:
    return market_margin_metrics(client, day, total_margin_amount)["margin_maintenance_pct"]


def institutional(client: TwseClient, day: str) -> dict[str, float]:
    payload = client.get("/fund/BFI82U", {
        "dayDate": day.replace("-", ""), "type": "day",
    })
    fields = payload.get("fields", [])
    if "單位名稱" not in fields or "買賣差額" not in fields:
        raise ValueError(f"BFI82U 欄位格式已改變：{fields}")
    name_i, net_i = fields.index("單位名稱"), fields.index("買賣差額")
    result = {"foreign_net": 0.0, "investment_trust_net": 0.0, "dealer_net": 0.0}
    for row in payload.get("data", []):
        name, net = row[name_i], number(row[net_i])
        if name.startswith("外資及陸資"):
            result["foreign_net"] += net
        elif name.startswith("投信"):
            result["investment_trust_net"] += net
        elif name.startswith("自營商"):
            result["dealer_net"] += net  # 自行買賣＋避險
    return result


def months_back(end: date, count: int) -> list[date]:
    values = []
    year, month = end.year, end.month
    for _ in range(count):
        values.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(values))


def load_cache(path: Path) -> dict[str, dict[str, float | str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = {}
        for row in csv.DictReader(f):
            parsed = {k: (row[k] if k == "date" else number(row[k])) for k in FIELDS}
            for key in STRUCTURE_FIELDS:
                if row.get(key):
                    parsed[key] = number(row[key])
            rows[row["date"]] = parsed
        return rows


def write_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def scrape(output: Path, months: int, end: date, delay: float = 0.2,
           limit: int | None = None) -> list[dict[str, float | str]]:
    client = TwseClient(delay=delay)
    cache = load_cache(output)
    market = {}
    for month in months_back(end, months):
        for row in market_month(client, month):
            if str(row["date"]) <= end.isoformat():
                market[str(row["date"])] = row
    days = sorted(market)
    if limit:
        days = days[-limit:]
    for index, day in enumerate(days, 1):
        cached = cache.get(day)
        if cached and all(key in cached for key in FIELDS):
            market[day] = cached
            continue
        row = market[day]
        try:
            row["margin_balance"] = margin_balance(client, day)
            row.update(institutional(client, day))
        except NoDataError as exc:
            print(f"[{index}/{len(days)}] 略過 {day}：盤後資料尚未完整發布（{exc}）")
            continue
        cache[day] = row
        print(f"[{index}/{len(days)}] 已取得 {day}")
        if index % 10 == 0:
            checkpoint = [cache[d] for d in days if d in cache]
            write_csv(output, checkpoint)
    rows = [cache[day] for day in days if day in cache]
    if rows and any(not rows[-1].get(key) for key in STRUCTURE_FIELDS):
        latest = rows[-1]
        metrics = market_margin_metrics(client, str(latest["date"]),
                                        float(latest["margin_balance"]))
        latest.update({key: round(value, 4) for key, value in metrics.items()})
        print(f"市場加權融資維持率：{latest['margin_maintenance_pct']:.2f}%")
        print(f"融資 Top-10 集中度：{latest['margin_top10_concentration_pct']:.2f}%")
    write_csv(output, rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("market.csv"))
    parser.add_argument("--months", type=int, default=8, help="回抓日曆月數（預設 8）")
    parser.add_argument("--end", type=date.fromisoformat, default=date.today(), help="截止日 YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=140, help="最多保留最近幾個交易日")
    parser.add_argument("--delay", type=float, default=0.2, help="每次請求至少間隔秒數")
    args = parser.parse_args()
    if args.months < 1 or args.limit < 120 or args.delay < 0:
        parser.error("months 須 >= 1、limit 須 >= 120、delay 須 >= 0")
    rows = scrape(args.output, args.months, args.end, args.delay, args.limit)
    print(f"完成：{args.output}（{len(rows)} 個交易日）")
    if len(rows) < 120:
        print("警告：不足 120 日，請增加 --months 後重跑")


if __name__ == "__main__":
    main()
