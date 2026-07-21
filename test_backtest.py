import unittest

from backtest import future_max_drawdown, run_backtest, supervised_thresholds


class BacktestTest(unittest.TestCase):
    def test_future_max_drawdown(self):
        self.assertAlmostEqual(future_max_drawdown([100, 110, 99, 105], 0, 3), 10)

    def test_walk_forward_does_not_use_future_for_score(self):
        rows = []
        for i in range(145):
            rows.append({"date": f"2025-{(i // 28) + 1:02d}-{(i % 28) + 1:02d}",
                         "close": 100 + i / 10, "volume": 1000, "margin_balance": 10000,
                         "turnover_value": 100000, "foreign_net": 100,
                         "investment_trust_net": 50, "dealer_net": -20})
        records, report = run_backtest(rows)
        self.assertEqual(records[0]["date"], rows[119]["date"])
        self.assertEqual(report["results"]["20d"]["samples"], 6)

    def test_calibration_requires_enough_samples(self):
        self.assertIsNone(supervised_thresholds([], "mdd_20d_pct"))


if __name__ == "__main__":
    unittest.main()
