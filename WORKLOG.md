# Measuring New York (data) — Worklog

> Append-only. **Newest entry at the top.** See
> `../personal-website/MEASURING_NEW_YORK_PLAN.md` §11 for the entry template
> and logging rules.

---

## 2026-05-30 — Ch. 3 kickoff: spec + axis 1 (ambient air) wired end-to-end
**Repo:** measuring-new-york
**Phase / chapter:** Phase 3c / Ch. 3 — **scaffold + air axis live; green-space + env-311 stubbed**
**Session length:** ~1h

**What changed (shipped, uncommitted):**
- `analyses/chapter-03/notebook.py` (new) — first-pass scaffold mirroring Ch. 2's structure. Full spec docstring (hypothesis, 3 axes, kill criterion = |rho| >= 0.75). Axis 1 wired end-to-end; axes 2 and 3 are explicit stubs with TODOs pointing at the right pipelines.
- `pipelines/osm_overpass.py` — Overpass started 406'ing requests with no User-Agent sometime in 2025. Added a `User-Agent` header (`measuring-new-york/0.1 (shanitpv@gmail.com)`) on the POST. Refetched parks: 2,772 elements cached.
- DOHMH air-quality data cached: PM2.5 + NO2, dataset `c3uy-2p5r`, 6,345 rows each.

**Verified:**
- DOHMH `c3uy-2p5r` ships **CD-level data directly** (`geo_type_name == 'CD'`, `geo_join_id` == `boro_cd`). 2,655 of 6,345 rows are CD-keyed. The UHF42 → CD crosswalk we tentatively scoped is **unnecessary**.
- Axis 1 numbers (Annual Average 2023, all 59 CDs):
  - PM2.5: 6.11 – 8.37 mcg/m3.  Top: 105 Midtown, 102 Village/Soho, 104 Chelsea/HK, 106 Stuy/Turtle Bay, 101 FiDi.  Bottom: 503 Tottenville, 414 Rockaway, 502 South Beach SI, 315 Sheepshead Bay, 313 Coney Island.
  - NO2: 9.36 – 26.11 ppb (much wider relative spread than PM2.5).
- PM2.5 ↔ NO2 within-axis Spearman: **+0.840**. Same traffic + density driver. Not a spine-kill (it's intra-axis), but means we should pick **one** representative air metric or treat them as a composite — not as independent axes. Will note in the chapter MethodologyFooter.

**Tried but didn't ship:**
- Initial Overpass parks fetch 406'd before the UA fix. Fix verified against `[out:json][timeout:25];out count;` (200 OK after adding UA).

**Blocked / partial:**
- Axis 2 (green-space) — stub. The OSM parks query uses `out center tags` which gives centers, not polygons. For the chosen metric (% residents within 10-min walk of a 1+ acre park) we want NYC Parks Properties (NYC Open Data dataset `enfh-gkve`) for authoritative polygons + official acreage. Next session.
- Axis 3 (env-311) — stub. Needs a server-side aggregated SoQL counts-by-(zip, complaint) extension in `pipelines.three_one_one`, mirroring `hpd_violations.fetch_counts_by_zip`. Window 2024-01-01 → 2026-06-01; complaint set: Noise (all types), Rat/Rodent, Illegal Dumping + Dirty Conditions, Idling + Air Quality. (User opted to include Idling/Air Quality despite the coupling risk with axis 1 — the spine test will surface that as a [KILL] flag if it fires, which is the right behavior.)

**Next action:**
- Pick one of axis 2 / axis 3 to wire next. Axis 3 is mechanically simpler (extend an existing pipeline + reuse zip→CD crosswalk); axis 2 is more novel work (Parks Properties pull + tract-walk-distance). Recommend axis 3 first since it lets the full spine test fire.

**Notes for next agent:**
- The chapter is **not yet runnable** as a green→publish pipeline; `make publish CHAPTER=3` will only carry the `out/facts.json` + `out/rankings.csv` that exist today (no SVG, no display geojson yet — by design; Ch. 2 pattern was to validate the spine first).
- All three axes will live at CD geography. DOHMH publishes CD-level directly; 311 + parks reach CD via the existing `geographies/zip_cd_crosswalk.csv` (311) and tract-centroid + pop weight (parks, when implemented).
- `pipelines.three_one_one.build_query` currently filters by `community_board = "01 BROOKLYN"`-style strings. For the chapter-3 counts-by-zip work, prefer `incident_zip` + the existing zip→CD crosswalk so the methodology is consistent with Ch. 2's HPD / OCA allocation.

---

## 2026-05-24 (afternoon) — Ch. 2 data foundation; HPD collinearity → 2-axis pivot
**Repo:** measuring-new-york
**Phase / chapter:** Phase 3b / Ch. 2 — **data foundation complete; SVG headline rendered**
**Session length:** ~2h (follow-on to the morning OCA-pipeline-shell session)

**What changed (shipped):**
- `shared/zip_to_cd.py` + `geographies/zip_cd_crosswalk.csv` (commit `848992e`) — area-weighted MODZCTA → CD crosswalk. 178 zips × 59 CDs → 349 (zip, CD) pairs. 108 zips (61%) span 2+ CDs, validating the choice over a centroid-only join.
- OCA bundle pulled (700 MB) to `cache/oca/` at snapshot 2026-05-10. ETag-stable; manifest updated automatically by `cache.record()`.
- ACS B25070 / B25064 / B25003 / B19013 cached at tract level via the existing `pipelines.acs_census` module (commit `848992e`). 2,327 rows per table.
- `pipelines/hpd_violations.py::fetch_counts_by_zip()` (commit `0ec26a8`) — server-side aggregated count per (zip, class) for a window. One Socrata request, ~600-row response. The existing per-CD `fetch()` is preserved for Ch. 0 backwards-compat.
- `analyses/chapter-02/notebook.py` (commits `848992e` + `0ec26a8`):
  - tract→CD via centroid sjoin matching Ch. 1's pattern (22 tracts unassigned — water / airport — acceptable).
  - Per-CD rent burden (B25070 brackets), median rent (renter-HH-weighted mean of tract medians), median income, renter HH count, OCA filings rate (via zip→CD crosswalk), HPD violations rate (total + class-C, same crosswalk).
  - Full 4-axis Spearman matrix with collinearity flagging in the printed summary.
  - `render_headline_choropleth()` — static SVG, series palette sequential ramp, 5–95 pct clip, 50-ft polygon simplification (Ch. 1 pattern), 5 anchor CDs labelled inline with the burden %.
- `pipelines/acs_census.py` (commit `3c48dba`) — small bugfix: cache check moved before the CENSUS_API_KEY check so cached loads work offline.

**Verified:**
- Full notebook run is ~30s warm (everything cached).
- Headline numbers (window 2024-01-01 → 2026-05-10):
  - 268,566 NYC residential eviction filings (1,182 dropped from non-NYC ZIPs)
  - 2,268,788 HPD violations (5,643 dropped)
  - rent burden ≥30%: 35%–63% range across CDs
  - severe rent burden ≥50%: 16%–40% range
- 4-axis Spearman matrix:
  - burden_30    ↔ median_rent   ρ = −0.774
  - burden_30    ↔ filings       ρ = +0.665
  - burden_30    ↔ hpd           ρ = +0.609
  - median_rent  ↔ filings       ρ = −0.768
  - median_rent  ↔ hpd           ρ = −0.691
  - filings      ↔ hpd           ρ = **+0.817**  ⚠ kill criterion fired
- 5 new anchor CDs each anchor a distinct (burden, distress) quadrant — see plan §10.
- `out/rent-burden-cd.svg` 234 KB; `out/rent-burden.geojson` ~190 KB; `out/facts.json` carries the full 4-axis numbers + the spearman matrix; `out/rankings.csv` is the same in long form.

**Tried but didn't ship:**
- `fetch_window()` (paginated raw rows) in hpd_violations.py — initial implementation 400'd because the schema didn't match (the existing per-CD code's assumed columns `communityboard` and `postcode` don't exist in the dataset; the real columns are `zip` and `boro`+`boroid` with no CD field). Replaced with the server-side aggregated approach. The replacement is strictly better for the use case (~600 rows vs 2.27M).
- A tract→CD area-weighted aggregation (alternative to centroid sjoin). Centroid is fine here because CDs are larger than tracts; deferred unless a future chapter needs sub-tract precision.

**Blocked / partial:**
- (none — data foundation is complete; the chapter is ready for prose drafting)

**Next action:**
- Hand off to the website repo: draft `content/posts/measuring-new-york-02-housing.mdx` using the per-chapter template (plan §7). Run `make publish CHAPTER=2` to copy `out/rent-burden-cd.svg` + `out/rent-burden.geojson` + `out/facts.json` into the website's `public/measuring-new-york/chapter-02/`.

**Notes for next agent:**
- The kill-criterion fire is a feature, not a bug. The "two axes + HPD as confirmer" framing is sharper than "three independent axes" would have been. Don't try to resurrect the three-axis claim in the prose.
- The 5 anchor CDs span the (burden, distress) 2D plane:
  - 206 Belmont — high burden + high distress (bottom-right)
  - 313 Brownsville — high burden + low-mid distress (bottom-left)
  - 109 Hamilton Heights — low-mid burden + high distress (top-right)
  - 108 UES — low burden + low distress (top-left) + high rent
  - 411 Bayside — low burden + low distress (top-left) + low-mid rent / homeownership
- HPD **class-C** (immediately hazardous) numbers are computed but not in the headline. CD 206 has 447 class-C violations per 1,000 renter HH per year — roughly one per two units per year. That's an extreme number worth quoting in the prose if a sharper quality signal is needed.
- Cache freshness: OCA is pinned to 2026-05-10 (explicit vintage exception); HPD + ACS pinned to the standard 2026-06-01 freeze. If a fresher OCA publish lands before prose ships, re-run `pipelines.oca_evictions --snapshot-info` and re-pin in `MANIFEST.json`.
- `pandas.DataFrameGroupBy.apply` emits a FutureWarning in the weighted-median-rent function on pandas ≥2.2; functionally fine, cosmetically loud. Suppress with `include_groups=False` if it becomes annoying.

---

## 2026-05-24 — Phase 3b kickoff: OCA eviction-filings pipeline shipped
**Repo:** measuring-new-york
**Phase / chapter:** Phase 3b / Ch. 2 — **pipeline shell only; no data fetched yet**
**Session length:** ~1.5h (shared with the website-repo session that drafted Ch. 2 §10 spec)

**What changed (shipped):**
- `pipelines/oca_evictions.py` (new, commit `1302b31`) — streaming
  CSV fetcher for the Housing Data Coalition's OCA Housing Court
  filings bundle. S3 base `https://oca-2-dev.s3.amazonaws.com/public/`.
  Handles two tables only (oca_index 497 MB + oca_addresses 203 MB);
  the other 9 tables in the bundle are noted in the module docstring
  for future chapters. `load_nyc_filings()` does a chunked filter
  (court ∈ NYC five courts + classification ∈ {Non-Payment, Holdover}
  + Residential + optional date window) and an inner join on
  indexnumberid against the address table. Snapshot date is fetched
  from `last-updated-date.txt` so cache filenames pin the actual
  data vintage rather than the series freeze.
- `MANIFEST.json` (same commit) — added `oca_evictions` vintage entry
  pinned at 2026-05-10 as an explicit exception to the 2026-06-01
  series freeze. Noted ZIP-only geography (no BBL/BIN), pointer to
  the HDC ETL repo, and the rationale.

**Verified:**
- `python -m pipelines.oca_evictions --snapshot-info` returns
  `2026-05-10` (HTTP 200 from S3).
- `python -m pipelines.oca_evictions --table index --dry-run` and
  `--table addresses --dry-run` both print the expected URL + cache
  key (`oca/oca_index-2026-05-10.csv`, `oca/oca_addresses-2026-05-10.csv`).
- `python -c "import json; json.loads(open('MANIFEST.json').read())"`
  parses cleanly.
- Did NOT actually pull the 700 MB. Deferred to the chapter-02
  notebook session (one-time cost, cached forever after).

**Tried but didn't ship:**
- Marshal-executed evictions (NYC Open Data `6z8x-wfk4`) as the
  displacement signal — would have been a smaller Socrata-pattern
  pipeline mirroring `hpd_violations.py`, but executions are only
  ~10–20% of filings and undersell the "displacement pressure" axis
  the chapter is built around. User chose OCA over Socrata; logged
  for posterity in case Ch. 6 (Safety) ever wants the execution
  endpoint for a different angle.
- The other 9 OCA tables (causes / parties / events / appearances /
  appearance_outcomes / motions / decisions / judgments / warrants)
  are noted in the module docstring but not wired up — none are
  needed for the Ch. 2 headline rate.

**Blocked / partial:**
- (none — pipeline shell is complete; download is deferred but the
  module runs end-to-end on `--dry-run`)

**Next action:**
- Build `shared/zip_to_cd.py` (area-weighted spatial join from the
  cached MODZCTA geometry to the cached DCP CD geometry — both
  geographies are already cached from Phase 1). Then fetch the
  OCA bundle and cache ACS B25070 + B25064 + B25003 + B19013 at
  tract level. Then start `analyses/chapter-02/notebook.py` with a
  per-CD rent-burden + filings-rate first pass to test the
  hypothesis that the three axes don't co-rank.

**Notes for next agent:**
- The OCA snapshot (2026-05-10) is older than the series vintage
  freeze (2026-06-01). This is an **explicit** exception logged in
  `MANIFEST.json` — same handling Ch. 0 used for its 2026-05-01
  311 snapshot. If a fresher HDC publish lands before Ch. 2 prose
  finalizes, re-pin the snapshot in `MANIFEST.json` and rerun
  `pipelines.oca_evictions --table index --table addresses` — the
  cache key auto-bumps because the snapshot date is in the filename.
- OCA addresses carry only ZIP. No BBL, no BIN, no street. CD
  aggregation has to go through a zip→CD crosswalk; some NYC ZIPs
  straddle multiple CDs (the area-weighting in `shared/zip_to_cd.py`
  is non-negotiable — a centroid join would mis-allocate ~10% of
  filings in CDs like 110/111 or 305/306).
- The 700 MB cache pull is a one-time cost. After the first fetch,
  `python -m pipelines.oca_evictions --table index` is instant
  (manifest hit). The chapter notebook should be designed to
  re-load via `load_nyc_filings(start_date=..., end_date=...)`
  many times without re-fetching.
- The `classification` field uses set-literal strings like
  `{NYCHA}` or `{"Specialty 2 (HHP) Zipcodes"}` for the
  `specialtydesignationtypes` column — Postgres array text format,
  not JSON. Don't try to `json.loads()` it; treat as a string and
  use `.str.contains("NYCHA")` for filters if needed.

---

## 2026-05-23 — Chapter 1 shipped (Mobility & Access)
**Repo:** measuring-new-york (+ artifacts handed off to personal-website)
**Phase / chapter:** Phase 3a / Ch. 1 — **Chapter shipped**
**Session length:** ~2h (Day 3 on top of Day 2)

**What changed (shipped):**
- `pipelines/lehd_lodes.py` (new) — fetcher for LEHD LODES Workplace
  Area Characteristics, NY state, with caching + manifest. Downloads
  the LODES8 v2022 release (~2.7 MB compressed, 4.47M NYC jobs across
  25k blocks → 2,303 tracts).
- `MANIFEST.json` — pinned LODES vintage (year 2022, LODES8 release).
- `analyses/chapter-01/notebook.py` — major refactor: computes
  isochrones **per Census tract** (2,303 NYC tracts in ~2 min) and
  aggregates to CDs via median + Q1/Q3. Replaces the single-centroid
  approach that was producing misleading CD-level numbers for big
  outer-borough CDs (Flushing, Jamaica, etc.). Adds the
  `population_weighted_origins()` helper.
- `shared/isochrone.py` — bumped `WALK_TO_ORIGIN_MAX_FT` to 5280
  (1.0 mi, TCRP Synthesis 95 upper bound). The wider catchment is
  honest about outer CDs whose pop-weighted centroids land 0.8-1.0
  mi from any station; the cost shows up in the walking-time charge
  (1.0 mi network ≈ 28 min), so distant origins still get small
  isochrones.
- Output artifacts in `analyses/chapter-01/out/` + published to
  `../personal-website/public/measuring-new-york/chapter-01/`:
  - `job-access.geojson` (288 KB) — CD choropleth with median +
    Q1/Q3 jobs reachable per CD.
  - `isochrones-45min.geojson` (522 KB) — 5 anchor-CD reach
    polygons (anchor breakdown, not used in the current MDX but
    kept for future use).
  - `facts.json` — headline numbers + per-anchor breakdowns.
- `make publish CHAPTER=1` proven end-to-end.

**Headline (per-tract median, aggregated to CD):**
- Best CD: Midtown East (CD 105) = 3,056,740 jobs reachable (68.4% of NYC)
- Worst CD: SI Tottenville (CD 503) = 13,352 jobs reachable
- **229× median variance** between best and worst CD.
- Largest intra-CD spread: South Ozone Park (CD 410) Q3/Q1 = 4.8×.

**Tried but didn't ship:**
- Initial 0.5 mi and 0.75 mi catchments produced 9+ CDs with zero
  reachable stops because pop-weighted centroids land far from
  actual stations in big outer CDs. Bumped to 1.0 mi; reduced zeros
  to 6 (genuine subway-less CDs like Bayside / Queens Village).
- Initial per-CD-centroid approach (Day 2): replaced with per-tract
  approach because single centroids don't represent residents living
  on the subway-rich side of a CD.
- Did NOT integrate bus GTFS. Documented as the top MethodologyFooter
  caveat in the chapter MDX.
- Did NOT swap straight-line walking for an OSM walk graph. Within
  ±10% in most NYC neighborhoods; logged as caveat.
- Did NOT add GTFS-Realtime reliability variance. Logged as caveat;
  that analysis is deferred to Ch. 8.

**Blocked / partial:**
- (none structural)

**Next action:**
- Phase 3b — Chapter 2 (Housing). See STATUS.md.

**Notes for next agent:**
- Per-tract isochrone runtime is ~2 min for all 2,303 NYC tracts.
  No intermediate caching yet — re-running the notebook recomputes
  from scratch. If Ch. 9's synthesis chapter needs many "what-if"
  isochrones (different departure times, different cutoffs), worth
  adding a parquet cache keyed on (tract, departure_hour,
  max_minutes).
- The 5 anchor CDs from plan §10 turned out to be a great
  selection — they span 3M → 18K jobs reachable cleanly.
- The "South Ozone Park has 4.8× intra-CD spread" finding is the
  chapter's most original insight. Worth reusing in Ch. 2 (Housing)
  — same data approach (per-tract → CD-level aggregate with
  quartiles) can surface micro-geography of rent and HPD violations.
- LEHD LODES is published annually; 2022 is the latest at vintage
  freeze. When 2023 data drops (typically Q3 of the following year),
  Ch. 1 should be re-run against the newer vintage; the chapter
  text references "2022 LODES" explicitly so the update is mechanical.

---

## 2026-05-23 — Phase 3a Day 2: real GTFS isochrones + ACS smoke-test
**Repo:** measuring-new-york (+ artifacts shipped to personal-website)
**Phase / chapter:** Phase 3a / Ch. 1
**Session length:** ~1h

**What changed (shipped):**
- `shared/isochrone.py` — replaced the Phase-1 stub with a real
  ~280-LOC time-dependent Dijkstra. Three modules of helpers
  (precompute / reachable_stops / polygonize) + an end-to-end
  `compute()` convenience + the original `precompute_isochrones()`
  signature kept for API stability. Performance: precompute is 0.7s
  once; routing is <0.1s per origin (we can do all 59 CDs in seconds).
- `analyses/chapter-01/notebook.py` — first real chapter-1 artifact.
  Computes 45-min AM-peak isochrones for all 5 anchor CDs (Midtown
  East, Williamsburg, Wakefield, South Ozone Park, Rockaway) on the
  feed's latest typical Tuesday (2026-09-01). Outputs a
  FeatureCollection + a facts.json with the headline ratio.
- **Headline:** Midtown East reaches 385 subway stops in 45 min;
  Rockaway reaches 23. **16.7× variance.** This is real evidence for
  the Ch. 1 hypothesis from plan §10 (job-access shed variance dwarfs
  median-commute variance — though we need LODES for the "jobs"
  denominator to make the second clause rigorous).
- `make publish CHAPTER=1` worked end-to-end. Artifacts at
  `../personal-website/public/measuring-new-york/chapter-01/`:
  `isochrones-45min.geojson` (448 KB), `facts.json` (1 KB).
- ACS smoke-test: pulled B19013 (median household income, 5 boroughs)
  + B08303 (travel-time-to-work, 2327 tracts). Both cached + manifested.
  Bronx $49,036, Manhattan $104,553 — 2.1× borough-level income range.
- Updated `.env` (gitignored) with the Census API key for local use.

**Tried but didn't ship:**
- Initial isochrone run gave CD 212 (Wakefield) zero reachable stops.
  Diagnosis: nearest subway stop is 0.63 mi from the centroid; my
  catchment was 0.50 mi. Bumped `WALK_TO_ORIGIN_MAX_FT` to the
  standard APTA/TCRP 95 0.75 mi subway-stop figure. Wakefield went to
  28 stops, all other CDs ticked up too. The 0.5 mi figure is from
  bus planning; 0.75 mi is the right subway figure.
- Did NOT integrate bus GTFS. Subway-only model excludes a meaningful
  chunk of NYC mobility (bus is ~50% of trips). Logged as caveat for
  the Ch. 1 MethodologyFooter; will revisit if time allows.
- Did NOT build the job-access overlay yet. Needs LEHD LODES origin-
  destination employment data; vintage not yet pinned in `MANIFEST.json`.
- Did NOT replace straight-line walking with the real `osmnx` walk
  graph. Straight-line × 1.4 is within ~10% in most NYC neighborhoods;
  the polish is worth doing but isn't blocking the headline numbers.

**Blocked / partial:**
- (none structural). The 5 anchor CDs all have nonzero reachable
  stops; the visual map renders for desktop browsers (headless can't
  do WebGL on this machine — graceful error fallback works).

**Next action:**
- See STATUS.md "Next action" — pick between (a) the LODES job-access
  overlay or (b) polish (osmnx walk graph + bus integration). The
  hypothesis already has real support so (a) is the higher-value next
  step.

**Notes for next agent:**
- Service date the algorithm picks is the latest matching Tuesday in
  the feed's calendar range (2026-09-01 right now). That's forward-
  looking; if a quarterly GTFS refresh changes the calendar, the
  service_date will shift. Lock it by passing `service_date=` to
  `precompute()` if reproducibility matters across runs.
- The boarding heuristic considers any trip departing within the next
  `MAX_BOARD_WAIT_MIN` = 20 minutes. Off-peak Sunday at 3am would need
  a longer window; if we ever do a late-night isochrone, raise this.
- Walking-transfer pairs are precomputed pairwise (O(N²) over parent
  stations). At ~500 NYC parent stations this is ~125k pair checks,
  done once in ~0.5s. If a future chapter loads NJT or Metro-North
  stations on top, this loop may want a kd-tree, but at NYC subway
  scale it's fine.
- The polygon union step is the slowest part of `compute()` —
  shapely's unary_union on 300+ buffers is ~50ms. Could be sped up
  with a small-then-big merge tree, but not worth optimizing yet.
- 16.7× variance is just the *count* of reachable stops; the real
  Ch. 1 metric should be jobs-reachable (LODES). The two will
  correlate strongly but the units matter for the prose.

---

## 2026-05-23 — Phase 3a Day 1: GTFS cached + gtfs-kit verified
**Repo:** measuring-new-york
**Phase / chapter:** Phase 3a / Ch. 1
**Session length:** ~30min (rest of the session was in the website repo)

**What changed (shipped):**
- `make fetch-gtfs --bundle subway` ran. MTA subway-only GTFS bundle
  cached at `cache/mta_gtfs/subway-2026-06-01.zip` — 5.8MB (much
  smaller than my Phase 1 estimate of ~50MB; the subway-only feed is
  modest). Manifested with SHA-256 in cache/MANIFEST.json.
- Installed `gtfs-kit` in venv.
- Verified `pipelines.mta_gtfs.load_subway()` returns a usable
  gtfs-kit Feed: 1 agency, 29 routes, 1488 stops (including N/S
  platform records), 21459 trips. Stop sample showed sensible names
  (Van Cortlandt Park-242 St at the top of the 1 line).
- Real 30-day 311 data pulled for all 59 CDs at the pinned
  2026-06-01 snapshot — for use by the website-side smoke test of
  the new interactive `<NycMap>` component. Cache grew by ~50MB
  across `cache/three_one_one/cd-*-2026-06-01-last30d.json`.

**Tried but didn't ship:**
- No isochrone work yet — that's the next concrete deliverable.
- No ACS work — gated on Census API key.

**Blocked / partial:**
- (none on the data side)

**Next action:**
- Build the first real GTFS isochrone in `shared/isochrone.py`. See
  STATUS.md for the design call to make (gtfs-kit + networkx vs
  r5py).

**Notes for next agent:**
- The 30-day 311 cache for all 59 CDs at snapshot 2026-06-01 means
  any chapter that wants per-CD 311 density now hits the cache for
  free (no re-fetching). If a chapter needs a different window/date,
  `pipelines.three_one_one.fetch(...)` with new args will populate
  the cache with new files.
- The website-side interactive `<NycMap>` was wired in the same
  session — see `personal-website/WORKLOG.md` for that side. The
  component reads a chapter's `*.geojson` from
  `/public/measuring-new-york/chapter-N/`, so the analysis-repo
  `make publish CHAPTER=N` step now has two flavors of artifact to
  ship: static (PNG/SVG, picked up via `fallbackImage`) or
  interactive (GeoJSON, picked up by the dynamic MapLibre component).

---

## 2026-05-23 — Chapter 0 shipped (Pilot)
**Repo:** measuring-new-york
**Phase / chapter:** Phase 2 / Ch. 0
**Session length:** ~1.5h (continuation of Phase 1)

**What changed (shipped):**
- Installed matplotlib in the venv.
- `analyses/chapter-00/notebook.py` extended with `write_teaser_png()`:
  loads CDs in EPSG:2263 (for area math), normalizes 311 counts by
  square mile, simplifies polygons at 50ft tolerance, plots with the
  series sequential ramp from `shared.palette`, clips the colorbar to
  the 5th–95th percentile so a couple of outlier CDs don't flatten the
  gradient. Output: 161KB PNG vs the 2.4MB SVG matplotlib was producing
  before.
- Dropped the unused `teaser-map.json` GeoJSON output — Ch. 0 ships
  static-only per plan §9, and a 2MB blob in the website's `/public`
  dir for no consumer is dead weight. The `write_teaser_geojson()`
  function stays in the file for when an interactive variant lands.
- Ran with real data: `LOOKBACK_DAYS=30 SNAPSHOT=2026-05-01 python
  analyses/chapter-00/notebook.py`. Result: 296,426 311 calls over the
  month across 59 CDs. Top: MN 12 (Washington Heights / Inwood) at
  8,716. Bottom: BX 2 at 2,172. Wakefield (BX 12) again shows as a
  clear hotspot, matching the earlier 1-day signal.
- `python -m shared.publish --chapter 0` copied
  `teaser.png` (161 KB) + `facts.json` (1 KB) into
  `../personal-website/public/measuring-new-york/chapter-00/`.

**Vintage exception (per plan §5.3):**
- Series snapshot is pinned 2026-06-01 in `MANIFEST.json`. Today
  (2026-05-23) is 9 days before that. Ch. 0 used 2026-05-01 instead
  — last full month boundary, definitively past. The chapter's
  MethodologyFooter calls this out so the website reader sees it.
  When 2026-06-01 passes, re-run the notebook with the locked vintage
  and `make publish CHAPTER=0` to refresh the artifacts.

**Tried but didn't ship:**
- SVG output (2.4MB from matplotlib's path-based renderer; PNG was
  15× smaller and sharper).
- Per-capita normalization for the teaser. Calls-per-sq-mi tells the
  density-of-friction story the pilot is about. Per-capita is the
  right frame for Ch. 8 and will show different CDs.

**Blocked / partial:**
- (none on the data side)

**Next action:**
- Start Chapter 1 (Mobility & Access). See STATUS.md "Next action".

**Notes for next agent:**
- The `compute_311_density_by_cd()` loop hits the 311 API 59 times
  (once per CD). With `--snapshot 2026-05-01 --days 30` this takes
  ~30s and lands ~30MB across 59 cache files. Subsequent runs are
  instant via cache. To wipe and re-fetch, drop the files in
  `cache/three_one_one/` or pass a new snapshot.
- The PNG renderer uses `palette.for_matplotlib()` which sets serif
  font defaults — if Source Serif 4 is not installed system-wide it
  silently falls back. The Ch. 0 PNG title font matches the website's
  Source Serif headings either way (matplotlib's font discovery on
  macOS finds the system serif). Verified visually in headless
  Chrome screenshots.

---

## 2026-05-23 — Phase 1 shipped: end-to-end proven on CD 301
**Repo:** measuring-new-york
**Phase / chapter:** Phase 1 / N/A (foundation)
**Session length:** ~3h

**What changed (shipped):**
- Directory layout per plan §3.2: `pipelines/`, `geographies/`,
  `cache/`, `analyses/{chapter-00,chapter-01}/out`, `shared/`, `scripts/`.
- Meta files: `README.md`, `STATUS.md`, `WORKLOG.md` (this file),
  `.gitignore`, `MANIFEST.json` with pinned vintages (ACS 2019–2023 5yr,
  NYC Open Data + MTA GTFS + OSM Overpass snapshots dated 2026-06-01),
  `cache/MANIFEST.json` written as each fetch lands.
- `Makefile` with targets: `venv`, `geographies`, `fetch-gtfs`,
  `chapter-N` (rebuild from cache), `chapter-N FRESH=1` (re-fetch),
  `publish CHAPTER=N`, `clean`, `lint`, `nbexec`.
- `requirements.txt` — Python 3.9 compatible: pandas, geopandas, duckdb,
  shapely, sodapy, requests, gtfs-kit, osmnx, matplotlib, jupyter,
  python-dotenv, tqdm, censusdata. (cenpy dropped — needs Python ≥3.10.)
- `shared/`:
  - `palette.py` — series color tokens mirrored from
    `personal-website/src/app/globals.css`, plus a
    `for_matplotlib()` rc-params helper.
  - `basemap.py` — EPSG:2263 ↔ 4326 reprojection helpers, a `load(kind)`
    convenience for each canonical geography, and `cd_code(borough,
    number)` for borough-prefixed 3-digit CD codes.
  - `isochrone.py` — placeholder for GTFS-based isochrones (Ch. 1 lift).
  - `cache.py` — MANIFEST.json read/write with SHA-256 + URL + fetch ts.
  - `publish.py` — copies `analyses/chapter-N/out/*` into
    `../personal-website/public/measuring-new-york/chapter-N/`.
    Accepts `--website-repo` to override the target path.
- `pipelines/` — six fetcher modules + a `refresh.py` orchestrator. Each
  exposes a `build_query(...)` (pure), `fetch(...)` (cached + manifested),
  `load(...)` (reads from cache), and a CLI with `--dry-run`.
  `mta_gtfs.py`, `doh_air.py`, `hpd_violations.py`, `three_one_one.py`,
  `acs_census.py`, `osm_overpass.py`.
- `scripts/download_geographies.py` — pulls Community Districts (59 + 12
  JIAs), NTAs 2020, Census Tracts 2020, MODZCTA from NYC Open Data.
  Corrected the CD dataset ID after the original guess 404'd: the
  current canonical CD ID is **`5crt-au7u`** (DCP version 26a), not the
  older `jp9i-3b7y`. NTA / tract / MODZCTA IDs were already correct.
- `analyses/chapter-00/notebook.py` — Chapter 0 pilot scaffold. Loops
  over all 59 CDs, fetches per-CD 311 density, writes a CD-choropleth
  GeoJSON (`out/teaser-map.json`) and a `out/facts.json` headline-number
  dict. Honors `LOOKBACK_DAYS` + `SNAPSHOT` env vars for ergonomic
  smoke-testing.
- Created Python 3.9 venv at `.venv/`. Installed core spatial + data
  stack (pandas 2.3, geopandas 1.0, shapely 2.0, pyproj 3.6, fiona
  1.10, requests 2.32, sodapy 2.2). gtfs-kit / osmnx / censusdata
  deferred to first use (in `requirements.txt`, not installed yet).

**Smoke tests run (in order):**
1. All four geographies downloaded, recorded in `cache/MANIFEST.json`.
   `CDs: 71 features, CRS: EPSG:2263, CD 301 area = 131,695,442 sq ft`.
2. Six pipeline `--dry-run` invocations — every module composes a
   well-formed request URL/payload.
3. **Real fetch:** `pipelines.three_one_one --cd 301 --days 1
   --snapshot 2025-12-01` → 153 records (53 KB), cached and manifested.
   Confirmed `community_board = '01 BROOKLYN'` filter selects CD 301
   correctly.
4. **End-to-end:** `LOOKBACK_DAYS=1 SNAPSHOT=2025-12-01 python
   analyses/chapter-00/notebook.py` ran all 59 CDs, produced
   `out/teaser-map.json` (3.9 MB GeoJSON, 71 features) and
   `out/facts.json` (9,766 311 calls on the test day; top-3 CDs
   reported).
5. **Publish:** `python -m shared.publish --chapter 0` copied both
   artifacts into `../personal-website/public/measuring-new-york/chapter-00/`.
   Then wiped — these were smoke-test outputs, not real Ch. 0 content,
   so leaving them in the website public dir would mislead the next
   agent. The publish path itself is proven.

**Tried but didn't ship:**
- MTA GTFS bundle (~200MB) — module is wired, not downloaded yet.
  Deferred to Chapter 1 start (per plan §9, interactive mobility maps
  are a Ch. 1/9-only thing anyway).
- Real ACS fetch — needs `CENSUS_API_KEY` env var (free signup). Dry-run
  validated the URL composition; the actual `GET` is one env-var away.
  Logged as an Open Blocker in STATUS, not blocking phase close.
- Did not install `cenpy` — needs Python ≥3.10. Substituted `censusdata`
  in requirements.txt. When we move to Python 3.12, switch to cenpy.
- Did not write the `.ipynb` form — shipped `notebook.py`. Plan allows
  either (§3.2). `jupytext` is in requirements for conversion.
- The 4MB teaser-map ships as raw GeoJSON. Production should reduce
  precision / simplify polygons (target <500KB). Logged as a Chapter 0
  visual-pipeline TODO.

**Blocked / partial:**
- (nothing breaking). Two soft blockers documented in STATUS open
  blockers section (Census key, GTFS pull); neither holds back the
  Chapter 0 prose.

**Next action:**
- See `STATUS.md` "Next action" — either start Chapter 0 prose in the
  website repo, or close the two soft blockers (Census key signup +
  MTA GTFS prefetch) now to de-risk Ch. 1.

**Notes for next agent:**
- Python version: plan §5.1 specifies 3.12, we built on system 3.9.6
  to avoid a Homebrew install. Most libs are fine on 3.9; the ones
  that aren't (`cenpy`) were swapped. If you need 3.12, recreate
  `.venv` from `brew install python@3.12`.
- `cache/MANIFEST.json` now has 5 entries (4 geographies + 1 311 fetch).
  Pipeline cache hits short-circuit network calls — drop the cache key
  or pass a new `--snapshot` to force re-fetch.
- The series palette in `shared/palette.py` mirrors the website CSS.
  If you change colors, update both.
- `mta_gtfs.py` uses well-known `rrgtfsfeeds.s3.amazonaws.com` URLs. If
  the MTA moves these (they have historically), update `BUNDLES` and
  re-record the manifest.
- The corrected CD dataset ID (`5crt-au7u`) is the one to use going
  forward — DCP version 26a, quarterly updates. Older IDs 404.
- The publish target uses `../personal-website/...` by default; pass
  `--website-repo /path/to/other` to override.

---
