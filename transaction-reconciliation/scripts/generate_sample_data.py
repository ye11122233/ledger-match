"""Deterministic synthetic data with independently specified expected outcomes."""
import argparse
import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["transaction_id", "transaction_date", "amount", "currency"]


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(FIELDS)
        writer.writerows(rows)


def generate_demo(output):
    def row(tid, amount, currency="GBP", day="2026-09-01"):
        return [tid, day, amount, currency]
    internal = [row("TXN001", "10.00"), row("TXN002", "20.00", "EUR"), row("TXN003", "30", "USD"),
                row("TXN005", "50"), row("TXN005", "50"), row("TXN006", "oops", "EUR"),
                row("TXN007", "70", "USD", "2026-02-30"), row("000008", "12.34"),
                row("TXN009", "90"), row("TXN010", "-10"), row("", "11"),
                row("TXN011", "0.10", "EUR"), row("TXN012", "100"), row("TXN013", "100"),
                row(" TXN014 ", " 14.50 ", " eur ")]
    platform = [row("TXN001", "10"), row("TXN002", "21", "EUR"), row("TXN004", "40"),
                row("TXN005", "50"), row("TXN006", "60", "EUR"), row("TXN007", "70", "USD"),
                row("000008", "12.34"), row("TXN009", "90", "USD"), row("TXN010", "10"),
                row("TXN011", "0.1", "EUR"), row("TXN012", "99"), row("TXN013", "101"), row("TXN014", "14.50", "EUR")]
    fixed = [row("TXN001", "10"), row("TXN002", "20", "EUR"), row("TXN003", "30", "USD"),
             row("TXN004", "40"), row("TXN005", "50"), row("TXN006", "60", "EUR"), row("TXN007", "70", "USD"),
             row("000008", "12.34"), row("TXN009", "90"), row("TXN010", "10"), row("TXN015", "11"),
             row("TXN011", "0.10", "EUR"), row("TXN012", "100"), row("TXN013", "100"), row("TXN014", "14.50", "EUR")]
    write_csv(output / "demo_internal.csv", internal)
    write_csv(output / "demo_platform.csv", platform)
    write_csv(output / "corrected_internal.csv", fixed)
    write_csv(output / "corrected_platform.csv", fixed)
    expected = {
        "demo": {"internal_rows": 15, "platform_rows": 13, "internal_invalid_rows": 6,
                 "platform_invalid_rows": 0, "counts": {"matched": 4, "amount_mismatch": 3,
                 "missing_platform": 2, "missing_internal": 2, "blocked": 4},
                 "eligible_keys": 11, "match_rate": 4 / 11,
                 "GBP_net_difference_minor": 0, "GBP_absolute_difference_minor": 200,
                 "EUR_net_difference_minor": -100, "EUR_absolute_difference_minor": 100},
        "corrected": {"rows_per_source": 15, "counts": {"matched": 15}, "match_rate": 1.0},
        "notes": "Expected outcomes are specified by the fixture author, not computed by the matching engine."
    }
    (output / "expected_results.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")


def generate_large(output, size):
    if not 100 <= size <= 99000:
        raise ValueError("size must be between 100 and 99000")
    rng = random.Random(42)
    internal, platform = [], []
    counts = {"matched": 0, "amount_mismatch": 0, "missing_platform": 0, "missing_internal": 0, "blocked": 0}
    for index in range(size):
        cents = rng.randrange(1, 1000000)
        row = [f"SYN{index:07d}", "2026-09-01", f"{cents // 100}.{cents % 100:02d}", ("GBP", "EUR", "USD")[index % 3]]
        category = index % 100
        if category == 0:
            internal.append(row)
            counts["missing_platform"] += 1
        elif category == 1:
            platform.append(row)
            counts["missing_internal"] += 1
        elif category == 2:
            internal.append(row)
            platform.append([*row[:2], f"{(cents + 1) // 100}.{(cents + 1) % 100:02d}", row[3]])
            counts["amount_mismatch"] += 1
        else:
            internal.append(row)
            platform.append(row)
            counts["matched"] += 1
    write_csv(output / "large_internal.csv", internal)
    write_csv(output / "large_platform.csv", platform)
    (output / "large_expected.json").write_text(json.dumps({"logical_keys": size, "counts": counts,
        "internal_rows": len(internal), "platform_rows": len(platform)}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=10000)
    parser.add_argument("--large", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "sample_data")
    args = parser.parse_args()
    generate_demo(args.output)
    if args.large:
        generate_large(args.output, args.size)
