import unittest

from reconciliation.matching import reconcile
from reconciliation.validation import load_csv
from tests.helpers import csv_bytes, row


class MatchingTests(unittest.TestCase):
    def match(self, left, right):
        return reconcile(load_csv(csv_bytes(left), "internal", "i.csv"),
                         load_csv(csv_bytes(right), "platform", "p.csv"))

    def test_equivalent_decimal_formats_match(self):
        self.assertEqual(self.match([row(amount="10")], [row(amount="10.00")])[0].status, "matched")
        self.assertEqual(self.match([row(amount="0.10")], [row(amount="0.1")])[0].status, "matched")

    def test_mismatch_has_signed_exact_difference(self):
        result = self.match([row(amount="10.01")], [row(amount="10.02")])[0]
        self.assertEqual((result.status, result.difference_minor), ("amount_mismatch", -1))

    def test_both_missing_directions_have_no_fabricated_difference(self):
        results = self.match([row("a")], [row("b")])
        self.assertEqual([r.status for r in results], ["missing_platform", "missing_internal"])
        self.assertTrue(all(r.difference_minor is None for r in results))

    def test_duplicate_keys_block_without_cartesian_product(self):
        results = self.match([row(), row()], [row(), row()])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "blocked")
        self.assertEqual(results[0].internal_rows, [2, 3])
        self.assertIsNone(results[0].internal_amount_minor)

    def test_invalid_partner_is_blocked_not_missing(self):
        for bad in (row(amount="bad"), row(day="bad")):
            with self.subTest(bad=bad):
                result = self.match([bad], [row()])[0]
                self.assertEqual(result.status, "blocked")
                self.assertEqual(result.platform_rows, [2])

    def test_all_invalid_keyless_records_produce_no_matching_keys(self):
        self.assertEqual(self.match([row("")], [row("", currency="")]), [])

    def test_all_invalid_keyed_records_are_retained(self):
        results = self.match([row(amount="bad")], [row(amount="bad")])
        self.assertEqual([r.status for r in results], ["blocked"])

    def test_currency_mismatch_yields_two_missing_keys_and_hint(self):
        results = self.match([row(currency="GBP")], [row(currency="USD")])
        self.assertEqual({r.status for r in results}, {"missing_internal", "missing_platform"})
        self.assertTrue(all("other currencies" in r.reason for r in results))

    def test_dates_do_not_participate_in_match_key(self):
        self.assertEqual(self.match([row(day="2026-09-01")], [row(day="2026-09-02")])[0].status, "matched")

    def test_large_amount_preserves_cent_difference_with_missing_rows(self):
        results = self.match([row("a", "999999999.99"), row("c", "0.01")], [row("a", "999999999.98"), row("b")])
        self.assertEqual(results[0].difference_minor, 1)
