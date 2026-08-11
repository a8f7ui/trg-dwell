"""
Area context: what else was happening where somebody was.

Why this exists
---------------
An analyst does not read a movement trail in isolation. A cluster of people at a
particular corner on a particular evening means one thing if there was a concert
there and quite another if there was a protest. Public reporting is what turns
"twelve stationary points" into "attended X".

This module holds that context — dated, located, public items such as local news
and event listings — and matches them to a participant's stops by place and
time.

The line, stated once more
--------------------------
**Context is about places and events, never about people.**

This does not search for posts by or about participants, does not match anybody
to a social media account, and does not attempt to find out who somebody is.
Doing so would be identity resolution, which this project refuses on principle,
and it would be an unusually invasive form of it.

Person-targeted collection is exactly what a real service would add next, and
the honest way to teach that is to describe the step and decline to take it —
not to take it and hope nobody minds.

Where the items come from
-------------------------
Items are loaded from `data/context/*.json`. An instructor curates that file, or
generates it with `tools/fetch_area_context.py`, which reads public RSS feeds
for the course city. The server never reaches out on its own during a course:
context is prepared beforehand, so no participant location is ever sent anywhere
to look something up.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .analysis import Stop, haversine_m

# How close, and how near in time, an item has to be before it is offered as an
# explanation for a stop.
CONTEXT_RADIUS_M = 400.0
CONTEXT_WINDOW_HOURS = 6


def load_items(context_dir: Path) -> list[dict]:
    """
    Read every context item available.

    Each item needs at minimum: a title, a date, and either coordinates or
    nothing (city-wide items match any location on their day).
    """
    if not context_dir.exists():
        return []
    items: list[dict] = []
    for path in sorted(context_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        for raw in (payload if isinstance(payload, list) else payload.get("items", [])):
            if not raw.get("title") or not raw.get("date"):
                continue
            items.append({
                "title": str(raw["title"])[:300],
                "date": str(raw["date"])[:10],
                "time": raw.get("time"),
                "lat": raw.get("lat"),
                "lon": raw.get("lon"),
                "place": str(raw.get("place", ""))[:160],
                "kind": str(raw.get("kind", "news"))[:40],
                "source": str(raw.get("source", ""))[:160],
                "url": str(raw.get("url", ""))[:400],
            })
    return items


def match_to_day(stops: list[Stop], day: str, items: list[dict]) -> dict:
    """
    Which context items could explain a stop on this day.

    Deliberately offered as *possible* explanations rather than conclusions. A
    concert two hundred metres away does not mean somebody attended it, and the
    wording says so.
    """
    if not items:
        return {"available": False}

    same_day = [i for i in items if i["date"] == day]
    if not same_day:
        return {"available": True, "matches": [], "city_wide": [],
                "narrative": "Nothing in the loaded area context falls on this day."}

    located = [i for i in same_day if i.get("lat") is not None and i.get("lon") is not None]
    city_wide = [i for i in same_day if i.get("lat") is None or i.get("lon") is None]

    matches = []
    for stop in stops:
        for item in located:
            try:
                d = haversine_m(stop.lat, stop.lon, float(item["lat"]), float(item["lon"]))
            except (TypeError, ValueError):
                continue
            if d > CONTEXT_RADIUS_M:
                continue
            if item.get("time"):
                try:
                    when = datetime.fromisoformat(f"{item['date']}T{item['time']}")
                    ref = stop.start.replace(tzinfo=None)
                    if abs((ref - when).total_seconds()) > CONTEXT_WINDOW_HOURS * 3600:
                        continue
                except ValueError:
                    pass
            matches.append({
                "stop_place": stop.poi_name,
                "stop_start": stop.start.isoformat(),
                "distance_m": round(d),
                **item,
            })

    # A participant who returns to the same place three times should not make
    # one news item appear three times.
    matches.sort(key=lambda m: m["distance_m"])
    seen: set[tuple] = set()
    deduped = []
    for m in matches:
        key = (m["title"], m["stop_place"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    matches = deduped
    return {
        "available": True,
        "matches": matches[:10],
        "city_wide": city_wide[:6],
        "narrative": _narrative(matches, city_wide),
        "caveat": (
            "These are things that were happening nearby, not things this person "
            "did. Being two hundred metres from an event is not attending it. An "
            "analyst would treat these as leads to check, and a careless one "
            "would treat them as findings."),
    }


def _narrative(matches: list[dict], city_wide: list[dict]) -> str:
    if not matches and not city_wide:
        return "No public reporting matches this day's stops."
    bits = []
    if matches:
        top = matches[0]
        bits.append(
            f"{len(matches)} public item(s) coincide with where this person "
            f"stopped. The closest is “{top['title']}”, about "
            f"{top['distance_m']} m from {top['stop_place'] or 'one of their stops'}.")
        bits.append(
            "This is the step where a trail stops being coordinates and starts "
            "being an account of somebody's day.")
    if city_wide:
        bits.append(f"{len(city_wide)} further item(s) affected the city generally.")
    return " ".join(bits)
