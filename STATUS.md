# Measuring New York (data) — Status

**Last updated:** 2026-05-23
**Phase:** 3a — **Chapter 1 shipped** (drafted; awaits user review).
  Per-tract isochrones for all 2,303 NYC tracts, LEHD LODES 2022
  integration, 229× median variance + 4.8× intra-CD spread for South
  Ozone Park as the headline. Ch. 0 shipped 2026-05-23 (commit
  `52a3ae1`); Phase 3a Day 1 shipped (commit `7fe518e`); Day 2+3 work
  currently uncommitted.
**Active chapter:** none in flight; Ch. 2 (Housing) is next.
**Active repo:** measuring-new-york (Phase 3b data work) +
  the website repo (Ch. 2 prose later).

## Working agreements
- Commit per chapter or per logical scaffolding change. Ch. 0 shipped
  2026-05-23 as `52a3ae1` (this repo) / `e693e1f` (website). Phase 3a
  Day 1 shipped as `7fe518e` (this repo) / `ece99da` (website). Day 2
  (isochrones + ACS smoke-test) currently uncommitted.
- Never push without explicit approval.

## Phase 1 exit criteria (per plan §4) — all met
- [x] Repo bootstrapped.
- [x] Canonical geographies cached.
- [x] NYC Open Data pipeline proven on CD 301 (and now on all 59 CDs).
- [x] `publish.py` proven end-to-end (Ch. 0 + Ch. 1 artifacts shipped).
- [x] MTA GTFS pipeline — feed cached, `gtfs-kit` loads it, isochrone
      computation working on all 5 anchor CDs.
- [x] Census ACS pipeline — `CENSUS_API_KEY` set in `.env` (gitignored);
      smoke-tested with B19013 (borough income, 5 rows) + B08303
      (travel-time-to-work, 2327 tracts cached). End-to-end via the
      existing pipeline module.

## Next action
Phase 3b — **Chapter 2 (Housing Stability & Affordability)**:
1. Plan §10: archive Ch. 1's active spec, draft Ch. 2's (hypothesis,
   anchor CDs, headline visual, kill criteria).
2. Wire eviction filings pipeline (OCA / NYC Open Data — new module).
   HPD violations pipeline already exists; ACS B25070 + B25064
   already smoke-tested.
3. Compute per-tract rent burden + violations density (re-using the
   per-tract approach from Ch. 1 so intra-CD variance can be surfaced).
Plan window: Aug 8–28.

## Recently shipped
- 2026-05-22 — Phase 0 (site scaffolding); 2026-05-23 — Phase 1
  (analysis repo bootstrap); Phase 2/Ch. 0 (pilot, commit `e693e1f`);
  Phase 3a Day 1 (interactive `<NycMap>`, commit `ece99da`).
- 2026-05-23 — **Phase 3a Day 2:**
  - `shared/isochrone.py` is now a real time-dependent Dijkstra over
    the GTFS schedule. 280 LOC. precompute() builds per-stop sorted
    departure lists + per-trip stop sequences + walking-transfer
    indexes (~1500 stops, ~8500 weekday trips). reachable_stops()
    runs heap-based Dijkstra with three edge kinds: ride (next stop
    on current trip), board (any trip departing within next 20 min),
    walk-transfer (nearby stops within 1500 ft). polygonize() builds
    the isochrone as union of walk-buffers around reachable stops,
    sized by remaining minutes.
  - `analyses/chapter-01/notebook.py` ships. Outputs
    `out/isochrones-45min.geojson` (FeatureCollection of 5 anchor-CD
    polygons) + `out/facts.json`. Real numbers: Midtown East reaches
    385 subway stops in 45 min vs Rockaway's 23 — **16.7× variance**.
    Headline supports the Ch. 1 hypothesis directly.
  - Caught + fixed: initial 0.5 mi catchment was too tight for some
    CDs (Wakefield's nearest stop is 0.63 mi from the centroid).
    Bumped `WALK_TO_ORIGIN_MAX_FT` to 0.75 mi — the APTA/TCRP 95
    subway-stop standard. CD 212 went from 0 to 28 reachable stops.
  - `make publish CHAPTER=1` landed artifacts at the website repo's
    `public/measuring-new-york/chapter-01/`.
  - Census API key smoke-tested: B19013 (borough income) + B08303
    (travel-time-to-work, 2327 tracts) cached. Key set in `.env`
    (gitignored).

## Recently shipped
- 2026-05-23 — **Phase 1 scaffold + end-to-end proof** (commit
  `52a3ae1` on github).
- 2026-05-23 — **Chapter 0 shipped** (commit `e693e1f` on website
  repo): 161KB static PNG + facts.json from 296,426 real 311 calls.
- 2026-05-23 — **Phase 3a Day 1:**
  - MTA subway GTFS cached (5.8MB; smaller than estimated). gtfs-kit
    installed; loads 1488 stops / 29 routes / 21459 trips end-to-end.
  - 30-day 311 data now cached at the pinned 2026-06-01 snapshot for
    all 59 CDs (under cache/three_one_one/cd-*-2026-06-01-last30d.json).
  - Website-side: real interactive `<NycMap>` shipped with MapLibre +
    deck.gl. See website-repo WORKLOG for the full breakdown.

## Open blockers
- **LEHD LODES vintage** not yet pinned in `MANIFEST.json`. Needed for
  the "jobs reachable in 45 min" overlay. The 2021 release is the most
  recent; sometimes 2022 if NIH has refreshed by now.
- **Vintage clock** — series snapshot pinned 2026-06-01, today 2026-05-23.
  Ch. 0 used 2026-05-01 as an explicit exception. Refresh after
  2026-06-01.
- **Census key in chat history.** The provided key is in this session's
  transcript. Rotate it (sign up again at the same URL) when convenient.

## Pointers
- Plan (canonical): website repo, `MEASURING_NEW_YORK_PLAN.md` at root
- Website worklog + status: website repo, `WORKLOG.md` and `STATUS.md`
- This repo's worklog: `./WORKLOG.md`
- Pinned vintages: `./MANIFEST.json`
- Cache manifest: `./cache/MANIFEST.json`
- Publish target: set `$WEBSITE_REPO_PATH` to the sibling website repo
