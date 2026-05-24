"""LEHD LODES — Workplace Area Characteristics.

The denominator for the "jobs reachable in 45 min" metric in Chapter 1.

LODES (Longitudinal Employer-Household Dynamics Origin-Destination
Employment Statistics) is published by the Census Bureau. The WAC file
gives jobs per Census **block** (~40k in NYC) for each year. We aggregate
to **tract** level (~2300 in NYC) for tractable spatial operations.

Vintage pinned in MANIFEST.json. LODES8 (the v8 schema) is the current
release; 2022 is the latest available year at time of pin.

Block GEOID structure: state(2) + county(3) + tract(6) + block(4) = 15 chars.
NYC counties: Bronx 005, Kings 047, NY 061, Queens 081, Richmond 085.
Tract GEOID = first 11 chars.

Usage::

    python -m pipelines.lehd_lodes --year 2022 --dry-run
    python -m pipelines.lehd_lodes --year 2022
"""

from __future__ import annotations

import argparse
import gzip
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import cache  # noqa: E402

# https://lehd.ces.census.gov/data/lodes/LODES8/LODESTechDoc8.1.pdf
URL_TMPL = "https://lehd.ces.census.gov/data/lodes/LODES8/ny/wac/ny_wac_S000_JT00_{year}.csv.gz"

NYC_COUNTY_FIPS = {"005", "047", "061", "081", "085"}  # 36 = NY state


def fetch(year: int = 2022, snapshot: str = "2026-06-01") -> Path:
    """Download the NY WAC file for the given year. ~30MB compressed."""
    import requests

    url = URL_TMPL.format(year=year)
    cache_name = f"lodes/ny_wac_S000_JT00_{year}.csv.gz"
    path = cache.path_for(cache_name)
    if cache.is_cached(cache_name):
        print(f"[cache hit] {cache_name}")
        return path
    print(f"[fetch] LODES NY WAC year={year} <- {url}")
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    with path.open("wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    entry = cache.record(cache_name, url)
    print(f"  bytes={entry['bytes']:>10}  sha256={entry['sha256'][:12]}…")
    return path


# Job columns we use from WAC. C000 = all jobs; CE01/CE02/CE03 = earnings tiers.
#   CE01: monthly earnings ≤ $1,250  (~ ≤ $15K/yr)
#   CE02: monthly earnings $1,251 – $3,333  (~ $15K – $40K/yr)
#   CE03: monthly earnings ≥ $3,334  (~ ≥ $40K/yr)
# By construction, C000 = CE01 + CE02 + CE03.
JOB_COLUMNS = ["C000", "CE01", "CE02", "CE03"]


def load(year: int = 2022, nyc_only: bool = True):
    """Return a pandas DataFrame of block-level jobs.

    Columns returned: ``w_geocode`` + every column in ``JOB_COLUMNS``.

    With ``nyc_only=True`` (default), filtered to the 5 NYC counties — drops
    ~95% of rows and keeps only the ones we need.
    """
    import pandas as pd

    path = fetch(year=year)
    df = pd.read_csv(path, dtype={"w_geocode": str}, usecols=["w_geocode", *JOB_COLUMNS])
    if nyc_only:
        prefix = df["w_geocode"].str[:5]
        df = df[prefix.isin({f"36{c}" for c in NYC_COUNTY_FIPS})].copy()
    return df


def aggregate_to_tracts(df, columns: list[str] | None = None) -> dict[str, dict[str, int]]:
    """Sum job-count columns per tract (11-digit GEOID).

    Returns ``{tract_geoid: {col: count}}``. Backward-compatible behavior:
    if a caller treats the return value as ``dict[str, int]`` it'll error
    loudly rather than silently shifting semantics.
    """
    cols = columns or JOB_COLUMNS
    df = df.copy()
    df["tract_geoid"] = df["w_geocode"].str[:11]
    agg = df.groupby("tract_geoid", as_index=False)[cols].sum()
    out: dict[str, dict[str, int]] = {}
    for r in agg.itertuples(index=False):
        out[r.tract_geoid] = {c: int(getattr(r, c)) for c in cols}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2022)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    url = URL_TMPL.format(year=args.year)
    if args.dry_run:
        print(f"[dry-run] GET {url}")
        return 0
    fetch(year=args.year)
    df = load(year=args.year)
    jobs_by_tract = aggregate_to_tracts(df)
    totals = {c: sum(t[c] for t in jobs_by_tract.values()) for c in JOB_COLUMNS}
    print(f"  loaded {len(df):,} NYC block rows")
    print(f"  aggregated to {len(jobs_by_tract):,} tracts")
    for c in JOB_COLUMNS:
        print(f"  {c}: {totals[c]:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
