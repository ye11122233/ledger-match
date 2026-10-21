import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import RULE_VERSION
from .legacy_messages import english_message

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "reconciliation.sqlite3"


class Database:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.executescript(Path(__file__).with_name("schema.sql").read_text(encoding="utf-8"))

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def query(self, sql, parameters=()):
        with self.connection() as conn:
            return [dict(row) for row in conn.execute(sql, parameters)]

    def find_run(self, internal_hash, platform_hash):
        rows = self.query(
            "SELECT id FROM reconciliation_runs WHERE internal_hash=? AND platform_hash=? AND rule_version=?",
            (internal_hash, platform_hash, RULE_VERSION))
        return rows[0]["id"] if rows else None

    def save(self, internal_hash, platform_hash, internal_filename, platform_filename, records, results):
        try:
            # One transaction: history can never expose half-written results.
            with self.connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO reconciliation_runs(created_at, rule_version, internal_filename, platform_filename, "
                    "internal_hash, platform_hash, status) VALUES (?, ?, ?, ?, ?, ?, 'completed')",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"), RULE_VERSION,
                     internal_filename, platform_filename, internal_hash, platform_hash))
                run_id = cursor.lastrowid
                for record in records:
                    record_id = conn.execute(
                        "INSERT INTO source_records(run_id, source, row_number, raw_json, transaction_id, currency, "
                        "transaction_date, amount_minor, is_valid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (run_id, record.source, record.row_number, json.dumps(record.raw, ensure_ascii=False),
                         record.transaction_id, record.currency, record.transaction_date, record.amount_minor, int(record.valid))
                    ).lastrowid
                    conn.executemany("INSERT INTO validation_issues(record_id, code, message) VALUES (?, ?, ?)",
                                     [(record_id, code, message) for code, message in record.issues])
                conn.executemany(
                    "INSERT INTO reconciliation_results(run_id, transaction_id, currency, status, internal_rows, "
                    "platform_rows, internal_amount_minor, platform_amount_minor, difference_minor, reason) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [(run_id, r.transaction_id, r.currency, r.status, json.dumps(r.internal_rows),
                      json.dumps(r.platform_rows), r.internal_amount_minor, r.platform_amount_minor,
                      r.difference_minor, r.reason) for r in results])
            return run_id, False
        except sqlite3.IntegrityError:
            # Also handles two sessions importing identical input at the same time.
            existing = self.find_run(internal_hash, platform_hash)
            if existing is None:
                raise
            return existing, True

    def run(self, run_id):
        rows = self.query("SELECT * FROM reconciliation_runs WHERE id=?", (run_id,))
        if not rows:
            raise ValueError("Run not found")
        return rows[0]

    def history(self):
        return self.query("""
            SELECT b.id, b.created_at, b.internal_filename, b.platform_filename,
                   COUNT(r.id) AS total_keys,
                   SUM(CASE WHEN r.status='matched' THEN 1 ELSE 0 END) AS matched,
                   SUM(CASE WHEN r.status<>'matched' THEN 1 ELSE 0 END) AS exception_keys,
                   SUM(CASE WHEN r.status='blocked' THEN 1 ELSE 0 END) AS blocked
            FROM reconciliation_runs b LEFT JOIN reconciliation_results r ON r.run_id=b.id
            GROUP BY b.id ORDER BY b.id DESC
        """)

    def results(self, run_id, statuses=None, currency=None, search=""):
        sql = "SELECT * FROM reconciliation_results WHERE run_id=?"
        params = [run_id]
        if statuses:
            sql += " AND status IN (" + ",".join("?" for _ in statuses) + ")"
            params.extend(statuses)
        if currency:
            sql += " AND currency=?"
            params.append(currency)
        if search:
            sql += " AND instr(transaction_id, ?) > 0"
            params.append(search)
        rows = self.query(sql + " ORDER BY transaction_id, currency", params)
        for row in rows:
            row["reason"] = english_message(row["reason"])
        return rows

    def issues(self, run_id):
        rows = self.query("""
            SELECT s.source, s.row_number, s.transaction_id, s.currency, s.raw_json, i.code, i.message
            FROM validation_issues i JOIN source_records s ON s.id=i.record_id
            WHERE s.run_id=? ORDER BY s.source, s.row_number, i.id
        """, (run_id,))
        for row in rows:
            row["message"] = english_message(row["message"])
        return rows

    def records(self, run_id, transaction_id):
        return self.query("SELECT * FROM source_records WHERE run_id=? AND transaction_id=? ORDER BY source,row_number",
                          (run_id, transaction_id))

    def trace(self, transaction_id):
        return self.query("""
            SELECT r.run_id, b.created_at, r.transaction_id, r.currency, r.status, r.difference_minor
            FROM reconciliation_results r JOIN reconciliation_runs b ON b.id=r.run_id
            WHERE r.transaction_id=? ORDER BY r.run_id DESC, r.currency
        """, (transaction_id,))

    def summary(self, run_id):
        counts = {row["status"]: row["count"] for row in self.query(
            "SELECT status, COUNT(*) AS count FROM reconciliation_results WHERE run_id=? GROUP BY status", (run_id,))}
        sources = self.query("""
            SELECT source, COUNT(*) AS total, SUM(is_valid) AS valid,
                   SUM(CASE WHEN is_valid=0 THEN 1 ELSE 0 END) AS invalid
            FROM source_records WHERE run_id=? GROUP BY source ORDER BY source
        """, (run_id,))
        amounts = self.query("""
            SELECT currency,
                SUM(CASE WHEN status='amount_mismatch' THEN difference_minor ELSE 0 END) AS net_difference_minor,
                SUM(CASE WHEN status='amount_mismatch' THEN ABS(difference_minor) ELSE 0 END) AS absolute_difference_minor,
                SUM(CASE WHEN status='missing_platform' THEN internal_amount_minor ELSE 0 END) AS missing_platform_minor,
                SUM(CASE WHEN status='missing_internal' THEN platform_amount_minor ELSE 0 END) AS missing_internal_minor
            FROM reconciliation_results WHERE run_id=? AND status<>'blocked' GROUP BY currency ORDER BY currency
        """, (run_id,))
        eligible = sum(count for status, count in counts.items() if status != "blocked")
        return {"counts": counts, "sources": sources, "amounts": amounts, "eligible_keys": eligible,
                "match_rate": counts.get("matched", 0) / eligible if eligible else None,
                "exception_keys": sum(v for k, v in counts.items() if k != "matched")}
