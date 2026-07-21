import unittest

from twse_scraper import NoDataError, TwseClient, institutional, margin_balance, market_margin_maintenance, market_month, roc_date


class FakeClient:
    def __init__(self, payload):
        self.payload = payload

    def get(self, path, params):
        return self.payload


class TwseScraperTest(unittest.TestCase):
    def test_roc_date(self):
        self.assertEqual(roc_date("115/07/20"), "2026-07-20")

    def test_market_month_by_field_name(self):
        payload = {"fields": ["日期", "成交股數", "成交金額", "發行量加權股價指數"],
                   "data": [["115/07/20", "1,000", "2,000", "23,456.7"]]}
        row = market_month(FakeClient(payload), __import__("datetime").date(2026, 7, 1))[0]
        self.assertEqual(row["close"], 23456.7)
        self.assertEqual(row["volume"], 1000)

    def test_margin_is_converted_from_thousand_dollars(self):
        payload = {"tables": [{"fields": ["項目", "今日餘額"],
                               "data": [["融資金額(仟元)", "569,035,788"]]}]}
        self.assertEqual(margin_balance(FakeClient(payload), "2026-07-20"), 569_035_788_000)

    def test_institutional_categories(self):
        payload = {"fields": ["單位名稱", "買賣差額"], "data": [
            ["自營商(自行買賣)", "1,000"], ["自營商(避險)", "-200"],
            ["投信", "300"], ["外資及陸資(不含外資自營商)", "2,000"],
            ["外資自營商", "999"], ["合計", "3,100"],
        ]}
        result = institutional(FakeClient(payload), "2026-07-20")
        self.assertEqual(result["dealer_net"], 800)
        self.assertEqual(result["investment_trust_net"], 300)
        self.assertEqual(result["foreign_net"], 2000)

    def test_no_data_is_a_distinct_error(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self): return b'{"stat":"no data"}'

        from unittest.mock import patch
        client = TwseClient(delay=0, retries=3)
        with patch("twse_scraper.urlopen", return_value=Response()) as mocked:
            with self.assertRaises(NoDataError):
                client.get("/test", {})
        self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    unittest.main()
