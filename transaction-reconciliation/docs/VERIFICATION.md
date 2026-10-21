# Verification evidence

Verified on 21 October 2026 (Europe/London), with Python 3.12.14, pandas 3.0.6, Streamlit 1.66.0 and SQLite on Windows 11.

## Automated checks

`python -m unittest discover -s tests -q`

**52 tests passed** for the English build, including 7 Streamlit interaction tests. Recorded suite duration: 2.167 seconds in this environment. Test names and assertions are available under `tests/`.

Coverage by behavior:

- File structure, UTF-8/BOM, missing fields, dates, currencies, exact decimal rules, record/byte limits and original line numbers.
- Normalization, preserved IDs and raw values, duplicate-key isolation, keyed and keyless invalid records.
- Outer matching, mismatches, both missing-side directions, currency hints and cent accuracy after outer joins.
- Independent fixture expectations, per-currency net/absolute sums, original record tracing and persistent history.
- Duplicate imports, rule changes, competing identical saves, SQL search parameters and complete transactional rollback.
- Report headers/BOM, exact negative difference formatting and escaping spreadsheet formulas.
- Page load, disabled incomplete submission, demo/repeat import, filters, corrected data, history comparison and raw-record inspection.
- English export headers, statuses and reasons; English rendering of stored messages without changing historical evidence; recovery from earlier browser-session choices.

Browser verification also confirmed that the app loads at `http://127.0.0.1:8501`, the demo completes, and the visible metrics and exception rows agree with the independent expected results.

The English update also checks both existing saved runs: system-generated result and validation explanations render in English. Original records and stored historical messages are preserved.

## Synthetic end-to-end measurement

Command: `python scripts/benchmark.py --size 10000`

| Measurement | Recorded result |
|---|---:|
| Logical transaction keys | 10,000 |
| Source records, both files combined | 19,800 |
| Matched keys | 9,700 |
| Amount mismatch keys | 100 |
| Missing internal keys | 100 |
| Missing platform keys | 100 |
| Validation + matching + SQLite persistence | 0.3678 seconds |
| Repeated identical import lookup | 0.0009 seconds |

The benchmark verifies its classifications against independently generated expectations before accepting the measurement. Machine-readable output is in `benchmark-10000.json`.

This is one local synthetic run, excludes browser rendering, and is not a production capacity guarantee. The 100,000-record-per-file input limit has boundary behavior tests using a smaller patched limit; a full 100,000-row production workload was not measured. The application has not been deployed or assessed as a multi-user financial service.

## Reproduce

Install the pinned dependencies, then run the commands above. Streamlit UI tests need local loopback sockets and a writable temporary directory. In a restricted environment, run the core suite independently as documented in README.
