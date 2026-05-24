# measuring-new-york

Data, pipelines, and notebooks behind the **Measuring New York** blog series on
[shanvannala.com](https://shanvannala.com). Articles live in a sibling repo
(`personal-website`); this repo is the upstream source of truth for every
chart, map, and number that ships in the series.

## Setup

```bash
make venv             # one-time: create .venv with Python 3.9 + install deps
source .venv/bin/activate
make geographies      # one-time: pull canonical boundary files (~50MB)
make chapter-0        # rebuild Ch. 0 artifacts from cache (idempotent)
make publish CHAPTER=0  # copy artifacts into ../personal-website
```

Set `FRESH=1` on any `chapter-N` target to re-fetch from upstream sources
instead of replaying the cache (`make chapter-1 FRESH=1`).

## Layout

```
pipelines/        one module per dataset (mta_gtfs, doh_air, ...)
geographies/      canonical boundary files (CDs, NTAs, tracts, MODZCTA)
cache/            raw downloads (gitignored except MANIFEST.json)
analyses/         one folder per chapter; notebooks + final artifacts
shared/           palette, basemap, publish, isochrone, cache helpers
scripts/          one-off utilities (geography downloader etc.)
MANIFEST.json     pinned dataset vintages — all chapters use these
```

## Conventions

- **Projection:** all spatial math in EPSG:2263 (NY State Plane, feet);
  reproject to EPSG:4326 only for output.
- **Default geography:** Community Districts (59). Tract-level only where a
  chapter justifies it.
- **Reproducibility:** every cached file has an entry in `cache/MANIFEST.json`
  with URL, fetch timestamp, SHA-256, size. Every artifact shipped to the
  website repo carries a comment pointing back at its source notebook cell.
- **Handoff:** `shared/publish.py` (driven by `make publish`) is the only
  sanctioned path from this repo to `personal-website`. No submodules, no
  build-time coupling.

## Pinned vintages

See `MANIFEST.json`. The vintages are frozen for the entire series; a chapter
that needs a different vintage must justify it in its worklog entry.

## License

TBD. Public + MIT is the default plan once Phase 1 stabilizes (see plan §13).
