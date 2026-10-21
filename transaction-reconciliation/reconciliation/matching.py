"""Use a pandas outer merge only after blocking invalid/duplicate keys."""
from collections import defaultdict
import pandas as pd

from .models import Result


def reconcile(internal, platform) -> list[Result]:
    groups = {"internal": defaultdict(list), "platform": defaultdict(list)}
    id_currencies = defaultdict(set)
    for record in [*internal, *platform]:
        if record.key:
            groups[record.source][record.key].append(record)
            id_currencies[record.transaction_id].add(record.currency)
    blocked = {
        key for source_groups in groups.values() for key, records in source_groups.items()
        if any(not record.valid for record in records)
    }
    frames = []
    for source in ("internal", "platform"):
        frame = pd.DataFrame([
            {"transaction_id": r.transaction_id, "currency": r.currency,
             f"{source}_amount": r.amount_minor, f"{source}_row": r.row_number}
            for records in groups[source].values() for r in records if r.key not in blocked
        ], columns=["transaction_id", "currency", f"{source}_amount", f"{source}_row"])
        # Nullable integers preserve exact cents even after an outer merge introduces NA.
        frame[f"{source}_amount"] = frame[f"{source}_amount"].astype("Int64")
        frame[f"{source}_row"] = frame[f"{source}_row"].astype("Int64")
        frames.append(frame)
    joined = frames[0].merge(frames[1], on=["transaction_id", "currency"], how="outer",
                            validate="one_to_one", indicator=True)
    results = []
    for row in joined.to_dict("records"):
        left = None if pd.isna(row["internal_amount"]) else int(row["internal_amount"])
        right = None if pd.isna(row["platform_amount"]) else int(row["platform_amount"])
        difference = left - right if left is not None and right is not None else None
        if row["_merge"] == "left_only":
            status, reason = "missing_platform", "No matching transaction in the payment-platform records"
        elif row["_merge"] == "right_only":
            status, reason = "missing_internal", "No matching transaction in the internal records"
        elif difference:
            status, reason = "amount_mismatch", "Amounts differ for the same transaction ID and currency"
        else:
            status, reason = "matched", "Transaction ID, currency and amount match"
        if status.startswith("missing_") and len(id_currencies[row["transaction_id"]]) > 1:
            reason += "; The same transaction ID appears in other currencies; check the currency"
        results.append(Result(row["transaction_id"], row["currency"], status,
                              [] if pd.isna(row["internal_row"]) else [int(row["internal_row"])],
                              [] if pd.isna(row["platform_row"]) else [int(row["platform_row"])],
                              left, right, difference, reason))
    for tid, currency in blocked:
        left = groups["internal"].get((tid, currency), [])
        right = groups["platform"].get((tid, currency), [])
        reasons = sorted({message for record in left + right for _, message in record.issues})
        results.append(Result(tid, currency, "blocked", [r.row_number for r in left],
                              [r.row_number for r in right],
                              left[0].amount_minor if len(left) == 1 else None,
                              right[0].amount_minor if len(right) == 1 else None,
                              None, "; ".join(reasons)))
    return sorted(results, key=lambda r: (r.transaction_id, r.currency))
