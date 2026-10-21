import unittest
from unittest.mock import patch

from reconciliation.models import InputError
from reconciliation.validation import load_csv
from tests.helpers import csv_bytes, row


class ValidationTests(unittest.TestCase):
    def load(self, rows):
        return load_csv(csv_bytes(rows), "internal", "test.csv")

    def test_normalization_retains_leading_zero_and_raw_values(self):
        record = self.load([row(" 0001 ", " 0.10 ", " gbp ")])[0]
        self.assertEqual((record.transaction_id, record.currency, record.amount_minor), ("0001", "GBP", 10))
        self.assertEqual(record.raw["transaction_id"], " 0001 ")
        self.assertTrue(record.valid)

    def test_invalid_amounts_are_never_rounded(self):
        for amount in ("0", "-1", "1.001", "NaN", "Infinity", "1e2", "1,000", "+1", "1000000000", "１２"):
            with self.subTest(amount=amount):
                record = self.load([row(amount=amount)])[0]
                self.assertIsNone(record.amount_minor)
                self.assertIn("invalid_amount", [code for code, _ in record.issues])

    def test_maximum_amount_is_exact(self):
        self.assertEqual(self.load([row(amount="999999999.99")])[0].amount_minor, 99999999999)

    def test_date_validation_including_leap_years(self):
        for day in ("2026-02-29", "2026-02-30", "2026-9-01", "01/09/2026", "0000-01-01"):
            with self.subTest(day=day):
                self.assertFalse(self.load([row(day=day)])[0].valid)
        self.assertTrue(self.load([row(day="2024-02-29")])[0].valid)

    def test_all_missing_fields_are_reported(self):
        record = self.load([["", "", "", ""]])[0]
        self.assertEqual(len(record.issues), 4)
        self.assertIsNone(record.key)

    def test_duplicate_marks_all_occurrences_even_if_invalid(self):
        records = self.load([row(), row(amount="bad")])
        self.assertTrue(all("duplicate_key" in [code for code, _ in r.issues] for r in records))

    def test_id_case_and_currency_distinguish_keys(self):
        records = self.load([row("abc"), row("ABC"), row("abc", currency="EUR")])
        self.assertTrue(all(r.valid for r in records))

    def test_invalid_currency_is_reported(self):
        self.assertFalse(self.load([row(currency="JPY")])[0].valid)

    def test_invalid_id_length_and_controls(self):
        for tid in ("a" * 129, "a\nb"):
            with self.subTest(tid=tid):
                self.assertFalse(self.load([row(tid)])[0].valid)

    def test_empty_and_header_only_files_fail(self):
        for content in (b"", b"\n", csv_bytes([])):
            with self.subTest(content=content), self.assertRaises(InputError):
                load_csv(content, "internal", "empty.csv")

    def test_missing_and_duplicate_headers_fail(self):
        for header in (["transaction_id"], ["transaction_id", "transaction_id", "amount", "currency"]):
            with self.subTest(header=header), self.assertRaises(InputError):
                load_csv(csv_bytes([], header), "internal", "header.csv")

    def test_wrong_column_count_fails_entire_file(self):
        with self.assertRaises(InputError):
            self.load([row(), ["short", "row"]])

    def test_unclosed_quote_fails(self):
        with self.assertRaises(InputError):
            load_csv(b'transaction_id,transaction_date,amount,currency\n"abc,2026-09-01,1,GBP', "internal", "broken.csv")

    def test_encoding_and_null_bytes_fail(self):
        for content in (b"\xff\xfe", b"\x00bad"):
            with self.subTest(content=content), self.assertRaises(InputError):
                load_csv(content, "internal", "bad.csv")

    def test_size_and_row_limits(self):
        with patch("reconciliation.validation.MAX_FILE_BYTES", 1), self.assertRaises(InputError):
            self.load([row()])
        with patch("reconciliation.validation.MAX_ROWS", 1), self.assertRaises(InputError):
            self.load([row(), row("002")])

    def test_blank_physical_lines_keep_original_row_numbers(self):
        content = b"transaction_id,transaction_date,amount,currency\n\n001,2026-09-01,1,GBP\n"
        self.assertEqual(load_csv(content, "internal", "line.csv")[0].row_number, 3)

    def test_extra_columns_preserved(self):
        content = csv_bytes([row() + ["memo"]], ["transaction_id", "transaction_date", "amount", "currency", "note"])
        record = load_csv(content, "internal", "extra.csv")[0]
        self.assertEqual(record.raw["note"], "memo")
        self.assertTrue(record.valid)
