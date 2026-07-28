import unittest

from risk_score import calculate, classify, institutional_score, margin_maintenance_score, margin_score, margin_structure_score, technical_components, technical_score, to_risk_score, volume_components, volume_score


class RiskScoreTest(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(classify(85), "高風險")
        self.assertEqual(classify(30), "低風險")

    def test_public_risk_score_adds_ten_points(self):
        self.assertEqual(to_risk_score(100), 10)
        self.assertEqual(to_risk_score(70), 40)
        self.assertEqual(to_risk_score(0), 100)

    def test_margin_deleveraging_is_safer(self):
        safe = margin_score(-4, -4, -8, 1, 0)
        risky = margin_score(6, 7, 12, 2, 2)
        self.assertGreater(safe, risky)

    def test_margin_maintenance_affects_margin_score(self):
        healthy = margin_score(0, 0, 0, 0, 0, 190)
        stressed = margin_score(0, 0, 0, 0, 0, 135)
        self.assertGreater(healthy, stressed)
        self.assertGreater(margin_maintenance_score(180), margin_maintenance_score(140))

    def test_concentrated_margin_structure_is_riskier(self):
        diversified = margin_structure_score(22, 90, 38, 10, 3)
        concentrated = margin_structure_score(58, 480, 72, 45, 28)
        self.assertGreater(diversified, concentrated)

    def test_forced_deleveraging_is_not_scored_as_safe(self):
        rebound = margin_score(-4, -5, -8, 2, 0, 0, 4)
        selloff = margin_score(-4, -5, -8, -2, 0, 0, -8)
        self.assertGreater(rebound, selloff)

    def test_overheated_volume_is_penalized(self):
        normal = volume_score(1.0, 0.5, 0)
        hot = volume_score(1.8, 2.0, 6)
        self.assertGreater(normal, hot)

    def test_heavy_volume_selloff_is_penalized(self):
        normal = volume_score(1, .2, 0, 1, .2)
        selloff = volume_score(1.6, -3, 0, 1.6, .5)
        self.assertGreater(normal, selloff)

    def test_weak_price_low_volume_is_not_treated_as_safe(self):
        neutral = volume_score(.75, 0, 0, .95, .2)
        weak = volume_score(.75, 0, 0, .95, .2, True, -2.5)
        self.assertGreater(neutral, weak)

    def test_bullish_technical_structure_is_safer(self):
        bullish = technical_components(110, 108, 105, 100, 3, 5, -2)
        bearish = technical_components(85, 90, 95, 100, -3, -12, -18)
        self.assertGreater(sum(bullish.values()), sum(bearish.values()))

    def test_short_term_decline_penalizes_technical_safety(self):
        distances = [0.0] * 20
        stable = technical_score(98, 100, 99, 95, 1, -2, -5, distances)
        falling = technical_score(98, 100, 99, 95, 1, -2, -5, distances, -3, 3)
        self.assertGreater(stable, falling)

    def test_three_day_institutional_buying_is_safer(self):
        buy = institutional_score(6, 1, 0, 7, 3, 1)
        sell = institutional_score(-6, -1, 0, -7, -3, 1)
        self.assertGreater(buy, sell)

    def test_institutional_strength_affects_score(self):
        strong = institutional_score(1, 0, 0, 1, 1, 1, 2, 2)
        weak = institutional_score(1, 0, 0, 1, 1, 1, -2, -2)
        self.assertGreater(strong, weak)

    def test_each_institutional_reversal_affects_score(self):
        sell_to_buy = institutional_score(
            1, .5, .3, 1.8, 1, 1, 0, 0, -1, -.5, -.3)
        buy_to_sell = institutional_score(
            -1, -.5, -.3, -1.8, -1, 1, 0, 0, 1, .5, .3)
        self.assertGreater(sell_to_buy, buy_to_sell)

    def test_foreign_reversal_has_more_weight_than_dealer(self):
        foreign_turns_buy = institutional_score(
            1, 0, 0, 1, 1, 1, 0, 0, -1, 0, 0)
        dealer_turns_buy = institutional_score(
            0, 0, 1, 1, 1, 1, 0, 0, 0, 0, -1)
        self.assertGreater(foreign_turns_buy, dealer_turns_buy)

    def test_end_to_end_score(self):
        rows = []
        for day in range(120):
            rows.append({
                "date": f"2026-{day + 1:03d}", "close": 20000 + day * 5,
                "volume": 4_000_000 + day * 1_000,
                "margin_balance": 300_000_000 - day * 100_000,
                "turnover_value": 400_000_000, "foreign_net": 22_000_000,
                "investment_trust_net": 2_000_000, "dealer_net": 1_000_000,
            })
        result = calculate(rows)
        self.assertGreaterEqual(result.total, 0)
        self.assertLessEqual(result.total, 100)
        self.assertIn("ma60", result.metrics)
        self.assertIn("estimated_margin_maintenance_pct", result.metrics)
        self.assertIn("volume_ratio_5d", result.metrics)
        self.assertIn("volume_ratio_previous_day", result.metrics)
        self.assertIn("volume", result.metrics)
        self.assertIn("margin_speed_score", result.metrics)
        self.assertIn("institutional_strength_5d_z", result.metrics)
        self.assertIn("institutional_strength_20d_z", result.metrics)
        self.assertEqual(result.metrics["estimated_margin_maintenance_pct"], 0)


if __name__ == "__main__":
    unittest.main()
