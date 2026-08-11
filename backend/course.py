"""
Where the course is being taught.

Why this exists
---------------
This tool was built for a course in Milwaukee, and for a while Milwaukee was
written into the map, the sample-data generator and half the documentation. That
is fine until somebody teaches it in Cincinnati, at which point the dashboard
opens on the wrong city, every stop is unmatched, and the environmental layers
describe streets nobody is standing on.

So the course location is a **setting**, stored in the database, set once at the
start and used by everything: where the map opens, where the sample generator
invents a week, which area the fetch tools default to, and which timezone times
are shown in when no participant has reported one yet.

Milwaukee remains the default, because a default that is a real place is more
useful than one that is 0,0 in the Atlantic.

On geocoding
------------
Typing "Cincinnati, Ohio" and getting coordinates requires asking somebody. That
somebody is OpenStreetMap's Nominatim service, and two things make it acceptable
here where a lookup during a course would not be:

- It is an **instructor** action at **setup** time. The thing being sent is the
  name of a city somebody typed, not a participant's position. No participant
  data exists yet in most cases, and none is involved either way.
- It is **optional**. Coordinates can be entered directly, and the whole feature
  works with the network unplugged.

Nominatim's usage policy asks for a genuine User-Agent and no heavy automated
use. Setting a course location once or twice is exactly the light, human use it
is meant for.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SETTING_KEY = "course_location"

# Downtown Milwaukee, Wisconsin. Used until somebody sets something else.
DEFAULT_LOCATION = {
    "name": "Milwaukee, Wisconsin",
    "lat": 43.0389,
    "lon": -87.9065,
    "zoom": 14,
    "timezone": "America/Chicago",
}

UA = "dwell-privacy-lab/1.0 (privacy course teaching tool; course setup)"

# Offered in the dashboard as a starting point. Anything zoneinfo recognises is
# accepted, so this list being US-centric does not limit anybody.
COMMON_TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver",
    "America/Phoenix", "America/Los_Angeles", "America/Anchorage",
    "Pacific/Honolulu", "Europe/London", "Europe/Berlin", "UTC",
]


class LocationError(ValueError):
    """A location that cannot be used, with a message meant for a human."""


# --------------------------------------------------------------------------
# Reading and writing
# --------------------------------------------------------------------------

def get_location(conn: sqlite3.Connection) -> dict:
    """
    The configured course location, or Milwaukee.

    Never raises. A corrupt or half-written setting falls back to the default
    rather than taking the dashboard down — an unusable map is a worse failure
    than a map pointing at the wrong city, because at least the second one is
    obvious enough to fix.
    """
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (SETTING_KEY,)).fetchone()
    except sqlite3.Error:
        return dict(DEFAULT_LOCATION, is_default=True)
    if not row:
        return dict(DEFAULT_LOCATION, is_default=True)
    try:
        stored = json.loads(row["value"])
        return {
            "name": str(stored.get("name") or DEFAULT_LOCATION["name"]),
            "lat": float(stored["lat"]),
            "lon": float(stored["lon"]),
            "zoom": int(stored.get("zoom") or DEFAULT_LOCATION["zoom"]),
            "timezone": str(stored.get("timezone") or DEFAULT_LOCATION["timezone"]),
            "is_default": False,
        }
    except (ValueError, KeyError, TypeError):
        return dict(DEFAULT_LOCATION, is_default=True)


def set_location(conn: sqlite3.Connection, name: str, lat: float, lon: float,
                 tz_name: str, zoom: int = 14) -> dict:
    """Store a course location. Validates before writing, never after."""
    location = validate(name, lat, lon, tz_name, zoom)
    conn.execute(
        "INSERT INTO settings (key, value, updated) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
        "updated = excluded.updated",
        (SETTING_KEY, json.dumps(location),
         datetime.now(timezone.utc).isoformat()))
    conn.commit()
    _reday(conn, location["timezone"])
    return dict(location, is_default=False)


def reset_location(conn: sqlite3.Connection) -> dict:
    """Back to Milwaukee."""
    conn.execute("DELETE FROM settings WHERE key = ?", (SETTING_KEY,))
    conn.commit()
    _reday(conn, DEFAULT_LOCATION["timezone"])
    return dict(DEFAULT_LOCATION, is_default=True)


def _reday(conn: sqlite3.Connection, tz_name: str) -> int:
    """
    Re-file existing points under the new timezone's days.

    Moving a course from Milwaukee to Berlin does not just move the map: it
    changes which calendar day every point already collected belongs to. Without
    this, days set before the move and days set after it would disagree, and the
    disagreement would show up as a reveal missing its evening.
    """
    from . import db
    return db.backfill_local_days(conn, tz_name)


def validate(name: str, lat: float, lon: float, tz_name: str,
             zoom: int = 14) -> dict:
    """
    Check a location is usable, with messages an instructor can act on.

    Latitude and longitude are the classic pair to get backwards, and a swapped
    pair is often still numerically valid — so the check that catches it is the
    one worth having, and out-of-range longitude is the common tell.
    """
    name = (name or "").strip()
    if not name:
        raise LocationError("Give the location a name, so the room knows what "
                            "they are looking at.")
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        raise LocationError("Latitude and longitude must be numbers.")
    if not -90 <= lat <= 90:
        raise LocationError(
            f"Latitude {lat} is out of range. It must be between -90 and 90 — "
            f"if this looks like a longitude, the two are the wrong way round.")
    if not -180 <= lon <= 180:
        raise LocationError(
            f"Longitude {lon} is out of range. It must be between -180 and 180.")
    tz_name = (tz_name or "").strip()
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise LocationError(
            f"'{tz_name}' is not a timezone this system recognises. Use a name "
            f"like America/New_York.")
    # 'EST' and 'MST' are real zoneinfo keys, but they are fixed offsets that
    # never observe daylight saving. Accepting one would quietly show every time
    # in the course an hour out for most of the year, which is precisely the
    # kind of confident, wrong number this project exists to warn about.
    if "/" not in tz_name and tz_name != "UTC":
        raise LocationError(
            f"'{tz_name}' is a fixed offset that ignores daylight saving, so "
            f"times would be an hour out for much of the year. Use the "
            f"region form instead, as in America/New_York.")
    try:
        zoom = int(zoom)
    except (TypeError, ValueError):
        zoom = 14
    return {
        "name": name[:120],
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "zoom": max(3, min(zoom, 18)),
        "timezone": tz_name,
    }


# --------------------------------------------------------------------------
# Geocoding
# --------------------------------------------------------------------------

def parse_nominatim(payload: list) -> list[dict]:
    """
    Turn a Nominatim response into candidates to choose between.

    Kept separate from the request so it can be tested without a network, and
    so a change in their response shape is one obvious place to look.
    """
    out = []
    for row in payload if isinstance(payload, list) else []:
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        label = str(row.get("display_name") or "").strip()
        if not label:
            continue
        out.append({
            "name": label,
            "short_name": _short_name(label),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "kind": str(row.get("type") or row.get("class") or ""),
        })
    return out


def _short_name(display_name: str) -> str:
    """
    "Cincinnati, Hamilton County, Ohio, United States" -> "Cincinnati, Ohio".

    Full display names run to several commas of county and postcode, which is
    not what belongs across the top of a dashboard. The city is the first part
    and the state or region is the part before the country — taking the first
    two would give the county, which is nobody's idea of where they are.
    """
    parts = [p.strip() for p in display_name.split(",") if p.strip()]
    if not parts:
        return display_name
    if len(parts) < 3:
        return ", ".join(dict.fromkeys(parts))
    return ", ".join(dict.fromkeys([parts[0], parts[-2]]))


def geocode(query: str, limit: int = 5, timeout: int = 20) -> list[dict]:
    """
    Look up a place name. Raises LocationError with something readable.

    Only ever called because an instructor typed a place name and pressed a
    button. Never called during a course, and never with anybody's position.
    """
    query = (query or "").strip()
    if not query:
        raise LocationError("Type a place name to look up.")
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": query, "format": "json", "limit": str(max(1, min(limit, 10))),
        "addressdetails": "0",
    })
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        raise LocationError(
            f"The lookup service refused the request ({exc.code}). You can "
            f"enter coordinates directly instead.")
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise LocationError(
            "Could not reach the lookup service. Check the connection, or "
            "enter coordinates directly — that works with no internet at all.")
    results = parse_nominatim(payload)
    if not results:
        raise LocationError(
            f"Nothing found for '{query}'. Try adding the state or country, "
            f"as in 'Cincinnati, Ohio'.")
    return results
