import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_knbs import discover_latest, parse_report, update_data

URL = 'https://www.knbs.or.ke/reports/consumer-price-indices-and-inflation-rates-september-2026/'
REPORT = '''<html><h1>Consumer Price Indices and Inflation Rates – September 2026</h1>
<h3>Overview</h3><p>Annual consumer price inflation was 6.8 per cent in September 2026,
as measured by the Consumer Price Index (CPI).</p></html>'''

class TestKNBS(unittest.TestCase):
    def test_latest_link(self):
        html = '<a href="/reports/consumer-price-indices-and-inflation-rates-august-2026/">Aug</a>' + '<a href="' + URL + '">Sep</a>'
        self.assertEqual(discover_latest(html), (2026, 9, URL))

    def test_parse_annual(self):
        row = parse_report(REPORT, 2026, 9, URL)
        self.assertEqual(row['annual_inflation_pct'], 6.8)
        self.assertEqual(row['period'], '2026-09')

    def test_wrong_heading(self):
        with self.assertRaises(ValueError):
            parse_report(REPORT.replace('September 2026</h1>', 'August 2026</h1>'), 2026, 9, URL)

    def test_no_annual_value(self):
        with self.assertRaises(ValueError):
            parse_report(REPORT.replace('6.8 per cent', 'missing'), 2026, 9, URL)

    def test_older_data_rejected(self):
        old = {'history': [{'period': '2026-09', 'annual_inflation_pct': 6.8, 'report_url': URL}]}
        with self.assertRaises(ValueError):
            update_data(old, {'period': '2026-08', 'annual_inflation_pct': 6.6, 'report_url': URL})

    def test_conflicting_data_rejected(self):
        old = {'history': [{'period': '2026-09', 'annual_inflation_pct': 6.8, 'report_url': URL}]}
        with self.assertRaises(ValueError):
            update_data(old, {'period': '2026-09', 'annual_inflation_pct': 7.0, 'report_url': URL})

    def test_add_month(self):
        old = {'history': [{'period': '2026-08', 'annual_inflation_pct': 6.6, 'report_url': URL}]}
        self.assertEqual(len(update_data(old, {'period': '2026-09', 'annual_inflation_pct': 6.8, 'report_url': URL})), 2)

if __name__ == '__main__':
    unittest.main()
