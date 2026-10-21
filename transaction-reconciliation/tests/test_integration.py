import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reconciliation.database import Database
from reconciliation.models import InputError
from reconciliation.reporting import ISSUE_FIELDS, RESULT_FIELDS, issue_rows, result_rows, to_csv_bytes
from reconciliation.service import process
from scripts.generate_sample_data import generate_demo, generate_large
from tests.helpers import csv_bytes, row


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / "artifacts" / "test-tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = Database(self.root / "test.sqlite3")
        generate_demo(self.root)

    def demo(self, prefix="demo"):
        return process((self.root / f"{prefix}_internal.csv").read_bytes(),
                       (self.root / f"{prefix}_platform.csv").read_bytes(),
                       f"{prefix}_internal.csv", f"{prefix}_platform.csv", self.database)

    def test_demo_matches_independent_expected_outcomes(self):
        run_id, reused = self.demo()
        expected = json.loads((self.root / "expected_results.json").read_text())["demo"]
        summary = self.database.summary(run_id)
        self.assertFalse(reused)
        self.assertEqual(summary["counts"], expected["counts"])
        self.assertEqual(summary["eligible_keys"], expected["eligible_keys"])
        self.assertAlmostEqual(summary["match_rate"], expected["match_rate"])
        for source in summary["sources"]:
            self.assertEqual(source["total"], expected[f"{source['source']}_rows"])
            self.assertEqual(source["invalid"], expected[f"{source['source']}_invalid_rows"])
        for amount in summary["amounts"]:
            if amount["currency"] in ("GBP", "EUR"):
                for key in ("net_difference_minor", "absolute_difference_minor"):
                    self.assertEqual(amount[key], expected[f"{amount['currency']}_{key}"])
        self.assertEqual(summary["exception_keys"], 11)

    def test_repeated_import_reuses_same_run_including_renamed_files(self):
        first, _ = self.demo()
        second, reused = process((self.root / "demo_internal.csv").read_bytes(),
                                 (self.root / "demo_platform.csv").read_bytes(), "renamed.csv", "renamed2.csv", self.database)
        self.assertEqual(first, second)
        self.assertTrue(reused)
        self.assertEqual(len(self.database.history()), 1)

    def test_changed_bytes_create_new_run_and_corrected_data_match(self):
        original, _ = self.demo()
        corrected, _ = self.demo("corrected")
        self.assertNotEqual(original, corrected)
        self.assertEqual(self.database.summary(corrected)["counts"], {"matched": 15})
        self.assertEqual(self.database.summary(corrected)["match_rate"], 1.0)

    def test_history_survives_new_database_connection(self):
        run_id, _ = self.demo()
        reopened = Database(self.database.path)
        self.assertEqual(reopened.history()[0]["id"], run_id)
        self.assertEqual(len(reopened.results(run_id)), 15)
        self.assertEqual(reopened.run(run_id)["status"], "completed")

    def test_results_filter_and_parameterized_search(self):
        run_id, _ = self.demo()
        self.assertEqual(len(self.database.results(run_id, ["amount_mismatch"], "GBP")), 2)
        self.assertEqual(len(self.database.results(run_id, search="TXN005")), 1)
        self.assertEqual(self.database.results(run_id, search="' OR 1=1 --"), [])
        self.assertEqual(len(self.database.results(run_id, search="%")), 0)

    def test_trace_includes_both_runs_and_raw_rows(self):
        before, _ = self.demo()
        after, _ = self.demo("corrected")
        self.assertEqual({r["run_id"] for r in self.database.trace("TXN005")}, {before, after})
        records = self.database.records(before, "TXN005")
        self.assertEqual(len(records), 3)
        self.assertEqual(json.loads(records[0]["raw_json"])["amount"], "50")

    def test_invalid_file_does_not_create_partial_history(self):
        with self.assertRaises(InputError):
            process(csv_bytes([row()]), b"bad\n", "i.csv", "p.csv", self.database)
        self.assertEqual(self.database.history(), [])

    def test_database_failure_rolls_back_entire_run(self):
        with self.database.connection() as conn:
            conn.execute("CREATE TRIGGER reject_result BEFORE INSERT ON reconciliation_results BEGIN SELECT RAISE(ABORT, 'forced failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.demo()
        for table in ("reconciliation_runs", "source_records", "validation_issues", "reconciliation_results"):
            self.assertEqual(self.database.query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"], 0)

    def test_all_keyless_invalid_rows_have_undefined_rate(self):
        content = csv_bytes([row("", currency="")])
        run_id, _ = process(content, content, "i.csv", "p.csv", self.database)
        summary = self.database.summary(run_id)
        self.assertIsNone(summary["match_rate"])
        self.assertEqual(summary["counts"], {})
        self.assertEqual(len(self.database.issues(run_id)), 4)

    def test_rule_version_change_does_not_reuse_old_run(self):
        first, _ = self.demo()
        with patch("reconciliation.database.RULE_VERSION", "future-test"):
            second, reused = self.demo()
        self.assertNotEqual(first, second)
        self.assertFalse(reused)

    def test_second_save_with_same_hashes_reuses_committed_run(self):
        run_id, _ = self.demo()
        run = self.database.run(run_id)
        saved, reused = self.database.save(run["internal_hash"], run["platform_hash"], "i.csv", "p.csv", [], [])
        self.assertEqual(saved, run_id)
        self.assertTrue(reused)

    def test_generated_large_data_matches_independent_counts(self):
        generate_large(self.root, 1000)
        expected = json.loads((self.root / "large_expected.json").read_text())
        run_id, _ = process((self.root / "large_internal.csv").read_bytes(),
                            (self.root / "large_platform.csv").read_bytes(), "i.csv", "p.csv", self.database)
        counts = self.database.summary(run_id)["counts"]
        self.assertEqual({k: counts.get(k, 0) for k in expected["counts"]}, expected["counts"])

    def test_english_reports_include_english_headers_statuses_and_reasons(self):
        run_id, _ = self.demo()
        result_report = to_csv_bytes(result_rows(self.database.results(run_id)), RESULT_FIELDS).decode("utf-8-sig")
        validation_report = to_csv_bytes(issue_rows(self.database.issues(run_id), self.database.run(run_id)), ISSUE_FIELDS).decode("utf-8-sig")
        self.assertIn("Transaction ID,Currency,Status", result_report)
        self.assertIn("Blocked by data issues", result_report)
        self.assertIn("Issue code,Reason", validation_report)
        self.assertIn("Amount must be positive", validation_report)
        self.assertFalse(any("\u4e00" <= char <= "\u9fff" for char in result_report + validation_report))

    def test_legacy_messages_render_in_english_without_modifying_stored_evidence(self):
        run_id, _ = self.demo()
        old_reason = "同一来源的交易编号和币种重复；该键全部记录隔离；amount 不能为空"
        old_issue = "金额须大于 0、最多两位小数且不超过 999999999.99"
        with self.database.connection() as conn:
            conn.execute("UPDATE reconciliation_results SET reason=? WHERE run_id=? AND transaction_id='TXN005'", (old_reason, run_id))
            conn.execute("UPDATE validation_issues SET message=? WHERE code='invalid_amount'", (old_issue,))
        reason = self.database.results(run_id, search="TXN005")[0]["reason"]
        self.assertIn("Duplicate transaction ID", reason)
        self.assertIn("amount is required", reason)
        self.assertTrue(all(issue["message"].startswith("Amount must be positive") for issue in self.database.issues(run_id) if issue["code"] == "invalid_amount"))
        stored = self.database.query("SELECT reason FROM reconciliation_results WHERE run_id=? AND transaction_id='TXN005'", (run_id,))[0]["reason"]
        self.assertEqual(stored, old_reason)
