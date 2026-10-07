import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from update_data import parse_prices

HEADER="<tr><th>From</th><th>To</th><th>Town</th><th>Super Petrol</th><th>Diesel</th><th>Kerosene</th></tr>"
def row(start,end,town,price="190.50"):
    return f"<tr><td>{start}</td><td>{end}</td><td>{town}</td><td>{price}</td><td>180</td><td>170</td></tr>"
class ParserTests(unittest.TestCase):
    def test_latest_period_only(self):
        records=parse_prices("<table>"+HEADER+row("15-01-2025","14-02-2025","Old town")+row("15-02-2025","14-03-2025","Test town")+"</table>")
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["town"],"Test town")
        self.assertEqual(records[0]["valid_from"],"2025-02-15")
    def test_error_page_rejected(self):
        with self.assertRaises(ValueError):parse_prices("<html>Access denied</html>")
    def test_bad_price_rejected(self):
        with self.assertRaises(ValueError):parse_prices("<table>"+HEADER+row("15-02-2025","14-03-2025","Test","0")+"</table>")
    def test_duplicate_rejected(self):
        r=row("15-02-2025","14-03-2025","Test")
        with self.assertRaises(ValueError):parse_prices("<table>"+HEADER+r+r+"</table>")
