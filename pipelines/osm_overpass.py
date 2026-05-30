"""OpenStreetMap fetcher via the Overpass API.

Reused by Chapters 1, 4, 5. We hit Overpass directly for control over the
query and to keep caching consistent. ``osmnx`` is the right tool for walk
networks (Chapter 1); this module focuses on POI / amenity pulls.

Usage::

    python -m pipelines.osm_overpass --query parks --dry-run
    python -m pipelines.osm_overpass --query parks
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

ENDPOINT = "https://overpass-api.de/api/interpreter"
NYC_BBOX = "40.4774,-74.2591,40.9176,-73.7004"  # south, west, north, east

# Overpass started 406'ing requests with no User-Agent in 2025.
USER_AGENT = "measuring-new-york/0.1 (shanitpv@gmail.com)"

QUERIES = {
    "parks": f"""
        [out:json][timeout:120];
        (
          way["leisure"="park"]({NYC_BBOX});
          relation["leisure"="park"]({NYC_BBOX});
        );
        out center tags;
    """,
    "supermarkets": f"""
        [out:json][timeout:120];
        (
          node["shop"="supermarket"]({NYC_BBOX});
          way["shop"="supermarket"]({NYC_BBOX});
        );
        out center tags;
    """,
    "pharmacies": f"""
        [out:json][timeout:120];
        (
          node["amenity"="pharmacy"]({NYC_BBOX});
          way["amenity"="pharmacy"]({NYC_BBOX});
        );
        out center tags;
    """,
    "schools": f"""
        [out:json][timeout:120];
        (
          node["amenity"="school"]({NYC_BBOX});
          way["amenity"="school"]({NYC_BBOX});
        );
        out center tags;
    """,
}


def build_payload(query: str) -> str:
    if query not in QUERIES:
        raise ValueError(f"unknown query {query!r}. expected one of {list(QUERIES)}")
    return QUERIES[query].strip()


def fetch(query: str, *, snapshot: str = "2026-06-01") -> Path:
    import requests

    payload = build_payload(query)
    cache_name = f"osm/{query}-{snapshot}.json"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path
    print(f"[fetch] Overpass  query={query}")
    r = requests.post(
        ENDPOINT,
        data={"data": payload},
        timeout=180,
        headers={"User-Agent": USER_AGENT},
    )
    r.raise_for_status()
    data = r.json()
    path.write_text(json.dumps(data))
    cache.record(cache_name, f"{ENDPOINT} (POST query={query})")
    print(f"  -> {len(data.get('elements', []))} elements")
    return path


def load(query: str, *, snapshot: str = "2026-06-01"):
    path = fetch(query, snapshot=snapshot)
    return json.loads(path.read_text())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", required=True, choices=list(QUERIES))
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.dry_run:
        print(f"[dry-run] POST {ENDPOINT}")
        print("  data=")
        for line in build_payload(args.query).splitlines():
            print(f"    {line}")
        return 0
    fetch(args.query, snapshot=args.snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
