from hashlib import sha256

from .matching import reconcile
from .validation import load_csv


def process(internal_bytes, platform_bytes, internal_filename, platform_filename, database):
    hashes = [sha256(content).hexdigest() for content in (internal_bytes, platform_bytes)]
    existing = database.find_run(*hashes)
    if existing is not None:
        return existing, True
    internal = load_csv(internal_bytes, "internal", internal_filename)
    platform = load_csv(platform_bytes, "platform", platform_filename)
    results = reconcile(internal, platform)
    return database.save(*hashes, internal_filename, platform_filename, internal + platform, results)
