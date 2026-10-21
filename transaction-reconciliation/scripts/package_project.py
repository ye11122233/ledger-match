"""Package source and reference data; exclude runtime data and environments."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".venv", "__pycache__", ".git", "data", "artifacts"}
ALLOWED = {".py", ".sql", ".md", ".toml", ".txt", ".cmd", ".csv", ".json", ".png"}


def package():
    target = ROOT.parent / "LedgerMatch-English.zip"
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.rglob("*")):
            relative = path.relative_to(ROOT)
            # Keep the English distribution free of older translated documents/screenshots.
            if any(not part.isascii() for part in relative.parts):
                continue
            if path.is_file() and not EXCLUDED.intersection(relative.parts):
                if path.suffix in ALLOWED or path.name == ".gitignore":
                    archive.write(path, Path(ROOT.name) / relative)
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        print(f"{target.name}: {len(archive.namelist())} files, {target.stat().st_size:,} bytes")
    return target


if __name__ == "__main__":
    package()
