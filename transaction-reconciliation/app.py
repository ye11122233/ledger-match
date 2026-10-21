"""Run with: python -m streamlit run app.py"""
import json
import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from reconciliation import RULE_VERSION
from reconciliation.database import DEFAULT_DB, Database
from reconciliation.models import CURRENCIES, SOURCE_LABELS, STATUS_LABELS, InputError
from reconciliation.reporting import ISSUE_FIELDS, RESULT_FIELDS, issue_rows, money, result_rows, to_csv_bytes
from reconciliation.service import process
from reconciliation.validation import load_csv

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="LedgerMatch · Transaction Reconciliation", page_icon="↔", layout="wide")
st.markdown("""<style>
    .block-container {max-width: 1260px; padding-top: 2.4rem; padding-bottom: 3rem;}
    .eyebrow {font-size:.78rem; font-weight:700; letter-spacing:.16em; color:#18715c; margin-bottom:12px;}
    .hero {font-size:2.25rem; font-weight:750; letter-spacing:-.04em; line-height:1.25; margin:0 0 12px;}
    .intro {color:#64746e; font-size:1rem; margin-bottom:28px; line-height:1.7;}
    [data-testid="stMetric"] {border:1px solid #dde7e1; padding:18px 20px; border-radius:12px; background:#fff;}
    [data-testid="stMetricLabel"] {color:#5a6c63;}
    [data-testid="stSidebar"] {border-right:1px solid #dce5df;}
</style>""", unsafe_allow_html=True)


def db():
    return Database(os.environ.get("RECONCILIATION_DB", str(DEFAULT_DB)))


def open_run(run_id):
    st.session_state.current_run = run_id
    st.session_state.next_page = "Results"
    st.rerun()


def submit(left, right, left_name, right_name):
    try:
        with st.spinner("Validating, reconciling and saving results..."):
            run_id, reused = process(left, right, left_name, right_name, db())
        st.session_state.notice = "Identical files detected. Showing the existing run." if reused else "Reconciliation complete. Results and source records have been saved."
        open_run(run_id)
    except InputError as exc:
        st.error(str(exc))
    except sqlite3.Error:
        st.error("The database is unavailable. Check that the data directory is writable, or try again later.")


def hero(eyebrow, title, description):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div><div class="hero">{title}</div><div class="intro">{description}</div>',
                unsafe_allow_html=True)


def upload_page():
    hero("01 / IMPORT & VALIDATE", "Two sources. Every difference accounted for.", "Upload internal and payment-platform records for the same period to validate transactions, reconcile amounts and trace exceptions.")
    with st.container(border=True):
        st.subheader("Try a complete reconciliation")
        st.write("Explore amount mismatches, duplicates, missing transactions and invalid data, then compare the corrected results.")
        c1, c2 = st.columns([3, 1])
        scenario = c1.selectbox("Demo dataset", ["Data with exceptions", "Corrected data"], label_visibility="collapsed")
        if c2.button("Run demo", type="primary", width="stretch"):
            prefix = "demo" if scenario == "Data with exceptions" else "corrected"
            left = ROOT / "sample_data" / f"{prefix}_internal.csv"
            right = ROOT / "sample_data" / f"{prefix}_platform.csv"
            submit(left.read_bytes(), right.read_bytes(), left.name, right.name)
    st.subheader("Upload your CSV files")
    st.caption("UTF-8 CSV · Up to 10 MB / 100,000 records per file · GBP, EUR and USD")
    left_col, right_col = st.columns(2)
    left_file = left_col.file_uploader("Internal transaction records", type=["csv"], key="internal_upload")
    right_file = right_col.file_uploader("Payment-platform records", type=["csv"], key="platform_upload")
    with st.expander("Required fields and reconciliation rules", expanded=False):
        st.dataframe(pd.DataFrame([
            {"Field": "transaction_id", "Example": "000123", "Requirement": "Required; treated as case-sensitive text; leading zeros preserved"},
            {"Field": "transaction_date", "Example": "2026-09-01", "Requirement": "A valid YYYY-MM-DD calendar date"},
            {"Field": "amount", "Example": "125.50", "Requirement": "Positive; up to two decimal places; maximum 999999999.99"},
            {"Field": "currency", "Example": "GBP", "Requirement": "GBP / EUR / USD; normalized to uppercase"},
        ]), hide_index=True, width="stretch")
        st.write("Match on transaction ID and currency, then compare gross amounts. Both files must cover the same period and transaction scope. Dates are validated but are not matching keys.")
        st.write("Keys with duplicates or validation failures are blocked. Records without an ID or currency appear in the validation report. Refunds, fees, FX conversion and settlement timing are outside this version's scope.")
        st.write("Missing columns, malformed rows or empty files reject the import. Row-level validation failures allow other records to proceed. Identical imports are identified by file content and rule version.")
    if left_file is not None and right_file is not None:
        if st.button("Preview and validate", width="stretch"):
            for file, source in ((left_file, "internal"), (right_file, "platform")):
                try:
                    records = load_csv(file.getvalue(), source, file.name)
                    invalid = sum(not r.valid for r in records)
                    st.write(f"**{SOURCE_LABELS[source]}** · {len(records)} records · {invalid} failed validation")
                    st.dataframe(pd.DataFrame([r.raw for r in records[:8]]), hide_index=True, width="stretch")
                    if invalid:
                        st.warning("Data issues found. Run reconciliation to download the complete validation report.")
                except InputError as exc:
                    st.error(str(exc))
    if st.button("Reconcile and save", type="primary", disabled=left_file is None or right_file is None):
        submit(left_file.getvalue(), right_file.getvalue(), left_file.name, right_file.name)
    st.caption("Download sample files:")
    c1, c2 = st.columns(2)
    for col, source in ((c1, "internal"), (c2, "platform")):
        sample = ROOT / "sample_data" / f"demo_{source}.csv"
        col.download_button(f"Download {SOURCE_LABELS[source]} sample", sample.read_bytes(), sample.name, "text/csv")


def result_page():
    hero("02 / RECONCILIATION", "Find the difference. Trace the cause.", "Review amounts by currency, filter exceptions and trace each issue to its source records.")
    database = db()
    run_id = st.session_state.get("current_run")
    if run_id is None:
        st.info("No run selected. Upload files, run a demo, or open a previous run from History.")
        return
    try:
        run = database.run(run_id)
    except ValueError:
        st.warning("This run is no longer available. Choose another run from History.")
        return
    st.caption(f"Run #{run_id:04d} · {run['created_at']} · Rules v{run['rule_version']}")
    st.write(f"Internal file: {run['internal_filename']} | Platform file: {run['platform_filename']}")
    if notice := st.session_state.pop("notice", None):
        st.success(notice)
    summary = database.summary(run_id)
    counts = summary["counts"]
    c1, c2, c3, c4 = st.columns(4)
    rate = summary["match_rate"]
    c1.metric("Match rate", "N/A" if rate is None else f"{rate:.1%}")
    c2.metric("Matched keys", counts.get("matched", 0))
    c3.metric("Exception keys", summary["exception_keys"])
    c4.metric("Blocked keys", counts.get("blocked", 0))
    st.caption(f"Match rate = matched keys / union of eligible unique keys ({summary['eligible_keys']} in this run). Blocked keys and records without identifiable keys are excluded. Exception keys include blocked keys. Failed validation counts source rows; do not add these counts together. Summary metrics are independent of the detail filters.")
    overview = [{"Source": SOURCE_LABELS[s["source"]], "Uploaded records": s["total"], "Valid": s["valid"], "Failed validation (incl. duplicates)": s["invalid"]}
                for s in summary["sources"]]
    st.dataframe(pd.DataFrame(overview), hide_index=True, width="stretch")
    c1, c2 = st.columns([1, 1.7])
    with c1:
        st.subheader("Result breakdown")
        if counts:
            chart = pd.DataFrame([{"Result": STATUS_LABELS[k], "Transaction keys": v} for k, v in counts.items()])
            st.bar_chart(chart.set_index("Result"), color="#18715c", horizontal=True)
        else:
            st.info("No identifiable transaction keys. Check the validation issues.")
    with c2:
        st.subheader("Amount differences by currency")
        amounts = [{"Currency": r["currency"], "Net difference": money(r["net_difference_minor"]),
                    "Absolute difference": money(r["absolute_difference_minor"]),
                    "Missing from platform": money(r["missing_platform_minor"]),
                    "Missing from internal": money(r["missing_internal_minor"])} for r in summary["amounts"]]
        if amounts:
            st.dataframe(pd.DataFrame(amounts), hide_index=True, width="stretch")
        else:
            st.info("No eligible amounts to summarize in this run.")
        st.caption("Difference = internal amount minus platform amount. Net and absolute differences include two-sided amount mismatches only. Missing-side amounts are separate. Blocked keys are excluded.")
    st.divider()
    details_tab, issues_tab, trace_tab = st.tabs(["Reconciliation details", "Validation issues", "Trace source records"])
    with details_tab:
        c1, c2, c3 = st.columns([2, 1, 2])
        labels = {label: status for status, label in STATUS_LABELS.items()}
        statuses = c1.multiselect("Result type", list(labels), default=[v for k, v in STATUS_LABELS.items() if k != "matched"], key="status_filter")
        currency = c2.selectbox("Currency", ["All", *CURRENCIES], key="currency_filter")
        search = c3.text_input("Transaction ID contains", placeholder="e.g. TXN002", key="result_search")
        selected_statuses = [labels[s] for s in statuses]
        # Empty status selection deliberately means no rows, not all rows.
        rows = result_rows(database.results(run_id, selected_statuses, None if currency == "All" else currency, search)) if statuses else []
        st.caption(f"Current filter: {len(rows)} transaction keys. Showing up to 1,000 rows; downloads include all filtered results.")
        if rows:
            st.dataframe(pd.DataFrame(rows[:1000]), hide_index=True, width="stretch")
        else:
            st.info("No records match the current filters.")
        st.download_button("Download filtered details", to_csv_bytes(rows, RESULT_FIELDS), f"run_{run_id}_filtered.csv", "text/csv")
        exceptions = database.results(run_id, [s for s in STATUS_LABELS if s != "matched"])
        st.download_button("Download all exceptions", to_csv_bytes(result_rows(exceptions), RESULT_FIELDS), f"run_{run_id}_exceptions.csv", "text/csv")
    with issues_tab:
        problems = issue_rows(database.issues(run_id), run)
        st.caption("A record may have more than one issue. Each issue appears separately, including records with a missing ID or currency.")
        if problems:
            st.dataframe(pd.DataFrame(problems[:1000]), hide_index=True, width="stretch")
        else:
            st.success("All records passed validation.")
        st.download_button("Download validation issues", to_csv_bytes(problems, ISSUE_FIELDS), f"run_{run_id}_validation.csv", "text/csv")
    with trace_tab:
        tid = st.text_input("Enter an exact transaction ID", key="trace_id", placeholder="e.g. TXN005")
        if tid:
            records = database.records(run_id, tid.strip())
            if not records:
                st.info("No source records found for this transaction ID in the current run.")
            for record in records:
                st.write(f"**{SOURCE_LABELS[record['source']]} · Source row {record['row_number']}** · {'Valid' if record['is_valid'] else 'Invalid'}")
                st.json(json.loads(record["raw_json"]), expanded=True)
            st.write("**Reconciliation history for this transaction**")
            history = database.trace(tid.strip())
            if history:
                st.dataframe(pd.DataFrame([{"Run": h["run_id"], "Time (UTC)": h["created_at"], "Currency": h["currency"],
                                            "Result": STATUS_LABELS[h["status"]], "Difference": money(h["difference_minor"])} for h in history]),
                             hide_index=True, width="stretch")


def history_page():
    hero("03 / HISTORY", "Every reconciliation, on record.", "Revisit results, compare exceptions before and after corrections, and track transaction changes.")
    database = db()
    runs = database.history()
    if not runs:
        st.info("No saved runs yet. Complete a reconciliation to save results locally.")
        return
    st.dataframe(pd.DataFrame([{"Run": r["id"], "Processed at (UTC)": r["created_at"], "Internal file": r["internal_filename"],
                                "Platform file": r["platform_filename"], "Matched keys": r["matched"], "Exception keys": r["exception_keys"],
                                "Blocked keys": r["blocked"]} for r in runs]), hide_index=True, width="stretch")
    options = {r["id"]: f"#{r['id']:04d} · {r['created_at']} · {r['internal_filename']}" for r in runs}
    chosen = st.selectbox("Select a run", list(options), format_func=options.get)
    if st.button("Open run", type="primary"):
        open_run(chosen)
    if len(runs) > 1:
        with st.expander("Compare two runs", expanded=True):
            c1, c2 = st.columns(2)
            before = c1.selectbox("Before / baseline run", list(options), index=1, format_func=options.get)
            after = c2.selectbox("After / comparison run", list(options), format_func=options.get)
            a, b = database.summary(before), database.summary(after)
            comparison = [{"Metric": label, f"Run #{before}": a["counts"].get(status, 0),
                           f"Run #{after}": b["counts"].get(status, 0)} for status, label in STATUS_LABELS.items()]
            if before != after:
                st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")
            st.caption("This comparison shows counts. Runs may cover different transaction scopes; review the input files before interpreting changes.")


if "next_page" in st.session_state:
    st.session_state.page = st.session_state.pop("next_page")
# Existing browser sessions may still contain widget choices from the old build.
if st.session_state.get("page") not in (None, "Upload & validate", "Results", "History"):
    st.session_state.page = "Results" if st.session_state.get("current_run") else "Upload & validate"
if "status_filter" in st.session_state and any(
    value not in STATUS_LABELS.values() for value in st.session_state.status_filter
):
    del st.session_state["status_filter"]
if st.session_state.get("currency_filter") not in (None, "All", *CURRENCIES):
    del st.session_state["currency_filter"]
if any("\u4e00" <= char <= "\u9fff" for char in st.session_state.get("notice", "")):
    del st.session_state["notice"]
with st.sidebar:
    st.markdown("## ↔ LedgerMatch")
    st.caption("Transaction reconciliation and exception reporting")
    st.divider()
    page = st.radio("Workspace", ["Upload & validate", "Results", "History"], key="page")
    st.divider()
    st.caption("Local processing · SQLite history")
    st.caption(f"Rules v{RULE_VERSION} · Portfolio project")
    st.caption("Match key: transaction ID + currency\n\nPrecision: integer cents\n\nTimestamps: UTC")

try:
    {"Upload & validate": upload_page, "Results": result_page, "History": history_page}[page]()
except sqlite3.Error:
    st.error("Cannot read the local database. Check that the data directory is writable and restart the application.")
