"""NYC Facilities Database — FacDB (Socrata dataset ji82-xba5).

DCP's authoritative point inventory of public/institutional facilities
citywide: libraries, childcare, health, schools, parks-as-facilities,
etc. One row per facility with ``latitude``/``longitude``, a direct
``cd`` (community district) field, and a ``capacity`` column where the
source agency reports one — which is what lets Chapter 4 measure
*sufficiency* (slots per resident), not just proximity.

Facilities are categorized at three levels: ``facdomain`` > ``facgroup``
> ``facsubgrp`` > ``factype``. We fetch one ``facsubgrp`` slice at a
time and cache it under that key. Known slices used by Ch. 4:

  PUBLIC LIBRARIES            -> ~228 branches (axis 3, civic)
  (childcare / health subgroups wired later for axis 2)

Vintage pin: 2026-06-01 (implicit in the cache key + manifest entry).

Usage::

    python -m pipelines.nyc_facdb --facsubgrp "PUBLIC LIBRARIES" --dry-run
    python -m pipelines.nyc_facdb --facsubgrp "PUBLIC LIBRARIES"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

DATASET_ID = "ji82-xba5"
ENDPOINT = f"https://data.cityofnewyork.us/resource/{DATASET_ID}.geojson"


def _slug(facsubgrp: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", facsubgrp.lower()).strip("-")


def _resolve(facsubgrp: str | None, facgroup: str | None) -> tuple[str, str]:
    """Return (where_clause, cache_slug) for a subgroup- or group-level pull."""
    if (facsubgrp is None) == (facgroup is None):
        raise ValueError("pass exactly one of facsubgrp / facgroup")
    if facsubgrp is not None:
        return f"facsubgrp = '{facsubgrp}'", _slug(facsubgrp)
    return f"facgroup = '{facgroup}'", _slug(facgroup)


def build_query(where: str, snapshot: str = "2026-06-01") -> dict:
    del snapshot  # snapshot pinning is implicit in the cache key
    return {
        "$select": (
            "uid, facname, facgroup, facsubgrp, factype, capacity, captype, "
            "opname, boro, cd, zipcode, latitude, longitude, geometry"
        ),
        "$where": where,
        "$limit": "50000",
    }


def fetch(facsubgrp: str | None = None, *, facgroup: str | None = None,
          snapshot: str = "2026-06-01") -> Path:
    """Fetch one FacDB subgroup- or group-level slice as GeoJSON.

    Pass exactly one of ``facsubgrp`` or ``facgroup``.
    """
    import requests

    where, slug = _resolve(facsubgrp, facgroup)
    cache_name = f"nyc_facdb/{slug}-{snapshot}.geojson"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path

    params = build_query(where, snapshot=snapshot)
    print(f"[fetch] FacDB  where=({where})  snapshot={snapshot}")
    r = requests.get(ENDPOINT, params=params, timeout=300)
    r.raise_for_status()
    payload = r.json()
    path.write_text(json.dumps(payload))
    cache.record(cache_name, r.url)
    n = len(payload.get("features", []))
    print(f"  -> {n} features  ({path.stat().st_size:,} bytes)")
    return path


def load(facsubgrp: str | None = None, *, facgroup: str | None = None,
         snapshot: str = "2026-06-01"):
    """Return a GeoDataFrame of facilities in one slice (EPSG:2263).

    Pass exactly one of ``facsubgrp`` or ``facgroup``. The FacDB GeoJSON
    export ships a null ``geometry`` member, so points are built from the
    ``latitude``/``longitude`` property columns (both reliably populated).
    ``capacity`` is coerced to numeric (note: it is **all-zero** for the
    day-care group — usable only as a facility count, not a slot count).
    Rows missing coordinates are dropped.
    """
    import geopandas as gpd
    import pandas as pd

    path = fetch(facsubgrp, facgroup=facgroup, snapshot=snapshot)
    feats = json.loads(path.read_text()).get("features", [])
    df = pd.DataFrame([f.get("properties", {}) for f in feats])
    df["latitude"] = pd.to_numeric(df.get("latitude"), errors="coerce")
    df["longitude"] = pd.to_numeric(df.get("longitude"), errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    if "capacity" in df.columns:
        df["capacity"] = pd.to_numeric(df["capacity"], errors="coerce")
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
        crs="EPSG:4326",
    )
    return gdf.to_crs(epsg=2263)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--facsubgrp")
    ap.add_argument("--facgroup")
    ap.add_argument("--snapshot", default="2026-06-01")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    where, _ = _resolve(args.facsubgrp, args.facgroup)
    if args.dry_run:
        print(f"[dry-run] GET {ENDPOINT}")
        for k, v in build_query(where, snapshot=args.snapshot).items():
            print(f"  {k} = {v}")
        return 0
    fetch(args.facsubgrp, facgroup=args.facgroup, snapshot=args.snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
