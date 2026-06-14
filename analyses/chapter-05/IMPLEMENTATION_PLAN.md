# Chapter 5 — Implementation Plan & Session Handoff

End-to-end plan for *Public Space & Urban Experience* — data pull →
analysis → first-draft article. Written to be executed by a fresh
session. The chapter **spec** (hypothesis, axes, kill criterion, datasets,
caveats) is in the sibling `PLAN.md`; this file is the **build plan +
current state**. Read `PLAN.md` first, then this.

> **Repos.** Data/analysis: `measuring-new-york` (this repo), branch
> **`ch5-public-space`**. Article: `personal-website`
> (`content/posts/measuring-new-york-05-public-space.mdx`), fed by
> `make publish CHAPTER=5`. Set `WEBSITE_REPO_PATH=../personal-website`.

---

## Locked decisions (do not relitigate)

1. **Spine = three baskets of public life** (user's call): open space
   (parks + plazas), street vitality (eateries + cultural venues),
   pedestrian realm (sidewalk generosity + pedestrianization).
2. **Eateries = OSM `restaurant|cafe|bar`** (NO `fast_food`); cultural =
   OSM `theatre|arts_centre|museum|gallery`; DOHMH `43nn-pn8j` is a
   footer cross-check only.
3. **Sidewalk width = polygon-area approximation** (sidewalk area ÷
   street-segment length per CD). Disclosed in footer. NOT the
   centerline-buffer method.
4. **First checkpoint = the spine verdict.** Build through the spine test,
   then PAUSE and report which framing won BEFORE anchors/visuals/prose.
   (The basket spine is at high risk of firing on the density confound —
   ρ≈0.74 nearly killed Ch.4 and this is worse. Fallback is path B below.)
5. **Vintage pin = 2026-06-01.** Geography = 59 residential CDs.
   EPSG:2263 for math, EPSG:4326 for output.

**Path B fallback (if the basket spine fires |ρ|≥0.75 or compresses near
1.00):** reframe to **vibrancy vs. comfort** — (a) vibrancy = eateries +
cultural + business density per 1k residents (`w7w3-xahh` or OSM); (b)
restorative space = park + plaza **acres per capita** (supply, not
proximity — the Ch.4 proximity≠sufficiency move); (c) pedestrian comfort
= sidewalk generosity + pedestrianized street-miles per capita. Headline
becomes a **vibrancy-vs-restorative-space scatter**.

---

## Current state (as of 2026-06-13)

Done:
- Branch `ch5-public-space` created (off `main`). **Uncommitted** — repo
  rule is never push without approval; hold commits for the user too.
- `analyses/chapter-05/PLAN.md` — chapter spec (decisions logged).
- `analyses/chapter-05/notebook.py` — scaffold reusing Ch.4's harness
  (`pct_within_walk` / `tract_to_cd` / `per_cd_population` / `spine_test`).
  Axis 1 wired on parks; plazas + axes 2/3 are typed stubs returning
  `None`. Compiles; runs in stub mode.
- `pipelines/nyc_dot_plazas.py` — **built** (`k5k6-6jex`; MultiPolygons,
  carries `borocd` + `shape_area`). Mirrors `nyc_parks.py`. Not yet run.
- `.venv` built (`make venv`, exit 0). Geographies NOT yet pulled.

Not done: `make geographies`; the 4 remaining data pulls; axis wiring;
spine test; everything after.

---

## Known blockers / wrinkles (hit these head-on)

- **Census API key.** ACS B01003 (pop weights) + B01001 (if path-B needs
  age denominators) require `CENSUS_API_KEY` in `measuring-new-york/.env`
  (gitignored, NOT in the clone). `pipelines/acs_census.py` checks cache
  before the key, so if `make geographies` / a prior run cached B01003
  this is a non-issue; otherwise the key must be set. Flag to the user if
  missing.
- **Sidewalk `vfx9-tbb6` is heavy + awkward.** The plain `.geojson`
  resource endpoint returns null geometry / empty props on a simple
  query (same Socrata quirk Ch.4 saw with FacDB), and the full
  planimetric layer is enormous (millions of polygons). Do NOT pull it
  whole. Use a Socrata **aggregation**: `$select=sum(shape_area)` grouped
  by whatever CD/geo field exists, or pull `shape_area` + a join key only
  (no geometry) and aggregate. If it stays intractable, axis 3 can ship
  on **pedestrianization only** (plazas + Open Streets) for the spine
  test and add sidewalk later — note the reduced axis in `facts.json`.
- **Open Streets dataset id is unconfirmed.** Verify the DOT "Open
  Streets Locations" Socrata id before building `nyc_dot_open_streets.py`
  — do NOT guess it. (`pedestrian` browse on NYC Open Data, or the
  data.gov "Open Streets Locations" catalog entry.)

---

## Phase 0 — Environment  ✅ venv done
1. `make venv` ✅
2. `make geographies` — CDs (`5crt-au7u`), tracts, NTAs, MODZCTA.
3. Ensure `CENSUS_API_KEY` set (or confirm B01003 cached).
4. Smoke-test: `python analyses/chapter-05/notebook.py` (parks-only stub).

## Phase 1 — Data pull (pipelines)
Build order (simplest first, to de-risk the method — Ch.4 discipline).
Each: `build_query`→`fetch`(cache+`record()`)→`load`(EPSG:2263)+`--dry-run`,
and a `MANIFEST.json` + `cache/MANIFEST.json` entry (URL, ts, SHA-256, size).

| # | Module / query | Source | Status |
|---|---|---|---|
| 1 | `pipelines/nyc_dot_plazas.py` | `k5k6-6jex` | ✅ built, not run |
| 2 | `osm_overpass.QUERIES["eateries"]` | OSM `restaurant\|cafe\|bar` | TODO (add to module) |
| 3 | cultural venues | OSM `theatre\|arts_centre\|museum\|gallery` | TODO (new query or pipeline) |
| 4 | `pipelines/nyc_sidewalk.py` | `vfx9-tbb6` (aggregate, see wrinkle) | TODO |
| 5 | `pipelines/nyc_dot_open_streets.py` | DOT Open Streets (id TBC) | TODO |
| — | DOHMH cross-check (optional) | `43nn-pn8j` | TODO (footer only) |

## Phase 2 — Analysis (gate everything on the spine test)
In `analyses/chapter-05/notebook.py` (reuse the inherited harness):
- **2a.** Wire axis 1 (parks ∪ plazas), axis 2 (mean of eateries +
  cultural walk-access), axis 3 (mean of sidewalk generosity +
  pedestrianization). Each = pop-weighted % within 2,640 ft.
- **2b. Run `spine_test`** → 3×3 Spearman, kill at |ρ|≥0.75.
  **⟵ FIRST CHECKPOINT. STOP. Report verdict + chosen framing to user.**
  - survives → keep three baskets; plan a completeness-score choropleth.
  - fires/compresses → switch to path B; build the vibrancy-vs-comfort
    scatter. Add business-density + per-capita acreage metrics, re-run.
- **2c.** (after user OK) Pick 5 anchors — 1/borough, spanning the
  measurement-space corners; include a "vibrant but no room to breathe"
  surprise anchor + a "quiet residential comfort" anchor. Names from
  `shared/cd_names.py`. Reuse a prior-chapter anchor for series coherence.
- **2d.** Render to `analyses/chapter-05/out/`: `public-space.geojson`
  (per-CD all axes + score + ranks + class, display-CRS, 50-ft simplified),
  headline visual SVG, `facts.json`, `rankings.csv`.

## Phase 3 — Publish + bookkeeping
- `make publish CHAPTER=5` → `personal-website/public/measuring-new-york/chapter-05/`.
- `hero.jpg` (placeholder ok; user swaps).
- `WORKLOG.md` entry in BOTH repos (newest at top).
- Promote spec to website plan §10 active block; demote Ch.4 → archived.

## Phase 4 — First-draft article (the artifact the user reviews)
`content/posts/measuring-new-york-05-public-space.mdx`. STYLE_GUIDE §2
8–11 section template, 2,000–3,000 words, voicey first-person (match the
Ch.4 register). Frontmatter like Ch.4: `title`, `date`, `readTime`,
`hero`, `excerpt`, `tags`, `series: "measuring-new-york"`, `seriesOrder: 5`,
`seriesPartTitle: "Public Space & Urban Experience"`, `toc: true`.

Sections → data:
1. **Cold open** — the surprise anchor, real numbers; set up the inversion.
2. **`<MetricCallout>`** — the headline number.
3. **Why public space deserves its own chapter** — third places,
   spontaneity, cohesion (`measuring_livability.md` §6).
4. **Why it's hard to measure** — the density trap; names the hypothesis.
5. **The map** — `<NycMap>` headline choropleth + post-map observation.
6. **Five neighborhoods** — static comparison table + `<NeighborhoodExplorer>`
   with 5 **flush-left** `<Anchor>` blocks (mind the MDX indentation +
   blank-line gotchas in STYLE_GUIDE §4/§8).
7. **The contradiction** — reframe the spine result (likely "one density
   signal; the inequality that matters is per-capita room").
8. *(optional)* **A chapter score** — only if the spine survives.
9. **What this means for a household/person** — 1–2 practical bullets.
10. **What this measure misses** — see PLAN.md's footer list.
11. **Reach for the next chapter** — tee up Ch.6 (Safety); backward
    links to Ch.1–4 are mandatory.
- **`<MethodologyFooter>`** — sources (with dataset IDs), notebook link,
  Ch.10 pointer.

## Phase 5 — Review handoff
Hand the user: spine verdict, anchor table, headline visual, draft MDX.
Revise on feedback. No `git push` (and hold commits) without explicit OK.

---

## Quick start for the next session
```bash
cd measuring-new-york
git switch ch5-public-space            # work is here, uncommitted
source .venv/bin/activate
export WEBSITE_REPO_PATH=../personal-website
make geographies                       # if not cached
# (ensure CENSUS_API_KEY in .env, or confirm B01003 cached)
python -m pipelines.nyc_dot_plazas     # run the built pipeline
python analyses/chapter-05/notebook.py # stub run; then wire axes per Phase 1–2
```
Then proceed Phase 1 → 2b and STOP at the spine verdict (checkpoint #1).
```
