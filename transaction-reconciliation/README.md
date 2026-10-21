# LedgerMatch — Transaction Reconciliation & Exception Reporting

A local Python application that compares internal transaction exports with payment-platform CSV records, identifies exceptions, and preserves an auditable processing history. Built as a portfolio project using **synthetic data**.

**Stack:** Python 3.12+, pandas, SQLite, Streamlit, unittest. The interface, validation messages, exported reports and demonstration guide are in English.

## Quick start

On the prepared Windows workspace, double-click **`start.cmd`**. The project environment is already installed. If the app is already running, open **http://127.0.0.1:8501** instead.

For a fresh checkout:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
```

`requirements.lock.txt` additionally pins the full resolved dependency set from the verified environment. Use `pip install -r requirements.lock.txt` when reproducing that exact set.

Select **Run demo** to process the bundled exception fixture. Choose **Corrected data** next, then compare both runs in **History**. No external services or credentials are needed. The server binds to the local loopback interface.

## Features

- Strict UTF-8 CSV validation: required columns, blank values, duplicate transaction keys, invalid dates, currencies and amounts.
- pandas outer join on `(transaction_id, currency)` with one-to-one merge validation.
- Matched, amount mismatch, missing internal, missing platform, and blocked classifications.
- Integer-cent arithmetic, per-currency signed and absolute differences, and separate missing-side amounts.
- Filters, downloadable exception and validation reports, original-row inspection, historical transaction lookup and batch comparison.
- SQLite transactions, parameterized queries and content-hash duplicate import detection.
- Independent expected results for both hand-authored fixtures and generated synthetic datasets.

## Input contract and rules

```csv
transaction_id,transaction_date,amount,currency
000123,2026-09-01,125.50,GBP
```

| Field | Rule |
|---|---|
| `transaction_id` | Required; text; preserves leading zeros; case-sensitive; max 128 characters; no control characters |
| `transaction_date` | Valid `YYYY-MM-DD` calendar date |
| `amount` | Positive decimal, at most two decimal places, max `999999999.99`; scientific notation and thousands separators rejected |
| `currency` | GBP, EUR or USD; normalized to uppercase |

Leading/trailing whitespace is removed for validation and matching; original fields are also preserved. Additional columns are retained in raw records. Each file is limited to 10 MiB and 100,000 source records.

The inputs must cover the same reporting period and the same definition of **completed gross transaction amounts**. Dates are validated but are not matching keys. Refunds, fees, FX conversion, settlement timing and timezone conversion are outside this version's scope.

Missing columns, duplicate column names, malformed CSV, wrong row widths, unsupported encoding and empty/header-only files reject the **entire import**. A row-level validation problem isolates that record and allows other records to proceed. Blank physical lines are ignored while preserving original physical line references.

Duplicate `(transaction_id, currency)` keys within either source isolate **all** occurrences. A key that has any invalid row on either side is **blocked** on both sides, preventing false missing-side exceptions and many-to-many joins. A record without an identifiable key appears only in the validation report; it cannot be reliably linked to a potential counterpart. Different currencies on the same ID produce separate missing-side exceptions with a currency hint.

## Metric definitions

- **Match rate:** matched unique keys / union of eligible unique keys. Blocked keys and records without identifiable keys are excluded. Zero eligible keys displays “not applicable”.
- **Exception keys:** mismatches + both missing-side categories + blocked keys. This is a key count, not a source-row count.
- **Validation failures:** original source rows with one or more problems; duplicate rows count as failures. One row can generate multiple validation issue entries.
- **Signed difference:** internal cents minus platform cents, for two-sided amount mismatches.
- **Absolute difference:** sum of absolute mismatch differences, exposing offsetting errors.
- Missing-side amounts are reported separately. Blocked keys do not contribute to amount totals. Currencies are never summed together.

Monetary values are parsed from decimal text to integer cents. pandas nullable `Int64` columns preserve exact cents when outer joins introduce missing values. Display and CSV export format cents without floating-point conversion. Text in CSV exports is escaped when it could be interpreted as a spreadsheet formula.

## Architecture

```text
app.py                         Streamlit navigation, interaction and display
reconciliation/
  validation.py                CSV parsing, normalization and row validation
  matching.py                  Block invalid keys and outer-merge valid records
  service.py                   Hash-based reuse and orchestration
  database.py / schema.sql     Atomic persistence, SQL reports and trace queries
  reporting.py                 Money formatting and safe CSV exports
scripts/
  generate_sample_data.py      Reproducible fixtures and independent expectations
  benchmark.py                 Verified end-to-end synthetic benchmark
tests/                         Unit, database integration and UI interaction tests
sample_data/                   Exception and corrected CSV pairs
docs/                          Walkthrough, design decisions and verification evidence
```

The four database tables are `reconciliation_runs`, `source_records`, `validation_issues` and `reconciliation_results`. `schema.sql` defines constraints, foreign keys and indexes. History, currency aggregates, exception counts and transaction tracing use SQL directly.

Every completed import commits its batch, source rows, issues and results in a single transaction. A failure rolls everything back. Duplicate imports are identified by the ordered pair of SHA-256 file-content hashes plus the rule version. Renaming a file reuses the original batch and its original metadata. Changing line order or bytes creates a new batch. A uniqueness constraint also protects against concurrent identical saves.

Data is stored in `data/reconciliation.sqlite3`, independent of the working directory. Set `RECONCILIATION_DB` to select another database. Timestamps are UTC. Databases and virtual environments are excluded from the shareable source archive.

## Tests and benchmark

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\benchmark.py --size 10000
```

The English build passes **52 unittest tests**, including Streamlit interaction tests and regression checks for English exports and historical messages. See [verification evidence](docs/VERIFICATION.md) for the measured data volume, timings and scope. Core tests can be run without UI sockets:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_validation tests.test_matching tests.test_integration tests.test_reporting
```

Regenerate demo files or add a larger input pair:

```powershell
.\.venv\Scripts\python.exe scripts\generate_sample_data.py --large --size 10000
```

The generator uses a fixed seed. Expected classification counts are specified independently of the reconciliation engine. Benchmark execution checks the expected counts before writing its report under `artifacts/`.

## Demonstration and portfolio use

Start with [the demonstration and interview guide](docs/DEMO_GUIDE.md). It includes the demo sequence, SQL examples, implementation decisions, interview questions and a fact-based CV description.

Existing runs from the original build also display English system messages, without changing the stored original records. User-supplied filenames, IDs and raw fields are preserved as evidence.

This version is a local, single-user portfolio application. It has no authentication or role separation, and is not deployed as a production financial system. The 100,000-row limit is an input guard, not a claim of tested production capacity. Historical comparisons show count changes and do not establish that two batches have identical business scope.
