"""Chapter 5 — Public Space & Urban Experience (first-pass scaffold).

Angle (`measuring_livability.md` §6): *cities are lived in public.* Framed
as the public realm as a third place — the space that is neither home nor
work where city life actually happens.

Goal of this first pass (mirrors Ch. 2/3/4): validate the chapter's spine
hypothesis BEFORE investing in any visual artifacts. The hypothesis is
that public-realm experience splits into **three semi-independent axes**:

  1. Open space      — % residents within a 10-min walk of a park (>= 1
                       acre) or a public plaza, pop-weighted.
  2. Street vitality — eateries + cultural venues, pop-weighted walk-
                       access composite.  [TODO]
  3. Pedestrian realm— sidewalk generosity + pedestrianization (Open
                       Streets + plazas), pop-weighted.  [TODO]

If any pair of axes co-ranks tightly (|rho| >= 0.75, the series kill
criterion), the spine collapses and the chapter gets re-spec'd.

KNOWN KILL RISK (see PLAN.md): all three axes are walk-access metrics and
walk-access tracks built density everywhere — public space, eateries,
culture, AND wide sidewalks all concentrate in the same dense cores. This
is worse than Ch. 4's near-miss (rho ~ 0.74). If the spine fires, fall
back to the vitality-vs-comfort spine (vibrancy / restorative space per
capita / pedestrian comfort). The spine test below is what decides.

Run with::

    python analyses/chapter-05/notebook.py

Status (kickoff):
  axis 1 (open space)     — parks wired; plazas pipeline TODO (k5k6-6jex)
  axis 2 (street vitality)— TODO (OSM eateries query + cultural venues)
  axis 3 (pedestrian realm)— TODO (sidewalk width decision gating, see PLAN)

Outputs (out/ inside this dir):
  facts.json    Per-CD per-axis metrics + the spine-test matrix.
  rankings.csv  Long-form per-CD per-axis rankings (sortable for QA).

Method note (shared with Ch. 3/4): all axes use the same access primitive —
% residents within a 2,640 ft (~10 min @ 3 mph) straight-line walk of the
amenity, population-weighted to CD level via B01003. Straight-line under-
counts vs a walk-network distance; acceptable for the spine test, revisit
before any headline visual.

NOTE (Punch list, PLAN.md): tract_to_cd / per_cd_population /
pct_within_walk / _acs_tract_df / _osm_points are copied verbatim from
Ch. 4's notebook. This is the 3rd reuse — promote to shared/access.py as
its own commit rather than copy a 4th time. Kept as a copy here to avoid
touching Ch. 3/4 mid-kickoff.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Load CENSUS_API_KEY (+ any other secrets) from measuring-new-york/.env so
# the ACS pop-weight fetch works without the caller exporting it by hand.
# No-op if .env is absent or python-dotenv isn't installed.
try:
    from dotenv import load_dotenv  # noqa: E402

    load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

from pipelines import (  # noqa: E402
    acs_census,
    nyc_dot_open_streets,
    nyc_dot_plazas,
    nyc_parks,
    osm_overpass,
)
from shared.cd_names import name_for  # noqa: E402
from shared.zip_to_cd import is_real_cd  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# 10-min walk @ 3 mph = 0.5 mi = 2640 ft straight-line. Same cutoff as
# Ch. 3/4, for cross-chapter consistency.
WALK_RADIUS_FT = 2640.0

# Open-space "park" cutoff — match Ch. 3/4 so the gathering-space framing
# is consistent with the green-space and civic baskets it borrows from.
OPEN_SPACE_PARK_MIN_ACRES = 1.0


# ---------- shared: tract -> CD + CD population (copied from Ch. 4) ----------

def tract_to_cd() -> "pd.Series":
    """Series keyed by tract GEOID (11-char), value = boro_cd."""
    import geopandas as gpd
    from shared import basemap

    tracts = basemap.load("tract")
    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()

    centroids = gpd.GeoDataFrame(
        {"geoid": tracts["geoid"]},
        geometry=tracts.geometry.representative_point(),
        crs=tracts.crs,
    )
    joined = gpd.sjoin(
        centroids, cds[["boro_cd", "geometry"]], how="left", predicate="within"
    )
    s = joined.set_index("geoid")["boro_cd"]
    print(f"  tract->CD: {len(s)} tracts, {s.isna().sum()} unassigned")
    return s


def _acs_tract_df(table: str) -> "pd.DataFrame":
    import pandas as pd

    raw = json.loads((acs_census.fetch(table, "tract")).read_text())
    df = pd.DataFrame(raw[1:], columns=raw[0])
    df["geoid"] = df["GEO_ID"].str[-11:]
    return df.set_index("geoid")


def per_cd_population(t2c: "pd.Series") -> "pd.Series":
    """Total population per CD (sum of B01003_001E across tracts)."""
    import pandas as pd

    pop = pd.to_numeric(_acs_tract_df("B01003")["B01003_001E"], errors="coerce")
    out = pd.DataFrame({"pop": pop})
    out["borocd"] = t2c.reindex(out.index)
    series = (
        out.dropna(subset=["borocd", "pop"])
        .groupby("borocd")["pop"].sum().round(0).astype(int)
    )
    series.name = "pop"
    return series


# ---------- shared access primitive (copied from Ch. 4) ----------

def pct_within_walk(points, t2c: "pd.Series", *, label: str) -> "pd.Series":
    """% residents within WALK_RADIUS_FT of any point in ``points``, per CD.

    ``points`` is a GeoDataFrame of amenity points/polygons in EPSG:2263.
    Per-tract straight-line distance to nearest amenity (sjoin_nearest);
    a tract is "covered" iff within WALK_RADIUS_FT; CD metric =
    pop-weighted mean of the coverage indicator (B01003). Returns [0, 1].
    """
    import geopandas as gpd
    import pandas as pd
    from shared import basemap

    points = points[points.geometry.notna() & ~points.geometry.is_empty].copy()
    points = points.reset_index(drop=True)
    points["_aid"] = points.index

    tracts = basemap.load("tract")
    centroids = gpd.GeoDataFrame(
        {"geoid": tracts["geoid"]},
        geometry=tracts.geometry.representative_point(),
        crs=tracts.crs,
    )
    nearest = gpd.sjoin_nearest(
        centroids, points[["_aid", "geometry"]], how="left", distance_col="dist_ft"
    )
    nearest = (
        nearest.sort_values("dist_ft")
        .drop_duplicates(subset=["geoid"], keep="first")
        .set_index("geoid")
    )

    pop = pd.to_numeric(_acs_tract_df("B01003")["B01003_001E"], errors="coerce")
    df = pd.DataFrame({
        "dist_ft": nearest["dist_ft"],
        "borocd": t2c.reindex(nearest.index),
        "pop": pop.reindex(nearest.index),
    }).dropna(subset=["borocd", "dist_ft", "pop"])

    df["within"] = (df["dist_ft"] <= WALK_RADIUS_FT).astype(int)
    df["within_pop"] = df["within"] * df["pop"]
    agg = df.groupby("borocd").agg(num=("within_pop", "sum"), denom=("pop", "sum"))
    series = (agg["num"] / agg["denom"]).round(4)
    series.name = label
    return series


def _osm_parks_geom(min_acres: float):
    """OSM parks as polygons (EPSG:2263), filtered to >= ``min_acres``.

    PROVISIONAL fallback for when the official DPR layer (Socrata
    enfh-gkve) is down. Builds polygons from the `parks_geom` Overpass query
    (`out geom;`): ways become Polygons from their node ring; relations become
    the union of their outer-member ways (inner holes ignored — a small
    area overcount on donut parks, immaterial to the 1-acre cut). Acreage is
    derived from polygon area (sq ft / 43,560), NOT official DPR acres, so
    it differs slightly from Ch. 3's parks. Re-run with enfh-gkve up to
    restore the authoritative layer.
    """
    import geopandas as gpd
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    raw = osm_overpass.load("parks_geom")
    geoms = []
    for el in raw.get("elements", []):
        try:
            if el.get("type") == "way" and el.get("geometry"):
                ring = [(g["lon"], g["lat"]) for g in el["geometry"]]
                if len(ring) >= 4:
                    geoms.append(Polygon(ring))
            elif el.get("type") == "relation" and el.get("members"):
                outers = []
                for m in el["members"]:
                    if m.get("type") == "way" and m.get("geometry") \
                            and m.get("role") in ("outer", "", None):
                        ring = [(g["lon"], g["lat"]) for g in m["geometry"]]
                        if len(ring) >= 4:
                            outers.append(Polygon(ring))
                if outers:
                    geoms.append(unary_union(outers))
        except Exception:
            continue

    gdf = gpd.GeoDataFrame(geometry=geoms, crs="EPSG:4326").to_crs(epsg=2263)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty & gdf.geometry.is_valid]
    gdf["acres"] = gdf.geometry.area / 43_560.0
    return gdf[gdf["acres"] >= min_acres].copy()


def _osm_points(query: str):
    """Load an OSM amenity query as a points GeoDataFrame (EPSG:2263)."""
    import geopandas as gpd
    from shapely.geometry import Point

    raw = osm_overpass.load(query)
    rows = []
    for el in raw.get("elements", []):
        lat = el.get("lat", (el.get("center") or {}).get("lat"))
        lon = el.get("lon", (el.get("center") or {}).get("lon"))
        if lat is None or lon is None:
            continue
        rows.append(Point(lon, lat))
    gdf = gpd.GeoDataFrame(geometry=rows, crs="EPSG:4326")
    return gdf.to_crs(epsg=2263)


# ---------- axis 1: open space (parks + plazas) ----------

def per_cd_open_space(t2c: "pd.Series") -> tuple["pd.Series", dict]:
    """% residents within a 10-min walk of a park (>= 1 acre) or plaza, per CD.

    Open space = *gathering* space (parks reframed from Ch. 3's green-space
    lens; see PLAN "Boundary with prior chapters"). Parks are wired now via
    the Ch. 3 pipeline; PLAZAS ARE A STUB until pipelines/nyc_dot_plazas.py
    (Socrata k5k6-6jex) is built. With plazas missing, this axis is
    parks-only and slightly undercounts dense Manhattan/Brooklyn plaza
    districts — fine for the first spine read, refine once plazas land.
    """
    import geopandas as gpd
    import pandas as pd

    # Prefer the official DPR layer (Socrata enfh-gkve); fall back to an
    # OSM-derived parks layer if it's unavailable (server 503 / network).
    # Re-running once enfh-gkve is back automatically restores the official
    # source — no code change needed.
    parks_source = "dpr:enfh-gkve"
    try:
        parks = nyc_parks.load(min_acres=OPEN_SPACE_PARK_MIN_ACRES)
        parks = parks[parks.geometry.notna() & ~parks.geometry.is_empty]
    except Exception as e:  # noqa: BLE001
        print(f"  [warn] official parks layer unavailable ({type(e).__name__}); "
              f"using OSM parks fallback (PROVISIONAL)")
        parks = _osm_parks_geom(OPEN_SPACE_PARK_MIN_ACRES)
        parks_source = "osm:parks_geom (PROVISIONAL — derived acreage)"
    print(f"  parks >= {OPEN_SPACE_PARK_MIN_ACRES:.0f} acre: {len(parks)} "
          f"[{parks_source}]")

    plazas = _load_plazas()  # None until the pipeline exists
    if plazas is not None and len(plazas):
        print(f"  DOT plazas: {len(plazas)}")
        gathering = gpd.GeoDataFrame(
            pd.concat(
                [parks[["geometry"]], plazas[["geometry"]]], ignore_index=True
            ),
            crs=parks.crs,
        )
        plaza_n = int(len(plazas))
    else:
        print("  DOT plazas: STUB (pipeline k5k6-6jex not built) — parks only")
        gathering = parks[["geometry"]].copy()
        plaza_n = None

    series = pct_within_walk(gathering, t2c, label="open_space_10min_pct")
    components = {
        "park_min_acres": OPEN_SPACE_PARK_MIN_ACRES,
        "counts": {"parks_ge_1acre": int(len(parks)), "plazas": plaza_n},
        "plaza_status": "wired" if plaza_n is not None else "stub:k5k6-6jex",
        "parks_source": parks_source,
        "parks_provisional": parks_source.startswith("osm"),
    }
    return series, components


def _load_plazas():
    """DOT Pedestrian Plazas as points/polys in EPSG:2263, or None (stub).

    TODO: build pipelines/nyc_dot_plazas.py (Socrata k5k6-6jex), mirroring
    pipelines/nyc_parks.py — fetch -> cache -> record(), load() returns a
    GeoDataFrame reprojected to EPSG:2263. Until then this returns None and
    axis 1 runs parks-only.
    """
    try:
        from pipelines import nyc_dot_plazas  # type: ignore  # noqa: F401
    except Exception:
        return None
    return nyc_dot_plazas.load()  # type: ignore[attr-defined]


# ---------- axis 2: street vitality (TODO) ----------

# OSM tags for the new `eateries` query (to add to osm_overpass.QUERIES):
#   amenity in (restaurant, cafe, bar, fast_food)  [confirm fast_food — PLAN]
# Cultural venues: amenity in (theatre, arts_centre), tourism in
#   (museum, gallery), or NYC DCLA Cultural Institutions (source TBC).

def per_cd_vitality(t2c: "pd.Series") -> tuple["pd.Series", dict]:
    """Eateries + cultural venues walk-access composite, per CD.

    Equal-weight mean of two pop-weighted walk-access %s:
      - eateries        (OSM amenity=restaurant|cafe|bar — fast_food EXCLUDED
                         per locked decision)
      - cultural venues (OSM amenity=theatre|arts_centre + tourism=museum|gallery)
    DOHMH 43nn-pn8j stays an authoritative eatery cross-check (footer only),
    not a spine input.
    """
    eateries = _osm_points("eateries")
    cultural = _osm_points("cultural")
    print(f"  eateries (OSM restaurant|cafe|bar): {len(eateries)}")
    print(f"  cultural (OSM theatre|arts_centre|museum|gallery): {len(cultural)}")

    eat_pct = pct_within_walk(eateries, t2c, label="eateries_10min_pct")
    cul_pct = pct_within_walk(cultural, t2c, label="cultural_10min_pct")
    series = ((eat_pct + cul_pct) / 2.0).round(4)
    series.name = "vitality_10min_pct"

    components = {
        "weights": "equal-weight mean of eateries + cultural walk-access %",
        "counts": {"eateries": int(len(eateries)), "cultural": int(len(cultural))},
        "source": (
            "OSM amenity=restaurant|cafe|bar (NO fast_food); "
            "amenity=theatre|arts_centre + tourism=museum|gallery"
        ),
        "subaxis_pct_range": {
            "eateries": [round(float(eat_pct.min()), 4), round(float(eat_pct.max()), 4)],
            "cultural": [round(float(cul_pct.min()), 4), round(float(cul_pct.max()), 4)],
        },
    }
    return series, components


# ---------- axis 3: pedestrian realm (TODO) ----------

def per_cd_ped_realm(t2c: "pd.Series") -> tuple["pd.Series", dict]:
    """Pedestrianization walk-access, per CD (axis 3, REDUCED for spine test).

    Pop-weighted % residents within a 10-min walk of pedestrianized public
    space = DOT plazas (k5k6-6jex, polygons) UNION Open Streets (uiay-nctu,
    line segments — id confirmed via the Socrata catalog, not guessed).

    SIDEWALK GENEROSITY IS DEFERRED. The planimetric sidewalk layer
    `vfx9-tbb6` is intractable via SODA: `SELECT *` returns ``[{}]``, the
    .geojson resource returns empty properties + null geometry, and the
    column metadata is empty (only `count(*)` works -> 50,865 rows). There is
    no CD field to aggregate on and no geometry to spatially join, so the
    locked area/length width proxy can't be computed from the API. Per the
    PLAN fallback, axis 3 ships pedestrianization-only for the spine test;
    sidewalk generosity gets added post-checkpoint from the DCP planimetric
    shapefile IF the spine survives. This is flagged in facts.json
    (`axis_reduced: true`) and is part of the checkpoint report.
    """
    import geopandas as gpd
    import pandas as pd

    plazas = nyc_dot_plazas.load()
    plazas = plazas[plazas.geometry.notna() & ~plazas.geometry.is_empty]
    open_streets = nyc_dot_open_streets.load()
    open_streets = open_streets[
        open_streets.geometry.notna() & ~open_streets.geometry.is_empty
    ]
    print(f"  DOT plazas: {len(plazas)}  Open Streets: {len(open_streets)}")

    pedestrianized = gpd.GeoDataFrame(
        pd.concat(
            [plazas[["geometry"]], open_streets[["geometry"]]], ignore_index=True
        ),
        crs=plazas.crs,
    )
    series = pct_within_walk(pedestrianized, t2c, label="ped_realm_10min_pct")

    components = {
        "components_used": ["plazas:k5k6-6jex", "open_streets:uiay-nctu"],
        "counts": {"plazas": int(len(plazas)), "open_streets": int(len(open_streets))},
        "axis_reduced": True,
        "sidewalk_status": (
            "DEFERRED: vfx9-tbb6 exposes no queryable columns/geometry via SODA "
            "(SELECT * -> [{}]; empty column metadata; count(*)=50865). "
            "Pedestrianization-only for the spine test per PLAN fallback; "
            "sidewalk width proxy to be added from the DCP planimetric "
            "shapefile post-checkpoint if the spine survives."
        ),
    }
    return series, components


# ---------- Path B: vibrancy vs. comfort (per-capita SUPPLY, not walk-access) ----------
#
# The three-basket walk-access spine fired (vitality ~ ped_realm = +0.786) on
# the density confound. Path B re-spines to measure *different forces* as
# per-capita SUPPLY (the Ch. 4 proximity != sufficiency move), so it doesn't
# just re-encode built density three ways:
#   - vibrancy     = market street life  (eateries + cultural per 1k residents)
#   - restorative  = room to breathe     (park + plaza ACRES per 1k residents)
#   - comfort      = designed-in walking  (Open Streets street-miles per 1k)
# Headline tension = vibrancy vs. restorative space.

def _assign_cd(gdf) -> "pd.Series":
    """Assign each geometry to the CD containing its representative point."""
    import geopandas as gpd
    from shared import basemap

    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)][["boro_cd", "geometry"]]
    pts = gpd.GeoDataFrame(
        geometry=gdf.geometry.representative_point(), crs=gdf.crs
    )
    joined = gpd.sjoin(pts, cds, how="left", predicate="within")
    # sjoin can duplicate on overlapping CDs; keep first match per input row.
    return joined[~joined.index.duplicated(keep="first")]["boro_cd"]


def _parks_with_acres():
    """Parks GeoDataFrame with an ``acres`` column (official, else OSM fallback)."""
    try:
        parks = nyc_parks.load(min_acres=OPEN_SPACE_PARK_MIN_ACRES)
        parks = parks[parks.geometry.notna() & ~parks.geometry.is_empty]
        return parks, "dpr:enfh-gkve"
    except Exception:  # noqa: BLE001
        return _osm_parks_geom(OPEN_SPACE_PARK_MIN_ACRES), \
            "osm:parks_geom (PROVISIONAL)"


def per_cd_vibrancy(cd_pop: "pd.Series") -> tuple["pd.Series", dict]:
    """Eateries + cultural venues per 1,000 residents, per CD."""
    import pandas as pd

    eateries = _osm_points("eateries")
    cultural = _osm_points("cultural")
    n = (_assign_cd(eateries).value_counts()
         .add(_assign_cd(cultural).value_counts(), fill_value=0))
    per1k = (n / cd_pop * 1000.0).dropna().round(3)
    per1k.name = "vibrancy_per1k"
    comp = {
        "definition": "OSM eateries (restaurant|cafe|bar) + cultural per 1k residents",
        "counts": {"eateries": int(len(eateries)), "cultural": int(len(cultural))},
        "note": "DCA Legally Operating Businesses (w7w3-xahh) can enrich this later; "
                "OSM eateries+cultural used now per PLAN ('or OSM').",
        "per1k_range": [float(per1k.min()), float(per1k.max())],
    }
    return per1k, comp


def per_cd_restorative(cd_pop: "pd.Series") -> tuple["pd.Series", dict]:
    """Park + plaza acres per 1,000 residents, per CD (restorative SUPPLY)."""
    import pandas as pd

    parks, parks_src = _parks_with_acres()
    park_acres = parks["acres"].groupby(_assign_cd(parks).values).sum()

    plazas = nyc_dot_plazas.load()
    plazas = plazas[plazas.geometry.notna() & ~plazas.geometry.is_empty].copy()
    plazas["acres"] = plazas["shape_area"] / 43_560.0
    plaza_acres = plazas["acres"].groupby(_assign_cd(plazas).values).sum()

    total_acres = park_acres.add(plaza_acres, fill_value=0)
    per1k = (total_acres / cd_pop * 1000.0).dropna().round(3)
    per1k.name = "restorative_acres_per1k"
    comp = {
        "definition": "park + plaza acres per 1k residents (supply, not walk-access)",
        "parks_source": parks_src,
        "parks_provisional": parks_src.startswith("osm"),
        "per1k_range": [float(per1k.min()), float(per1k.max())],
    }
    return per1k, comp


def per_cd_comfort(cd_pop: "pd.Series") -> tuple["pd.Series", dict]:
    """Open Streets centerline-miles per 1,000 residents, per CD."""
    import pandas as pd

    os_lines = nyc_dot_open_streets.load()
    os_lines = os_lines[
        os_lines.geometry.notna() & ~os_lines.geometry.is_empty
    ].copy()
    os_lines["miles"] = os_lines.geometry.length / 5280.0  # EPSG:2263 feet
    miles = os_lines["miles"].groupby(_assign_cd(os_lines).values).sum()
    per1k = (miles / cd_pop * 1000.0).reindex(cd_pop.index).fillna(0.0).round(4)
    per1k.name = "comfort_os_miles_per1k"
    comp = {
        "definition": "Open Streets street-miles per 1k residents (sidewalk deferred)",
        "open_streets_segments": int(len(os_lines)),
        "axis_reduced": True,
        "sidewalk_status": "deferred (vfx9-tbb6 unusable via SODA; add DCP shapefile later)",
        "per1k_range": [float(per1k.min()), float(per1k.max())],
    }
    return per1k, comp


# ---------- anchors + headline render (Path B scatter) ----------

# 5 anchors, 1 per borough, spanning the vibrancy x restorative quadrants.
# 206/503 reuse Ch. 4's anchors for series coherence.
#   105 Midtown            — MN — vibrant but no room to breathe (surprise)
#   301 Williamsburg       — BK — vibrant, tight on open space
#   411 Bayside/Little Neck— QN — quiet residential comfort (lo vib, hi room)
#   206 Belmont/E. Tremont — BX — short on both (double deficit)
#   503 Tottenville        — SI — the most restorative CD in the city
ANCHOR_CDS = ["105", "301", "411", "206", "503"]


def _quadrant_class(vib, res, vib_med, res_med) -> str:
    hi_v, hi_r = vib >= vib_med, res >= res_med
    return ("lively_roomy" if hi_v and hi_r else
            "lively_tight" if hi_v and not hi_r else
            "quiet_roomy" if (not hi_v) and hi_r else "quiet_tight")


def render_headline(frame: "pd.DataFrame") -> dict:
    """Render the Path-B headline: vibrancy-vs-restorative scatter + geojson.

    Writes:
      out/vibrancy-vs-restorative.svg   static headline scatter (the chapter)
      out/public-space.geojson          per-CD all axes + ranks + quadrant
                                         class, display-CRS, 50-ft simplified,
                                         consumed by <NycMap>/<NeighborhoodExplorer>
    """
    import matplotlib.pyplot as plt
    from shared import basemap, palette

    palette.for_matplotlib()
    f = frame.set_index("borocd")
    vib_med = float(f["vibrancy_per1k"].median())
    res_med = float(f["restorative_acres_per1k"].median())

    QCOLOR = {
        "lively_tight": palette.ALERT,      # vibrant, no room — the tension
        "quiet_roomy": palette.ACCENT,      # room, little life
        "lively_roomy": "#4a8a85",          # the rare both
        "quiet_tight": palette.MUTED,       # short on both
    }
    cls = {cd: _quadrant_class(r["vibrancy_per1k"], r["restorative_acres_per1k"],
                               vib_med, res_med)
           for cd, r in f.iterrows()}

    # ---- geojson sibling for <NycMap> ----
    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()
    cds["geometry"] = cds.geometry.simplify(50.0, preserve_topology=True)
    geo = cds[["boro_cd", "geometry"]].copy()
    geo["name"] = geo["boro_cd"].map(name_for)
    for col in ["vibrancy_per1k", "restorative_acres_per1k", "comfort_os_miles_per1k",
                "open_space_10min_pct", "vitality_10min_pct", "ped_realm_10min_pct"]:
        geo[col] = f[col].reindex(geo["boro_cd"].values).values
    geo["rank_vibrancy"] = geo["vibrancy_per1k"].rank(ascending=False, method="min").astype("Int64")
    geo["rank_restorative"] = geo["restorative_acres_per1k"].rank(ascending=False, method="min").astype("Int64")
    geo["quadrant"] = geo["boro_cd"].map(cls)
    geojson_path = OUT / "public-space.geojson"
    basemap.to_display(geo).to_file(geojson_path, driver="GeoJSON")
    print(f"[wrote] {geojson_path}  ({geojson_path.stat().st_size:,} bytes)")

    # ---- headline scatter ----
    fig, ax = plt.subplots(figsize=(8.5, 8.0))
    for cd, r in f.iterrows():
        c = QCOLOR[cls[cd]]
        is_anchor = cd in ANCHOR_CDS
        ax.scatter(r["vibrancy_per1k"], r["restorative_acres_per1k"],
                   s=70 if is_anchor else 32, c=c,
                   edgecolor=palette.TEXT if is_anchor else "none",
                   linewidth=0.8, zorder=3 if is_anchor else 2,
                   alpha=0.95 if is_anchor else 0.6)
    ax.axvline(vib_med, color=palette.BORDER, lw=1, zorder=1)
    ax.axhline(res_med, color=palette.BORDER, lw=1, zorder=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    for cd in ANCHOR_CDS:
        r = f.loc[cd]
        ax.annotate(f"  {name_for(cd).split(' / ')[0]}",
                    xy=(r["vibrancy_per1k"], r["restorative_acres_per1k"]),
                    fontsize=8.5, color=palette.TEXT, va="center", zorder=4)
    ax.set_xlabel("Vibrancy — eateries + cultural venues per 1,000 residents (log)")
    ax.set_ylabel("Restorative space — park + plaza acres per 1,000 residents (log)")
    ax.set_title("Lively or roomy — rarely both", fontsize=15, loc="left", pad=8)
    ax.text(0.0, 1.012,
            f"NYC community districts · vibrancy ⊥ restorative space (ρ = "
            f"{f['vibrancy_per1k'].rank().corr(f['restorative_acres_per1k'].rank()):+.2f})",
            transform=ax.transAxes, fontsize=9.5, color=palette.TEXT_SECONDARY,
            ha="left", va="bottom")
    svg_path = OUT / "vibrancy-vs-restorative.svg"
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[wrote] {svg_path}  ({svg_path.stat().st_size:,} bytes)")

    return {
        "anchors": ANCHOR_CDS,
        "vibrancy_median_per1k": round(vib_med, 3),
        "restorative_median_per1k": round(res_med, 3),
        "quadrant_counts": {k: int(v) for k, v in
                            __import__("collections").Counter(cls.values()).items()},
        "files": {"scatter_svg": svg_path.name, "geojson": geojson_path.name},
    }


# ---------- spine test (copied from Ch. 4) ----------

def spine_test(axes: dict) -> dict:
    """Spearman rho on every available axis pair; flag |rho| >= 0.75."""
    import itertools

    import pandas as pd

    present = {k: v for k, v in axes.items() if v is not None}
    if len(present) < 2:
        print(f"\n[spine] only {len(present)} axis ready — test deferred "
              f"until >=2 axes are wired.")
        return {"ready": False, "axes_ready": list(present)}

    frame = pd.DataFrame(present).dropna()
    # Spearman rho = Pearson correlation of the ranks (no scipy dependency).
    ranks = frame.rank()
    result = {"ready": True, "n": int(len(frame)), "pairs": {}, "kill": False}
    print(f"\n[spine] n = {len(frame)} CDs")
    for a, b in itertools.combinations(present, 2):
        rho = ranks[a].corr(ranks[b])
        fires = bool(abs(rho) >= 0.75)
        result["pairs"][f"{a} ~ {b}"] = round(float(rho), 3)
        result["kill"] = result["kill"] or fires
        print(f"  {a:>22} ~ {b:<22} rho = {rho:+.3f}  "
              f"{'<<< KILL' if fires else 'ok'}")
    print(f"[spine] verdict: "
          f"{'SPINE COLLAPSES — re-spec (path B)' if result['kill'] else 'spine survives'}")
    return result


def main() -> int:
    import pandas as pd

    print("[ch.5] tract->CD + CD population (ACS B01003)")
    t2c = tract_to_cd()
    cd_pop = per_cd_population(t2c)

    print("[ch.5] axis 1 — open space (parks + plazas)")
    open_space, open_components = per_cd_open_space(t2c)

    print("[ch.5] axis 2 — street vitality (eateries + cultural)")
    vitality, vitality_components = per_cd_vitality(t2c)

    print("[ch.5] axis 3 — pedestrian realm (pedestrianization; sidewalk deferred)")
    ped_realm, ped_components = per_cd_ped_realm(t2c)

    axes = {
        "open_space_10min_pct": open_space,
        "vitality_10min_pct": vitality,
        "ped_realm_10min_pct": ped_realm,
    }
    spine = spine_test(axes)

    # ---- Path B: vibrancy vs. comfort (per-capita supply) ----
    print("\n[ch.5] PATH B — vibrancy vs. restorative space vs. comfort (per-capita)")
    vibrancy, vibrancy_c = per_cd_vibrancy(cd_pop)
    restorative, restorative_c = per_cd_restorative(cd_pop)
    comfort, comfort_c = per_cd_comfort(cd_pop)
    path_b_axes = {
        "vibrancy_per1k": vibrancy,
        "restorative_acres_per1k": restorative,
        "comfort_os_miles_per1k": comfort,
    }
    print("[path-B] headline tension = vibrancy vs. restorative space")
    path_b_spine = spine_test(path_b_axes)

    # assemble per-CD frame for the artifacts (basket axes + path-B axes)
    ready = {k: v for k, v in axes.items() if v is not None}
    frame = pd.DataFrame({**ready, **path_b_axes})
    frame["pop"] = cd_pop.reindex(frame.index)
    frame.index.name = "borocd"
    frame = frame.reset_index()
    frame["cd_name"] = frame["borocd"].map(name_for)

    # quadrant class on the frame (for rankings.csv + anchor table)
    vib_med = float(frame["vibrancy_per1k"].median())
    res_med = float(frame["restorative_acres_per1k"].median())
    frame["quadrant"] = [
        _quadrant_class(v, r, vib_med, res_med)
        for v, r in zip(frame["vibrancy_per1k"], frame["restorative_acres_per1k"])
    ]
    rankings = frame.sort_values("vibrancy_per1k", ascending=False)
    rankings.to_csv(OUT / "rankings.csv", index=False)

    print("\n[ch.5] render headline (Path-B scatter + geojson)")
    render = render_headline(frame)

    anchor_table = [
        {
            "borocd": cd,
            "name": name_for(cd),
            "vibrancy_per1k": round(float(frame.set_index("borocd").loc[cd, "vibrancy_per1k"]), 2),
            "restorative_acres_per1k": round(float(frame.set_index("borocd").loc[cd, "restorative_acres_per1k"]), 2),
            "comfort_os_miles_per1k": round(float(frame.set_index("borocd").loc[cd, "comfort_os_miles_per1k"]), 4),
            "quadrant": frame.set_index("borocd").loc[cd, "quadrant"],
        }
        for cd in ANCHOR_CDS
    ]

    facts = {
        "chapter": 5,
        "title_working": "Public Space & Urban Experience",
        "walk_radius_ft": WALK_RADIUS_FT,
        "n_cds": int(frame["borocd"].nunique()),
        "axes_ready": list(ready),
        "open_space": {
            **open_components,
            "pct_range": (
                [round(float(open_space.min()), 4), round(float(open_space.max()), 4)]
                if open_space is not None else None
            ),
        },
        "vitality": vitality_components,
        "ped_realm": ped_components,
        "spine_test": spine,
        "path_b": {
            "framing": "vibrancy vs. restorative space (headline) + pedestrian comfort",
            "vibrancy": vibrancy_c,
            "restorative": restorative_c,
            "comfort": comfort_c,
            "correlations": path_b_spine,
            "anchors": anchor_table,
            "render": render,
        },
    }
    (OUT / "facts.json").write_text(json.dumps(facts, indent=2) + "\n")
    print(f"\n[ch.5] wrote out/facts.json + out/rankings.csv "
          f"({len(frame)} CDs, basket axes: {facts['axes_ready']} + path-B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
