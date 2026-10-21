"""Streamlit interaction tests; each test uses a separate local database."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from reconciliation.database import Database
from reconciliation.models import STATUS_LABELS

ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT / "artifacts" / "test-tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.database = Database(Path(self.temp.name) / "app.sqlite3")
        self.env = patch.dict(os.environ, {"RECONCILIATION_DB": str(self.database.path)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()

    def demo(self):
        self.app.button[0].click().run()
        self.assertEqual(len(self.app.exception), 0)

    def test_initial_page_and_disabled_incomplete_upload(self):
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(self.app.button[1].disabled)
        self.assertEqual(self.database.history(), [])
        self.assertEqual(self.app.radio[0].options, ["Upload & validate", "Results", "History"])
        self.assertEqual(self.app.button[0].label, "Run demo")

    def test_demo_and_repeated_demo_reuse_history(self):
        self.demo()
        self.assertEqual(self.app.metric[0].value, "36.4%")
        self.assertEqual(self.app.metric[2].value, "11")
        self.app.radio[0].set_value("Upload & validate").run()
        self.demo()
        self.assertEqual(len(self.database.history()), 1)

    def test_filters_can_select_matching_records_and_return_empty(self):
        self.demo()
        self.app.multiselect[0].set_value([STATUS_LABELS["matched"]]).run()
        # First dataframe is source counts; second is amount summary; third is details.
        self.assertEqual(len(self.app.dataframe[2].value), 4)
        self.app.text_input(key="result_search").set_value("does-not-exist").run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertTrue(any("No records match the current filters" in info.value for info in self.app.info))

    def test_corrected_demo_reaches_full_match(self):
        self.app.selectbox[0].set_value("Corrected data").run()
        self.demo()
        self.assertEqual(self.app.metric[0].value, "100.0%")
        self.assertEqual(self.app.metric[2].value, "0")
        self.assertEqual(len(self.app.exception), 0)

    def test_history_open_and_compare(self):
        self.demo()
        self.app.radio[0].set_value("Upload & validate").run()
        self.app.selectbox[0].set_value("Corrected data").run()
        self.demo()
        self.app.radio[0].set_value("History").run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(self.app.dataframe[0].value), 2)
        self.assertEqual(len(self.app.dataframe[1].value), 5)
        self.app.button[0].click().run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.metric[0].value, "100.0%")

    def test_trace_shows_original_duplicate_rows(self):
        self.demo()
        self.app.text_input(key="trace_id").set_value("TXN005").run()
        self.assertEqual(len(self.app.json), 3)
        self.assertEqual(len(self.app.exception), 0)

    def test_old_browser_session_choices_are_reset_to_english(self):
        self.demo()
        run_id = self.app.session_state["current_run"]
        # Start without an English frontend widget tree, as at code reload.
        self.app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
        self.app.session_state["current_run"] = run_id
        self.app.session_state["page"] = "对账结果"
        self.app.session_state["status_filter"] = ["金额不一致"]
        self.app.session_state["currency_filter"] = "全部"
        self.app.run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.radio[0].value, "Results")
        self.assertEqual(self.app.metric[0].label, "Match rate")
        self.assertEqual(self.app.selectbox[0].value, "All")
        self.assertTrue(all(status in STATUS_LABELS.values() for status in self.app.multiselect[0].value))


if __name__ == "__main__":
    unittest.main()
