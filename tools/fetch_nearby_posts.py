#!/usr/bin/env python3
"""
Collect genuinely geotagged public posts near the course area.

    python3 tools/fetch_nearby_posts.py --around 43.0389,-87.9065 --radius 1500 \
        --days 2026-09-14:2026-09-18 --out data/context/milwaukee-posts.json

The point of this layer is one specific moment in the classroom: a participant
sees that while they were standing at a particular corner, a stranger a hundred
metres away posted a photo of it publicly, and it is still there. Not "somebody
posted about you" — nobody posted about them. Just: *this was happening around
you, in public, and it is on the record.*

Which platforms this can honestly use
-------------------------------------
You asked about TikTok. It cannot be done, and it is worth saying why plainly
rather than quietly substituting something else:

- **TikTok** has no public API for searching posts by location. The research API
  is grant-gated, does not expose geosearch, and its terms forbid the use this
  would put it to. Getting the data would mean scraping the web client, which
  breaks TikTok's terms of service. A privacy course cannot run on data taken in
  breach of somebody's terms; the lesson would collapse under the contradiction.
- **Instagram and Facebook** removed public location search from their APIs in
  2018, precisely because it was being used for this.
- **X/Twitter** removed its free geo-search tier and its current API pricing
  puts location search out of reach.

What remains are platforms that publish geotagged material openly and mean it:

- **Wikimedia Commons** — freely licensed photographs with real coordinates, no
  account, no key, no rate-limit paperwork. Ordinary people photographing
  ordinary streets. Historic rather than same-week, so use `--undated` to offer
  them as "this is what is publicly on the record about this spot".
- **Flickr** — genuinely geotagged public photos with real upload dates, which
  is the closest lawful equivalent to what you had in mind. Needs a free API
  key: https://www.flickr.com/services/apps/create/apply

Both are the honest version of the lesson. The dishonest version would be to
scrape TikTok and not mention it.

What this refuses to do
-----------------------
This searches for posts made **near a place**. It does not search for posts by
or about a participant, and author names are discarded on the way in — the
output format has no field for them. Nothing here can be pointed at a person,
and it must not be adapted to.

Run it before the course. The server never fetches during one, so no
participant location is ever sent to a third party.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

UA = "dwell-privacy-lab/1.0 (privacy course teaching tool; area context only)"

# Posts are matched to stops at 120 m, so collecting much beyond a kilometre or
# two is wasted effort — it only produces items that can never match.
DEFAULT_RADIUS_M = 1500


def _get_json(url: str, timeout: int = 45) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        print(f"  request failed: {exc}")
        return None


# ----------------------------------------------------------- Wikimedia Commons

def parse_commons(payload: dict, undated_as: str | None) -> list[dict]:
    """
    Turn a Commons geosearch response into context items.

    Commons gives coordinates and a title but no upload date in the geosearch
    result, so these are offered undated unless `--undated` pins them to a day.
    An undated item without coordinates would be useless; these have
    coordinates, which is the part that carries the lesson.
    """
    items = []
    for row in payload.get("query", {}).get("geosearch", []):
        title = str(row.get("title", "")).strip()
        if not title or row.get("lat") is None or row.get("lon") is None:
            continue
        # "File:Milwaukee City Hall 2019.jpg" -> "Milwaukee City Hall 2019"
        label = title.split(":", 1)[-1].rsplit(".", 1)[0].replace("_", " ").strip()
        if not label:
            continue
        items.append({
            "title": f"Public photo posted here: {label}",
            "date": undated_as,
            "lat": round(float(row["lat"]), 6),
            "lon": round(float(row["lon"]), 6),
            "place": "",
            "kind": "photo",
            "source": "Wikimedia Commons",
            "url": "https://commons.wikimedia.org/wiki/"
                   + urllib.parse.quote(title.replace(" ", "_"), safe=":/"),
        })
    return items


def fetch_commons(lat: float, lon: float, radius_m: int, limit: int,
                  undated_as: str | None) -> list[dict]:
    # Commons caps geosearch radius at 10 km and limit at 500.
    url = ("https://commons.wikimedia.org/w/api.php?action=query&list=geosearch"
           f"&gscoord={lat}%7C{lon}&gsradius={min(radius_m, 10000)}"
           f"&gslimit={min(limit, 500)}&gsnamespace=6&format=json&formatversion=2")
    print(f"  Wikimedia Commons within {radius_m} m ...")
    payload = _get_json(url)
    return parse_commons(payload, undated_as) if payload else []


# ------------------------------------------------------------------- Flickr

def parse_flickr(payload: dict) -> list[dict]:
    """
    Turn a Flickr photos.search response into context items.

    Flickr returns the owner's name and NSID. Both are dropped here: the item
    format has nowhere to put them, and a stranger's identity is not part of
    this lesson. What matters is that a photo was taken at that spot, that day.
    """
    items = []
    for row in payload.get("photos", {}).get("photo", []):
        if row.get("latitude") in (None, 0, "0") or row.get("longitude") in (None, 0, "0"):
            continue
        taken = str(row.get("datetaken", ""))[:19]
        if not taken:
            continue
        try:
            when = datetime.fromisoformat(taken)
        except ValueError:
            continue
        title = str(row.get("title", "")).strip() or "untitled"
        items.append({
            "title": f"Public photo posted here: {title}",
            "date": when.date().isoformat(),
            "time": when.time().isoformat(timespec="minutes"),
            "lat": round(float(row["latitude"]), 6),
            "lon": round(float(row["longitude"]), 6),
            "place": "",
            "kind": "photo",
            "source": "Flickr",
            "url": f"https://www.flickr.com/photo.gne?id={row.get('id', '')}",
        })
    return items


def fetch_flickr(api_key: str, lat: float, lon: float, radius_m: int,
                 days: list[str], limit: int) -> list[dict]:
    # Flickr takes its radius in kilometres and caps it at 32.
    radius_km = max(0.1, min(radius_m / 1000.0, 32))
    params = {
        "method": "flickr.photos.search",
        "api_key": api_key,
        "lat": f"{lat}", "lon": f"{lon}", "radius": f"{radius_km:.3f}",
        "radius_units": "km",
        "min_taken_date": f"{days[0]} 00:00:00",
        "max_taken_date": f"{days[-1]} 23:59:59",
        "extras": "geo,date_taken",
        "per_page": str(min(limit, 500)),
        "format": "json", "nojsoncallback": "1",
        "content_type": "1", "safe_search": "1",
    }
    url = "https://api.flickr.com/services/rest/?" + urllib.parse.urlencode(params)
    print(f"  Flickr within {radius_km:.1f} km, {days[0]} to {days[-1]} ...")
    payload = _get_json(url)
    if not payload:
        return []
    if payload.get("stat") != "ok":
        print(f"  Flickr refused: {payload.get('message', 'unknown error')}")
        return []
    return parse_flickr(payload)


# --------------------------------------------------------------------- glue

def day_range(spec: str) -> list[str]:
    """'2026-09-14:2026-09-18' -> every date in between, inclusive."""
    first, _, last = spec.partition(":")
    start = date.fromisoformat(first)
    end = date.fromisoformat(last) if last else start
    if end < start:
        raise ValueError("the end of the range is before the start")
    return [(start + timedelta(days=n)).isoformat()
            for n in range((end - start).days + 1)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--around", required=True, metavar="LAT,LON",
                    help="centre of the course area")
    ap.add_argument("--radius", type=int, default=DEFAULT_RADIUS_M,
                    help=f"metres (default {DEFAULT_RADIUS_M})")
    ap.add_argument("--days", help="YYYY-MM-DD[:YYYY-MM-DD], required for Flickr")
    ap.add_argument("--flickr-key", help="free Flickr API key; omit to skip Flickr")
    ap.add_argument("--undated", metavar="YYYY-MM-DD",
                    help="pin undated Commons photos to this day so they can match")
    ap.add_argument("--limit", type=int, default=200, help="per source")
    ap.add_argument("--out", type=Path, default=Path("data/context/nearby-posts.json"))
    args = ap.parse_args()

    try:
        lat_s, lon_s = args.around.split(",")
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        print("--around must look like 43.0389,-87.9065")
        return 2

    days = day_range(args.days) if args.days else []

    items: list[dict] = []
    items += fetch_commons(lat, lon, args.radius, args.limit, args.undated)

    if args.flickr_key:
        if not days:
            print("  Flickr needs --days; skipping it.")
        else:
            items += fetch_flickr(args.flickr_key, lat, lon, args.radius,
                                  days, args.limit)
    else:
        print("  no --flickr-key given; skipping Flickr.")

    # Undated items can never match a stop, and silently writing them out would
    # look like the tool worked when it did not.
    dated = [i for i in items if i.get("date")]
    dropped = len(items) - len(dated)

    seen, unique = set(), []
    for item in dated:
        key = (item["title"], item["date"], item["lat"], item["lon"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=lambda i: (i["date"], i["title"]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"items": unique}, indent=2) + "\n")

    print(f"\nWrote {len(unique)} located post(s) to {args.out}")
    if dropped:
        print(f"  {dropped} undated item(s) discarded — pass --undated "
              f"YYYY-MM-DD to keep the Commons ones.")
    if unique:
        print("  Load them with:  python -m backend.load_sample")
    else:
        print("  Nothing matched. Try a larger --radius, or a wider --days range.")
    print("\nPosts match a stop only within 120 m and 2 hours. That tightness is "
          "deliberate:\n  at 400 m this stops meaning 'right where you were "
          "standing'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
