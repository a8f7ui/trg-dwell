"""
Turning location points into the things this course is about: stops, places,
routines, and the confident-sounding guesses a commercial system would make.

Two principles run through this file.

1. **Report what was observed, not what was assumed.** Even collecting in the
   background, a phone does not report continuously — the platforms throttle
   heavily when somebody is still, and suspend background apps from time to
   time. Every dwell figure produced here is *observed* dwell: a floor, not an
   estimate. We say so, everywhere, rather than quietly interpolating across
   gaps we did not see.

2. **Characterise behaviour, never identity.** The output describes patterns:
   visitor or local, the character of an area, the kind of activity a stop
   suggests, the commercial segment a marketer would file someone under. It
   does not attempt to work out who somebody is, where they live, or match them
   against any outside record. That line is the whole ethical basis of the
   exercise, and it is enforced by simply never writing the code that would
   cross it.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import config

# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    return (sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points))


# --------------------------------------------------------------------------
# Place categories
# --------------------------------------------------------------------------

# What kind of activity a place type suggests. Probabilistic by nature: a cafe
# can be a work session or a first date, and the system cannot tell.
ACTIVITY_BY_KIND = {
    "hotel": "staying overnight",
    "residential": "at a residence",
    "office": "working",
    "conference_venue": "attending an event",
    "coworking": "working",
    "campus": "studying",
    "library": "studying",
    "coffee": "eating or drinking",
    "restaurant": "eating or drinking",
    "bar": "eating or drinking",
    "retail": "shopping",
    "grocery": "shopping",
    "park": "leisure",
    "attraction": "leisure or sightseeing",
    "transit": "travelling",
}

# The character of the surrounding area, as a location-intelligence product
# would bucket it.
# Phrased as complete noun phrases that all read correctly after "a", because
# these strings get dropped straight into sentences shown to participants.
AREA_BY_KIND = {
    "retail": "commercial district", "restaurant": "commercial district",
    "bar": "commercial district", "coffee": "commercial district",
    "grocery": "commercial district",
    "office": "business district", "conference_venue": "business district",
    "coworking": "business district",
    "attraction": "tourist area", "park": "tourist area", "hotel": "tourist area",
    "residential": "residential area",
    "campus": "study area", "library": "study area",
    "transit": "transit hub",
}

# Readable names for the place types. The raw keys are fine in code but look
# like database columns when shown to a participant.
KIND_LABEL = {
    "hotel": "hotel", "residential": "residential address",
    "office": "office", "conference_venue": "conference venue",
    "coworking": "coworking space", "campus": "campus", "library": "library",
    "coffee": "coffee shop", "restaurant": "restaurant", "bar": "bar",
    "retail": "shop", "grocery": "supermarket", "park": "park",
    "attraction": "visitor attraction", "transit": "transit stop",
}


def kind_label(kind: str) -> str:
    return KIND_LABEL.get(kind, kind.replace("_", " ") if kind else "unmatched")


LODGING_KINDS = {"hotel", "residential"}
WORK_KINDS = {"office", "conference_venue", "coworking"}
STUDY_KINDS = {"campus", "library"}
LEISURE_KINDS = {"park", "attraction"}
SHOPPING_KINDS = {"retail", "grocery"}
DINING_KINDS = {"coffee", "restaurant", "bar"}


# --------------------------------------------------------------------------
# Data shapes
# --------------------------------------------------------------------------

@dataclass
class Point:
    ts: datetime
    lat: float
    lon: float
    accuracy_m: float = 0.0
    session_id: str = ""
    battery_pct: int | None = None
    connection: str = ""
    collection_mode: str = ""


@dataclass
class Stop:
    lat: float
    lon: float
    start: datetime
    end: datetime
    point_count: int
    observed_seconds: float
    poi_name: str = ""
    poi_kind: str = ""
    poi_distance_m: float | None = None
    poi_alternatives: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "point_count": self.point_count,
            "observed_seconds": round(self.observed_seconds),
            "observed_minutes": round(self.observed_seconds / 60, 1),
            "poi_name": self.poi_name,
            "poi_kind": self.poi_kind,
            "poi_kind_label": kind_label(self.poi_kind),
            "poi_distance_m": (round(self.poi_distance_m, 1)
                               if self.poi_distance_m is not None else None),
            "poi_alternatives": self.poi_alternatives,
            "activity_guess": ACTIVITY_BY_KIND.get(self.poi_kind, "unknown"),
        }


# --------------------------------------------------------------------------
# Stop detection
# --------------------------------------------------------------------------

def detect_stops(points: list[Point],
                 roam_radius_m: float | None = None,
                 min_dwell_s: float | None = None,
                 max_gap_s: float | None = None) -> list[Stop]:
    """
    Find places where somebody stayed put.

    This is the standard "stay point" approach: walk forward from each point
    while later points remain within a small radius of it; if that run lasted
    long enough, it is a stop.

    The one addition is a gap guard. If two consecutive points are far apart in
    time, the app was closed in between and we have no idea what happened. We
    refuse to treat that as continuous dwell — inventing time the app never saw
    would be exactly the kind of confident overreach this course criticises.
    """
    roam_radius_m = roam_radius_m if roam_radius_m is not None else config.STOP_ROAM_RADIUS_M
    min_dwell_s = min_dwell_s if min_dwell_s is not None else config.STOP_MIN_DWELL_S
    max_gap_s = max_gap_s if max_gap_s is not None else config.STOP_MAX_GAP_S

    pts = sorted(points, key=lambda p: p.ts)
    stops: list[Stop] = []
    n = len(pts)
    i = 0

    while i < n:
        j = i + 1
        while j < n:
            if (pts[j].ts - pts[j - 1].ts).total_seconds() > max_gap_s:
                break
            if haversine_m(pts[i].lat, pts[i].lon, pts[j].lat, pts[j].lon) > roam_radius_m:
                break
            j += 1

        last = j - 1
        if last > i:
            duration = (pts[last].ts - pts[i].ts).total_seconds()
            if duration >= min_dwell_s:
                run = pts[i:last + 1]
                lat, lon = centroid([(p.lat, p.lon) for p in run])
                stops.append(Stop(
                    lat=lat, lon=lon,
                    start=run[0].ts, end=run[-1].ts,
                    point_count=len(run),
                    observed_seconds=duration,
                ))
                i = last + 1
                continue
        i += 1

    return stops


# --------------------------------------------------------------------------
# Place matching
# --------------------------------------------------------------------------

def attach_poi_context(stops: list[Stop], places: list[dict],
                       radius_m: float | None = None) -> None:
    """
    Say what sort of place each stop was near.

    Deliberately reports alternatives. If a stop sits between a cafe and a bank,
    the honest answer is "one of these two", and showing that ambiguity is a
    teaching point in itself: real systems pick the most commercially useful
    guess and print it without a hedge.
    """
    radius_m = radius_m if radius_m is not None else config.POI_MATCH_RADIUS_M

    for stop in stops:
        scored = []
        for place in places:
            d = haversine_m(stop.lat, stop.lon, place["lat"], place["lon"])
            if d <= radius_m:
                scored.append((d, place))
        scored.sort(key=lambda x: x[0])

        if not scored:
            stop.poi_name = ""
            stop.poi_kind = ""
            stop.poi_distance_m = None
            stop.poi_alternatives = []
            continue

        best_d, best = scored[0]
        stop.poi_name = best["name"]
        stop.poi_kind = best["kind"]
        stop.poi_distance_m = best_d
        stop.poi_alternatives = [
            {"name": p["name"], "kind": p["kind"], "distance_m": round(d, 1)}
            for d, p in scored[1:4]
        ]


@dataclass
class Place:
    """A location visited one or more times, pooled across stops."""
    lat: float
    lon: float
    stops: list[Stop] = field(default_factory=list)

    @property
    def observed_seconds(self) -> float:
        return sum(s.observed_seconds for s in self.stops)

    @property
    def visit_count(self) -> int:
        return len(self.stops)

    @property
    def days(self) -> set[str]:
        return {s.start.date().isoformat() for s in self.stops}

    @property
    def kind(self) -> str:
        kinds = [s.poi_kind for s in self.stops if s.poi_kind]
        return Counter(kinds).most_common(1)[0][0] if kinds else ""

    @property
    def name(self) -> str:
        names = [s.poi_name for s in self.stops if s.poi_name]
        return Counter(names).most_common(1)[0][0] if names else "an unidentified place"

    def as_dict(self) -> dict:
        return {
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "name": self.name,
            "kind": self.kind,
            "kind_label": kind_label(self.kind),
            "visit_count": self.visit_count,
            "days_seen": sorted(self.days),
            "day_count": len(self.days),
            "observed_seconds": round(self.observed_seconds),
            "observed_minutes": round(self.observed_seconds / 60, 1),
            "activity_guess": ACTIVITY_BY_KIND.get(self.kind, "unknown"),
            "first_seen": min(s.start for s in self.stops).isoformat(),
            "last_seen": max(s.end for s in self.stops).isoformat(),
        }


def cluster_places(stops: list[Stop], radius_m: float | None = None) -> list[Place]:
    """Group stops that are effectively the same location into one place."""
    radius_m = radius_m if radius_m is not None else config.PLACE_CLUSTER_RADIUS_M
    # Longest stops first, so the most substantial visits seed the clusters.
    ordered = sorted(stops, key=lambda s: s.observed_seconds, reverse=True)
    places: list[Place] = []

    for stop in ordered:
        for place in places:
            if haversine_m(stop.lat, stop.lon, place.lat, place.lon) <= radius_m:
                place.stops.append(stop)
                lat, lon = centroid([(s.lat, s.lon) for s in place.stops])
                place.lat, place.lon = lat, lon
                break
        else:
            places.append(Place(lat=stop.lat, lon=stop.lon, stops=[stop]))

    places.sort(key=lambda p: p.observed_seconds, reverse=True)
    return places


# --------------------------------------------------------------------------
# Coverage: how much of the day did we actually see?
# --------------------------------------------------------------------------

def observed_coverage(points: list[Point], max_gap_s: float | None = None) -> dict:
    """
    Work out how much of the day the app was actually watching.

    This is one of the most useful numbers in the whole system for teaching:
    it lets a participant see that a handful of minutes of attention produced
    a detailed picture of their day.
    """
    max_gap_s = max_gap_s if max_gap_s is not None else config.STOP_MAX_GAP_S
    if len(points) < 2:
        return {"observed_seconds": 0, "span_seconds": 0, "coverage_pct": 0.0,
                "session_count": 0, "gap_count": 0, "longest_gap_seconds": 0}

    pts = sorted(points, key=lambda p: p.ts)
    observed = 0.0
    gaps: list[float] = []
    for a, b in zip(pts, pts[1:]):
        delta = (b.ts - a.ts).total_seconds()
        if delta <= max_gap_s:
            observed += delta
        else:
            gaps.append(delta)

    span = (pts[-1].ts - pts[0].ts).total_seconds()

    # How much of this was gathered while the participant was not looking at
    # the app. This is the number that lands hardest in the daily reveal.
    background = sum(1 for p in pts if p.collection_mode == "background")
    known_mode = sum(1 for p in pts if p.collection_mode)

    return {
        "observed_seconds": round(observed),
        "observed_minutes": round(observed / 60, 1),
        "span_seconds": round(span),
        "span_hours": round(span / 3600, 1),
        "coverage_pct": round(100 * observed / span, 1) if span > 0 else 0.0,
        "session_count": len({p.session_id for p in pts if p.session_id}),
        "gap_count": len(gaps),
        "longest_gap_seconds": round(max(gaps)) if gaps else 0,
        "longest_gap_minutes": round(max(gaps) / 60, 1) if gaps else 0.0,
        "point_count": len(pts),
        "background_points": background,
        "background_pct": round(100 * background / known_mode, 1) if known_mode else None,
    }


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------

def _plural(n: int, singular: str, plural: str | None = None) -> str:
    """"1 stop" / "3 stops". These strings are shown to participants, so they
    need to read like English rather than like a log file."""
    return f"{n} {singular}" if n == 1 else f"{n} {plural or singular + 's'}"


def _confidence_word(score: float) -> str:
    if score >= 0.75:
        return "fairly confident"
    if score >= 0.5:
        return "moderately confident"
    if score >= 0.3:
        return "guessing"
    return "barely more than a coin flip"


def _find_anchor(places: list[Place]) -> Place | None:
    """
    The place somebody appears to start and end their day.

    Note carefully what this does NOT do: it does not call this "home", it does
    not look up an address, and it does not go anywhere near identifying the
    person. It notes that a pattern exists. That distinction is the difference
    between a teaching tool and a stalking tool.
    """
    if not places:
        return None
    candidates = [p for p in places if p.kind in LODGING_KINDS]
    if candidates:
        return max(candidates, key=lambda p: p.observed_seconds)
    # No lodging-type place seen: fall back to whichever place brackets the day.
    earliest = min(places, key=lambda p: min(s.start for s in p.stops))
    latest = max(places, key=lambda p: max(s.end for s in p.stops))
    return earliest if earliest is latest else None


def infer_day(points: list[Point], stops: list[Stop], places: list[Place],
              prior_days: list[dict] | None = None) -> dict:
    """
    Produce the assessment a commercial location-intelligence product would.

    Everything returned carries a confidence value and a stated basis, and the
    caveats list is populated honestly — including cases where the system is
    probably wrong. Being visibly, correctably wrong in front of a class is the
    point: automated profiling makes confident mistakes and acts on them anyway.
    """
    prior_days = prior_days or []
    coverage = observed_coverage(points)
    anchor = _find_anchor(places)
    kinds = [p.kind for p in places if p.kind]
    kind_counts = Counter(kinds)

    caveats: list[str] = []
    findings: dict = {}

    # --- Visitor or local -------------------------------------------------
    if anchor and anchor.kind == "hotel":
        findings["visitor_or_local"] = {
            "value": "visitor",
            "confidence": 0.72,
            "basis": (f"The place you spent longest, and started and ended the day at, "
                      f"sits next to {anchor.name} — a hotel. People who sleep in hotels "
                      f"are usually not from around here."),
        }
    elif anchor and anchor.kind == "residential":
        findings["visitor_or_local"] = {
            "value": "local resident",
            "confidence": 0.66,
            "basis": (f"Your day began and ended around {anchor.name}, a residential "
                      f"address type. That pattern usually means you live locally."),
        }
    else:
        findings["visitor_or_local"] = {
            "value": "unclear",
            "confidence": 0.25,
            "basis": "No clear overnight anchor was observed in the data collected today.",
        }
        caveats.append(
            "The app never saw where you started or ended your day, so the "
            "visitor-versus-local judgement here is weak.")

    # --- Character of the areas visited -----------------------------------
    area_counts = Counter(AREA_BY_KIND.get(k, "mixed-use area") for k in kinds)
    if area_counts:
        top_area, top_n = area_counts.most_common(1)[0]
        if len(kinds) == 1:
            area_basis = (f"The one identifiable place you stopped at sits in what "
                          f"looks like a {top_area}.")
        else:
            verb = "sits" if top_n == 1 else "sit"
            area_basis = (f"Of the {_plural(len(kinds), 'identifiable place')} you "
                          f"stopped at, {top_n} {verb} in what looks like a {top_area}.")
        findings["area_character"] = {
            "value": top_area,
            "confidence": round(min(0.85, 0.35 + 0.15 * top_n), 2),
            "basis": area_basis,
            "breakdown": dict(area_counts),
        }

    # --- What kinds of activity --------------------------------------------
    activities = Counter(ACTIVITY_BY_KIND.get(k, "unknown") for k in kinds)
    activities.pop("unknown", None)
    if activities:
        findings["activities"] = [
            {"activity": a, "stop_count": n} for a, n in activities.most_common()
        ]

    # --- Daily rhythm -------------------------------------------------------
    if points:
        pts = sorted(points, key=lambda p: p.ts)
        rhythm = {
            "first_seen": pts[0].ts.isoformat(),
            "last_seen": pts[-1].ts.isoformat(),
            "first_seen_local": pts[0].ts.strftime("%H:%M"),
            "last_seen_local": pts[-1].ts.strftime("%H:%M"),
            "active_span_hours": round(
                (pts[-1].ts - pts[0].ts).total_seconds() / 3600, 1),
            "distinct_places": len(places),
            "stop_count": len(stops),
        }
        # Collecting in the background means the first and last points of a day
        # are usually just a phone sitting on a bedside table. The figure that
        # actually describes somebody's routine is when they left wherever they
        # slept, and when they got back.
        if anchor:
            away = [s for s in stops
                    if haversine_m(s.lat, s.lon, anchor.lat, anchor.lon)
                    > config.PLACE_CLUSTER_RADIUS_M]
            if away:
                left = min(s.start for s in away)
                returned = max(s.end for s in away)
                rhythm["left_anchor_local"] = left.strftime("%H:%M")
                rhythm["returned_local"] = returned.strftime("%H:%M")
                rhythm["hours_out"] = round(
                    (returned - left).total_seconds() / 3600, 1)
        findings["rhythm"] = rhythm

    # --- The commercial segment --------------------------------------------
    has_work = bool(kind_counts.keys() & WORK_KINDS)
    has_study = bool(kind_counts.keys() & STUDY_KINDS)
    has_leisure = bool(kind_counts.keys() & LEISURE_KINDS)
    has_shopping = bool(kind_counts.keys() & SHOPPING_KINDS)
    visitor = findings["visitor_or_local"]["value"] == "visitor"
    local = findings["visitor_or_local"]["value"] == "local resident"

    segment, seg_conf, seg_basis = "not enough evidence", 0.2, (
        "Too few identifiable stops to place you in a segment today.")

    if visitor and has_work:
        segment, seg_conf = "business traveller", 0.68
        seg_basis = ("Hotel overnight plus time at a workplace or event venue — the "
                     "pattern advertisers file under business travel.")
    elif visitor and (has_leisure or has_shopping):
        segment, seg_conf = "leisure traveller", 0.63
        seg_basis = ("Hotel overnight plus attractions, parks or shops, with no "
                     "workplace visit — reads as a trip taken for pleasure.")
    elif local and has_work:
        segment, seg_conf = "commuting professional", 0.6
        seg_basis = ("A residential start, a workplace during the day, and a return — "
                     "the classic commuter shape.")
    elif local and has_study:
        segment, seg_conf = "student", 0.58
        seg_basis = "Time on a campus or in a library, from a residential base."
    elif local:
        segment, seg_conf = "local resident, pattern unclear", 0.35
        seg_basis = "You appear to be local, but today's stops do not form a clear routine."

    # Thin data should reduce confidence, not be papered over.
    if len(places) < 3:
        seg_conf *= 0.75
        caveats.append(
            f"Only {_plural(len(places), 'distinct place')} were observed today — "
            f"this is a judgement made on very little.")
    if coverage["coverage_pct"] < 15:
        seg_conf *= 0.8
        caveats.append(
            f"The app was only watching for about {coverage['observed_minutes']} minutes "
            f"across a {coverage['span_hours']}-hour span — roughly "
            f"{coverage['coverage_pct']}% of your day.")

    findings["segment"] = {
        "value": segment,
        "confidence": round(min(0.9, seg_conf), 2),
        "confidence_word": _confidence_word(min(0.9, seg_conf)),
        "basis": seg_basis,
    }

    # A specific way this label could be wrong about this person. Included even
    # when the data is good, because good data is exactly when a profiling
    # system sounds most authoritative.
    if segment in SEGMENT_COUNTEREXAMPLE:
        caveats.append(SEGMENT_COUNTEREXAMPLE[segment])

    # Activity guesses come from the type of place, not from anything observed
    # about what the person was doing there.
    ambiguous_kinds = kind_counts.keys() & (DINING_KINDS | SHOPPING_KINDS)
    if ambiguous_kinds:
        caveats.append(
            "Activities above are guessed purely from the type of place, never "
            "from anything actually observed. An hour in a cafe might be a work "
            "meeting, a first date, a job interview or shelter from the rain. "
            "This system records 'eating or drinking' and moves on.")

    # --- Ambiguity in place matching ---------------------------------------
    ambiguous = [s for s in stops if s.poi_alternatives]
    if ambiguous:
        example = ambiguous[0]
        alts = ", ".join(a["name"] for a in example.poi_alternatives[:2])
        caveats.append(
            f"{len(ambiguous)} of your stops sat close to more than one place. "
            f"One was matched to {example.poi_name}, but {alts} sat just as near. "
            f"A real system would pick whichever was most commercially useful and "
            f"show it to you without mentioning the doubt.")

    unmatched = [s for s in stops if not s.poi_kind]
    if unmatched:
        caveats.append(
            f"{_plural(len(unmatched), 'stop')} could not be matched to any known "
            f"place, so {'it is' if len(unmatched) == 1 else 'they are'} missing "
            f"from the reasoning above entirely.")

    return {
        "coverage": coverage,
        "findings": findings,
        "caveats": caveats,
        "anchor": anchor.as_dict() if anchor else None,
    }


def compare_with_prior(today: dict, prior: list[dict]) -> dict:
    """
    Build the "yesterday I guessed X, today I'm more sure" thread.

    The week-long arc is the strongest part of the lesson: a single day looks
    like a curiosity, but watching the picture tighten day after day is what
    makes the point land.
    """
    if not prior:
        return {
            "is_first_day": True,
            "narrative": ("This is the first day of data, so there is nothing to compare "
                          "against yet. Keep the app running and check back tomorrow — "
                          "the interesting part is what happens when days start "
                          "stacking up."),
            "new_places": [],
            "repeat_places": [],
            "confidence_change": None,
        }

    prior_names: set[str] = set()
    for day in prior:
        prior_names.update(p["name"] for p in day.get("places", []))

    today_places = today.get("places", [])
    new_places = [p for p in today_places if p["name"] not in prior_names]
    repeat_places = [p for p in today_places if p["name"] in prior_names]

    prior_conf = [d["assessment"]["findings"].get("segment", {}).get("confidence", 0)
                  for d in prior]
    prior_best = max(prior_conf) if prior_conf else 0
    today_conf = today["assessment"]["findings"].get("segment", {}).get("confidence", 0)
    prior_segment = prior[-1]["assessment"]["findings"].get("segment", {}).get("value", "")
    today_segment = today["assessment"]["findings"].get("segment", {}).get("value", "")

    # "not enough evidence" is a non-answer, so it must not be talked about as
    # though it were a conclusion.
    vague = {"not enough evidence", "local resident, pattern unclear", ""}
    prior_known = prior_segment not in vague
    today_known = today_segment not in vague

    bits: list[str] = []
    if prior_known and today_known and prior_segment == today_segment:
        bits.append(f"Yesterday I put you down as a {prior_segment}. Today's movement "
                    f"says the same thing.")
    elif prior_known and today_known:
        bits.append(f"Yesterday I had you as a {prior_segment}. Today I would say "
                    f"{today_segment} instead — the picture is still shifting.")
    elif today_known and not prior_known:
        bits.append(f"Until today I could not place you at all. Now I would call you "
                    f"a {today_segment}.")
    elif prior_known and not today_known:
        bits.append(f"Yesterday I had you as a {prior_segment}. Today the app saw too "
                    f"little to say either way — but yesterday's guess does not "
                    f"disappear just because today was quiet.")
    else:
        bits.append("I still do not have enough to place you in a category. That is "
                    "not the same as knowing nothing about you.")

    if repeat_places:
        names = ", ".join(p["name"] for p in repeat_places[:3])
        bits.append(f"You returned to {_plural(len(repeat_places), 'place')} I have "
                    f"seen before ({names}). Repeat visits are what turn a list of "
                    f"dots into a routine.")
    if new_places:
        bits.append(f"{_plural(len(new_places), 'place')} "
                    f"{'was' if len(new_places) == 1 else 'were'} new to me today.")

    if today_conf > prior_best:
        bits.append("I am more confident about you than I was yesterday.")
    elif today_conf < prior_best:
        bits.append("Today's data was thinner, so I am actually less sure than I was.")

    return {
        "is_first_day": False,
        "narrative": " ".join(bits),
        "new_places": new_places,
        "repeat_places": repeat_places,
        "confidence_change": round(today_conf - prior_best, 2),
        "days_of_data": len(prior) + 1,
    }


# --------------------------------------------------------------------------
# The "what you can do about it" step
# --------------------------------------------------------------------------

# For each segment, one concrete way this specific judgement could be wrong
# about this specific person — and, crucially, why nothing in the data would
# reveal the mistake. A profiling system that cannot be contradicted by its own
# inputs is the thing worth being alarmed about.
SEGMENT_COUNTEREXAMPLE = {
    "business traveller": (
        "If you actually live in this city and merely stayed in a hotel this week "
        "— renovations, a conference rate, a fallen-out housemate — you would be "
        "filed as a business traveller regardless. Nothing in this data could tell "
        "the difference."),
    "leisure traveller": (
        "If your trip mixed work and leisure, simply not visiting an office is "
        "enough for this system to call it a holiday and sell you accordingly."),
    "commuting professional": (
        "If you were staying at a friend's or relative's home rather than your own, "
        "this system would still record you as a local resident with a settled "
        "routine. It cannot tell whose home it is."),
    "student": (
        "Time in a library or on a campus is enough to be labelled a student. "
        "Staff, visitors, and people who just like the reading room all look "
        "identical here."),
}


AGENCY_STEPS = [
    {
        "title": "Switch location access to “While Using the App”",
        "detail": ("Open your phone's settings, find this app, and look at Location. If "
                   "any app is set to “Always”, it can collect when you are not looking. "
                   "Very few apps genuinely need that."),
        "what_would_have_changed": ("Nothing on today's map would exist for apps you "
                                    "never opened."),
    },
    {
        "title": "Turn off Precise Location for apps that do not need it",
        "detail": ("Both iOS and Android let you give an app your rough area instead of "
                   "your exact position. A weather app does not need to know which "
                   "building you are in."),
        "what_would_have_changed": ("Your stops would have blurred into a neighbourhood. "
                                    "The individual shops and venues named today would "
                                    "not have been identifiable."),
    },
    {
        "title": "Reset your advertising identifier",
        "detail": ("iOS: Settings → Privacy → Tracking. Android: Settings → Privacy → "
                   "Ads. Resetting breaks the thread that links today's activity to "
                   "everything you did before."),
        "what_would_have_changed": ("The week-over-week profile built up so far would "
                                    "have been split into disconnected fragments."),
    },
    {
        "title": "Audit which apps currently have location permission",
        "detail": ("Go through the full list in your privacy settings. Most people find "
                   "several apps they no longer use, still holding access."),
        "what_would_have_changed": ("Every app on that list could have produced a map "
                                    "like today's, without ever telling you."),
    },
    {
        "title": "Turn location off entirely and see what breaks",
        "detail": ("Try a day with location services off. Note which apps genuinely stop "
                   "working, and which simply nag you."),
        "what_would_have_changed": ("Today's reveal would have been a blank screen. "
                                    "There would have been nothing to infer."),
    },
]


def agency_step(day_index: int) -> dict:
    return AGENCY_STEPS[day_index % len(AGENCY_STEPS)]


# --------------------------------------------------------------------------
# Aggregate map with k-anonymity
# --------------------------------------------------------------------------

def hex_aggregate(rows: list[dict], resolution: int | None = None,
                  k: int | None = None) -> dict:
    """
    Bucket every location point into hexagons and hide the sparse ones.

    A hexagon is only returned if at least `k` DIFFERENT participants were seen
    inside it. This is k-anonymity, and the reason it matters is easy to
    demonstrate badly: without it, an "aggregate" map still shows a lone
    hexagon out in the suburbs that belongs to exactly one person, which tells
    you precisely where that person was.

    `rows` need only contain participant_id, lat and lon.
    """
    import h3

    resolution = resolution if resolution is not None else config.H3_RESOLUTION
    k = k if k is not None else config.K_ANONYMITY_THRESHOLD

    cells: dict[str, dict] = defaultdict(lambda: {"participants": set(), "pings": 0})
    for row in rows:
        cell = h3.latlng_to_cell(row["lat"], row["lon"], resolution)
        cells[cell]["participants"].add(row["participant_id"])
        cells[cell]["pings"] += 1

    kept, suppressed = [], 0
    for cell, data in cells.items():
        n_people = len(data["participants"])
        if n_people < k:
            suppressed += 1
            continue
        boundary = h3.cell_to_boundary(cell)
        lat, lon = h3.cell_to_latlng(cell)
        kept.append({
            "cell": cell,
            "participant_count": n_people,
            "ping_count": data["pings"],
            "center": {"lat": lat, "lon": lon},
            # GeoJSON convention is [lon, lat]; h3 returns (lat, lon).
            "boundary": [[p[1], p[0]] for p in boundary],
        })

    kept.sort(key=lambda c: c["participant_count"], reverse=True)
    return {
        "resolution": resolution,
        "k_threshold": k,
        "cells": kept,
        "cells_shown": len(kept),
        "cells_suppressed": suppressed,
        "explanation": (
            f"Each hexagon is about {int(_hex_edge_m(resolution))} m across. A hexagon "
            f"is only drawn when at least {k} different participants were recorded "
            f"inside it. {suppressed} hexagon(s) were hidden because too few people "
            f"visited them — showing those would effectively point at individuals."
        ),
    }


def _hex_edge_m(resolution: int) -> float:
    import h3
    return h3.average_hexagon_edge_length(resolution, unit="m")
