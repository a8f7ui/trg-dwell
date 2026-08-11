"""
Environmental enrichment: what else was watching, where they went.

Why this exists
---------------
A location trail on its own is one source, and one source is deniable. What
makes location data genuinely dangerous is *corroboration* — the moment a phone
ping lines up with a camera, a plate reader, a Wi-Fi association and a card
terminal, all at the same place and minute. Any one of those is circumstantial.
Together they are a record.

That is the mechanism by which a fragmented, "anonymous" location feed becomes
something a state agency, a data broker or a criminal buyer can act on. This
module makes that mechanism visible, using only public information about
*places*.

The line this module does not cross
-----------------------------------
Enrichment here describes the **environment**, never the person.

It will say "your route passed within range of nine cameras and two plate
readers, and four independent sources could place you at that stop." It will not
look up who you are, pull records about you, or attempt to match you to anything
outside this system. Environmental context makes the *exposure* legible; it does
not resolve identity, and no code here reaches toward that.

Honesty about what "in range" means
-----------------------------------
A camera existing near a point is not proof of anything. It may face the other
way, may not record, may overwrite in 48 hours, and its footage may be
unavailable to anyone who wants it. Every figure produced here is an *upper
bound on opportunity*, not evidence of observation, and the wording throughout
says so. Overclaiming here would be the same failure the course criticises in
commercial profiling.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from .analysis import Point, Stop, haversine_m

# --------------------------------------------------------------------------
# What kinds of thing can observe a person, and from how far
# --------------------------------------------------------------------------

# Ranges are deliberately conservative round numbers. Real coverage depends on
# lens, mounting height, lighting, and what is in the way — none of which any
# public dataset records. These are "close enough to be plausible", not
# measurements.
FEATURE_KINDS = {
    "camera": {
        "label": "CCTV camera",
        "range_m": 40,
        "observes": "your face, your clothing, who you arrived with",
        "operator": "councils, businesses, private residents",
    },
    "alpr": {
        "label": "automatic plate reader",
        "range_m": 30,
        "observes": "your vehicle's plate, direction and timestamp",
        "operator": "police forces, private parking and repossession firms",
    },
    "wifi": {
        "label": "Wi-Fi access point",
        "range_m": 45,
        "observes": "your device's presence, and often its identifier",
        "operator": "whoever runs the network, plus anyone who mapped it",
    },
    "payment": {
        "label": "card terminal",
        "range_m": 15,
        "observes": "that a specific account was present, to the second",
        "operator": "banks, payment processors, the merchant",
    },
    "transit": {
        "label": "transit gate or reader",
        "range_m": 25,
        "observes": "a travelcard tap, tied to an account",
        "operator": "transit authorities",
    },
}

# How much a source adds to a claim that somebody was at a place. A phone ping
# is the weakest: it places a device, not a person, and it is the one thing the
# person could plausibly deny.
CORROBORATION_WEIGHT = {
    "phone": 1.0,
    "camera": 2.5,
    "alpr": 2.0,
    "wifi": 1.5,
    "payment": 3.0,
    "transit": 2.5,
}


@dataclass
class Feature:
    feature_id: str
    kind: str
    lat: float
    lon: float
    name: str = ""
    source: str = ""

    @property
    def range_m(self) -> float:
        return FEATURE_KINDS.get(self.kind, {}).get("range_m", 30)

    def as_dict(self) -> dict:
        spec = FEATURE_KINDS.get(self.kind, {})
        return {
            "feature_id": self.feature_id,
            "kind": self.kind,
            "label": spec.get("label", self.kind),
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "name": self.name,
            "source": self.source,
            "range_m": self.range_m,
        }


# --------------------------------------------------------------------------
# Spatial index
# --------------------------------------------------------------------------

class FeatureIndex:
    """
    A coarse grid so that checking thousands of points against thousands of
    features does not turn into millions of distance calculations.
    """

    CELL_DEG = 0.002        # roughly 200 m

    def __init__(self, features: list[Feature]):
        self.features = features
        self.grid: dict[tuple[int, int], list[Feature]] = {}
        for f in features:
            self.grid.setdefault(self._cell(f.lat, f.lon), []).append(f)

    def _cell(self, lat: float, lon: float) -> tuple[int, int]:
        return (int(lat / self.CELL_DEG), int(lon / self.CELL_DEG))

    def near(self, lat: float, lon: float, radius_m: float) -> list[tuple[Feature, float]]:
        """Features within radius_m, with their distance."""
        span = int(radius_m / (self.CELL_DEG * 111_320)) + 1
        base = self._cell(lat, lon)
        found: list[tuple[Feature, float]] = []
        for dy in range(-span, span + 1):
            for dx in range(-span, span + 1):
                for f in self.grid.get((base[0] + dy, base[1] + dx), ()):
                    d = haversine_m(lat, lon, f.lat, f.lon)
                    if d <= radius_m:
                        found.append((f, d))
        found.sort(key=lambda pair: pair[1])
        return found


# --------------------------------------------------------------------------
# Exposure along a trail
# --------------------------------------------------------------------------

def assess_exposure(points: list[Point], stops: list[Stop],
                    index: FeatureIndex) -> dict:
    """
    How observable this day was, beyond the phone itself.

    Returns counts of what the route passed, which stops could have been
    corroborated by more than one source, and — the number that matters — how
    much of the day was spent within range of something that records.
    """
    if not points or not index.features:
        return {"available": False}

    passed: dict[str, set[str]] = {k: set() for k in FEATURE_KINDS}
    covered_points = 0
    # Counted per kind as well as overall. Reporting only a combined figure
    # would be misleading: mapped Wi-Fi is near-total in a city centre, so a
    # single number climbs above 90% and reads as "cameras saw you all day",
    # which is not what it means. Cameras are the figure people care about, so
    # cameras get their own number.
    covered_by_kind: dict[str, int] = {k: 0 for k in FEATURE_KINDS}

    for p in points:
        hits = index.near(p.lat, p.lon, 50)
        kinds_here = set()
        for feature, distance in hits:
            if distance <= feature.range_m:
                passed.setdefault(feature.kind, set()).add(feature.feature_id)
                kinds_here.add(feature.kind)
        if kinds_here:
            covered_points += 1
        for k in kinds_here:
            covered_by_kind[k] += 1

    # Per-stop corroboration: how many independent kinds of source could place
    # somebody at this stop, and how strong that combination is.
    stop_reports = []
    for stop in stops:
        hits = index.near(stop.lat, stop.lon, 60)
        kinds = Counter()
        witnesses = []
        for feature, distance in hits:
            if distance <= feature.range_m:
                kinds[feature.kind] += 1
                witnesses.append({
                    "kind": feature.kind,
                    "label": FEATURE_KINDS[feature.kind]["label"],
                    "distance_m": round(distance),
                    "name": feature.name,
                })

        score = CORROBORATION_WEIGHT["phone"] + sum(
            CORROBORATION_WEIGHT.get(k, 1.0) for k in kinds)
        stop_reports.append({
            "lat": round(stop.lat, 6),
            "lon": round(stop.lon, 6),
            "poi_name": stop.poi_name,
            "start": stop.start.isoformat(),
            "observed_minutes": round(stop.observed_seconds / 60, 1),
            "source_kinds": sorted(kinds),
            "source_count": 1 + sum(kinds.values()),
            "witnesses": witnesses[:6],
            "corroboration": round(score, 1),
            "verdict": _corroboration_verdict(score, len(kinds)),
        })

    stop_reports.sort(key=lambda s: s["corroboration"], reverse=True)
    coverage_pct = round(100 * covered_points / len(points), 1)
    coverage_by_kind = {
        k: round(100 * n / len(points), 1)
        for k, n in covered_by_kind.items() if n
    }
    camera_pct = coverage_by_kind.get("camera", 0.0)

    total_features = sum(len(v) for v in passed.values())
    return {
        "available": True,
        "coverage_pct": coverage_pct,
        "coverage_by_kind": coverage_by_kind,
        "camera_coverage_pct": camera_pct,
        "points_in_range": covered_points,
        "point_total": len(points),
        "passed": {
            k: {
                "count": len(v),
                "label": FEATURE_KINDS[k]["label"],
                "observes": FEATURE_KINDS[k]["observes"],
                "operator": FEATURE_KINDS[k]["operator"],
            }
            for k, v in passed.items() if v
        },
        "total_features_passed": total_features,
        "stops": stop_reports,
        "strongest_stop": stop_reports[0] if stop_reports else None,
        "narrative": _narrative(camera_pct, coverage_pct, passed, stop_reports),
        "caveats": _caveats(total_features),
    }


def _corroboration_verdict(score: float, distinct_kinds: int) -> str:
    if distinct_kinds == 0:
        return "phone only — deniable"
    if distinct_kinds == 1:
        return "two sources — hard to dismiss"
    if distinct_kinds == 2:
        return "three kinds of source — effectively established"
    return "four or more kinds of source — not realistically deniable"


def _narrative(camera_pct: float, any_pct: float,
               passed: dict, stops: list[dict]) -> str:
    if not passed:
        return ("No recording infrastructure is mapped near today's route. That does "
                "not mean there was none — only that none is in the public data.")

    bits = []
    parts = ", ".join(
        f"{len(v)} {FEATURE_KINDS[k]['label']}{'s' if len(v) != 1 else ''}"
        for k, v in passed.items() if v)
    bits.append(f"Today's route passed within range of {parts}.")

    # The corroboration point leads, because it is the actual lesson. Coverage
    # percentages come afterwards and heavily qualified — they are easy to
    # misread as "you were filmed for most of the day", which is not what being
    # within range of a camera means.
    strong = [s for s in stops if len(s["source_kinds"]) >= 2]
    if strong:
        top = strong[0]
        where = top["poi_name"] or "one of your stops"
        bits.append(
            f"At {where}, {top['source_count']} separate sources could place you "
            f"there at the same time. One source is circumstantial. That many, "
            f"agreeing, is a record.")

    if camera_pct:
        bits.append(
            f"About {camera_pct}% of the points recorded fell within range of a "
            f"mapped camera — though that figure counts every point equally, so it "
            f"is dominated by the hours spent sitting in one place, and being near "
            f"a camera is not the same as being filmed by it.")
    return " ".join(bits)


def _caveats(total_features: int) -> list[str]:
    caveats = [
        "A camera being near you is not proof it recorded you. It may face the "
        "other way, may not be recording, may overwrite within days, and its "
        "footage may be unavailable to anyone who wants it. These figures are an "
        "upper bound on opportunity, not evidence of observation.",
        "This uses only public maps of infrastructure. Real coverage is certainly "
        "higher — most private cameras are not mapped, and no public dataset "
        "records where mobile plate readers were parked on a given day.",
    ]
    if total_features == 0:
        caveats.append(
            "Nothing was found near today's route, which most likely means the "
            "area is not well mapped rather than that it is unwatched.")
    return caveats


# --------------------------------------------------------------------------
# Who would want this, and why — the consequence step
# --------------------------------------------------------------------------

ACTOR_PROFILES = [
    {
        "actor": "A data broker",
        "wants": "to sell you as an audience segment",
        "uses": "Stops and their timing, matched to place categories. Your trail "
                "alone is enough; the infrastructure above is irrelevant to them.",
        "needs_access_to": "nothing you did not already give away by installing an app.",
    },
    {
        "actor": "An advertiser or insurer",
        "wants": "to price you, or decide whether to approach you at all",
        "uses": "Recurring patterns — where you sleep, how you commute, whether "
                "you visit gyms or bars or clinics.",
        "needs_access_to": "a purchased location feed, sold legally today.",
    },
    {
        "actor": "A state security or intelligence service",
        "wants": "to establish presence beyond dispute, and to identify associates",
        "uses": "The corroboration above. A phone ping alone can be argued with; "
                "a ping that agrees with camera footage and a card transaction "
                "cannot. Co-location with other tracked devices reveals who you "
                "were with.",
        "needs_access_to": "a purchased or compelled location feed, plus lawful or "
                           "unlawful access to camera and payment systems.",
    },
    {
        "actor": "A criminal buyer or stalker",
        "wants": "to predict where you will be",
        "uses": "The routine, not any single day. Two weeks of trail gives arrival "
                "times accurate to a few minutes.",
        "needs_access_to": "a resold feed, or a single compromised app on your phone.",
    },
]
