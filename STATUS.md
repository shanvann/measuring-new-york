# Measuring New York (data) — Status

**Last updated:** 2026-05-23
**Phase:** 3a — **Chapter 1 (Mobility & Access)** active. Ch. 0 shipped
  2026-05-23 (commit `52a3ae1`). See website-repo plan §10 for the
  full Ch. 1 spec.
**Active chapter:** Ch. 1
**Active repo:** measuring-new-york (GTFS + ACS + OSM pipelines) +
  personal-website (real MapLibre `<NycMap>`)

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
Build the first real GTFS isochrone in `shared/isochrone.py`.
- Input: GTFS feed + origin (lat, lon) + departure window + max minutes.
- Output: a GeoJSON polygon of the area reachable in N minutes by
  transit + walk legs.
- Smoke test targets: CD 414 (Rockaway, transit-isolated → small
  polygon) and CD 105 (Midtown East → covers most of dense subway
  grid).

Pragmatic MVP path: gtfs-kit's walk-network helpers + a `networkx`
Dijkstra over (stop, time) nodes. More rigorous path: `r5py` (wraps
Conveyal R5; JVM dep but battle-tested). Decide on arrival.

After isochrone: ACS commute pull (B08303, B08301) — needs the
Census API key (see Open blockers).

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
