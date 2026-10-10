import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from update_cbk import parse_rates


def page(date='09-10-2026', usd='129.91', gbp='172.04', eur='145.92'):
    return f'<html><body><h2>Daily KES Exchange Rates</h2><table><tr><td>US DOLLAR</td><td>{usd}</td></tr><tr><td>STG POUND</td><td>{gbp}</td></tr><tr><td>EURO</td><td>{eur}</td></tr></table><p>More...</p><p>Posted On: {date}</p></body></html>'


class CBKTests(unittest.TestCase):
    def test_valid_summary(self):
        result = parse_rates(page())
        self.assertEqual(result['date'], '2026-10-09')
        self.assertEqual(result['rates']['USD'], 129.91)

    def test_missing_currency_rejected(self):
        with self.assertRaises(ValueError):
            parse_rates(page().replace('STG POUND', 'UNKNOWN'))

    def test_invalid_rate_rejected(self):
        with self.assertRaises(ValueError):
            parse_rates(page(usd='0.00'))

    def test_no_section_rejected(self):
        with self.assertRaises(ValueError):
            parse_rates('<html>Access denied</html>')


if __name__ == '__main__':
    unittest.main()
