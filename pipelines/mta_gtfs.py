"""MTA GTFS bundle fetcher + thin loader.

The full subway + bus bundles total ~200MB and parsing them is heavy. The
real isochrone work lands with Chapter 1 (Mobility & Access) in
``shared/isochrone.py``. This module just gets bytes onto disk reliably and
exposes a ``load_subway()`` helper for callers that only need GTFS metadata.

Usage::

    python -m pipelines.mta_gtfs --fetch              # downloads ~200MB
    python -m pipelines.mta_gtfs --fetch --bundle subway
    python -m pipelines.mta_gtfs --list-bundles
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

# MTA publishes static GTFS at well-known URLs under new.mta.info.
BUNDLES = {
    "subway": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip",
    "bus_manhattan": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_m.zip",
    "bus_bronx": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_bx.zip",
    "bus_brooklyn": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_b.zip",
    "bus_queens": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_q.zip",
    "bus_staten_island": "https://rrgtfsfeeds.s3.amazonaws.com/gtfs_si.zip",
}


def fetch_bundle(bundle: str, *, snapshot: str = "2026-06-01") -> Path:
    import requests

    if bundle not in BUNDLES:
        raise ValueError(f"unknown bundle {bundle!r}. expected one of {list(BUNDLES)}")
    url = BUNDLES[bundle]
    cache_name = f"mta_gtfs/{bundle}-{snapshot}.zip"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path
    print(f"[fetch] {bundle} <- {url}")
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    with path.open("wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    entry = cache.record(cache_name, url)
    print(f"  bytes={entry['bytes']:>10}  sha256={entry['sha256'][:12]}…")
    return path


def load_subway(snapshot: str = "2026-06-01"):
    """Return a gtfs-kit Feed object for the subway bundle."""
    try:
        import gtfs_kit
    except ImportError as e:
        raise ImportError("gtfs-kit not installed; run `pip install gtfs-kit`") from e
    path = fetch_bundle("subway", snapshot=snapshot)
    return gtfs_kit.read_feed(path, dist_units="ft")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--bundle", default="subway", choices=list(BUNDLES))
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--list-bundles", action="store_true")
    args = ap.parse_args(argv)

    if args.list_bundles:
        for k, v in BUNDLES.items():
            print(f"{k:20s}  {v}")
        return 0
    if args.fetch:
        fetch_bundle(args.bundle, snapshot=args.snapshot)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
