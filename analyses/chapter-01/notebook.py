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

# Plan §10: the 5 anchor CDs for Ch. 1.
ANCHOR_CDS = [
    ("105", "Midtown East", "MN"),
    ("301", "Williamsburg / Greenpoint", "BK"),
    ("212", "Wakefield / Williamsbridge", "BX"),
    ("410", "South Ozone Park / Howard Beach", "QN"),
    ("414", "Rockaway", "QN"),
]
ANCHOR_BORO_CDS = {c for c, _, _ in ANCHOR_CDS}
ANCHOR_NAME = {c: name for c, name, _ in ANCHOR_CDS}

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


def jobs_reachable(polygon, tracts_gdf, jobs_by_tract: dict[str, int]) -> int:
    """Sum jobs in tracts intersecting the polygon, weighted by area share.

    Inputs in EPSG:4326. Internally projects to EPSG:2263 for area math
    (state plane feet — accurate at NYC scale).
    """
    candidates_idx = tracts_gdf.sindex.query(polygon, predicate="intersects")
    if len(candidates_idx) == 0:
        return 0
    candidates = tracts_gdf.iloc[candidates_idx]
    # Project for area math
    poly_proj = (
        candidates.iloc[[0]].set_geometry([polygon], crs=4326).to_crs(2263).geometry.iloc[0]
    )
    candidates_proj = candidates.to_crs(2263)
    total = 0.0
    for tract in candidates_proj.itertuples(index=False):
        geoid = getattr(tract, "geoid")
        jobs = jobs_by_tract.get(geoid, 0)
        if jobs == 0:
            continue
        inter = tract.geometry.intersection(poly_proj)
        if inter.is_empty:
            continue
        share = inter.area / tract.geometry.area
        total += jobs * share
    return int(round(total))


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
    print(f"  jobs_by_tract: {len(jobs_by_tract)} tracts, {sum(jobs_by_tract.values()):,} total jobs")

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
        jobs = jobs_reachable(result.polygon, tracts, jobs_by_tract)
        per_tract[geoid] = {
            "reachable_stops": len(result.reachable_stops),
            "jobs_reachable_45min": jobs,
            "boro_cd": tract_to_cd[geoid],
        }
        if (i + 1) % 200 == 0:
            print(f"  ... {i + 1}/{len(tract_to_cd)} tracts done ({_t.time()-t0:.0f}s elapsed)")
    print(f"  all {len(per_tract)} tracts done in {_t.time()-t0:.1f}s")

    # Aggregate to CDs via median + quartiles
    from statistics import median, quantiles
    per_cd: dict[str, dict] = {}
    cd_tracts: dict[str, list[int]] = {}
    for geoid, info in per_tract.items():
        cd_tracts.setdefault(info["boro_cd"], []).append(info["jobs_reachable_45min"])
    for boro_cd, values in cd_tracts.items():
        if not values:
            continue
        sorted_vals = sorted(values)
        q = quantiles(values, n=4) if len(values) >= 4 else [median(values)] * 3
        per_cd[boro_cd] = {
            "jobs_reachable_45min": int(median(values)),
            "jobs_reachable_45min_q1": int(q[0]),
            "jobs_reachable_45min_q3": int(q[2]),
            "jobs_reachable_45min_min": int(min(values)),
            "jobs_reachable_45min_max": int(max(values)),
            "tract_count": len(values),
            # also surface the *best* tract in the CD (where stops are highest)
            "reachable_stops_max": max(per_tract[g]["reachable_stops"] for g in per_tract if per_tract[g]["boro_cd"] == boro_cd),
        }
        per_cd[boro_cd]["reachable_stops"] = per_cd[boro_cd]["reachable_stops_max"]  # alias for choropleth
    print(f"  aggregated to {len(per_cd)} CDs")

    # Attach to CD polygons + write choropleth
    cds_out = cds_pop.copy()
    cds_out["jobs_reachable_45min"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["jobs_reachable_45min"])
    cds_out["jobs_reachable_q1"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["jobs_reachable_45min_q1"])
    cds_out["jobs_reachable_q3"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["jobs_reachable_45min_q3"])
    cds_out["tract_count"] = cds_out["boro_cd"].map(lambda c: per_cd[c]["tract_count"])
    cds_out["is_anchor"] = cds_out["boro_cd"].isin(ANCHOR_BORO_CDS)
    cds_out["name"] = cds_out["boro_cd"].map(lambda c: ANCHOR_NAME.get(c, ""))
    # simplify geometry for size
    cds_out["geometry"] = cds_out.geometry.simplify(0.00015, preserve_topology=True)

    geojson = json.loads(cds_out.to_json())
    for feat in geojson["features"]:
        props = feat["properties"]
        feat["properties"] = {
            "boro_cd": props["boro_cd"],
            "jobs_reachable_45min": props["jobs_reachable_45min"],
            "jobs_reachable_q1": props["jobs_reachable_q1"],
            "jobs_reachable_q3": props["jobs_reachable_q3"],
            "tract_count": props["tract_count"],
            "is_anchor": props["is_anchor"],
            "name": props["name"],
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
        "city_total_jobs_2022_lodes": sum(jobs_by_tract.values()),
        "anchor_cds": [
            {
                "boro_cd": c, "name": name, "borough": b,
                "jobs_reachable_45min_median": per_cd[c]["jobs_reachable_45min"],
                "jobs_reachable_45min_q1": per_cd[c]["jobs_reachable_45min_q1"],
                "jobs_reachable_45min_q3": per_cd[c]["jobs_reachable_45min_q3"],
                "tract_count": per_cd[c]["tract_count"],
                "share_of_city_jobs_pct": round(
                    per_cd[c]["jobs_reachable_45min"] / sum(jobs_by_tract.values()) * 100, 1
                ),
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
