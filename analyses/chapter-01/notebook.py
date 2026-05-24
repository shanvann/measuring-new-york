"""Chapter 1 — Mobility & Access.

Produces the artifacts that ship in the Ch. 1 MDX:
  out/job-access.geojson         CD choropleth: jobs reachable in 45 min
                                 via subway+walk from each CD's centroid
                                 (the headline visual).
  out/isochrones-45min.geojson   FeatureCollection: one polygon per anchor CD,
                                 showing the 45-min AM-peak transit reach
                                 (the secondary visual / overlay).
  out/facts.json                 Headline numbers for <MetricCallout/> blocks.

Inputs:
  - MTA subway GTFS (pipelines.mta_gtfs)
  - Community Districts geography (shared.basemap)
  - 2020 Census Tracts geography (shared.basemap)
  - LEHD LODES 2022 NY WAC (pipelines.lehd_lodes)

Algorithm:
  For each of NYC's 59 CDs:
    1. Pick the CD's representative_point as origin
    2. Compute 45-min AM-peak transit+walk isochrone (shared.isochrone)
    3. Intersect the isochrone polygon with every NYC census tract
    4. Sum jobs in those tracts, area-weighted by intersection share

Run with::

    python analyses/chapter-01/notebook.py
    DEPARTURE_HOUR=17 python analyses/chapter-01/notebook.py  # PM peak
"""

from __future__ import annotations

import json
import os
import sys
import time as _t
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipelines import mta_gtfs, lehd_lodes  # noqa: E402
from shared import basemap, isochrone  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# Plan §10: the 5 anchor CDs for Ch. 1 — surfaced specifically in the prose
# / table. Names are slightly more specific than the all-CDs map below
# (e.g., "Midtown East" vs the broader "Midtown").
ANCHOR_CDS = [
    ("105", "Midtown East", "MN"),
    ("301", "Williamsburg / Greenpoint", "BK"),
    ("212", "Wakefield / Williamsbridge", "BX"),
    ("410", "South Ozone Park / Howard Beach", "QN"),
    ("414", "Rockaway", "QN"),
]
ANCHOR_BORO_CDS = {c for c, _, _ in ANCHOR_CDS}
ANCHOR_NAME = {c: name for c, name, _ in ANCHOR_CDS}

# Common-use neighborhood names for all 59 NYC residential CDs.
# Source: NYC DCP Community District neighborhood listings.
CD_NEIGHBORHOOD = {
    # Manhattan
    "101": "Financial District / Battery Park City",
    "102": "Greenwich Village / Soho",
    "103": "Lower East Side / Chinatown",
    "104": "Chelsea / Hell's Kitchen",
    "105": "Midtown",
    "106": "Stuyvesant Town / Turtle Bay",
    "107": "Upper West Side",
    "108": "Upper East Side",
    "109": "Manhattanville / Hamilton Heights",
    "110": "Central Harlem",
    "111": "East Harlem",
    "112": "Washington Heights / Inwood",
    # Bronx
    "201": "Mott Haven / Melrose",
    "202": "Hunts Point / Longwood",
    "203": "Morrisania / Crotona",
    "204": "Highbridge / Concourse",
    "205": "University Heights / Fordham",
    "206": "Belmont / East Tremont",
    "207": "Kingsbridge Heights / Bedford Park",
    "208": "Riverdale / Fieldston",
    "209": "Soundview / Parkchester",
    "210": "Throgs Neck / Co-op City",
    "211": "Pelham Parkway / Morris Park",
    "212": "Williamsbridge / Baychester",
    # Brooklyn
    "301": "Williamsburg / Greenpoint",
    "302": "Fort Greene / Brooklyn Heights",
    "303": "Bedford-Stuyvesant",
    "304": "Bushwick",
    "305": "East New York / Cypress Hills",
    "306": "Park Slope / Carroll Gardens",
    "307": "Sunset Park",
    "308": "Crown Heights / Prospect Heights",
    "309": "South Crown Heights / Lefferts Gardens",
    "310": "Bay Ridge / Dyker Heights",
    "311": "Bensonhurst / Bath Beach",
    "312": "Borough Park",
    "313": "Coney Island / Brighton Beach",
    "314": "Flatbush / Midwood",
    "315": "Sheepshead Bay / Manhattan Beach",
    "316": "Brownsville",
    "317": "East Flatbush / Farragut",
    "318": "Canarsie / Flatlands",
    # Queens
    "401": "Astoria",
    "402": "Sunnyside / Woodside",
    "403": "Jackson Heights / North Corona",
    "404": "Elmhurst / Corona",
    "405": "Ridgewood / Maspeth",
    "406": "Forest Hills / Rego Park",
    "407": "Flushing / Bay Terrace",
    "408": "Hillcrest / Fresh Meadows",
    "409": "Kew Gardens / Woodhaven",
    "410": "South Ozone Park / Howard Beach",
    "411": "Bayside / Little Neck",
    "412": "Jamaica / Hollis",
    "413": "Queens Village / Cambria Heights",
    "414": "Rockaway / Broad Channel",
    # Staten Island
    "501": "St. George / Stapleton",
    "502": "South Beach / Willowbrook",
    "503": "Tottenville / Great Kills",
}

DEFAULT_MAX_MINUTES = 45
DEFAULT_DEPARTURE_HOUR = 8


def cd_centroid_latlon(cds_gdf, boro_cd: str) -> tuple[float, float]:
    """Fallback: simple geometric representative point."""
    row = cds_gdf[cds_gdf["boro_cd"] == boro_cd].iloc[0]
    p = row.geometry.representative_point()
    return (p.y, p.x)


def population_weighted_origins(cds_gdf, tracts_gdf) -> dict[str, tuple[float, float]]:
    """For each CD, return a population-weighted origin point.

    NYC census tracts are designed for ~4k residents each, so the mean of
    tract centroids within a CD approximates a population-weighted centroid
    without needing explicit population weights.

    Falls back to representative_point() for CDs that contain no tract
    centroids (shouldn't happen for the 59 residential CDs but kept for
    safety).
    """
    import geopandas as gpd
    # Tract centroids (use representative_point to ensure inside polygon)
    tract_centroids = gpd.GeoDataFrame(
        {"geoid": tracts_gdf["geoid"]},
        geometry=tracts_gdf.geometry.representative_point(),
        crs=tracts_gdf.crs,
    )
    # Spatial join: which CD does each tract centroid fall into?
    joined = gpd.sjoin(tract_centroids, cds_gdf[["boro_cd", "geometry"]], how="left", predicate="within")

    out: dict[str, tuple[float, float]] = {}
    for boro_cd, group in joined.groupby("boro_cd"):
        xs = group.geometry.x.mean()
        ys = group.geometry.y.mean()
        out[boro_cd] = (ys, xs)  # (lat, lon)

    # Fill any missing CDs with the geometric fallback
    for cd_row in cds_gdf.itertuples(index=False):
        if cd_row.boro_cd not in out:
            p = cd_row.geometry.representative_point()
            out[cd_row.boro_cd] = (p.y, p.x)
    return out


def jobs_reachable(
    polygon,
    tracts_gdf,
    jobs_by_tract: dict[str, dict[str, int]],
    columns: list[str],
) -> dict[str, int]:
    """Sum each `column` of LODES jobs in tracts intersecting the polygon,
    area-weighted by intersection share.

    Inputs in EPSG:4326. Internally projects to EPSG:2263 for area math
    (state plane feet — accurate at NYC scale).

    Returns ``{col: int}`` with one entry per requested column.
    """
    out = {c: 0.0 for c in columns}
    candidates_idx = tracts_gdf.sindex.query(polygon, predicate="intersects")
    if len(candidates_idx) == 0:
        return {c: 0 for c in columns}
    candidates = tracts_gdf.iloc[candidates_idx]
    poly_proj = (
        candidates.iloc[[0]].set_geometry([polygon], crs=4326).to_crs(2263).geometry.iloc[0]
    )
    candidates_proj = candidates.to_crs(2263)
    for tract in candidates_proj.itertuples(index=False):
        geoid = getattr(tract, "geoid")
        tier_jobs = jobs_by_tract.get(geoid)
        if not tier_jobs:
            continue
        inter = tract.geometry.intersection(poly_proj)
        if inter.is_empty:
            continue
        share = inter.area / tract.geometry.area
        for col in columns:
            v = tier_jobs.get(col, 0)
            if v:
                out[col] += v * share
    return {c: int(round(v)) for c, v in out.items()}


def main() -> int:
    import geopandas as gpd

    max_min = float(os.environ.get("MAX_MINUTES", DEFAULT_MAX_MINUTES))
    dep_hour = int(os.environ.get("DEPARTURE_HOUR", DEFAULT_DEPARTURE_HOUR))

    print("[chapter-1] loading inputs...")
    feed = mta_gtfs.load_subway()
    service_date = isochrone.pick_typical_weekday(feed)
    departure = datetime(service_date.year, service_date.month, service_date.day, dep_hour, 0)
    print(f"  service date: {service_date.strftime('%A %Y-%m-%d')}, departure {departure.time()}")

    cds = gpd.read_file(basemap.geo_path("cd")).to_crs(epsg=4326)
    cds["boro_cd"] = cds["boro_cd"].astype(str).str.zfill(3)
    # Keep only the 59 residential CDs. NYC has 12 Joint Interest Areas
    # (parks, airports — JFK is one) in the DCP dataset; their codes fall
    # outside the per-borough valid range. Strict filter:
    #   MN 101-112, BX 201-212, BK 301-318, QN 401-414, SI 501-503.
    VALID_PER_BOROUGH = {1: 12, 2: 12, 3: 18, 4: 14, 5: 3}
    def _is_residential_cd(code: str) -> bool:
        b = int(code[0])
        n = int(code[1:])
        return b in VALID_PER_BOROUGH and 1 <= n <= VALID_PER_BOROUGH[b]
    cds_pop = cds[cds["boro_cd"].apply(_is_residential_cd)].copy()
    print(f"  CDs: {len(cds_pop)} (residential only; {len(cds) - len(cds_pop)} JIAs excluded)")

    tracts = gpd.read_file(basemap.geo_path("tract"))
    if tracts.crs is None:
        tracts.set_crs(4326, inplace=True)
    print(f"  tracts: {len(tracts)} (CRS {tracts.crs})")

    print("  loading LEHD LODES 2022 NY WAC...")
    lodes_df = lehd_lodes.load(year=2022)
    jobs_by_tract = lehd_lodes.aggregate_to_tracts(lodes_df)
    nyc_totals = {c: sum(t.get(c, 0) for t in jobs_by_tract.values()) for c in lehd_lodes.JOB_COLUMNS}
    print(f"  jobs_by_tract: {len(jobs_by_tract)} tracts")
    for c, total in nyc_totals.items():
        print(f"    {c}: {total:,}")

    print(f"\n[chapter-1] precomputing routing indexes...")
    t0 = _t.time()
    pre = isochrone.precompute(feed, service_date=service_date)
    print(f"  precompute: {_t.time()-t0:.1f}s ({len(pre.stop_xy)} stops, {len(pre.trip_stops)} trips)")

    print(f"\n[chapter-1] building population-weighted CD origins...")
    cd_origins = population_weighted_origins(cds_pop, tracts)
    print(f"  resolved {len(cd_origins)} CD origins from tract centroids")

    # --- isochrones for anchor CDs (high-fidelity polygons we'll ship) ---
    print(f"\n[chapter-1] anchor-CD isochrones...")
    anchor_features = []
    for boro_cd, name, borough in ANCHOR_CDS:
        origin = cd_origins[boro_cd]
        result = isochrone.compute(feed, origin, departure, max_minutes=max_min, pre=pre)
        anchor_features.append({
            "type": "Feature",
            "geometry": result.polygon.__geo_interface__,
            "properties": {
                "boro_cd": boro_cd, "borough": borough, "name": name,
                "origin_lat": origin[0], "origin_lon": origin[1],
                "max_minutes": max_min, "departure": departure.isoformat(),
                "reachable_stops": len(result.reachable_stops),
            },
        })
        print(f"  CD {boro_cd} ({name:35s})  reachable stops: {len(result.reachable_stops):>4}")

    fc_iso = {"type": "FeatureCollection", "features": anchor_features}
    iso_path = OUT / "isochrones-45min.geojson"
    iso_path.write_text(json.dumps(fc_iso, separators=(",", ":")))
    print(f"  wrote {iso_path} ({iso_path.stat().st_size:,} bytes)")

    # --- per-tract isochrones, then aggregate to CD via median ---
    # The chapter's job-access metric is a per-resident measure, so we
    # compute it from each tract's centroid (NYC tracts are designed for
    # ~4k residents, so unweighted tract aggregation ≈ population weighting)
    # then report each CD's median. Quartiles surface intra-CD variance —
    # in CDs like Jamaica, tracts near subway terminals have very different
    # access from outer-edge tracts.
    print(f"\n[chapter-1] per-tract isochrones across {len(tracts)} tracts...")
    t0 = _t.time()
    # NYC tracts only (state 36 + NYC counties)
    NYC_PREFIXES = {f"36{c}" for c in ["005", "047", "061", "081", "085"]}
    nyc_tracts = tracts[tracts["geoid"].str[:5].isin(NYC_PREFIXES)].copy()
    print(f"  filtered to {len(nyc_tracts)} NYC tracts")

    # Spatial-join tracts -> CDs once
    import geopandas as gpd
    tract_centroids = gpd.GeoDataFrame(
        {"geoid": nyc_tracts["geoid"]},
        geometry=nyc_tracts.geometry.representative_point(),
        crs=nyc_tracts.crs,
    )
    tract_cd_map = gpd.sjoin(
        tract_centroids, cds_pop[["boro_cd", "geometry"]], how="left", predicate="within"
    )[["geoid", "boro_cd"]].dropna()
    tract_to_cd = dict(zip(tract_cd_map["geoid"], tract_cd_map["boro_cd"]))
    print(f"  {len(tract_to_cd)} tracts mapped to a residential CD")

    per_tract: dict[str, dict] = {}
    centroids_by_tract = dict(zip(tract_centroids["geoid"], tract_centroids.geometry))
    for i, geoid in enumerate(tract_to_cd):
        pt = centroids_by_tract[geoid]
        origin = (pt.y, pt.x)
        result = isochrone.compute(feed, origin, departure, max_minutes=max_min, pre=pre)
        tier_jobs = jobs_reachable(result.polygon, tracts, jobs_by_tract, lehd_lodes.JOB_COLUMNS)
        per_tract[geoid] = {
            "reachable_stops": len(result.reachable_stops),
            "jobs_reachable_45min": tier_jobs["C000"],
            "ce01_reachable": tier_jobs["CE01"],
            "ce02_reachable": tier_jobs["CE02"],
            "ce03_reachable": tier_jobs["CE03"],
            "boro_cd": tract_to_cd[geoid],
        }
        if (i + 1) % 200 == 0:
            print(f"  ... {i + 1}/{len(tract_to_cd)} tracts done ({_t.time()-t0:.0f}s elapsed)")
    print(f"  all {len(per_tract)} tracts done in {_t.time()-t0:.1f}s")

    # Aggregate to CDs via median + quartiles, per tier
    from statistics import median, quantiles
    per_cd: dict[str, dict] = {}
    cd_tract_geoids: dict[str, list[str]] = {}
    for geoid, info in per_tract.items():
        cd_tract_geoids.setdefault(info["boro_cd"], []).append(geoid)

    TIER_KEYS = [
        ("jobs_reachable_45min", "C000"),
        ("ce01_reachable", "CE01"),
        ("ce02_reachable", "CE02"),
        ("ce03_reachable", "CE03"),
    ]
    for boro_cd, geoids in cd_tract_geoids.items():
        if not geoids:
            continue
        entry: dict = {
            "tract_count": len(geoids),
            "reachable_stops_max": max(per_tract[g]["reachable_stops"] for g in geoids),
        }
        for field, tier_col in TIER_KEYS:
            values = [per_tract[g][field] for g in geoids]
            entry[field] = int(median(values))
            entry[f"{field}_q1"] = int(quantiles(values, n=4)[0]) if len(values) >= 4 else int(median(values))
            entry[f"{field}_q3"] = int(quantiles(values, n=4)[2]) if len(values) >= 4 else int(median(values))
            # % of NYC's tier total
            tier_total = nyc_totals[tier_col]
            entry[f"{field}_score"] = round(entry[field] / tier_total * 100, 1) if tier_total else 0

        # Mobility Access Score = % of total NYC jobs (single-dimension).
        # The variance class uses the all-jobs (C000) spread; tier-specific
        # variance is implied by the tier scores below.
        entry["mobility_access_score"] = entry["jobs_reachable_45min_score"]
        q1, q3 = entry["jobs_reachable_45min_q1"], entry["jobs_reachable_45min_q3"]
        spread = (q3 / q1) if q1 > 0 else float("inf")
        if spread < 1.5:
            variance_class = "uniform"
        elif spread < 3.0:
            variance_class = "moderate"
        else:
            variance_class = "uneven"
        entry["variance_class"] = variance_class
        entry["q3_over_q1"] = round(spread, 2) if spread != float("inf") else None
        entry["reachable_stops"] = entry["reachable_stops_max"]
        per_cd[boro_cd] = entry
    print(f"  aggregated to {len(per_cd)} CDs")

    # Attach to CD polygons + write choropleth
    cds_out = cds_pop.copy()
    for field, _ in TIER_KEYS:
        cds_out[field] = cds_out["boro_cd"].map(lambda c, f=field: per_cd[c][f])
        cds_out[f"{field}_score"] = cds_out["boro_cd"].map(lambda c, f=field: per_cd[c][f"{f}_score"])
    cds_out["jobs_reachable_q1"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["jobs_reachable_45min_q1"])
    cds_out["jobs_reachable_q3"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["jobs_reachable_45min_q3"])
    cds_out["mobility_access_score"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["mobility_access_score"])
    cds_out["variance_class"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["variance_class"])
    cds_out["tract_count"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["tract_count"])
    cds_out["is_anchor"] = cds_out["boro_cd"].isin(ANCHOR_BORO_CDS)
    cds_out["name"] = cds_out["boro_cd"].map(lambda c: CD_NEIGHBORHOOD.get(c, c))
    cds_out["geometry"] = cds_out.geometry.simplify(0.00015, preserve_topology=True)

    geojson = json.loads(cds_out.to_json())
    for feat in geojson["features"]:
        props = feat["properties"]
        feat["properties"] = {
            "boro_cd": props["boro_cd"],
            "name": props["name"],
            "jobs_reachable_45min": props["jobs_reachable_45min"],
            "jobs_reachable_q1": props["jobs_reachable_q1"],
            "jobs_reachable_q3": props["jobs_reachable_q3"],
            "mobility_access_score": props["mobility_access_score"],
            "ce01_reachable": props["ce01_reachable"],
            "ce02_reachable": props["ce02_reachable"],
            "ce03_reachable": props["ce03_reachable"],
            "ce01_score": props["ce01_reachable_score"],
            "ce02_score": props["ce02_reachable_score"],
            "ce03_score": props["ce03_reachable_score"],
            "variance_class": props["variance_class"],
            "tract_count": props["tract_count"],
            "is_anchor": props["is_anchor"],
        }
    job_path = OUT / "job-access.geojson"
    job_path.write_text(json.dumps(geojson, separators=(",", ":")))
    print(f"  wrote {job_path} ({job_path.stat().st_size:,} bytes)")

    # Facts
    sorted_by_jobs = sorted(per_cd.items(), key=lambda kv: -kv[1]["jobs_reachable_45min"])
    sorted_by_stops = sorted(per_cd.items(), key=lambda kv: -kv[1]["reachable_stops"])
    best_jobs = sorted_by_jobs[0]
    worst_jobs = sorted_by_jobs[-1]
    best_stops = sorted_by_stops[0]
    worst_stops = sorted_by_stops[-1]

    facts = {
        "service_date": service_date.strftime("%Y-%m-%d"),
        "departure": departure.isoformat(),
        "max_minutes": max_min,
        "city_total_jobs_2022_lodes": nyc_totals["C000"],
        "city_total_by_tier": {
            "ce01_lte_15k": nyc_totals["CE01"],
            "ce02_15k_to_40k": nyc_totals["CE02"],
            "ce03_gte_40k": nyc_totals["CE03"],
        },
        "anchor_cds": [
            {
                "boro_cd": c, "name": name, "borough": b,
                "jobs_reachable_45min_median": per_cd[c]["jobs_reachable_45min"],
                "jobs_reachable_45min_q1": per_cd[c]["jobs_reachable_45min_q1"],
                "jobs_reachable_45min_q3": per_cd[c]["jobs_reachable_45min_q3"],
                "tract_count": per_cd[c]["tract_count"],
                "mobility_access_score": per_cd[c]["mobility_access_score"],
                "variance_class": per_cd[c]["variance_class"],
                "q3_over_q1": per_cd[c]["q3_over_q1"],
                "tier_scores": {
                    "ce01": per_cd[c]["ce01_reachable_score"],
                    "ce02": per_cd[c]["ce02_reachable_score"],
                    "ce03": per_cd[c]["ce03_reachable_score"],
                },
                "tier_reachable": {
                    "ce01": per_cd[c]["ce01_reachable"],
                    "ce02": per_cd[c]["ce02_reachable"],
                    "ce03": per_cd[c]["ce03_reachable"],
                },
            }
            for c, name, b in ANCHOR_CDS
        ],
        "headline": {
            "best_cd": {"boro_cd": best_jobs[0], "jobs_reachable_median": best_jobs[1]["jobs_reachable_45min"]},
            "worst_cd": {"boro_cd": worst_jobs[0], "jobs_reachable_median": worst_jobs[1]["jobs_reachable_45min"]},
            "ratio_jobs": round(best_jobs[1]["jobs_reachable_45min"] / max(worst_jobs[1]["jobs_reachable_45min"], 1), 1),
        },
    }
    facts_path = OUT / "facts.json"
    facts_path.write_text(json.dumps(facts, indent=2) + "\n")
    print(f"  wrote {facts_path}")
    print()
    print(f"[chapter-1] headlines (jobs reachable, CD median across tracts):")
    print(f"  best:  CD {best_jobs[0]} = {best_jobs[1]['jobs_reachable_45min']:,}")
    print(f"  worst: CD {worst_jobs[0]} = {worst_jobs[1]['jobs_reachable_45min']:,}")
    print(f"  ratio: {facts['headline']['ratio_jobs']}×")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
