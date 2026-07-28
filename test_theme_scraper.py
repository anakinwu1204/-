import unittest

from theme_scraper import THEMES, complete_themes, parse_tpex_stock_day


class FakeClient:
    def get_openapi(self, _path):
        return [
            {"公司代號": "2330", "產業別": "24"},
            {"公司代號": "2302", "產業別": "24"},
            {"公司代號": "1101", "產業別": "01"},
            {"公司代號": "9105", "產業別": "91"},
            {"公司代號": "12AB", "產業別": "02"},
        ]

    def get_tpex_profiles(self):
        return []


class ThemeScraperTest(unittest.TestCase):
    def test_unmapped_stocks_are_added_to_industry_fallback(self):
        themes = complete_themes(FakeClient())
        self.assertIn("2302", themes["半導體其他"])
        self.assertIn("9105", themes["其他上市櫃"])

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

    def test_electronics_are_split_by_primary_theme(self):
        themes = complete_themes(FakeClient())
        self.assertNotIn("2308", themes["機器人"])
        self.assertIn("2308", themes["電源供應"])
        self.assertIn("3665", themes["機器人"])
        self.assertIn("2368", themes["PCB"])
        self.assertIn("2375", themes["被動元件"])

    def test_non_electronics_are_split_into_subthemes(self):
        themes = complete_themes(FakeClient())
        self.assertIn("2330", themes["晶圓代工"])
        self.assertIn("6446", themes["生物新藥"])
        self.assertIn("9958", themes["鋼構工程"])
        self.assertIn("2607", themes["物流港口"])
        self.assertIn("1436", themes["建設開發"])

    def test_glass_quartz_and_ccl_subthemes(self):
        themes = complete_themes(FakeClient())
        self.assertIn("2484", themes["石英元件"])
        self.assertIn("3016", themes["矽晶圓"])
        self.assertIn("1802", themes["玻纖布"])
        self.assertIn("2409", themes["TGV玻璃基板"])
        self.assertIn("6274", themes["CCL銅箔基板"])
        self.assertIn("3081", themes["光通訊"])

    def test_tpex_daily_price_parser(self):
        payload = {"tables": [{"fields": ["代號", "名稱", "收盤 "],
                               "data": [["6274", "台燿", "1,355.00"],
                                        ["6488", "環球晶", "---"]]}]}
        result = parse_tpex_stock_day(payload, {"6274", "6488"})
        self.assertEqual(result["6274"]["close"], 1355.0)
        self.assertNotIn("6488", result)

    def test_cross_industry_technology_themes_are_curated(self):
        themes = complete_themes(FakeClient())
        self.assertIn("3163", themes["光通訊"])
        self.assertIn("3221", themes["石英元件"])
        self.assertIn("3260", themes["記憶體"])
        self.assertIn("5439", themes["PCB"])
        self.assertIn("3357", themes["被動元件"])
        self.assertIn("3689", themes["連接器線材"])
        self.assertNotIn("3130", themes["電子檢測"])
        self.assertIn("5274", themes["IC設計"])
        self.assertIn("6147", themes["封裝測試"])
        self.assertIn("3105", themes["化合物半導體"])

    def test_all_tpex_companies_are_added_to_industry_fallback(self):
        class Client(FakeClient):
            def get_tpex_profiles(self):
                return [{"SecuritiesCompanyCode": "4123",
                         "SecuritiesIndustryCode": "22"},
                        {"SecuritiesCompanyCode": "1299",
                         "SecuritiesIndustryCode": "33"}]

        themes = complete_themes(Client())
        self.assertIn("4123", themes["生技醫療其他"])
        self.assertIn("1299", themes["農業科技其他"])


if __name__ == "__main__":
    unittest.main()
