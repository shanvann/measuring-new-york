"""Cache manifest helpers.

Every cached file in ``cache/`` has an entry in ``cache/MANIFEST.json``:
source URL, fetch timestamp, SHA-256, byte size. The manifest is committed;
the cached blobs themselves are gitignored.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO_ROOT / "cache"
MANIFEST = CACHE_DIR / "MANIFEST.json"


def _load_manifest() -> dict:
    if not MANIFEST.exists():
        return {"note": "auto-created", "entries": {}}
    with MANIFEST.open() as f:
        return json.load(f)


def _save_manifest(data: dict) -> None:
    with MANIFEST.open("w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def path_for(name: str) -> Path:
    """Resolve a cache key (e.g. ``'osm/parks-2026-06-01.json'``) to a path."""
    p = CACHE_DIR / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def record(name: str, source_url: str, *, fetched_at: Optional[str] = None) -> dict:
    """Append/update a manifest entry for ``cache/<name>``.

    Returns the recorded entry dict.
    """
    p = path_for(name)
    if not p.exists():
        raise FileNotFoundError(p)
    entry = {
        "source_url": source_url,
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": _sha256(p),
        "bytes": p.stat().st_size,
    }
    manifest = _load_manifest()
    manifest.setdefault("entries", {})[name] = entry
    _save_manifest(manifest)
    return entry


def lookup(name: str) -> Optional[dict]:
    """Return the manifest entry for ``name`` if present."""
    return _load_manifest().get("entries", {}).get(name)


def is_cached(name: str) -> bool:
    """True if the file is on disk AND has a manifest entry."""
    return path_for(name).exists() and lookup(name) is not None
