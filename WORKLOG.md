# Measuring New York (data) — Worklog

> Append-only. **Newest entry at the top.** See
> `../personal-website/MEASURING_NEW_YORK_PLAN.md` §11 for the entry template
> and logging rules.

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
