"""GTFS isochrone helpers (Chapter 1 — Mobility & Access).

Pragmatic implementation: time-dependent Dijkstra over the GTFS schedule
with straight-line walk legs (×1.4 detour factor). Not RAPTOR, not CSA —
just a heap-based search over stop visits with three kinds of edges:

1. **Ride edges:** continue on the trip you just arrived on to the next
   stop in sequence.
2. **Board edges:** from any stop visit at time T, board any trip that
   departs from the same stop within the next ``MAX_BOARD_WAIT`` minutes.
3. **Walk-transfer edges:** walk to nearby stops (straight-line distance
   times ``WALK_DETOUR_FACTOR``).

The isochrone polygon is the union of:
- A walk-circle around the origin sized for the full budget (in case you
  never board anything).
- A walk-buffer around each reachable stop, sized by the *remaining*
  minutes after arrival (so a stop you arrive at with 30 of 45 min left
  contributes a 30-min walk-circle around it).

Caveats / known-imperfections (will be in the Ch. 1 MethodologyFooter):
- Walk legs are straight-line × 1.4. A real walk graph (osmnx) would
  catch dead-end streets and bridges; for an MVP this is within ~10% in
  most NYC neighborhoods.
- Only the subway feed is loaded by default (no bus, no LIRR/Metro-North,
  no Access-A-Ride). Bus is the biggest gap; ~50% of NYC trips involve
  a bus leg.
- No realtime adjustment — we use scheduled times. The Ch. 1 hypothesis
  about reliability variance lives in a separate analysis using MTA's
  GTFS-Realtime feed; this module is schedule-only.
- Service date is whichever ``DEFAULT_SERVICE_DATE`` resolves to from
  ``calendar.txt`` — we pick a typical Tuesday within the feed's range.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

WALK_SPEED_FT_PER_MIN = 264.0   # 3 mph = 4.83 km/h, the AASHTO pedestrian default
WALK_DETOUR_FACTOR = 1.4        # straight-line distance × this ≈ network distance
TRANSFER_WALK_MAX_FT = 1500.0   # ~5.7 min walk; beyond this, drop the transfer edge
MAX_BOARD_WAIT_MIN = 20.0       # at any stop, only consider trips leaving in the next 20 min
WALK_TO_ORIGIN_MAX_FT = 5280.0  # 1.0 mi — upper-bound subway catchment (TCRP Synthesis 95).
# Wide catchment makes the model honest about outer CDs whose population
# centroids sit ~0.8-1.0 mi from any station. The cost shows up in the
# walking-time charge: 1.0 mi network is ~28 min, leaving ~17 min for transit
# — so distant origins get small isochrones, which is the right behavior.
MIN_TRANSFER_TIME_MIN = 0.5     # buffer to walk between platforms, etc.


@dataclass
class IsochroneResult:
    """Outputs of one isochrone computation."""
    origin: tuple[float, float]              # (lon, lat) in WGS84
    departure: datetime
    max_minutes: float
    reachable_stops: dict[str, float]        # stop_id -> arrival minutes
    polygon: object                          # shapely Polygon / MultiPolygon (WGS84)


# ---------- GTFS time helpers ----------

def _hhmmss_to_minutes(s: str) -> float:
    """Parse a GTFS HH:MM:SS string into minutes past midnight.

    GTFS allows times >24:00:00 (continuation of the previous service day);
    those return values >= 24*60.
    """
    h, m, sec = s.split(":")
    return int(h) * 60 + int(m) + int(sec) / 60.0


def _service_ids_for_date(feed, date: datetime) -> set[str]:
    """Which calendar service_ids are active on the given date.

    Honors ``calendar.txt`` weekday flags and ``calendar_dates.txt``
    additions/removals.
    """
    weekday = date.strftime("%A").lower()  # 'monday' etc.
    yyyymmdd = int(date.strftime("%Y%m%d"))
    active: set[str] = set()

    cal = feed.calendar
    if cal is not None:
        mask = (cal[weekday] == 1) & (cal["start_date"].astype(int) <= yyyymmdd) & (cal["end_date"].astype(int) >= yyyymmdd)
        active.update(cal.loc[mask, "service_id"].tolist())

    if feed.calendar_dates is not None and not feed.calendar_dates.empty:
        cd = feed.calendar_dates
        # exception_type 1 = added, 2 = removed
        adds = cd[(cd["date"].astype(int) == yyyymmdd) & (cd["exception_type"] == 1)]
        removes = cd[(cd["date"].astype(int) == yyyymmdd) & (cd["exception_type"] == 2)]
        active.update(adds["service_id"].tolist())
        active.difference_update(removes["service_id"].tolist())
    return active


def pick_typical_weekday(feed, prefer_weekday: int = 1) -> datetime:
    """Choose a service date that's a typical weekday within the feed's range.

    ``prefer_weekday``: 0=Mon, 1=Tue, …, 6=Sun. Default Tuesday.

    Picks the latest matching weekday within the feed's calendar range so we
    use current (not historical) service. Falls back to today if calendar.txt
    is empty/missing.
    """
    cal = feed.calendar
    if cal is None or cal.empty:
        return datetime.today()
    end_yyyymmdd = int(cal["end_date"].astype(int).max())
    end = datetime.strptime(str(end_yyyymmdd), "%Y%m%d")
    # walk backwards to the most recent matching weekday
    for delta in range(7):
        candidate = end - timedelta(days=delta)
        if candidate.weekday() == prefer_weekday:
            return candidate
    return end  # shouldn't happen


# ---------- Spatial helpers (no geopandas required for the hot loop) ----------

EARTH_R_FT = 20_902_231.0  # mean Earth radius in feet


def haversine_ft(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in feet."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_FT * math.asin(math.sqrt(a))


# ---------- GTFS preprocessing ----------

@dataclass
class _Precomputed:
    """Service-day-frozen view of the feed for fast routing.

    - ``stop_xy[stop_id]`` -> (lat, lon)
    - ``stop_departures[stop_id]`` -> sorted list of (dep_min, trip_id, seq)
    - ``trip_stops[trip_id]`` -> sorted list of (seq, stop_id, arr_min, dep_min)
    """
    stop_xy: dict[str, tuple[float, float]]
    stop_departures: dict[str, list[tuple[float, str, int]]]
    trip_stops: dict[str, list[tuple[int, str, float, float]]]
    transfers_by_stop: dict[str, list[tuple[str, float]]]  # stop_id -> [(other_stop_id, walk_min)]


def _build_walking_transfers(stops_df, max_ft: float = TRANSFER_WALK_MAX_FT) -> dict[str, list[tuple[str, float]]]:
    """For each stop, precompute walking transfers to all stops within max_ft.

    O(N²) in stops — fine at NYC scale (~500 parent stations, ~1500 platforms).
    To keep the routing graph honest we collapse N/S platform suffixes by
    parent_station when possible: a transfer "between the same physical
    station" is essentially free, and we already use parent_station to
    de-dup the stop list before pairing.
    """
    # Collapse to parent stations where defined (platform stops point at
    # their parent via parent_station).
    parents = (
        stops_df[stops_df.get("location_type", 1).fillna(0).astype(int) == 1]
        if "location_type" in stops_df.columns
        else stops_df
    )
    if parents.empty:
        parents = stops_df

    out: dict[str, list[tuple[str, float]]] = defaultdict(list)
    rows = list(parents.itertuples(index=False))
    for i in range(len(rows)):
        s1 = rows[i]
        for j in range(i + 1, len(rows)):
            s2 = rows[j]
            d = haversine_ft(s1.stop_lat, s1.stop_lon, s2.stop_lat, s2.stop_lon)
            if d <= max_ft:
                walk_min = (d * WALK_DETOUR_FACTOR) / WALK_SPEED_FT_PER_MIN + MIN_TRANSFER_TIME_MIN
                out[s1.stop_id].append((s2.stop_id, walk_min))
                out[s2.stop_id].append((s1.stop_id, walk_min))
    return out


def precompute(feed, service_date: Optional[datetime] = None) -> _Precomputed:
    """Freeze a feed against a service date and return route-ready indexes."""
    if service_date is None:
        service_date = pick_typical_weekday(feed)

    service_ids = _service_ids_for_date(feed, service_date)
    trips = feed.trips
    active_trips = trips[trips["service_id"].isin(service_ids)]
    active_trip_ids = set(active_trips["trip_id"])

    stop_times = feed.stop_times[feed.stop_times["trip_id"].isin(active_trip_ids)].copy()
    stop_times["dep_min"] = stop_times["departure_time"].map(_hhmmss_to_minutes)
    stop_times["arr_min"] = stop_times["arrival_time"].map(_hhmmss_to_minutes)
    stop_times["stop_sequence"] = stop_times["stop_sequence"].astype(int)
    stop_times = stop_times.sort_values(["trip_id", "stop_sequence"])

    # Per-stop departure index — for "what trips can I board here?"
    stop_departures: dict[str, list[tuple[float, str, int]]] = defaultdict(list)
    for r in stop_times.itertuples(index=False):
        stop_departures[r.stop_id].append((float(r.dep_min), r.trip_id, int(r.stop_sequence)))
    for sid in stop_departures:
        stop_departures[sid].sort()

    # Per-trip stop sequence — for "if I'm on trip X at sequence N, what's N+1?"
    trip_stops: dict[str, list[tuple[int, str, float, float]]] = defaultdict(list)
    for r in stop_times.itertuples(index=False):
        trip_stops[r.trip_id].append((int(r.stop_sequence), r.stop_id, float(r.arr_min), float(r.dep_min)))
    for tid in trip_stops:
        trip_stops[tid].sort()

    # Stop coordinates
    stop_xy = {r.stop_id: (float(r.stop_lat), float(r.stop_lon)) for r in feed.stops.itertuples(index=False)}

    transfers = _build_walking_transfers(feed.stops)

    return _Precomputed(
        stop_xy=stop_xy,
        stop_departures=stop_departures,
        trip_stops=trip_stops,
        transfers_by_stop=transfers,
    )


# ---------- Core routing ----------

def _initial_stops(pre: _Precomputed, origin_latlon: tuple[float, float], budget_min: float) -> list[tuple[str, float]]:
    """All stops within ``WALK_TO_ORIGIN_MAX_FT`` of origin, costed by walk-time."""
    olat, olon = origin_latlon
    out: list[tuple[str, float]] = []
    for sid, (slat, slon) in pre.stop_xy.items():
        d = haversine_ft(olat, olon, slat, slon)
        if d <= WALK_TO_ORIGIN_MAX_FT:
            walk_min = (d * WALK_DETOUR_FACTOR) / WALK_SPEED_FT_PER_MIN
            if walk_min <= budget_min:
                out.append((sid, walk_min))
    return out


def _bisect_left_dep(deps: list[tuple[float, str, int]], target_min: float) -> int:
    """Index of first departure with dep_min >= target_min."""
    lo, hi = 0, len(deps)
    while lo < hi:
        mid = (lo + hi) // 2
        if deps[mid][0] < target_min:
            lo = mid + 1
        else:
            hi = mid
    return lo


def reachable_stops(
    pre: _Precomputed,
    origin_latlon: tuple[float, float],
    departure: datetime,
    max_minutes: float,
) -> dict[str, float]:
    """Time-dependent Dijkstra from origin.

    Returns ``{stop_id: arrival_minutes_after_departure}`` for every stop
    reachable within ``max_minutes``.
    """
    depart_min_of_day = departure.hour * 60 + departure.minute + departure.second / 60.0

    arrival: dict[str, float] = {}
    pq: list[tuple[float, str]] = []

    for sid, walk_min in _initial_stops(pre, origin_latlon, max_minutes):
        arrival[sid] = walk_min
        heapq.heappush(pq, (walk_min, sid))

    while pq:
        cost, sid = heapq.heappop(pq)
        if cost > arrival.get(sid, math.inf):
            continue  # stale heap entry
        if cost > max_minutes:
            break  # pq is sorted; nothing reachable in budget remains

        absolute_now = depart_min_of_day + cost

        # --- Board edges: any trip leaving this stop in the next MAX_BOARD_WAIT min ---
        deps = pre.stop_departures.get(sid, [])
        if deps:
            i = _bisect_left_dep(deps, absolute_now)
            while i < len(deps):
                dep_min, trip_id, seq = deps[i]
                wait = dep_min - absolute_now
                if wait > MAX_BOARD_WAIT_MIN:
                    break
                # Look up what the next stop on this trip is.
                trip = pre.trip_stops.get(trip_id)
                if trip:
                    # find seq in trip (sorted by sequence — linear is fine, ~30 stops/trip)
                    for k, (s, _stop, _arr, _dep) in enumerate(trip):
                        if s == seq:
                            if k + 1 < len(trip):
                                _, next_stop, next_arr, _ = trip[k + 1]
                                ride_time = next_arr - dep_min
                                total = cost + wait + ride_time
                                if total < arrival.get(next_stop, math.inf) and total <= max_minutes:
                                    arrival[next_stop] = total
                                    heapq.heappush(pq, (total, next_stop))
                            break
                i += 1

        # --- Walk-transfer edges to nearby stops ---
        for other_sid, walk_min in pre.transfers_by_stop.get(sid, []):
            total = cost + walk_min
            if total < arrival.get(other_sid, math.inf) and total <= max_minutes:
                arrival[other_sid] = total
                heapq.heappush(pq, (total, other_sid))

    return arrival


def polygonize(
    pre: _Precomputed,
    arrivals: dict[str, float],
    origin_latlon: tuple[float, float],
    max_minutes: float,
):
    """Convert arrival-times into a shapely Polygon (WGS84).

    Each reachable stop contributes a walk-circle sized by its *remaining*
    budget. The origin gets a full max-walk circle in case nothing was
    boarded. The union is the isochrone.
    """
    from shapely.geometry import Point
    from shapely.ops import unary_union
    import pyproj

    # Project to EPSG:2263 (feet) for accurate buffering, then back.
    to_2263 = pyproj.Transformer.from_crs(4326, 2263, always_xy=True).transform
    to_4326 = pyproj.Transformer.from_crs(2263, 4326, always_xy=True).transform

    def buf(lat: float, lon: float, radius_ft: float):
        x, y = to_2263(lon, lat)
        return Point(x, y).buffer(radius_ft, quad_segs=24)

    parts = []
    # Origin's max-walk circle (network distance ≈ straight-line × 1.4).
    origin_radius_ft = (max_minutes * WALK_SPEED_FT_PER_MIN) / WALK_DETOUR_FACTOR
    parts.append(buf(origin_latlon[0], origin_latlon[1], origin_radius_ft))

    for sid, arr in arrivals.items():
        remaining = max_minutes - arr
        if remaining <= 0:
            continue
        radius_ft = (remaining * WALK_SPEED_FT_PER_MIN) / WALK_DETOUR_FACTOR
        lat, lon = pre.stop_xy[sid]
        parts.append(buf(lat, lon, radius_ft))

    merged = unary_union(parts)
    # back to WGS84 for output
    from shapely.ops import transform as shp_transform
    return shp_transform(to_4326, merged)


def compute(
    feed,
    origin_latlon: tuple[float, float],
    departure: datetime,
    max_minutes: float = 45.0,
    pre: Optional[_Precomputed] = None,
) -> IsochroneResult:
    """End-to-end isochrone computation.

    Pass ``pre`` if you've already called ``precompute(feed)`` once — that's
    the expensive step and can be reused across many origins.
    """
    if pre is None:
        pre = precompute(feed, service_date=departure.date() if hasattr(departure, "date") else None)
    arrivals = reachable_stops(pre, origin_latlon, departure, max_minutes)
    poly = polygonize(pre, arrivals, origin_latlon, max_minutes)
    return IsochroneResult(
        origin=origin_latlon,
        departure=departure,
        max_minutes=max_minutes,
        reachable_stops=arrivals,
        polygon=poly,
    )


def precompute_isochrones(
    gtfs_path: Path,
    origins: Iterable[tuple[float, float]],
    minutes: Iterable[int] = (15, 30, 45),
    departure: str = "Tue 08:00",
) -> dict:
    """Compute travel-time polygons from each origin for each cutoff.

    Kept for API stability with the Phase-1 stub. Most callers should use
    ``compute()`` directly with a pre-built ``_Precomputed``.
    """
    import gtfs_kit
    from datetime import datetime as _dt

    feed = gtfs_kit.read_feed(gtfs_path, dist_units="ft")
    # Parse "Tue 08:00" -> a real datetime on the feed's typical Tuesday.
    _wd, hhmm = departure.split()
    weekday = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].index(_wd.lower()[:3])
    service_date = pick_typical_weekday(feed, prefer_weekday=weekday)
    h, m = map(int, hhmm.split(":"))
    dep_dt = _dt(service_date.year, service_date.month, service_date.day, h, m)

    pre = precompute(feed, service_date=service_date)

    out: dict = {}
    for cutoff in minutes:
        features = []
        for olat, olon in origins:
            res = compute(feed, (olat, olon), dep_dt, max_minutes=float(cutoff), pre=pre)
            features.append({
                "type": "Feature",
                "geometry": res.polygon.__geo_interface__,
                "properties": {
                    "origin_lat": olat,
                    "origin_lon": olon,
                    "max_minutes": cutoff,
                    "reachable_stops": len(res.reachable_stops),
                    "departure": dep_dt.isoformat(),
                },
            })
        out[cutoff] = {"type": "FeatureCollection", "features": features}
    return out
