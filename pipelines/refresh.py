"""Re-fetch every dataset a chapter needs.

Driven by the Makefile via ``make chapter-N FRESH=1``. Each chapter declares
its dataset list here; ``main(chapter=N)`` walks the list and forces a
fresh fetch (bypassing the cache).
"""

from __future__ import annotations

import argparse

CHAPTER_DATASETS = {
    0: [
        ("three_one_one", {"cd": "301", "days": 30}),
    ],
    1: [
        ("mta_gtfs", {"bundle": "subway"}),
        ("osm_overpass", {"query": "parks"}),
        ("acs_census", {"table": "B08303", "geo": "tract"}),
    ],
    2: [
        ("hpd_violations", {"days": 365}),
        ("acs_census", {"table": "B25070", "geo": "tract"}),
        ("acs_census", {"table": "B25064", "geo": "tract"}),
    ],
    3: [
        ("doh_air", {"pollutant": "Fine particles (PM 2.5)"}),
    ],
}


def refresh(chapter: int) -> None:
    from importlib import import_module
    from shared import cache

    if chapter not in CHAPTER_DATASETS:
        raise ValueError(f"no dataset list for chapter {chapter}")

    for mod_name, kwargs in CHAPTER_DATASETS[chapter]:
        mod = import_module(f"pipelines.{mod_name}")
        # crude bust: drop the manifest entry for whatever this fetch produces,
        # then call fetch().
        if hasattr(mod, "build_query"):
            cache_keys_before = set(cache._load_manifest().get("entries", {}))
        print(f"\n=== refresh {mod_name}({kwargs}) ===")
        # `fetch` writes to cache + updates manifest; if the cache already has
        # the key, it short-circuits. To force a refresh, we drop the file
        # before calling.
        if "fetch_bundle" in dir(mod):
            mod.fetch_bundle(**kwargs)
        else:
            mod.fetch(**kwargs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter", type=int, required=True)
    args = ap.parse_args(argv)
    refresh(args.chapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
