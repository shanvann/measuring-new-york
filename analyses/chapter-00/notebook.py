"""Chapter 0 — pilot teaser.

Produces two artifacts in ``out/``:
  teaser.png       Static choropleth — the visual that ships in the MDX.
                   PNG (not SVG) because matplotlib's path-based SVG is
                   2MB+ for 59 NYC polygons; PNG at 144 DPI is ~160KB.
  facts.json       Headline numbers for <MetricCallout/> blocks.

A GeoJSON variant (``write_teaser_geojson``) is available for any future
interactive map, but is not emitted by default — Ch. 0 is static-only per
plan §9, and shipping a 2MB GeoJSON to /public for nothing inflates the
static asset directory.

Run with::

    python analyses/chapter-00/notebook.py
    LOOKBACK_DAYS=30 SNAPSHOT=2026-05-01 python analyses/chapter-00/notebook.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared import basemap, palette  # noqa: E402

OUT = HERE / "out"
OUT.mkdir(exist_ok=True)

SNAPSHOT = "2026-06-01"
DEFAULT_LOOKBACK_DAYS = 30
GEOMETRY_PRECISION_DECIMALS = 5  # ~1m precision at NYC latitudes


def compute_311_density_by_cd(days: int) -> dict[str, int]:
    """Return {boro_cd: count} for 311 requests in the last ``days`` days."""
    from pipelines import three_one_one

    cd_codes = [basemap.cd_code(b, n) for b in ["MN", "BX", "BK", "QN", "SI"]
                for n in range(1, 19) if not (b == "SI" and n > 3)]

    counts: dict[str, int] = {}
    for cd in cd_codes:
        try:
            df = three_one_one.load(cd=cd, days=days, snapshot=SNAPSHOT)
            counts[cd] = int(len(df))
        except Exception as e:
            print(f"  [warn] {cd}: {e!s}")
            counts[cd] = 0
    return counts


def _round_coords(obj, ndigits: int):
    """Recursively round floats in a GeoJSON coordinate tree."""
    if isinstance(obj, float):
        return round(obj, ndigits)
    if isinstance(obj, list):
        return [_round_coords(x, ndigits) for x in obj]
    return obj


def write_teaser_geojson(counts: dict[str, int]) -> Path:
    """Emit the per-CD choropleth as GeoJSON for the interactive ``<NycMap>``.

    Computes ``calls_per_sqmi`` (matching the PNG render's metric) so the
    interactive tooltip shows the same density number the headline visual
    is built around. Geometry is simplified at 50 ft and reprojected to
    WGS84; coordinates are rounded to keep the payload small.
    """
    cds = basemap.load("cd")  # EPSG:2263
    cds["boro_cd"] = cds["boro_cd"].astype(str).str.zfill(3)
    cds["calls_30d"] = cds["boro_cd"].map(counts).fillna(0).astype(int)
    cds = cds[cds["boro_cd"].astype(int) < 600].copy()

    area_sqmi = cds.geometry.area / (5280.0 ** 2)
    cds["calls_per_sqmi"] = (cds["calls_30d"] / area_sqmi).round(1)
    cds["geometry"] = cds.geometry.simplify(50.0, preserve_topology=True)
    cds = basemap.to_display(cds)

    geojson = json.loads(cds.to_json())
    for feat in geojson["features"]:
        props = feat["properties"]
        feat["properties"] = {
            "boro_cd": props["boro_cd"],
            "calls_30d": props["calls_30d"],
            "calls_per_sqmi": props["calls_per_sqmi"],
        }
        feat["geometry"]["coordinates"] = _round_coords(
            feat["geometry"]["coordinates"], GEOMETRY_PRECISION_DECIMALS
        )

    path = OUT / "teaser-map.json"
    path.write_text(json.dumps(geojson, separators=(",", ":")))
    print(f"  wrote {path} ({path.stat().st_size:,} bytes; {len(geojson['features'])} features)")
    return path


def write_teaser_png(counts: dict[str, int], lookback_days: int) -> Path:
    """Render the choropleth as a static PNG using the series palette."""
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    from matplotlib.colors import LinearSegmentedColormap

    palette.for_matplotlib()

    # Work in projected coords so simplification + area math are correct, then
    # reproject to display CRS only for plotting bounds. Simplify is in feet.
    cds = basemap.load("cd")  # EPSG:2263
    cds["boro_cd"] = cds["boro_cd"].astype(str).str.zfill(3)
    cds["calls"] = cds["boro_cd"].map(counts).fillna(0).astype(int)
    cds = cds[cds["boro_cd"].astype(int) < 600].copy()

    # Calls per square mile — strips out the "Manhattan CDs are huge"
    # confound and surfaces density-of-friction.
    area_sqmi = cds.geometry.area / (5280.0 ** 2)
    cds["calls_per_sqmi"] = (cds["calls"] / area_sqmi).fillna(0)

    # Simplify polygons: ~50ft tolerance keeps the city outline crisp but
    # drops most of the small wiggle. Reduces draw cost dramatically.
    cds["geometry"] = cds.geometry.simplify(50.0, preserve_topology=True)

    cmap = LinearSegmentedColormap.from_list("mny_seq", palette.RAMP_SEQUENTIAL, N=256)
    vmax = float(cds["calls_per_sqmi"].quantile(0.95))
    vmin = float(cds["calls_per_sqmi"].quantile(0.05))

    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    cds.plot(
        column="calls_per_sqmi",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        ax=ax,
        edgecolor=palette.BORDER,
        linewidth=0.4,
    )
    ax.set_axis_off()
    ax.set_title(
        f"311 calls per square mile · last {lookback_days} days",
        fontsize=12,
        color=palette.TEXT,
        pad=12,
    )

    sm = plt.cm.ScalarMappable(
        cmap=cmap, norm=mcolors.Normalize(vmin=vmin, vmax=vmax)
    )
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, orientation="horizontal", fraction=0.04, pad=0.02, shrink=0.6)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(labelsize=8, colors=palette.TEXT_SECONDARY)
    cbar.set_label("calls / sq mi (5th–95th pct)", fontsize=9, color=palette.TEXT_SECONDARY)

    path = OUT / "teaser.png"
    fig.savefig(path, format="png", dpi=144)
    plt.close(fig)
    print(f"  wrote {path} ({path.stat().st_size:,} bytes)")
    return path


def _cd_name(code: str) -> str:
    """Friendly name for headline CDs. Hand-curated for the ones we surface."""
    names = {
        "101": "MN 1 – Financial District / Tribeca",
        "104": "MN 4 – Chelsea / Clinton",
        "112": "MN 12 – Washington Heights / Inwood",
        "201": "BX 1 – Melrose / Mott Haven",
        "204": "BX 4 – Highbridge / Concourse",
        "212": "BX 12 – Wakefield / Williamsbridge",
        "301": "BK 1 – Williamsburg / Greenpoint",
        "303": "BK 3 – Bedford-Stuyvesant",
        "401": "QN 1 – Astoria",
        "414": "QN 14 – Rockaway",
        "501": "SI 1 – St. George / Stapleton",
    }
    return names.get(code, code)


def write_facts(counts: dict[str, int], lookback_days: int) -> Path:
    nonzero = {k: v for k, v in counts.items() if v > 0}
    total = sum(nonzero.values())
    top = Counter(nonzero).most_common(5)
    bottom = sorted(nonzero.items(), key=lambda kv: kv[1])[:5]
    facts = {
        "snapshot": SNAPSHOT,
        "lookback_days": lookback_days,
        "total_311_calls": total,
        "cd_count": len(nonzero),
        "calls_per_day": round(total / max(lookback_days, 1), 1),
        "top_5_cds_by_call_volume": [
            {"boro_cd": k, "name": _cd_name(k), "calls": v} for k, v in top
        ],
        "bottom_5_cds_by_call_volume": [
            {"boro_cd": k, "name": _cd_name(k), "calls": v} for k, v in bottom
        ],
    }
    path = OUT / "facts.json"
    path.write_text(json.dumps(facts, indent=2) + "\n")
    print(f"  wrote {path}")
    print(f"    total={total:,}  calls/day={facts['calls_per_day']:,}  CDs={facts['cd_count']}")
    print(f"    top CD: {top[0][1]:,} calls -> {_cd_name(top[0][0])}")
    return path


def main() -> int:
    import os
    global SNAPSHOT
    days = int(os.environ.get("LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS))
    SNAPSHOT = os.environ.get("SNAPSHOT", SNAPSHOT)
    print(f"[chapter-0] computing 311 density by CD (lookback={days}d, snapshot={SNAPSHOT})...")
    counts = compute_311_density_by_cd(days=days)
    nonzero = sum(1 for v in counts.values() if v > 0)
    print(f"[chapter-0] got counts for {len(counts)} CDs ({nonzero} non-zero)")

    print("[chapter-0] writing teaser PNG...")
    write_teaser_png(counts, lookback_days=days)

    print("[chapter-0] writing teaser GeoJSON for interactive <NycMap>...")
    write_teaser_geojson(counts)

    print("[chapter-0] writing facts...")
    write_facts(counts, lookback_days=days)

    print("[chapter-0] done. publish with: make publish CHAPTER=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
