#!/usr/bin/env python3
"""台股風險儀表板本機伺服器。"""

from __future__ import annotations

import argparse
import json
import os
import threading
from dataclasses import asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from statistics import fmean
from urllib.parse import urlparse

from risk_score import calculate, load_csv
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
            "volume": float(row["volume"]),
        })
    latest_row = rows[-1]
    institutions = {
        key: float(latest_row[key]) for key in
        ("foreign_net", "investment_trust_net", "dealer_net")
    }
    return {"latest": asdict(latest), "series": series, "institutions": institutions,
            "row_count": len(rows), "source": csv_path.name}


class Handler(SimpleHTTPRequestHandler):
    csv_path = ROOT / "market.csv"

    def end_headers(self) -> None:
        # 開發中的儀表板不快取 HTML/JS/CSS，避免程式更新後仍顯示舊欄位。
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/healthz":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if urlparse(self.path).path == "/api/dashboard":
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
        if self.path == "/":
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
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
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
