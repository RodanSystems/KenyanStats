import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_knbs import parse_explorer, update_data

GOOD = '''<html><body><h1>Kenya Consumer Price Index</h1>
Current CPI 156.47 September 2026 Inflation (MoM): 0.4%
Inflation (YoY) 6.76% September 2026 Previous Month: 6.59%
Inflation (MoM) 0.4% September 2026</body></html>'''

class ExplorerTests(unittest.TestCase):
    def test_extract_precise_yoy_and_month(self):
        o = parse_explorer(GOOD)
        self.assertEqual(o['period'], '2026-09')
        self.assertEqual(o['annual_inflation_pct'], 6.8)
    def test_existing_verified_report_is_preserved(self):
        old = {'history': [{'period': '2026-09', 'annual_inflation_pct': 6.8,
                            'report_url': 'https://www.knbs.or.ke/reports/example'}]}
        self.assertEqual(update_data(old, parse_explorer(GOOD)), old['history'])
    def test_no_yoy_value_rejected(self):
        with self.assertRaises(ValueError):
            parse_explorer(GOOD.replace('Inflation (YoY)', 'No YoY'))
    def test_mismatched_or_ambiguous_data_rejected(self):
        with self.assertRaises(ValueError):
            parse_explorer(GOOD + GOOD)
    def test_future_period_rejected(self):
        with self.assertRaises(ValueError):
            parse_explorer(GOOD.replace('6.76% September 2026', '6.76% December 2099'))
    def test_no_script_injection_content_used(self):
        with self.assertRaises(ValueError):
            parse_explorer('<script>Inflation (YoY) 6.76% September 2026</script>')

if __name__ == '__main__':
    unittest.main()
