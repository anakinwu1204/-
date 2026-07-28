#!/usr/bin/env python3
"""台股風險儀表板本機伺服器。"""

from __future__ import annotations

import argparse
import csv
import json
import os
import threading
from dataclasses import asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import fmean
from urllib.parse import urlparse

from risk_score import calculate, load_csv
from sector_scraper import scrape as scrape_sectors
from twse_scraper import scrape


ROOT = Path(__file__).resolve().parent


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    try:
        return default if value is None else int(value)
    except ValueError as exc:
        raise SystemExit(f"環境變數 {name} 必須是整數，目前為 {value!r}") from exc


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    try:
        return default if value is None else float(value)
    except ValueError as exc:
        raise SystemExit(f"環境變數 {name} 必須是數字，目前為 {value!r}") from exc


def dashboard_data(csv_path: Path) -> dict:
    rows = load_csv(csv_path)
    latest = calculate(rows)
    scores = []
    for end in range(119, len(rows)):
        score = calculate(rows[:end + 1])
        scores.append({"date": score.date, "total": score.total})
    score_by_date = {item["date"]: item["total"] for item in scores}
    series = []
    closes = [float(row["close"]) for row in rows]
    for i, row in enumerate(rows):
        series.append({
            "date": row["date"],
            "close": closes[i],
            "ma60": round(fmean(closes[i - 59:i + 1]), 2) if i >= 59 else None,
            "ma120": round(fmean(closes[i - 119:i + 1]), 2) if i >= 119 else None,
            "score": score_by_date.get(str(row["date"])),
            "volume": float(row["turnover_value"]),
        })
    latest_row = rows[-1]
    institutions = {
        key: float(latest_row[key]) for key in
        ("foreign_net", "investment_trust_net", "dealer_net")
    }
    return {"latest": asdict(latest), "series": series, "institutions": institutions,
            "row_count": len(rows), "source": csv_path.name}


def sector_data(csv_path: Path, market_path: Path) -> dict:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    market = load_csv(market_path)
    market_close = {str(row["date"]): float(row["close"]) for row in market}
    by_sector: dict[str, list[dict]] = {}
    for row in rows:
        by_sector.setdefault(row["sector"], []).append({
            "date": row["date"], "close": float(row["close"]),
            "daily_return_pct": float(row["daily_return_pct"])})
    results = []
    for name, history in by_sector.items():
        history.sort(key=lambda item: item["date"])
        if len(history) < 21:
            continue
        latest = history[-1]
        r5 = (latest["close"] / history[-6]["close"] - 1) * 100
        r20 = (latest["close"] / history[-21]["close"] - 1) * 100
        dates = [item["date"] for item in history]
        m0, m5, m20 = (market_close.get(dates[-1]), market_close.get(dates[-6]),
                        market_close.get(dates[-21]))
        if not all((m0, m5, m20)):
            continue
        market_daily = (m0 / market_close[dates[-2]] - 1) * 100
        rel1 = latest["daily_return_pct"] - market_daily
        rel5 = r5 - (m0 / m5 - 1) * 100
        rel20 = r20 - (m0 / m20 - 1) * 100
        # 短線輪動優先：當日20%、5日50%、20日30%，避免舊漲幅掩蓋轉弱。
        strength = max(0, min(100, 50 + rel1 * 2 + rel5 * 5 + rel20))
        if rel5 > 0 >= rel20:
            state = "轉強"
        elif rel5 < 0 <= rel20:
            state = "轉弱"
        elif strength >= 60:
            state = "強勢"
        elif strength < 40:
            state = "弱勢"
        else:
            state = "中性"
        results.append({
            "sector": name, "date": latest["date"],
            "daily_return_pct": round(latest["daily_return_pct"], 2),
            "return_5d_pct": round(r5, 2), "return_20d_pct": round(r20, 2),
            "relative_5d_pct": round(rel5, 2),
            "relative_20d_pct": round(rel20, 2),
            "relative_daily_pct": round(rel1, 2),
            "strength": round(strength, 1), "state": state,
        })
    results.sort(key=lambda item: item["strength"], reverse=True)
    return {"date": results[0]["date"] if results else None,
            "sectors": results, "count": len(results)}


class Handler(SimpleHTTPRequestHandler):
    csv_path = ROOT / "market.csv"

    def end_headers(self) -> None:
        # 開發中的儀表板不快取 HTML/JS/CSS，避免程式更新後仍顯示舊欄位。
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        request_path = urlparse(self.path).path
        if request_path == "/healthz":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if request_path == "/api/dashboard":
            try:
                body = json.dumps(dashboard_data(self.csv_path), ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return
        if request_path == "/api/sectors":
            try:
                body = json.dumps(sector_data(ROOT / "sectors.csv", self.csv_path),
                                  ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return
        if request_path in ("", "/"):
            self.path = "/dashboard/index.html"
        super().do_GET()

    def translate_path(self, path: str) -> str:
        relative = urlparse(path).path.lstrip("/")
        return str(ROOT / relative)

    def log_message(self, format: str, *args: object) -> None:
        print(f"[dashboard] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path,
                        default=Path(os.environ.get("CSV_PATH", str(ROOT / "market.csv"))))
    # 公開雲端平台必須監聽所有介面；本機仍可用 --host 127.0.0.1 覆蓋。
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=env_int("PORT", 8000))
    parser.add_argument("--auto-refresh-minutes", type=int,
                        default=env_int("AUTO_REFRESH_MINUTES", 0),
                        help="背景更新證交所資料的間隔；0 表示關閉")
    parser.add_argument("--refresh-months", type=int,
                        default=env_int("TWSE_REFRESH_MONTHS", 8))
    parser.add_argument("--refresh-limit", type=int,
                        default=env_int("TWSE_REFRESH_LIMIT", 140))
    parser.add_argument("--refresh-delay", type=float,
                        default=env_float("TWSE_REQUEST_DELAY", .25))
    args = parser.parse_args()
    if args.port < 1 or args.auto_refresh_minutes < 0 or args.refresh_months < 1 \
            or args.refresh_limit < 120 or args.refresh_delay < 0:
        parser.error("PORT 須 > 0、更新週期須 >= 0、月份須 >= 1、筆數須 >= 120、延遲須 >= 0")
    Handler.csv_path = args.csv.resolve()
    if args.auto_refresh_minutes > 0:
        def refresh_loop() -> None:
            while True:
                try:
                    print("[refresh] 開始更新證交所資料")
                    scrape(Handler.csv_path, months=args.refresh_months,
                           end=__import__("datetime").date.today(),
                           delay=args.refresh_delay, limit=args.refresh_limit)
                    scrape_sectors(Handler.csv_path, ROOT / "sectors.csv", 45,
                                   args.refresh_delay)
                    print("[refresh] 資料更新完成")
                except Exception as exc:
                    print(f"[refresh] 更新失敗：{exc}")
                threading.Event().wait(args.auto_refresh_minutes * 60)
        threading.Thread(target=refresh_loop, daemon=True, name="twse-refresh").start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"儀表板：http://{args.host}:{args.port}")
    print(f"資料：{Handler.csv_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
