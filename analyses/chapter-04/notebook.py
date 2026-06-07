"""Chapter 4 — Access to Daily Needs (first-pass scaffold).

Angle (`measuring_livability.md` §5): *livability is partly the absence
of logistical friction.* Framed as the 15-minute neighborhood — how much
effort the ordinary errands of a household take.

Goal of this first pass (mirrors Ch. 2/3): validate the chapter's spine
hypothesis BEFORE investing in any visual artifacts. The hypothesis is
that access to daily needs splits into **three semi-independent axes**:

  1. Food access     — % residents within a 10-min walk of a full-service
                       grocery (NYS Retail Food Stores >= 5,000 sqft;
                       OSM supermarkets as a completeness cross-check),
                       pop-weighted.
  2. Care access     — pharmacies + childcare + healthcare, pop-weighted
                       walk-access (within-axis composite).  [TODO]
  3. Civic/learning  — schools + libraries + parks, pop-weighted walk-
                       access.  [TODO]

If any pair of axes co-ranks tightly (|rho| >= 0.75, Ch. 2's kill
criterion), the spine collapses and the chapter gets re-spec'd.

KNOWN KILL RISK (see PLAN.md): all three axes are walk-access metrics
and walk-access tracks built density everywhere, so the basket axes may
co-rank purely on density. If the spine fires, fall back to the
dimensions-of-access spine (proximity / per-capita sufficiency /
car-reliance). The spine test below is what decides.

Run with::

    python analyses/chapter-04/notebook.py

Status (2026-06-06):
  axis 1 (food)   — wired end-to-end (NYS 9a8c-vfzj + OSM supermarkets)
  axis 2 (care)   — TODO (pharmacies wired in OSM; childcare/healthcare
                    pipelines not built yet)
  axis 3 (civic)  — TODO (schools+parks reusable; libraries pipeline TODO)

Outputs (out/ inside this dir):
  facts.json    Per-CD per-axis metrics + the spine-test matrix.
  rankings.csv  Long-form per-CD per-axis rankings (sortable for QA).

Method note (shared with Ch. 3): all axes use the same access primitive —
% residents within a 2,640 ft (~10 min @ 3 mph) straight-line walk of the
amenity, population-weighted to CD level via B01003. Straight-line under-
counts vs a walk-network distance; acceptable for the spine test, revisit
before any headline visual.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from pipelines import (  # noqa: E402
    acs_census,
    nyc_childcare,
    nyc_facdb,
    nyc_parks,
    nys_food_stores,
    osm_overpass,
)
from shared.cd_names import name_for  # noqa: E402
from shared.zip_to_cd import is_real_cd  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

# 10-min walk @ 3 mph = 0.5 mi = 2640 ft straight-line. Same cutoff as
# Ch. 3 green-space, for cross-chapter consistency.
WALK_RADIUS_FT = 2640.0


# ---------- shared: tract -> CD + CD population (mirrors Ch. 3) ----------

def tract_to_cd() -> "pd.Series":
    """Series keyed by tract GEOID (11-char), value = boro_cd.

    Centroid-sjoin pattern; tracts nest mostly inside CDs.
    """
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


# ---------- shared access primitive ----------

def pct_within_walk(points, t2c: "pd.Series", *, label: str) -> "pd.Series":
    """% residents within WALK_RADIUS_FT of any point in ``points``, per CD.

    ``points`` is a GeoDataFrame of amenity points/polygons in EPSG:2263.
    For each tract, straight-line distance from its representative point
    to the nearest amenity (``sjoin_nearest``); a tract is "covered" iff
    within WALK_RADIUS_FT; CD metric = pop-weighted mean of the coverage
    indicator (B01003). Returns a value in [0, 1] per CD.
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


# ---------- axis 1: food access ----------

def per_cd_food(t2c: "pd.Series") -> tuple["pd.Series", dict]:
    """% residents within 10-min walk of a full-service grocery, per CD.

    NYS Retail Food Stores (>= SUPERMARKET_MIN_SQFT) is the spine source.
    OSM supermarkets are loaded only as a completeness cross-check — the
    count delta goes in the chapter footer, not the spine.
    """
    stores = nys_food_stores.load(min_sqft=nys_food_stores.SUPERMARKET_MIN_SQFT)
    print(f"  NYS groceries >= {nys_food_stores.SUPERMARKET_MIN_SQFT:.0f} sqft: "
          f"{len(stores)}")
    series = pct_within_walk(stores, t2c, label="food_10min_pct")

    crosscheck = {"nys_supermarkets": int(len(stores))}
    try:
        osm = _osm_points("supermarkets")
        crosscheck["osm_supermarkets"] = int(len(osm))
        print(f"  OSM supermarkets (cross-check): {len(osm)}")
    except Exception as e:  # noqa: BLE001 — cross-check only, never blocks spine
        crosscheck["osm_supermarkets"] = None
        crosscheck["osm_error"] = str(e)
        print(f"  OSM cross-check skipped: {e}")
    return series, crosscheck


# ---------- food *quality*: a store is not a supermarket ----------
#
# Proximity to a food store != proximity to fresh produce. Most NYC food
# stores are small (bodegas/corner stores) that don't carry full fresh
# selections. We measure, per CD, the share of NYS-licensed food stores
# that are full-service groceries (>= SUPERMARKET_MIN_SQFT), among stores
# with a reported square footage. Low share = bodega-dominated = the
# "fresh-food desert" pattern.

def per_cd_supermarket_share(t2c: "pd.Series") -> tuple["pd.Series", dict]:
    """% of a CD's food stores that are full-service groceries, + summary."""
    import geopandas as gpd
    import pandas as pd
    from shared import basemap

    g = nys_food_stores.load(min_sqft=None)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["sqft"] = pd.to_numeric(g.get("square_footage"), errors="coerce")
    g = g[g["sqft"].notna()].copy()
    g["is_super"] = (g["sqft"] >= nys_food_stores.SUPERMARKET_MIN_SQFT).astype(int)

    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()
    j = gpd.sjoin(g, cds[["boro_cd", "geometry"]], how="left",
                  predicate="within").dropna(subset=["boro_cd"])
    agg = j.groupby("boro_cd").agg(stores=("is_super", "size"),
                                   supers=("is_super", "sum"))
    share = (100.0 * agg["supers"] / agg["stores"]).round(1)
    share.name = "supermarket_share_pct"

    n_total = int(len(g))
    n_super = int(g["is_super"].sum())
    bottom = share[agg["stores"] >= 20].sort_values().head(5)
    summary = {
        "stores_total": n_total,
        "supermarkets": n_super,
        "supermarket_share_citywide_pct": round(100.0 * n_super / n_total, 1),
        "small_store_share_pct": round(100.0 * (n_total - n_super) / n_total, 1),
        "small_per_supermarket": round((n_total - n_super) / n_super, 1),
        "most_bodega_dominated": [
            {"borocd": cd, "name": name_for(cd),
             "supermarket_share_pct": float(share[cd]),
             "bodega_per_supermarket": round(
                 (int(agg.loc[cd, "stores"]) - int(agg.loc[cd, "supers"]))
                 / max(int(agg.loc[cd, "supers"]), 1), 1)}
            for cd in bottom.index
        ],
    }
    print(f"  supermarket share: {summary['supermarket_share_citywide_pct']}% "
          f"citywide ({summary['small_per_supermarket']} small stores per "
          f"supermarket); most bodega-dominated: "
          f"{summary['most_bodega_dominated'][0]['name']} "
          f"({summary['most_bodega_dominated'][0]['supermarket_share_pct']}%)")
    return share, summary


# ---------- axis 2: care access (TODO) ----------

CHILDCARE_FACGROUP = "DAY CARE AND PRE-KINDERGARTEN"
HEALTHCARE_FACSUBGRP = "HOSPITALS AND CLINICS"


def per_cd_care(t2c: "pd.Series") -> tuple["pd.Series", dict]:
    """Pharmacies + childcare + healthcare walk-access composite, per CD.

    Equal-weight (1/3 each) mean of three pop-weighted walk-access
    coverage shares — the "family / health logistics" basket:
      - pharmacies (OSM ``amenity=pharmacy``)
      - childcare  (FacDB DAY CARE AND PRE-KINDERGARTEN group: day care,
                    DOE UPK, preschools)
      - healthcare (FacDB HOSPITALS AND CLINICS)

    NOTE — proximity only. The intended *sufficiency* metric (childcare
    slots per child under 5) is NOT computed here: FacDB's ``capacity``
    column is all-zero for the day-care group, so we can count facilities
    but not slots. Sufficiency awaits an OCFS capacity source and feeds
    the dimensions-of-access fallback spine (see PLAN.md), not this axis.
    """
    pharm = _osm_points("pharmacies")
    print(f"  OSM pharmacies: {len(pharm)}")
    childcare = nyc_facdb.load(facgroup=CHILDCARE_FACGROUP)
    print(f"  FacDB childcare/UPK: {len(childcare)}")
    health = nyc_facdb.load(HEALTHCARE_FACSUBGRP)
    print(f"  FacDB hospitals & clinics: {len(health)}")

    ph = pct_within_walk(pharm, t2c, label="pharmacy_10min_pct")
    cc = pct_within_walk(childcare, t2c, label="childcare_10min_pct")
    hc = pct_within_walk(health, t2c, label="healthcare_10min_pct")

    import pandas as pd

    comp = pd.concat([ph, cc, hc], axis=1)
    series = comp.mean(axis=1).round(4)
    series.name = "care_10min_pct"
    components = {
        "weights": {"pharmacies": 1 / 3, "childcare": 1 / 3, "healthcare": 1 / 3},
        "counts": {
            "pharmacies": int(len(pharm)),
            "childcare": int(len(childcare)),
            "healthcare": int(len(health)),
        },
        "sufficiency_note": (
            "proximity only; FacDB capacity is all-zero for day care so "
            "slot-sufficiency is deferred to an OCFS source + fallback spine"
        ),
    }
    return series, components


# ---------- axis 3: civic / learning access (TODO) ----------

CIVIC_PARK_MIN_ACRES = 1.0


def per_cd_civic(t2c: "pd.Series") -> tuple["pd.Series", dict]:
    """Schools + libraries + parks walk-access composite, per CD.

    Equal-weight (1/3 each) mean of three pop-weighted walk-access
    coverage shares — the "public daily-life infrastructure" basket:
      - schools   (OSM ``amenity=school``)
      - libraries (FacDB ``PUBLIC LIBRARIES``, all three systems)
      - parks     (NYC Parks Properties >= 1 acre, reused from Ch. 3)
    Weights are equal by default and stated here per plan §9 (within-
    chapter composite). Returns the composite series + per-component
    series for QA / the methodology footer.
    """
    schools = _osm_points("schools")
    print(f"  OSM schools: {len(schools)}")
    libraries = nyc_facdb.load("PUBLIC LIBRARIES")
    print(f"  FacDB public libraries: {len(libraries)}")
    parks = nyc_parks.load(min_acres=CIVIC_PARK_MIN_ACRES)
    parks = parks[parks.geometry.notna() & ~parks.geometry.is_empty]
    print(f"  parks >= {CIVIC_PARK_MIN_ACRES:.0f} acre: {len(parks)}")

    sch = pct_within_walk(schools, t2c, label="school_10min_pct")
    lib = pct_within_walk(libraries, t2c, label="library_10min_pct")
    prk = pct_within_walk(parks, t2c, label="park_10min_pct")

    import pandas as pd

    comp = pd.concat([sch, lib, prk], axis=1)
    series = comp.mean(axis=1).round(4)
    series.name = "civic_10min_pct"
    components = {
        "weights": {"schools": 1 / 3, "libraries": 1 / 3, "parks": 1 / 3},
        "counts": {
            "schools": int(len(schools)),
            "libraries": int(len(libraries)),
            "parks_ge_1acre": int(len(parks)),
        },
    }
    return series, components


# ---------- sufficiency: childcare slots per child under 5 ----------
#
# The chapter's pivot (PLAN.md): proximity is largely a density signal;
# the harder, more interesting question is whether what's nearby is
# *enough*. We test it on childcare — the amenity where "one nearby"
# most often hides "no room in it." Sufficiency = under-5 childcare slots
# per 100 children under 5, per CD. If sufficiency does NOT track
# childcare proximity, the proximity != sufficiency thesis holds.

def childcare_points():
    """Combined under-5 childcare facilities (DOHMH centers + OCFS home).

    Disjoint sets: DOHMH = NYC Health Code centers (under-5), OCFS = NYS
    home-based family day care (DCC centers are absent from OCFS NYC, so
    no double-count). Each point carries a numeric ``slots`` column.
    """
    import pandas as pd

    dohmh = nyc_childcare.load("dohmh")
    ocfs = nyc_childcare.load("ocfs")
    print(f"  DOHMH centers: {len(dohmh)} ({dohmh['slots'].sum():,.0f} slots)")
    print(f"  OCFS home-based: {len(ocfs)} ({ocfs['slots'].sum():,.0f} slots)")
    cols = ["slots", "geometry"]
    combined = pd.concat([dohmh[cols], ocfs[cols]], ignore_index=True)
    combined = combined.dropna(subset=["geometry"])
    return combined


def per_cd_childcare_slots(points, t2c: "pd.Series") -> "pd.Series":
    """Sum childcare slots to CD via point-in-polygon (EPSG:2263)."""
    import geopandas as gpd
    from shared import basemap

    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()
    joined = gpd.sjoin(points, cds[["boro_cd", "geometry"]], how="left",
                       predicate="within")
    series = joined.dropna(subset=["boro_cd"]).groupby("boro_cd")["slots"].sum()
    series.name = "childcare_slots"
    return series


def per_cd_children_under5(t2c: "pd.Series") -> "pd.Series":
    """Children under 5 per CD (B01001_003E male + B01001_027E female)."""
    import pandas as pd

    df = _acs_tract_df("B01001")
    kids = (pd.to_numeric(df["B01001_003E"], errors="coerce").fillna(0)
            + pd.to_numeric(df["B01001_027E"], errors="coerce").fillna(0))
    out = pd.DataFrame({"kids": kids})
    out["borocd"] = t2c.reindex(out.index)
    series = (out.dropna(subset=["borocd"]).groupby("borocd")["kids"]
              .sum().round(0).astype(int))
    series.name = "children_under5"
    return series


def childcare_sufficiency(t2c: "pd.Series") -> tuple["pd.Series", "pd.Series", dict]:
    """Slots per 100 children under 5, per CD. Returns (sufficiency,
    childcare proximity, summary). Proximity is recomputed from the same
    combined facility points so the two metrics are self-consistent."""
    pts = childcare_points()
    slots = per_cd_childcare_slots(pts, t2c)
    kids = per_cd_children_under5(t2c)
    prox = pct_within_walk(pts, t2c, label="childcare_prox_pct")

    import pandas as pd

    suff = (100.0 * slots / kids.reindex(slots.index)).round(1)
    suff.name = "childcare_slots_per_100_u5"
    summary = {
        "total_slots": int(slots.sum()),
        "total_children_under5": int(kids.sum()),
        "citywide_slots_per_100_u5": round(float(100.0 * slots.sum() / kids.sum()), 1),
        "suff_range": [round(float(suff.min()), 1), round(float(suff.max()), 1)],
    }
    return suff, prox, summary


# ---------- spine test ----------

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
    # Spearman rho = Pearson correlation of the ranks. Computed this way
    # to avoid a scipy dependency (df.corr(method="spearman") needs it).
    ranks = frame.rank()
    result = {"ready": True, "n": int(len(frame)), "pairs": {}, "kill": False}
    print(f"\n[spine] n = {len(frame)} CDs")
    for a, b in itertools.combinations(present, 2):
        rho = ranks[a].corr(ranks[b])
        fires = bool(abs(rho) >= 0.75)
        result["pairs"][f"{a} ~ {b}"] = round(float(rho), 3)
        result["kill"] = result["kill"] or fires
        print(f"  {a:>18} ~ {b:<18} rho = {rho:+.3f}  "
              f"{'<<< KILL' if fires else 'ok'}")
    print(f"[spine] verdict: {'SPINE COLLAPSES — re-spec' if result['kill'] else 'spine survives'}")
    return result


# ---------- headline render: geojson (for <NycMap>) + static SVG ----------

# Anchors for the chapter (1 per borough), used for SVG labels and prose.
ANCHOR_CDS = ["405", "316", "112", "206", "503"]

# "Walkable" cutoff for the access-class quadrant map: a CD where at least
# this share of residents are within a 10-min walk (averaged across the
# food/care/civic baskets). Stored as a percentage (proximity_mean × 100).
# 85% cleanly separates the genuine car-dependent errand deserts (Staten
# Island, eastern Queens, Co-op City — all <= 84%) from dense districts
# that are walkable but may still be undersupplied.
WALKABLE_PCT = 85.0


def render_headline(frame: "pd.DataFrame") -> Path:
    """Per-CD display-CRS geojson + a static childcare-sufficiency SVG.

    Bakes the chapter's three map axes into one geojson so the
    ``<NycMap>`` axis-toggle switches without re-fetching:
      food_10min_pct              % residents within 10-min walk of grocery
      proximity_mean              combined daily-needs walk-access (%, 0-100)
      childcare_slots_per_100_u5  licensed slots per 100 children under 5
    ``rank_*`` are 1-based (1 = best on that axis). Writes:
      out/daily-needs.geojson         consumed by <NycMap>/<NeighborhoodExplorer>
      out/childcare-sufficiency.svg   static headline visual / fallback
    """
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from shared import basemap, palette

    palette.for_matplotlib()
    f = frame.set_index("borocd")

    cds = basemap.load("cd")
    cds = cds[cds["boro_cd"].apply(is_real_cd)].copy()
    cds["geometry"] = cds.geometry.simplify(50.0, preserve_topology=True)

    geo = cds[["boro_cd", "geometry"]].copy()
    geo["name"] = geo["boro_cd"].map(name_for)
    geo["food_10min_pct"] = (f["food_10min_pct"].reindex(geo["boro_cd"].values).values * 100).round(1)
    geo["proximity_mean"] = (f["proximity_mean"].reindex(geo["boro_cd"].values).values * 100).round(1)
    geo["childcare_slots_per_100_u5"] = f["childcare_slots_per_100_u5"].reindex(geo["boro_cd"].values).values.round(1)
    geo["supermarket_share_pct"] = f["supermarket_share_pct"].reindex(geo["boro_cd"].values).values.round(1)
    geo["rank_food"] = geo["food_10min_pct"].rank(ascending=False, method="min").astype("Int64")
    geo["rank_proximity"] = geo["proximity_mean"].rank(ascending=False, method="min").astype("Int64")
    geo["rank_childcare"] = geo["childcare_slots_per_100_u5"].rank(ascending=False, method="min").astype("Int64")

    # The "walkable != available" classification — a 2x2 of proximity vs
    # sufficiency that makes the chapter's takeaway legible on one map.
    #   walkable  = >=90% of residents within a 10-min walk on average
    #               (proximity_mean, stored 0-100 here, so >= WALKABLE_PCT)
    #   served    = childcare slots/100 u5 at or above the median CD
    served_cut = float(geo["childcare_slots_per_100_u5"].median())
    walkable = geo["proximity_mean"] >= WALKABLE_PCT
    served = geo["childcare_slots_per_100_u5"] >= served_cut
    geo["access_class"] = [
        ("walk_served" if w and s else "walk_under" if w and not s
         else "car_served" if (not w) and s else "car_under")
        for w, s in zip(walkable, served)
    ]
    print(f"  access_class (walkable>={WALKABLE_PCT:.0f}%, served>={served_cut:.1f}/100): "
          + ", ".join(f"{k}={v}" for k, v in geo['access_class'].value_counts().items()))

    geojson_path = OUT / "daily-needs.geojson"
    basemap.to_display(geo).to_file(geojson_path, driver="GeoJSON")
    print(f"[wrote] {geojson_path}  ({geojson_path.stat().st_size:,} bytes)")

    # static SVG: childcare sufficiency (the chapter's headline finding)
    plot_cds = cds.merge(
        geo[["boro_cd", "childcare_slots_per_100_u5"]], on="boro_cd", how="left"
    )
    vals = plot_cds["childcare_slots_per_100_u5"].astype(float)
    cmap = LinearSegmentedColormap.from_list("mny_seq", palette.RAMP_SEQUENTIAL, N=256)
    fig, ax = plt.subplots(figsize=(8.5, 9.5))
    plot_cds.plot(
        column="childcare_slots_per_100_u5", cmap=cmap,
        vmin=float(vals.quantile(0.05)), vmax=float(vals.quantile(0.95)),
        ax=ax, edgecolor=palette.BORDER, linewidth=0.4,
        missing_kwds={"color": palette.SURFACE, "edgecolor": palette.BORDER},
    )
    for row in plot_cds.itertuples(index=False):
        if row.boro_cd not in ANCHOR_CDS:
            continue
        p = row.geometry.representative_point()
        ax.annotate(
            f"CD {row.boro_cd}\n{row.childcare_slots_per_100_u5:.0f}/100",
            xy=(p.x, p.y), ha="center", va="center", fontsize=8, color=palette.TEXT,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=palette.BG,
                      edgecolor=palette.BORDER, linewidth=0.5),
        )
    ax.set_axis_off()
    ax.set_title("Childcare slots per 100 children under 5", fontsize=14,
                 color=palette.TEXT, pad=10, loc="left")
    ax.text(0.0, 1.005, "Licensed slots (DOHMH + OCFS) · ACS 2019–2023 under-5 population",
            transform=ax.transAxes, fontsize=9, color=palette.TEXT_SECONDARY,
            ha="left", va="bottom")
    svg_path = OUT / "childcare-sufficiency.svg"
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[wrote] {svg_path}  ({svg_path.stat().st_size:,} bytes)")

    access_summary = {
        "walkable_pct_cutoff": WALKABLE_PCT,
        "served_cutoff_slots_per_100": round(served_cut, 1),
        "class_counts": {k: int(v) for k, v in geo["access_class"].value_counts().items()},
    }
    return geojson_path, access_summary


def main() -> int:
    import pandas as pd

    print("[ch.4] tract->CD + CD population (ACS B01003)")
    t2c = tract_to_cd()
    cd_pop = per_cd_population(t2c)

    print("[ch.4] axis 1 — food access (NYS groceries + OSM cross-check)")
    food, food_crosscheck = per_cd_food(t2c)

    print("[ch.4] food quality — supermarket share (a store is not a supermarket)")
    super_share, food_quality = per_cd_supermarket_share(t2c)

    print("[ch.4] axis 2 — care access (pharmacies + childcare + healthcare)")
    care, care_components = per_cd_care(t2c)

    print("[ch.4] axis 3 — civic/learning access (schools + libraries + parks)")
    civic, civic_components = per_cd_civic(t2c)

    axes = {"food_10min_pct": food, "care_10min_pct": care, "civic_10min_pct": civic}
    spine = spine_test(axes)

    print("[ch.4] sufficiency — childcare slots per 100 children under 5")
    suff, cc_prox, suff_summary = childcare_sufficiency(t2c)
    # The thesis test: does proximity to childcare predict ENOUGH childcare?
    paired = pd.DataFrame({"prox": cc_prox, "suff": suff}).dropna()
    prox_suff_rho = float(paired["prox"].rank().corr(paired["suff"].rank()))
    print(f"[suff] childcare proximity ~ sufficiency: rho = {prox_suff_rho:+.3f}  "
          f"(n={len(paired)}) — low |rho| supports proximity != sufficiency")
    suff_summary["proximity_vs_sufficiency_rho"] = round(prox_suff_rho, 3)

    # assemble per-CD frame for the artifacts
    frame = pd.DataFrame({k: v for k, v in axes.items() if v is not None})
    frame["proximity_mean"] = frame[[c for c in frame.columns]].mean(axis=1).round(4)
    frame["childcare_prox_pct"] = cc_prox.reindex(frame.index)
    frame["childcare_slots_per_100_u5"] = suff.reindex(frame.index)
    frame["supermarket_share_pct"] = super_share.reindex(frame.index)
    frame["pop"] = cd_pop.reindex(frame.index)
    frame.index.name = "borocd"
    frame = frame.reset_index()
    frame["cd_name"] = frame["borocd"].map(name_for)

    rankings = frame.sort_values("food_10min_pct", ascending=False)
    rankings.to_csv(OUT / "rankings.csv", index=False)

    # headline scatter: childcare proximity vs sufficiency, per CD
    scatter = frame[["borocd", "cd_name", "childcare_prox_pct",
                     "childcare_slots_per_100_u5", "pop"]].dropna()
    scatter.to_csv(OUT / "proximity-vs-sufficiency.csv", index=False)

    print("[ch.4] render headline: daily-needs geojson + sufficiency SVG")
    _, access_summary = render_headline(frame)

    facts = {
        "chapter": 4,
        "title_working": "Access to Daily Needs",
        "walk_radius_ft": WALK_RADIUS_FT,
        "n_cds": int(frame["borocd"].nunique()),
        "axes_ready": [k for k, v in axes.items() if v is not None],
        "food": {
            "supermarket_min_sqft": nys_food_stores.SUPERMARKET_MIN_SQFT,
            "crosscheck": food_crosscheck,
            "pct_range": [
                round(float(frame["food_10min_pct"].min()), 4),
                round(float(frame["food_10min_pct"].max()), 4),
            ],
        },
        "food_quality": food_quality,
        "care": {
            **care_components,
            "pct_range": [
                round(float(frame["care_10min_pct"].min()), 4),
                round(float(frame["care_10min_pct"].max()), 4),
            ],
        },
        "civic": {
            **civic_components,
            "pct_range": [
                round(float(frame["civic_10min_pct"].min()), 4),
                round(float(frame["civic_10min_pct"].max()), 4),
            ],
        },
        "spine_test": spine,
        "sufficiency": suff_summary,
        "access_class": access_summary,
    }
    (OUT / "facts.json").write_text(json.dumps(facts, indent=2) + "\n")
    print(f"\n[ch.4] wrote out/facts.json + out/rankings.csv "
          f"({len(frame)} CDs, axes: {facts['axes_ready']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
