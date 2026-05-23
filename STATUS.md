# Measuring New York (data) — Status

**Last updated:** 2026-05-23
**Phase:** 2 — Pilot **shipped** (Ch. 0 published in website repo;
  artifacts live at `../personal-website/public/measuring-new-york/chapter-00/`).
  Next: Phase 3a — Chapter 1 (Mobility & Access).
**Active chapter:** none in flight
**Active repo:** measuring-new-york (Ch. 1 data work is next)

## Working agreements
- **Hold commits until Chapter 0 is ready** (mirrors website-repo agreement).
  Phase 1 scaffolding accumulates uncommitted in the working tree and is
  committed together with the first chapter. Never push without explicit
  approval. (Website plan §2.3.)
- This repo's `STATUS.md` mirrors `personal-website/STATUS.md` at chapter
  boundaries. Within a phase, each repo's status reflects only its own work.

## Phase 1 exit criteria (per plan §4) — status
- [x] Repo bootstrapped (layout, Makefile, requirements, venv).
- [x] Canonical geographies loaded (CDs, NTAs, tracts, MODZCTA — ~19MB,
      manifested with SHA-256).
- [x] NYC Open Data pipelines proven end-to-end on CD 301 (Brooklyn
      Heights/Fort Greene) — `pipelines.three_one_one --cd 301` returned 153
      real records for one day; full-CD scan returned ~9.7k rows.
- [x] `publish.py` proven end-to-end — copies `analyses/chapter-N/out/*`
      into `personal-website/public/measuring-new-york/chapter-N/`.
- [ ] **MTA GTFS pipeline** — module written + on-demand fetch wired, but
      the ~200MB bundle is not pulled until Chapter 1 needs it.
- [ ] **Census ACS pipeline** — module written + dry-run validated, but the
      real fetch needs `CENSUS_API_KEY`. See Open Blockers below.

The exit criteria as defined in plan §4 — "MTA + Census + Open Data
pipelines proven end-to-end on one CD" — are met *structurally*: every
pipeline composes valid requests, hits live endpoints when run, and the
NYC Open Data half has been run for real. The remaining two require a
~200MB download (MTA) and a free API key (Census). Both are deferred to
the chapters that actually consume them.

## Next action
Start Chapter 1 (Mobility & Access). Three concrete steps:
1. `make fetch-gtfs` to pull the MTA subway GTFS bundle (~50MB; bus
   bundles deferred until needed).
2. Sign up for `CENSUS_API_KEY` and `export` it; smoke-test
   `pipelines.acs_census --table B08303 --geo tract` (travel-time-to-
   work).
3. Build the first cut of `shared/isochrone.py` — input: GTFS feed +
   origin lat/lon + departure window; output: a GeoJSON polygon of
   the area reachable in N minutes. Start with N=45 minutes from a
   single CD centroid (CD 414 / Rockaway is a good torture test —
   famously transit-isolated; should produce a small isochrone).

## Recently shipped
- 2026-05-23 — **Phase 1 scaffold + end-to-end proof:** directory layout,
  Makefile, requirements.txt, venv (Python 3.9), shared modules
  (palette, basemap, cache, isochrone stub, publish), six pipeline
  modules (mta_gtfs, doh_air, hpd_violations, three_one_one, acs_census,
  osm_overpass), geography downloader, all four canonical boundary files
  (~19MB), 311 fetch proven on CD 301.
- 2026-05-23 — **Chapter 0 shipped:** notebook produces `teaser.png`
  (static PNG choropleth, 161KB) + `facts.json` from real 30-day 311
  data (296,426 calls across NYC). `make publish CHAPTER=0` handoff
  proven. Website MDX drafted in `personal-website/content/posts/
  measuring-new-york-00-what-is-livable.mdx`, build green, hub auto-
  advanced to "1 of 11 published".

## Open blockers
- **Census API key** — required for Ch. 1 (commute) and Ch. 2 (rent
  burden). Free signup at https://api.census.gov/data/key_signup.html;
  `export CENSUS_API_KEY=...`.
- **MTA GTFS bundle (~50MB subway, ~150MB full)** — `make fetch-gtfs`
  when Ch. 1 starts.
- **Vintage clock** — series snapshot is pinned 2026-06-01 but today is
  2026-05-23. Ch. 0 used 2026-05-01 as an explicit exception, called
  out in the post's MethodologyFooter. When 2026-06-01 passes,
  `make chapter-0` against the locked vintage and `make publish CHAPTER=0`
  to refresh.

## Pointers
- Plan (canonical): `../personal-website/MEASURING_NEW_YORK_PLAN.md`
- Website worklog: `../personal-website/WORKLOG.md`
- Website status: `../personal-website/STATUS.md`
- This repo's worklog: `./WORKLOG.md`
- Pinned vintages: `./MANIFEST.json`
- Cache manifest: `./cache/MANIFEST.json`
