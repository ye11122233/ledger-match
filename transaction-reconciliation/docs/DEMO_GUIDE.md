# LedgerMatch — Demonstration and Interview Guide

## Run the project

Open http://127.0.0.1:8501 if the application is already running. On the prepared Windows workspace, double-click `start.cmd` to start it later. For a fresh checkout, follow the setup commands in README.

The application interface, validation messages, CSV report headers, result statuses and exception explanations are in English. Original user-provided data is preserved as uploaded.

## Three-minute demonstration

**1. Explain the problem.**

“This project compares a company's internal transaction export with a payment-platform export. The two sources should cover the same period and transaction scope. The tool checks data quality, identifies missing transactions and amount differences, and preserves evidence for investigation.”

**2. Run the exception dataset.**

On **Upload & validate**, leave **Data with exceptions** selected and click **Run demo**. The internal source has 15 rows and the platform source has 13.

| Result | Unique transaction keys |
|---|---:|
| Matched | 4 |
| Amount mismatch | 3 |
| Missing from platform | 2 |
| Missing from internal | 2 |
| Blocked by data issues | 4 |

There are 11 eligible keys: 4 / 11 gives a 36.4% match rate. There are 11 exception keys, including 4 blocked keys. The internal file has 6 failed source rows. One of those rows has no transaction ID and therefore cannot become a matching key. Explain the difference between source-row counts, issue counts and transaction-key counts.

**3. Investigate specific cases.**

- Enter `TXN005` under **Trace source records**. Two internal rows share the same ID and currency, while the platform has one. The entire key is blocked; the tool does not silently choose a row or create a many-to-many match.
- Filter for **Amount mismatch** and **GBP**. `TXN012` differs by +1.00, while `TXN013` differs by -1.00. Their net difference is zero, but the absolute difference is 2.00. Comparing totals alone would miss both errors.
- `TXN009` uses different currencies in the two files. It produces two missing-side exceptions and a currency hint; no FX conversion is attempted.
- `TXN006` has an invalid amount, `TXN007` an invalid date and `TXN010` a negative amount. Their keys are blocked, so the valid counterparts are not incorrectly reported as missing.

**4. Export the investigation.**

Click **Download filtered details**, **Download all exceptions**, or **Download validation issues**. Reports include source-row references and English explanations. The validation report also contains records without identifiable keys. A row with multiple issues appears once per issue.

**5. Show a corrected import and history.**

Return to **Upload & validate**, select **Corrected data** and click **Run demo**. Both files now contain 15 valid records, all matched. In **History**, compare the two runs. Reimporting the same file contents opens the existing run rather than creating another copy.

The corrected fixture represents a human-reviewed outcome: missing records are supplied, invalid values are corrected, duplicates are resolved, the currency is verified and the unidentified row receives ID `TXN015`. The software does not infer those corrections automatically. Batch comparisons show counts; confirm the transaction scope before interpreting any improvement.

## Read the code in this order

1. `sample_data/`: understand the examples and their independent expected results.
2. `validation.py`: distinguish rejected files, isolated rows, normalized values and raw evidence.
3. `matching.py`: follow key blocking, unique matching and the outer join.
4. `schema.sql` and `database.py`: understand table relationships, SQL summaries, parameters and transactions.
5. `service.py`: follow the content-hash check and processing workflow.
6. `reporting.py` and `app.py`: understand exact amount formatting, exports and interaction.
7. `tests/`: inspect which business decisions are explicitly verified.

## Explain the implementation decisions

**Why pandas and SQL?** pandas validates typed tabular data and performs matching in memory. SQLite persists runs and performs real reporting queries: historical lookup, exception counts, currency summaries and transaction tracing.

**Why integer cents?** Decimal text is validated before conversion to an integer. Fractional cents are rejected. Nullable integer columns preserve precision when an outer join introduces missing values. Amounts are formatted without converting them back to floats.

**Why block duplicates?** A duplicate could be an export problem or a business-data problem. Preserving all occurrences makes the uncertainty visible and lets a user investigate before resubmitting corrected data.

**How are results verified?** Hand-authored fixtures specify expected results independently. Unit tests check boundaries; database integration tests check persistence and summaries; Streamlit interaction tests exercise the visible workflow. The larger synthetic generator records expected classification counts without using the reconciliation engine.

**What happens if saving fails?** The run, source rows, issues and results are written in one SQLite transaction. A forced-write-failure test checks that no partial run remains.

**What counts as a duplicate import?** The ordered pair of input SHA-256 hashes and the rule version identifies a run. Renaming files still opens the original run. Changing bytes or row order creates a new run. A uniqueness constraint also protects competing saves of identical inputs.

**What happens to earlier Chinese runs?** Known system-generated messages are translated when read. Their original database values and raw transaction fields are retained. Translation does not trigger another reconciliation or alter the amounts.

**What are the limits?** This is a local, single-user portfolio application with a fixed CSV schema, three currencies and exact matching. Refunds, fees, FX and settlement timing require new business rules before implementation.

## SQL examples

Pass `:run_id` and `:transaction_id` as query parameters.

```sql
-- Exceptions by currency and type
SELECT currency, status, COUNT(*) AS exception_keys
FROM reconciliation_results
WHERE run_id = :run_id AND status <> 'matched'
GROUP BY currency, status;

-- Expose offsetting amount differences
SELECT currency,
       SUM(difference_minor) AS net_difference_minor,
       SUM(ABS(difference_minor)) AS absolute_difference_minor
FROM reconciliation_results
WHERE run_id = :run_id AND status = 'amount_mismatch'
GROUP BY currency;

-- Trace a transaction across runs
SELECT b.id, b.created_at, r.currency, r.status, r.difference_minor
FROM reconciliation_runs b
JOIN reconciliation_results r ON r.run_id = b.id
WHERE r.transaction_id = :transaction_id
ORDER BY b.id DESC;
```

## CV wording

> Built a transaction reconciliation tool using Python, pandas, SQLite and Streamlit to validate CSV exports, identify amount mismatches and missing transactions, and generate traceable exception reports.
>
> Implemented integer-cent comparisons, content-hash duplicate import detection and atomic batch persistence; verified behavior with 52 automated unit, integration and UI tests.

If a scale metric is useful, state that a local synthetic test reconciled 10,000 transaction keys across 19,800 source records. Refer to the verification report for that run's measured timing and scope. Do not present synthetic results as customer outcomes or production throughput.

Before discussing this project in an interview, practise changing a rule, adding a test and explaining the resulting behavior yourself.
