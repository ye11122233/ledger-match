import csv
import io

HEADER = ["transaction_id", "transaction_date", "amount", "currency"]


def csv_bytes(rows, header=HEADER):
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(header)
    writer.writerows(rows)
    return text.getvalue().encode("utf-8-sig")


def row(tid="001", amount="10.00", currency="GBP", day="2026-09-01"):
    return [tid, day, amount, currency]
