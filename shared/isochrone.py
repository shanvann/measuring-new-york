"""GTFS isochrone helpers (placeholder for Chapter 1's heavy lift).

Real implementation arrives with Chapter 1 (Mobility & Access). The plan
calls for precomputed isochrones shipped as GeoJSON so the website never
does routing at request time.

This module defines the function signature so chapter notebooks can be
sketched today against the eventual API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def precompute_isochrones(
    gtfs_path: Path,
    origins: Iterable[tuple[float, float]],
    minutes: Iterable[int] = (15, 30, 45),
    departure: str = "Tue 08:00",
) -> dict:
    """Compute travel-time polygons from each origin for each cutoff.

    Returns a dict of FeatureCollections keyed by minute cutoff. Will be
    implemented against ``gtfs-kit`` + a walk-network graph in Chapter 1.
    """
    raise NotImplementedError(
        "isochrone precompute lands with Chapter 1 — see plan §8 row 1"
    )
