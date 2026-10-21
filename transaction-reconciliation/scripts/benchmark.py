"""Reproducible end-to-end benchmark; verify results before reporting timings."""
import argparse
import json
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from reconciliation.database import Database
from reconciliation.service import process
from scripts.generate_sample_data import generate_large


def benchmark(size):
    directory = ROOT / "artifacts" / "benchmark-tmp"
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        path = Path(temp)
        generate_large(path, size)
        expected = json.loads((path / "large_expected.json").read_text())
        internal = (path / "large_internal.csv").read_bytes()
        external = (path / "large_platform.csv").read_bytes()
        database = Database(path / "benchmark.sqlite3")
        start = perf_counter()
        run_id, _ = process(internal, external, "large_internal.csv", "large_platform.csv", database)
        elapsed = perf_counter() - start
        actual = database.summary(run_id)["counts"]
        assert {key: actual.get(key, 0) for key in expected["counts"]} == expected["counts"]
        start = perf_counter()
        repeated, reused = process(internal, external, "large_internal.csv", "large_platform.csv", database)
        repeat_elapsed = perf_counter() - start
        assert reused and repeated == run_id
        return {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                "platform": platform.platform(), "logical_keys": size,
                "total_source_records": expected["internal_rows"] + expected["platform_rows"],
                "end_to_end_seconds": round(elapsed, 4), "duplicate_import_seconds": round(repeat_elapsed, 4),
                "counts": actual, "expected_verified": True,
                "scope": "Local synthetic CSV validation, pandas matching and SQLite persistence; excludes browser rendering. One run, not a production capacity guarantee."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=10000)
    args = parser.parse_args()
    result = benchmark(args.size)
    (ROOT / "artifacts" / f"benchmark-{args.size}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
