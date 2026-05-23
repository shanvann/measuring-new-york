"""Download canonical NYC boundary files.

Sources are pinned in ../MANIFEST.json. Files land in ../geographies/.
Manifest entries (SHA + size + fetched_at) land in ../cache/MANIFEST.json
so we can detect drift later.

Usage::

    python scripts/download_geographies.py            # download all
    python scripts/download_geographies.py --list     # show URLs only
    python scripts/download_geographies.py --force    # re-download
    python scripts/download_geographies.py --only cd  # one geography
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

GEO_DIR = REPO_ROOT / "geographies"
MANIFEST = REPO_ROOT / "MANIFEST.json"


def _load_sources() -> dict:
    with MANIFEST.open() as f:
        manifest = json.load(f)
    return manifest["vintages"]["geographies"]


_KIND_TO_FILENAME = {
    "community_districts_59": "community_districts_59.geojson",
    "nta_2020": "nta_2020.geojson",
    "census_tracts_2020": "census_tracts_2020.geojson",
    "modzcta": "modzcta.geojson",
}


def _short_kind(k: str) -> str:
    return {
        "community_districts_59": "cd",
        "nta_2020": "nta",
        "census_tracts_2020": "tract",
        "modzcta": "modzcta",
    }[k]


def download_one(kind: str, url: str, *, force: bool = False) -> Path:
    filename = _KIND_TO_FILENAME[kind]
    target = GEO_DIR / filename
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not force:
        print(f"[skip] {filename} already on disk (use --force to re-download)")
        return target

    print(f"[fetch] {kind}  <-  {url}")
    r = requests.get(url, timeout=120, stream=True)
    r.raise_for_status()
    with target.open("wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    # mirror into cache/ for the manifest (also lets us blow away geographies/
    # safely)
    cache_key = f"geographies/{filename}"
    cache_path = cache.path_for(cache_key)
    cache_path.write_bytes(target.read_bytes())
    entry = cache.record(cache_key, url)
    print(f"  bytes={entry['bytes']:>10}  sha256={entry['sha256'][:12]}…")
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show URLs, don't download")
    ap.add_argument("--force", action="store_true", help="re-download if present")
    ap.add_argument("--only", choices=list(_KIND_TO_FILENAME), help="download a single geography")
    args = ap.parse_args(argv)

    sources = _load_sources()
    if args.list:
        for k, v in sources.items():
            print(f"{k:30s}  {v['source']}")
        return 0

    items = [(args.only, sources[args.only])] if args.only else list(sources.items())
    for kind, info in items:
        download_one(kind, info["source"], force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
