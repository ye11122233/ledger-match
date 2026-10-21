"""Strict UTF-8 CSV ingestion. No float conversion or silent row dropping."""
import csv
import io
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal

from .models import CURRENCIES, MAX_FILE_BYTES, MAX_ROWS, REQUIRED_COLUMNS, InputError, Record

AMOUNT = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,2})?\Z")
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def load_csv(content: bytes, source: str, filename: str) -> list[Record]:
    if source not in ("internal", "platform"):
        raise ValueError("Unknown source")
    if len(content) > MAX_FILE_BYTES:
        raise InputError(f"{filename}: File exceeds the 10 MB limit.")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InputError(f"{filename}: Save the file as UTF-8 CSV and upload it again.") from exc
    if "\x00" in decoded:
        raise InputError(f"{filename}: Contains null bytes and cannot be read as CSV.")
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        header = next(reader, None)
        if not header:
            raise InputError(f"{filename}: The file is empty or has no header.")
        header = [x.strip() for x in header]
        if len(header) != len(set(header)):
            raise InputError(f"{filename}: The header contains duplicate column names.")
        missing = set(REQUIRED_COLUMNS) - set(header)
        if missing:
            raise InputError(f"{filename}: Missing required columns: {', '.join(sorted(missing))}.")
        records = []
        while True:
            row_number = reader.line_num + 1
            values = next(reader, None)
            if values is None:
                break
            if not values:  # CSV permits empty physical lines.
                continue
            if len(values) != len(header):
                raise InputError(f"{filename} row {row_number}: The column count does not match the header.")
            if len(records) >= MAX_ROWS:
                raise InputError(f"{filename}: Exceeds the 100,000-record limit.")
            raw = dict(zip(header, values))
            normalized = {key: value.strip() for key, value in raw.items()}
            tid = normalized["transaction_id"]
            currency = normalized["currency"].upper()
            day = normalized["transaction_date"]
            amount = normalized["amount"]
            issues = []
            for key in REQUIRED_COLUMNS:
                if not normalized[key]:
                    issues.append(("missing_field", f"{key} is required"))
            if tid and (len(tid) > 128 or any(ord(c) < 32 for c in tid)):
                issues.append(("invalid_id", "Transaction ID must be at most 128 characters and contain no control characters"))
            if currency and currency not in CURRENCIES:
                issues.append(("invalid_currency", "Currency must be GBP, EUR or USD"))
            if day:
                try:
                    if not ISO_DATE.fullmatch(day):
                        raise ValueError()
                    date.fromisoformat(day)
                except ValueError:
                    issues.append(("invalid_date", "Date must be a valid YYYY-MM-DD calendar date"))
            minor = None
            if amount:
                if not AMOUNT.fullmatch(amount) or Decimal(amount) <= 0:
                    issues.append(("invalid_amount", "Amount must be positive, have at most two decimal places and not exceed 999999999.99"))
                else:
                    minor = int(Decimal(amount) * 100)
            records.append(Record(source, filename, row_number, raw, tid, currency, day, minor, issues))
    except csv.Error as exc:
        raise InputError(f"{filename}: Malformed CSV near line {reader.line_num}: {exc}") from exc
    if not records:
        raise InputError(f"{filename}: The file has a header but no transaction records.")
    groups = defaultdict(list)
    for record in records:
        if record.key:
            groups[record.key].append(record)
    for group in groups.values():
        if len(group) > 1:
            for record in group:
                record.issues.append(("duplicate_key", "Duplicate transaction ID and currency within one source; all records for this key are isolated"))
    return records
