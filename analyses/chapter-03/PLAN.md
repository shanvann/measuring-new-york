# Chapter 3 — Environmental Quality

Working plan + session status for Phase 3c. Lives alongside the chapter
notebook so the spec, the in-flight work, and the punch list are all in
one place. Authoritative chapter spec is `MEASURING_NEW_YORK_PLAN.md`
§10 in the website repo; this file is the data-repo working copy and
gets archived/promoted at the end of Phase 3c.

## Spec

**Hypothesis (working).** A New Yorker's environmental experience splits
into three semi-independent axes:

1. **Ambient air quality** — PM2.5 + NO2 annual means (DOHMH `c3uy-2p5r`,
   CD geography). Regional + traffic-driven.
2. **Green-space access** — % residents within a 10-min walk of a park
   ≥ 1 acre, population-weighted (NYC Parks Properties + Ch. 1 isochrones).
   Planning / zoning-driven.
3. **Local nuisance burden** — env-related 311 complaints per 1,000
   residents per year. Street-level + enforcement-driven.

**Kill criterion (mirrors Ch. 2).** If any pair of axes co-ranks with
|ρ| ≥ 0.75, the spine collapses and the chapter gets re-spec'd. Ch. 2's
kill fired on filings↔HPD at +0.82 and that's why it shipped as a
2-axis story. Same playbook here.

**Anchor CDs.** Not picked yet. Following Ch. 2's pattern, anchors get
chosen after the spine test runs on real data.

## Decision log (2026-05-30 session)

- **Air pollutants.** Use both PM2.5 and NO2; pick the latest Annual
  Average year independently per pollutant.
- **Air spine representative = PM2.5.** Intra-axis PM2.5↔NO2 = +0.840
  → treat air as one axis. Spine test uses `pm25_annual` as the air
  proxy (canonical health metric); NO2 is reported alongside for
  reproducibility but isn't a spine column.
- **Green-space metric.** % residents within 10-min walk of a 1+ acre
  park, pop-weighted. (Picked over "% CD area as park" and
  "nearest-park distance" for being closest to lived experience.)
  First-pass cutoff = 0.5 mi (2,640 ft) straight-line — conservative
  vs. an osmnx walk-network distance.
- **311 complaint set.** Noise (all types), Rat/Rodent, Illegal Dumping +
  Dirty Conditions + Sanitation Condition, Idling + Air Quality.
  Idling/Air Quality is included **despite** the coupling risk with the
  ambient-air axis — the spine test will flag it if it fires.
- **Spec scope.** Data-repo notebook docstring + this PLAN.md for now;
  promote to website-repo §10 once the spine test runs on all three axes.
- **UHF42 crosswalk: not needed.** DOHMH `c3uy-2p5r` ships CD-level data
  directly (`geo_join_id` == `boro_cd`, 2,655 of 6,345 rows CD-keyed).
- **Spine survives (3-axis test, 2026-05-30).** Spearman ρ on 59 CDs:
  air↔green +0.432, air↔env-311 +0.623, green↔env-311 +0.361. All
  pairs are below the 0.75 kill threshold → the chapter stays 3-axis.
  Idling/Air Quality bucket did not pull air↔env-311 above kill (in
  fact env-311 is dominated by Noise, ~85% of complaint volume); the
  flagged coupling risk did not fire.
- **Editorial framing rule #1 — scope.** The chapter is "Environmental
  Quality," not "Air Quality." The cold open, framing section (§3),
  and methodology footer must make clear that the spine has three
  axes — air, green-space, and civic-complaint volume — and that the
  argument lives in their *combination*, not in any single axis.
- **Editorial framing rule #2 — noise = behavior, not exposure.** We
  measure noise via NYC 311 complaints, not decibel meters. The chapter
  prose must name this distinction explicitly the first time noise is
  discussed: 311 captures *who is bothered enough to file a complaint*,
  not *how loud the block actually is*. The CD 212 / zip 10466 finding
  (1 address ≈ 13% of zip volume, 97% "Loud Music/Party" — see Medium
  piece linked in WORKLOG) is the worked example. This framing is what
  makes a "civic-noise" axis defensible inside an environmental chapter;
  without it, the axis pretends to be exposure data and the 10466 case
  unmasks it.
- **Env-311 primary metric switched to distinct complaining addresses
  per 1k pop per yr** (2026-05-30, late session). The raw call-rate
  let the zip-10466 super-caller pattern push CD 212 to 572/1k/yr
  (~3× #2). Counting *how many distinct addresses* in each CD filed at
  least one env-311 call in the window — instead of how many calls —
  measures complaint-behavior breadth, not volume. CD 212 collapses
  from rank #1 (572 calls/1k/yr) to rank 37/59 (18.0 addrs/1k/yr,
  93% of city median). The metric switch was structural rather than
  ad-hoc capping; raw call totals are retained in `facts.json` for
  reproducibility. Pipeline addition:
  `three_one_one.fetch_env_distinct_addrs_by_zip`.

## Status

### Done
- **Notebook scaffold + 3-axis wiring** (`analyses/chapter-03/notebook.py`).
  Full spec docstring, all three axes wired end-to-end, spine test
  reports on `pm25_annual ↔ green_10min_pct ↔ env311_per_1k_pop_per_yr`.
- **Axis 1 — Ambient air.** PM2.5 + NO2, Annual Average 2023, all 59
  CDs. PM2.5 6.11–8.37 µg/m³ (Manhattan-core highest, outer-borough
  coastal lowest — passes sanity). NO2 9.36–26.11 ppb. Intra-axis
  Spearman PM2.5↔NO2 = **+0.840** → treat air as a single axis;
  methodology note for the chapter footer.
- **Axis 2 — Green-space.** New `pipelines/nyc_parks.py` pulls NYC
  Parks Properties (`enfh-gkve`): 2,058 polygons, 867 ≥ 1 acre,
  30,113 total qualifying acres at the 2026-06-01 snapshot. Notebook
  `per_cd_green()` computes per-tract straight-line distance via
  `gpd.sjoin_nearest` (EPSG:2263, feet), thresholds at 2,640 ft
  (~10 min @ 3 mph), and pop-weights with B01003 to CD level. Range
  0.74–1.00, mean 0.98.
  ⚠ The metric is **heavily compressed** — most CDs cluster near 1.00,
  only the bottom 5 are meaningfully differentiated (CD 410, 314, 311,
  312, 317 — all south Brooklyn / SE Queens). At the spine-test stage
  it still discriminates enough to rank-correlate; before the headline
  visual we should revisit (tighter acreage cutoff, walk-network
  isochrone instead of straight-line, or switch to acres-per-capita
  within walk distance).
- **Axis 3 — env-311.** New `per_cd_env311()` consumes the
  `three_one_one.load_env_counts_by_zip` aggregate (834 zip-bucket
  rows for 2024-01-01..2026-06-01) and allocates to CDs via the
  existing area-weighted `geographies/zip_cd_crosswalk.csv`. CD-level
  rates per 1k pop per year for total + each bucket. 2,204,890
  complaints in window; 15,183 dropped from non-NYC/invalid ZIPs.
- **ACS B01003 (total pop).** Added to `pipelines/acs_census.py`
  TABLES dict, cached at tract level. Tract→CD via centroid sjoin
  matches Ch. 2's pattern; CD pop range 59k–251k, total 8.52M.
- **Overpass UA fix.** `pipelines/osm_overpass.py` now sends a
  `User-Agent` header. Overpass had started 406'ing anonymous requests.
  2,772 park elements cached — kept for other chapters; **superseded
  for Ch. 3** by `nyc_parks` (authoritative polygons + acreage).
- **`fetch_env_counts_by_zip` pipeline.** Shipped in
  `pipelines/three_one_one.py`. Four server-side SoQL GROUP-BY-zip
  aggregates (one per bucket: noise / rodent / dirty / idair), unioned
  and cached. Pattern mirrors `hpd_violations.fetch_counts_by_zip`.

### Spine test result (2026-05-30, n = 59)

Run on the super-caller-robust env-311 metric
(`env311_addrs_per_1k_pop_per_yr`):

| pair                                       | ρ      | fires kill? |
|--------------------------------------------|--------|-------------|
| `pm25_annual` ↔ `green_10min_pct`          | +0.432 | no          |
| `pm25_annual` ↔ `env311_addrs_per_1k_pop`  | +0.625 | no          |
| `green_10min_pct` ↔ `env311_addrs_per_1k_pop` | +0.174 | no       |

All pairs below the 0.75 kill threshold → **spine survives**, chapter
stays 3-axis.

Two notable shifts from the raw-call-rate version of the test:
- `green ↔ env-311` dropped from +0.361 to +0.174 — the prior
  correlation was partly a super-caller artifact in dense low-green
  CDs, not a real green↔complaint linkage.
- `air ↔ env-311` held at +0.625 — the air-axis correlation is
  *structural* (dense areas are dirty and complainy), not a
  super-caller artifact.

Citywide env-311 distribution (new metric, distinct addrs/1k/yr):
min 10.7, median 19.4, p90 28.4, max 37.4 — a 3.5× spread vs the raw
metric's 14× spread, more legible for a choropleth.

### Locked (this session)
- **Chapter title:** *Breathing Room.* Voicey single-image; carries
  air + green + civic-noise without listing them.
- **Cold-open anchor:** CD 112 Washington Heights / Inwood, opened on
  the *In the Heights* "96,000" scene — Usnavi's broken bodega fan,
  the heat, the blackout. Sets up the chapter's central inversion:
  high env-burden ≠ unlivable; can mean dense, occupied, cared-for.
- **Five anchors** (5/5 boroughs):

  | CD  | Borough | Anchors                                       |
  |-----|---------|-----------------------------------------------|
  | 112 | MN      | cold open / lived-experience inversion        |
  | 105 | MN      | stacked-burden peak (air #1, env-311 #2)      |
  | 206 | BX      | **see note below** (re-framing under new metric) |
  | 311 | BK      | green-poor contrast (green #3-worst)          |
  | 503 | SI      | low-burden contrast (air #cleanest, env-311 #14-lowest) |

  **CD 206 role — surprise-finding anchor.** Belmont was originally
  picked as a "stacked-burden" anchor against the raw call-rate
  metric (top-5 env-311 + top-10 air). Under the distinct-address
  metric it ranks 16/59 (air) + 18/59 (env-311) — middle of pack.
  Kept in the anchor set and re-cast as the chapter's surprise-finding
  anchor: *the South Bronx neighborhoods you'd expect to top the
  environmental-burden ranking don't — once you stop counting calls
  and start counting blocks.* This makes the metric switch part of
  the chapter's argument instead of hiding it in the footer. The
  `<Anchor cd="206">` paragraph should walk through the rank change
  explicitly. (Locked 2026-05-30.)
- **Headline-map axis:** PM2.5 (cleanest variance, no metric-switch
  caveat needed on the visual). Env-311 lives in the prose and the
  anchor table.
- **MetricCallout:** "Midtown's PM2.5 is 37% higher than the city's
  cleanest community districts" (8.37 vs 6.11 µg/m³).

### Open / next session
- **Green metric compression.** Range 0.74–1.00, mean 0.98. Fine for
  the spine; OK to ship for the static comparison table (the
  green-poor anchor 311 reads cleanly). Revisit only if a later draft
  wants a green choropleth.
- **Headline visual.** Spine survived → unblocked. Render a CD-level
  PM2.5 choropleth following Ch. 2 `render_headline_choropleth`'s
  treatment (sequential ramp, 5–95th pctile clip, 50-ft polygon
  simplification, display-CRS geojson sibling for `<NycMap>`).
- **Promote spec to website-repo `MEASURING_NEW_YORK_PLAN.md` §10.**
  Mirror this PLAN's Decision log + Spine result. Cross-repo edit.
- **Draft chapter MDX** in the website repo. 11-section template per
  STYLE_GUIDE §2; both editorial framing rules above are binding.

## Punch list — next session(s)

1. Render the PM2.5 headline visual (notebook
   `render_headline_pm25_choropleth`) + sibling CD-level geojson
   for `<NycMap>` consumption.
2. Promote Ch. 3 spec to website-repo `MEASURING_NEW_YORK_PLAN.md` §10
   (cross-repo edit; demote Ch. 2 spec to archived).
3. Draft chapter MDX in personal-website
   (`src/content/blog/measuring-new-york-3-breathing-room.mdx` or
   equivalent), 11-section template per STYLE_GUIDE §2.
4. Per-anchor `<Anchor>` blocks: cold open on CD 112 with the
   *In the Heights* hook; CD 206 framed as the surprise-finding
   anchor (Bronx isn't the worst once you switch metrics).
5. Wire `<MethodologyFooter>` with the framing rules baked in
   (env-quality scope, noise=behavior, metric-switch caveat,
   green-metric compression caveat).

## Vintage pins (per `MANIFEST.json`)

| Source         | Vintage                        | Notes                          |
|----------------|--------------------------------|--------------------------------|
| DOHMH air      | Annual Average 2023            | latest annual at snapshot      |
| NYC 311        | 2024-01-01 .. 2026-06-01       | post-pandemic baseline         |
| NYC Parks      | 2026-06-01                     | enfh-gkve; 2,058 polygons      |
| ACS            | 2019–2023 5-year               | B01003 added; B01003+ shipped  |
| Zip → CD       | already shipped (Ch. 2)        | area-weighted crosswalk        |
