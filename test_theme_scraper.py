import unittest

from theme_scraper import THEMES, complete_themes


class FakeClient:
    def get_openapi(self, _path):
        return [
            {"公司代號": "2330", "產業別": "24"},
            {"公司代號": "1101", "產業別": "01"},
            {"公司代號": "9105", "產業別": "91"},
            {"公司代號": "12AB", "產業別": "02"},
        ]


class ThemeScraperTest(unittest.TestCase):
    def test_unmapped_stocks_are_added_to_industry_fallback(self):
        themes = complete_themes(FakeClient())
        self.assertIn("2330", themes["半導體其他"])
        self.assertIn("9105", themes["其他上市"])

    def test_curated_stock_is_not_duplicated_in_fallback(self):
        themes = complete_themes(FakeClient())
        self.assertIn("1101", THEMES["水泥"])
        self.assertNotIn("1101", themes.get("水泥其他", []))

    def test_non_numeric_security_code_is_ignored(self):
        themes = complete_themes(FakeClient())
        self.assertNotIn("12AB", {code for codes in themes.values() for code in codes})

    def test_equipment_engineering_is_a_separate_theme(self):
        themes = complete_themes(FakeClient())
        self.assertIn("2404", themes["設備工程"])
        self.assertIn("6196", themes["設備工程"])


if __name__ == "__main__":
    unittest.main()
