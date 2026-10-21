import csv
import io
import unittest

from reconciliation.reporting import ISSUE_FIELDS, RESULT_FIELDS, money, to_csv_bytes


class ReportingTests(unittest.TestCase):
    def test_exact_money_formatting(self):
        for amount, expected in ((None, ""), (0, "0.00"), (1, "0.01"), (-1, "-0.01"), (99999999999, "999999999.99")):
            with self.subTest(amount=amount):
                self.assertEqual(money(amount), expected)

    def test_empty_report_keeps_headers_and_bom(self):
        content = to_csv_bytes([], RESULT_FIELDS)
        self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(next(csv.reader(io.StringIO(content.decode("utf-8-sig")))), RESULT_FIELDS)

    def test_formula_payloads_escaped_but_numeric_difference_preserved(self):
        content = to_csv_bytes([{"Transaction ID": "=1+1", "Currency": "+cmd", "Difference (internal - platform)": "-0.01"}], RESULT_FIELDS)
        result = next(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        self.assertEqual(result["Transaction ID"], "'=1+1")
        self.assertEqual(result["Currency"], "'+cmd")
        self.assertEqual(result["Difference (internal - platform)"], "-0.01")

    def test_raw_amount_formula_payload_escaped(self):
        content = to_csv_bytes([{"Original amount": "  @SUM(1,2)"}], ISSUE_FIELDS)
        result = next(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        self.assertTrue(result["Original amount"].startswith("'"))
