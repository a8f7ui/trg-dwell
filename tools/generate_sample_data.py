#!/usr/bin/env python3
"""
Sample-data generator for "What Your Phone Knows".

Purpose
-------
Invent realistic-but-entirely-fictional participant data so that the backend,
the instructor dashboard and the daily-reveal screens can be built, tested and
demonstrated without involving a single real phone or real person.

Nothing here is real. Participants are invented, their routines are invented,
and the places they visit are invented names attached to coordinates scattered
around a chosen city centre. No real business, address or person is referenced.

An important detail about realism
---------------------------------
The real app only collects while it is open on screen (no background tracking).
So this generator does NOT emit a smooth, continuous trail. It builds a private
"ground truth" of where each person actually went, and then emits location
points ONLY during the handful of moments each day when that person had the app
open. The result is patchy and gappy — which is exactly what the real data will
look like.

That patchiness is pedagogically useful: it lets an instructor show that even
occasional glimpses are enough to reconstruct a routine.

Requires only the Python standard library.

Usage
-----
    python3 tools/generate_sample_data.py --participants 12 --days 5 --out data/sample
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# Geography helpers
# --------------------------------------------------------------------------

METERS_PER_DEG_LAT = 111_320.0


def offset_meters(lat: float, lon: float, dx_m: float, dy_m: float) -> tuple[float, float]:
    """Shift a coordinate by dx metres east and dy metres north."""
    dlat = dy_m / METERS_PER_DEG_LAT
    dlon = dx_m / (METERS_PER_DEG_LAT * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


# --------------------------------------------------------------------------
# The invented city
# --------------------------------------------------------------------------

# Word banks used to mint fictional place names. Deliberately generic so that
# no real business is implied.
_NAME_FIRST = [
    "Riverside", "Third Street", "Old Mill", "Cedar", "Union", "Lantern",
    "Marble", "Foxglove", "Northgate", "Copper", "Quarry", "Bellweather",
    "Sable", "Kestrel", "Larkspur", "Ironwood", "Tallow", "Windrow",
    "Halfpenny", "Verdigris", "Alder", "Pike", "Sundial", "Mercer",
]
_NAME_SECOND = {
    "hotel": ["Hotel", "Inn", "Lodge", "House"],
    "coffee": ["Coffee", "Roasters", "Espresso Bar", "Coffee House"],
    "restaurant": ["Kitchen", "Diner", "Table", "Grill", "Canteen"],
    "retail": ["Outfitters", "Mercantile", "Supply Co.", "Goods"],
    "office": ["Tower", "Works", "Building", "Offices"],
    "conference_venue": ["Conference Centre", "Exhibition Hall", "Forum"],
    "transit": ["Station", "Transit Centre", "Platform"],
    "park": ["Park", "Green", "Commons", "Gardens"],
    "bar": ["Tavern", "Bar", "Alehouse", "Social Club"],
    "gym": ["Fitness", "Athletic Club", "Gym"],
    "grocery": ["Market", "Grocers", "Provisions"],
    "residential": ["Apartments", "Residences", "Court", "Flats"],
    "campus": ["Campus", "Hall", "Institute"],
    "library": ["Library", "Reading Room", "Archive"],
    "coworking": ["Workspace", "Studios", "Coworking"],
    "attraction": ["Museum", "Gallery", "Observatory", "Aquarium"],
}

# How many of each place type to scatter around the city centre, and roughly how
# far out (in metres) they may sit.
_POI_PLAN = {
    "hotel": (6, 1600),
    "coffee": (12, 2000),
    "restaurant": (15, 2000),
    "retail": (10, 1800),
    "office": (8, 1500),
    "conference_venue": (3, 1200),
    "transit": (6, 2200),
    "park": (4, 2000),
    "bar": (8, 1800),
    "gym": (4, 2000),
    "grocery": (5, 2400),
    "residential": (8, 3000),
    "campus": (2, 2600),
    "library": (3, 2000),
    "coworking": (3, 1600),
    "attraction": (4, 2200),
}


@dataclass
class Poi:
    poi_id: str
    name: str
    kind: str
    lat: float
    lon: float


def build_city(center_lat: float, center_lon: float, rng: random.Random) -> list[Poi]:
    """Scatter fictional places of each type around a city centre."""
    pois: list[Poi] = []
    used_names: set[str] = set()
    counter = 0
    for kind, (count, max_radius) in _POI_PLAN.items():
        for _ in range(count):
            # Bias toward the centre by taking sqrt of a uniform draw.
            radius = max_radius * math.sqrt(rng.random())
            bearing = rng.uniform(0, 2 * math.pi)
            lat, lon = offset_meters(
                center_lat, center_lon,
                radius * math.cos(bearing),
                radius * math.sin(bearing),
            )
            for _attempt in range(20):
                name = f"{rng.choice(_NAME_FIRST)} {rng.choice(_NAME_SECOND[kind])}"
                if name not in used_names:
                    break
            used_names.add(name)
            counter += 1
            pois.append(Poi(f"poi_{counter:03d}", name, kind, round(lat, 6), round(lon, 6)))
    return pois


def pois_of(pois: list[Poi], kind: str) -> list[Poi]:
    return [p for p in pois if p.kind == kind]


def nearest_of_kind(pois: list[Poi], kind: str, lat: float, lon: float,
                    rng: random.Random, pick_from: int = 3) -> Poi:
    """Pick one of the closest few places of a type — people rarely cross town
    for coffee, but they don't always choose the single nearest one either."""
    candidates = sorted(pois_of(pois, kind), key=lambda p: haversine_m(lat, lon, p.lat, p.lon))
    return rng.choice(candidates[:max(1, min(pick_from, len(candidates)))])


# --------------------------------------------------------------------------
# Personas
# --------------------------------------------------------------------------

# Each entry is a stop in the day:
#   (place kind, target arrival hour, jitter in minutes, duration minutes,
#    duration jitter, probability of happening at all)
PERSONAS: dict[str, dict] = {
    "conference_visitor": {
        "anchor_kind": "hotel",
        "wake_hour": 7.6,
        "stops": [
            ("coffee",            8.05, 20,  20,  10, 0.9),
            ("conference_venue",  8.75, 25, 195,  30, 1.0),
            ("restaurant",       12.3,  30,  60,  20, 0.95),
            ("conference_venue", 13.6,  30, 205,  40, 1.0),
            ("retail",           17.6,  40,  40,  20, 0.45),
            ("bar",              19.2,  50,  95,  40, 0.7),
        ],
        "return_hour": 21.3,
    },
    "local_commuter": {
        "anchor_kind": "residential",
        "wake_hour": 7.7,
        "stops": [
            ("transit",   8.05, 15,  12,   6, 0.8),
            ("office",    8.6,  25, 215,  30, 1.0),
            ("restaurant", 12.4, 30,  45,  15, 0.85),
            ("office",    13.3, 25, 255,  40, 1.0),
            ("gym",       18.1,  45,  60,  20, 0.4),
            ("grocery",   19.3,  50,  25,  12, 0.45),
        ],
        "return_hour": 20.1,
    },
    "tourist": {
        "anchor_kind": "hotel",
        "wake_hour": 8.9,
        "stops": [
            ("coffee",      9.4,  40,  30,  15, 0.85),
            ("park",       10.4,  50,  70,  30, 0.7),
            ("attraction", 12.0,  60,  95,  35, 0.8),
            ("restaurant", 13.9,  50,  70,  25, 0.9),
            ("retail",     15.8,  60,  60,  30, 0.75),
            ("restaurant", 19.1,  50,  90,  30, 0.9),
        ],
        "return_hour": 21.6,
    },
    "remote_worker": {
        "anchor_kind": "residential",
        "wake_hour": 8.4,
        "stops": [
            ("coffee",     9.1,  35, 145,  45, 0.9),
            ("restaurant", 12.1, 30,  50,  20, 0.8),
            ("coworking",  13.3, 35, 205,  50, 0.85),
            ("grocery",    17.6, 45,  30,  15, 0.5),
        ],
        "return_hour": 18.6,
    },
    "student": {
        "anchor_kind": "residential",
        "wake_hour": 8.5,
        "stops": [
            ("campus",     9.2,  40, 175,  45, 0.95),
            ("restaurant", 12.6, 35,  45,  20, 0.8),
            ("library",    13.6, 40, 195,  60, 0.85),
            ("coffee",     17.3, 50,  45,  25, 0.6),
            ("bar",        20.1, 60, 100,  40, 0.35),
        ],
        "return_hour": 22.1,
    },
}

DEVICES = [
    ("iPhone 14",        "iOS",     "17.5.1", 390, 844),
    ("iPhone 15 Pro",    "iOS",     "18.1",   393, 852),
    ("iPhone SE (3rd)",  "iOS",     "17.4",   375, 667),
    ("Pixel 8",          "Android", "14",     412, 915),
    ("Pixel 7a",         "Android", "14",     412, 892),
    ("Galaxy S23",       "Android", "13",     360, 780),
    ("Galaxy A54",       "Android", "14",     385, 854),
    ("iPhone 13 mini",   "iOS",     "17.6",   375, 812),
]

LANGUAGES = ["en-US", "en-US", "en-US", "en-GB", "es-US", "fr-FR", "de-DE"]


@dataclass
class Participant:
    participant_id: str
    device_model: str
    os_name: str
    os_version: str
    screen_w: int
    screen_h: int
    timezone: str
    language: str
    joined_at: str
    # Prefixed with an underscore because it is generator-only ground truth.
    # The backend never receives this; the whole point is that the system has to
    # infer behaviour from movement alone.
    _persona: str
    _anchor_poi_id: str = ""
    _anchor_name: str = ""


# --------------------------------------------------------------------------
# Ground truth: where the person actually went
# --------------------------------------------------------------------------

@dataclass
class Stop:
    poi: Poi
    start: datetime
    end: datetime


def travel_speed_mps(distance_m: float, rng: random.Random) -> float:
    """Walk short hops; drive or ride longer ones."""
    if distance_m < 700:
        return rng.uniform(1.1, 1.6)        # walking
    if distance_m < 2500:
        return rng.uniform(4.0, 7.5)        # bus / slow city driving
    return rng.uniform(8.0, 13.0)           # driving


def build_day_plan(participant: Participant, pois: list[Poi], anchor: Poi,
                   day_start: datetime, rng: random.Random) -> list[Stop]:
    """Turn a persona template into concrete stops with real clock times."""
    spec = PERSONAS[participant._persona]
    plan: list[Stop] = []
    cursor_lat, cursor_lon = anchor.lat, anchor.lon
    last_end = day_start + timedelta(hours=spec["wake_hour"] + rng.uniform(-0.3, 0.3))

    for kind, hour, jitter_min, dur_min, dur_jit, prob in spec["stops"]:
        if rng.random() > prob:
            continue
        arrive = day_start + timedelta(hours=hour, minutes=rng.gauss(0, jitter_min / 2))
        # Never arrive before we finished the previous stop.
        if arrive < last_end + timedelta(minutes=4):
            arrive = last_end + timedelta(minutes=rng.uniform(5, 14))
        duration = max(8.0, rng.gauss(dur_min, dur_jit / 2))
        poi = nearest_of_kind(pois, kind, cursor_lat, cursor_lon, rng)
        depart = arrive + timedelta(minutes=duration)
        plan.append(Stop(poi, arrive, depart))
        cursor_lat, cursor_lon = poi.lat, poi.lon
        last_end = depart

    # Head back to the overnight anchor.
    ret = day_start + timedelta(hours=spec["return_hour"], minutes=rng.gauss(0, 25))
    if ret < last_end + timedelta(minutes=8):
        ret = last_end + timedelta(minutes=rng.uniform(10, 25))
    plan.append(Stop(anchor, ret, day_start + timedelta(hours=27)))
    return plan


def build_ground_truth(plan: list[Stop], anchor: Poi, day_start: datetime,
                       rng: random.Random, step_s: int = 30) -> list[tuple[datetime, float, float, float]]:
    """
    Produce a dense (t, lat, lon, speed) timeline for the whole day by walking
    through the plan: dwell at a stop, travel to the next, dwell again.
    """
    track: list[tuple[datetime, float, float, float]] = []
    t = day_start
    cur_lat, cur_lon = anchor.lat, anchor.lon

    for stop in plan:
        dist = haversine_m(cur_lat, cur_lon, stop.poi.lat, stop.poi.lon)
        speed = travel_speed_mps(dist, rng) if dist > 1 else 1.0
        travel_s = dist / speed if dist > 1 else 0.0
        depart_at = stop.start - timedelta(seconds=travel_s)

        # 1. Sit still where we are until it's time to leave.
        while t < depart_at:
            jl, jo = offset_meters(cur_lat, cur_lon, rng.gauss(0, 4), rng.gauss(0, 4))
            track.append((t, jl, jo, 0.0))
            t += timedelta(seconds=step_s)

        # 2. Travel, interpolating along a slightly bowed line.
        if travel_s > 0:
            bow_x, bow_y = rng.gauss(0, dist * 0.06), rng.gauss(0, dist * 0.06)
            mid_lat, mid_lon = offset_meters(
                (cur_lat + stop.poi.lat) / 2, (cur_lon + stop.poi.lon) / 2, bow_x, bow_y)
            n = max(1, int(travel_s // step_s))
            for i in range(n):
                frac = (i + 1) / n
                # Quadratic Bezier through the bowed midpoint, so routes are not
                # perfectly straight lines across the map.
                a = (1 - frac) ** 2
                b = 2 * (1 - frac) * frac
                c = frac ** 2
                lat = a * cur_lat + b * mid_lat + c * stop.poi.lat
                lon = a * cur_lon + b * mid_lon + c * stop.poi.lon
                lat, lon = offset_meters(lat, lon, rng.gauss(0, 6), rng.gauss(0, 6))
                track.append((t, lat, lon, speed))
                t += timedelta(seconds=step_s)

        cur_lat, cur_lon = stop.poi.lat, stop.poi.lon

        # 3. Dwell at the stop.
        while t < stop.end:
            jl, jo = offset_meters(cur_lat, cur_lon, rng.gauss(0, 5), rng.gauss(0, 5))
            track.append((t, jl, jo, 0.0))
            t += timedelta(seconds=step_s)

    return track


# --------------------------------------------------------------------------
# Observation: the slice of ground truth the app actually sees
# --------------------------------------------------------------------------

# How likely someone is to open the app in each hour of the waking day. Peaks at
# the natural pauses — morning coffee, lunch, end of day — and again in the
# evening when the daily reveal notification arrives.
SESSION_HOUR_WEIGHTS = [
    (7.0, 0.6), (8.0, 1.4), (9.0, 1.2), (10.0, 0.7), (11.0, 0.8),
    (12.0, 1.5), (13.0, 1.1), (14.0, 0.7), (15.0, 0.8), (16.0, 0.9),
    (17.0, 1.1), (18.0, 1.2), (19.0, 0.9), (20.0, 1.3), (21.0, 1.6), (22.0, 0.6),
]

# Assume phones are charged overnight and drain through the day.
WAKE_HOUR = 7.0
BATTERY_DRAIN_PCT_PER_HOUR = 3.6


def build_sessions(day_start: datetime, rng: random.Random,
                   engagement: float) -> list[tuple[datetime, datetime]]:
    """
    Decide when this person had the app open today.

    `engagement` (0..1) is how diligent the participant is. Low-engagement
    people produce sparse days — which is realistic, and worth showing an
    instructor, because it explains why some participants' reveals are thin.
    """
    hours = [h for h, _ in SESSION_HOUR_WEIGHTS]
    weights = [w for _, w in SESSION_HOUR_WEIGHTS]
    target = max(1, round(engagement * rng.uniform(3.0, 6.0)))

    chosen: list[float] = []
    for _attempt in range(40):
        if len(chosen) >= target:
            break
        h = rng.choices(hours, weights=weights)[0] + rng.random()
        # Don't stack two sessions on top of each other.
        if any(abs(h - c) < 0.6 for c in chosen):
            continue
        chosen.append(h)

    sessions: list[tuple[datetime, datetime]] = []
    for h in sorted(chosen):
        start = day_start + timedelta(hours=h)
        duration_s = rng.uniform(60, 420)          # 1 to 7 minutes on screen
        sessions.append((start, start + timedelta(seconds=duration_s)))
    return sessions


def battery_at(t: datetime, day_start: datetime, start_pct: float) -> int:
    """Full-ish in the morning, draining through the waking day."""
    hours_awake = (t - day_start).total_seconds() / 3600.0 - WAKE_HOUR
    if hours_awake <= 0:
        return int(min(100.0, start_pct))
    pct = start_pct - hours_awake * BATTERY_DRAIN_PCT_PER_HOUR
    return int(max(5.0, min(100.0, pct)))


def connection_for(kind: str, moving: bool, rng: random.Random) -> str:
    """Wi-Fi where people settle in, cellular on the move."""
    if moving:
        return "cellular"
    if kind in {"hotel", "residential", "office", "coffee", "library", "coworking", "campus"}:
        return "wifi" if rng.random() < 0.85 else "cellular"
    return "cellular" if rng.random() < 0.7 else "wifi"


def kind_at(plan: list[Stop], t: datetime) -> tuple[str, bool]:
    """Which place (if any) the person is sitting in at time t."""
    for stop in plan:
        if stop.start <= t <= stop.end:
            return stop.poi.kind, False
    return "", True


# --------------------------------------------------------------------------
# Main generation
# --------------------------------------------------------------------------

def generate(args: argparse.Namespace) -> dict:
    rng = random.Random(args.seed)
    tz = timezone(timedelta(hours=args.utc_offset))

    pois = build_city(args.center_lat, args.center_lon, rng)
    course_start = datetime.fromisoformat(args.start_date).replace(tzinfo=tz)

    participants: list[Participant] = []
    persona_names = list(PERSONAS.keys())
    for i in range(args.participants):
        model, os_name, os_ver, sw, sh = rng.choice(DEVICES)
        persona = persona_names[i % len(persona_names)]
        anchor = rng.choice(pois_of(pois, PERSONAS[persona]["anchor_kind"]))
        participants.append(Participant(
            participant_id=f"p_{i + 1:03d}",
            device_model=model,
            os_name=os_name,
            os_version=os_ver,
            screen_w=sw,
            screen_h=sh,
            timezone=args.timezone_name,
            language=rng.choice(LANGUAGES),
            joined_at=course_start.isoformat(),
            _persona=persona,
            _anchor_poi_id=anchor.poi_id,
            _anchor_name=anchor.name,
        ))

    pings: list[dict] = []
    truth_rows: list[dict] = []
    ping_counter = 0
    session_counter = 0

    for p in participants:
        anchor = next(x for x in pois if x.poi_id == p._anchor_poi_id)
        # Some people are simply more diligent about opening the app than others.
        engagement = rng.uniform(0.45, 1.0)
        start_battery = rng.uniform(88, 100)

        for day_index in range(args.days):
            day_start = (course_start + timedelta(days=day_index)).replace(
                hour=0, minute=0, second=0, microsecond=0)

            plan = build_day_plan(p, pois, anchor, day_start, rng)
            track = build_ground_truth(plan, anchor, day_start, rng)
            if not track:
                continue
            track_start = track[0][0]

            if args.emit_ground_truth:
                # Thinned to roughly one point every 10 minutes. This file only
                # exists to show an instructor what the app *missed*, so fine
                # detail is unnecessary and would bloat the repository.
                for (t, lat, lon, spd) in track[::20]:
                    truth_rows.append({
                        "participant_id": p.participant_id,
                        "day_index": day_index,
                        "ts": t.isoformat(),
                        "lat": round(lat, 6),
                        "lon": round(lon, 6),
                        "speed_mps": round(spd, 2),
                    })

            for (s_start, s_end) in build_sessions(day_start, rng, engagement):
                session_counter += 1
                session_id = f"s_{session_counter:05d}"
                t = s_start
                interval = rng.uniform(15, 25)
                while t <= s_end:
                    idx = int((t - track_start).total_seconds() // 30)
                    if 0 <= idx < len(track):
                        _, lat, lon, spd = track[idx]
                        kind, moving = kind_at(plan, t)
                        # GPS is worse in dense areas and when moving.
                        accuracy = abs(rng.gauss(12 if not moving else 22, 7)) + 4
                        lat, lon = offset_meters(
                            lat, lon,
                            rng.gauss(0, accuracy / 2.5),
                            rng.gauss(0, accuracy / 2.5),
                        )
                        ping_counter += 1
                        pings.append({
                            "ping_id": ping_counter,
                            "participant_id": p.participant_id,
                            "session_id": session_id,
                            "ts": t.isoformat(),
                            "lat": round(lat, 6),
                            "lon": round(lon, 6),
                            "accuracy_m": round(accuracy, 1),
                            "battery_pct": battery_at(t, day_start, start_battery),
                            "connection": connection_for(kind, moving, rng),
                        })
                    t += timedelta(seconds=interval)

    return {
        "pois": pois,
        "participants": participants,
        "pings": pings,
        "ground_truth": truth_rows,
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "seed": args.seed,
            "days": args.days,
            "participant_count": len(participants),
            "ping_count": len(pings),
            "session_count": session_counter,
            "center": {"lat": args.center_lat, "lon": args.center_lon},
            "timezone": args.timezone_name,
            "utc_offset_hours": args.utc_offset,
            "course_start": course_start.isoformat(),
            "notice": (
                "ENTIRELY SYNTHETIC. No real person, device, business or address "
                "is represented in this file."
            ),
        },
    }


def write_outputs(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "pois.json").write_text(
        json.dumps([asdict(p) for p in result["pois"]], indent=2) + "\n")

    (out_dir / "participants.json").write_text(
        json.dumps([asdict(p) for p in result["participants"]], indent=2) + "\n")

    (out_dir / "meta.json").write_text(json.dumps(result["meta"], indent=2) + "\n")

    pings = result["pings"]
    if pings:
        with (out_dir / "pings.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(pings[0].keys()))
            writer.writeheader()
            writer.writerows(pings)
    # Compact rather than indented — this file is read by code, not people, and
    # pings.csv already exists for anyone who wants to eyeball it.
    (out_dir / "pings.json").write_text(
        json.dumps(pings, separators=(",", ":")) + "\n")

    if result["ground_truth"]:
        with (out_dir / "ground_truth.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(result["ground_truth"][0].keys()))
            writer.writeheader()
            writer.writerows(result["ground_truth"])

    (out_dir / "README.md").write_text(f"""# Sample data — entirely synthetic

Generated by `tools/generate_sample_data.py`. **Nothing in here is real.**
No real person, device, business or address is represented.

- `participants.json` — invented participants and their device details.
  Fields beginning with `_` are generator-only ground truth (such as which
  persona template produced the data). The backend never receives these; the
  system has to infer behaviour from movement alone.
- `pings.csv` / `pings.json` — the location points the app would have sent.
  **Deliberately patchy**, because the real app only collects while it is open
  on screen.
- `pois.json` — the invented places used to build routines. In production this
  role is played by OpenStreetMap data.
- `ground_truth.csv` — where people actually went, including everything the app
  never saw. Useful for teaching: it shows what the gaps hid.
- `meta.json` — generation parameters, including the random seed.

Regenerate with the same seed to get identical data:

```bash
python3 tools/generate_sample_data.py --seed {result['meta']['seed']} \\
    --participants {result['meta']['participant_count']} \\
    --days {result['meta']['days']} --out data/sample
```
""")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate synthetic participant data for What Your Phone Knows.")
    ap.add_argument("--participants", type=int, default=12)
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260810)
    ap.add_argument("--start-date", default="2026-09-14",
                    help="Course start date, YYYY-MM-DD (a Monday by default).")
    ap.add_argument("--center-lat", type=float, default=30.2672,
                    help="City centre latitude (default: a US downtown).")
    ap.add_argument("--center-lon", type=float, default=-97.7431)
    ap.add_argument("--timezone-name", default="America/Chicago")
    ap.add_argument("--utc-offset", type=float, default=-5.0,
                    help="Hours from UTC for the course location.")
    ap.add_argument("--emit-ground-truth", action="store_true", default=True)
    ap.add_argument("--out", default="data/sample")
    args = ap.parse_args()

    result = generate(args)
    write_outputs(result, Path(args.out))

    m = result["meta"]
    print("Generated synthetic sample data")
    print(f"  participants : {m['participant_count']}")
    print(f"  days         : {m['days']}")
    print(f"  app sessions : {m['session_count']}")
    print(f"  location pings: {m['ping_count']}")
    print(f"  written to   : {args.out}/")


if __name__ == "__main__":
    main()
