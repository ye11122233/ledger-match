import csv
import io
import json

from .models import SOURCE_LABELS, STATUS_LABELS


def money(minor):
    if minor is None:
        return ""
    sign = "-" if minor < 0 else ""
    major, cents = divmod(abs(minor), 100)
    return f"{sign}{major}.{cents:02d}"


def result_rows(results):
    return [{
        "Transaction ID": r["transaction_id"], "Currency": r["currency"], "Status": STATUS_LABELS[r["status"]],
        "Internal amount": money(r["internal_amount_minor"]), "Platform amount": money(r["platform_amount_minor"]),
        "Difference (internal - platform)": money(r["difference_minor"]),
        "Internal source rows": ", ".join(map(str, json.loads(r["internal_rows"]))),
        "Platform source rows": ", ".join(map(str, json.loads(r["platform_rows"]))), "Reason": r["reason"],
    } for r in results]


def issue_rows(issues, run):
    rows = []
    for issue in issues:
        raw = json.loads(issue["raw_json"])
        rows.append({"Source": SOURCE_LABELS[issue["source"]], "Filename": run[f"{issue['source']}_filename"],
                     "Source row": issue["row_number"], "Transaction ID": raw["transaction_id"],
                     "Currency": raw["currency"], "Original date": raw["transaction_date"], "Original amount": raw["amount"],
                     "Issue code": issue["code"], "Reason": issue["message"]})
    return rows


RESULT_FIELDS = ["Transaction ID", "Currency", "Status", "Internal amount", "Platform amount", "Difference (internal - platform)", "Internal source rows", "Platform source rows", "Reason"]
ISSUE_FIELDS = ["Source", "Filename", "Source row", "Transaction ID", "Currency", "Original date", "Original amount", "Issue code", "Reason"]
NUMERIC_FIELDS = {"Internal amount", "Platform amount", "Difference (internal - platform)", "Source row"}


def to_csv_bytes(rows, fields):
    """UTF-8 BOM for Excel; escape spreadsheet formulas in user-supplied text."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        safe = {}
        for key in fields:
            value = row.get(key, "")
            if key not in NUMERIC_FIELDS and isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                value = "'" + value
            safe[key] = value
        writer.writerow(safe)
    return output.getvalue().encode("utf-8-sig")
