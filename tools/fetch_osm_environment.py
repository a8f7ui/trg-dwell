#!/usr/bin/env python3
"""
Fetch real observing infrastructure for a course area, from OpenStreetMap.

Downloads the publicly mapped cameras, plate readers and similar for a bounding
box, and writes them in the format the backend loads. Uses the Overpass API,
which is free and needs no account.

    python3 tools/fetch_osm_environment.py --bbox 30.18,-97.85,30.36,-97.63
    python3 tools/fetch_osm_environment.py --around 30.2672,-97.7431 --radius 5000

Then load it:

    python3 tools/fetch_osm_environment.py ... --out data/sample/environment.json
    python -m backend.load_sample

What this does and does not fetch
---------------------------------
It fetches things OpenStreetMap records about **places**: surveillance cameras,
ALPR installations, and transit gates. All of it is public, contributed by
volunteers, and describes street furniture rather than people.

It deliberately does NOT fetch Wi-Fi observations from WiGLE or similar
wardriving databases. Those services work by you sending them the coordinates
you are interested in — which would mean transmitting participants' locations to
a third party, and this app promises participants that their data goes to the
course server and nowhere else. Breaking that promise to make a lesson about
broken promises would be a poor trade. If you want Wi-Fi in the picture, obtain a
static extract for your area ahead of time and convert it offline.

Coverage is patchy and always an undercount. OpenStreetMap has excellent camera
coverage in some cities and almost none in others, and no public dataset records
private cameras or where a mobile plate reader was parked. Say so when you teach
from it.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OVERPASS = "https://overpass-api.de/api/interpreter"

# OSM tagging for things that observe. `man_made=surveillance` is the main one;
# the surveillance:type sub-tag distinguishes cameras from plate readers.
QUERY_TEMPLATE = """
[out:json][timeout:120];
(
  node["man_made"="surveillance"]({bbox});
  way["man_made"="surveillance"]({bbox});
  node["highway"="speed_camera"]({bbox});
  node["barrier"="toll_booth"]({bbox});
  node["public_transport"="stop_position"]["network"]({bbox});
);
out center tags;
"""


def classify(tags: dict) -> str | None:
    """Map OSM tags onto the kinds the backend understands."""
    stype = (tags.get("surveillance:type") or "").lower()
    if "alpr" in stype or "anpr" in stype or tags.get("highway") == "speed_camera":
        return "alpr"
    if tags.get("man_made") == "surveillance":
        # Some surveillance nodes are microphones or guards; only cameras count.
        if stype in ("", "camera", "webcam"):
            return "camera"
        return None
    if tags.get("barrier") == "toll_booth":
        return "alpr"
    if tags.get("public_transport") == "stop_position":
        return "transit"
    return None


def fetch(bbox: str) -> list[dict]:
    query = QUERY_TEMPLATE.format(bbox=bbox)
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS, data=data,
        headers={"User-Agent": "dwell-privacy-lab/1.0 (course teaching tool)"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise SystemExit(
            f"Overpass returned {exc.code}. It rate-limits heavy use; wait a minute "
            f"and try again, or use a smaller area.")
    except urllib.error.URLError as exc:
        raise SystemExit(f"Could not reach Overpass: {exc.reason}")

    features = []
    for i, element in enumerate(payload.get("elements", []), start=1):
        tags = element.get("tags", {})
        kind = classify(tags)
        if not kind:
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        features.append({
            "feature_id": f"osm_{element.get('type', 'node')}_{element.get('id', i)}",
            "kind": kind,
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "name": tags.get("name", "") or tags.get("operator", ""),
            "source": "openstreetmap",
        })
    return features


def bbox_around(lat: float, lon: float, radius_m: float) -> str:
    dlat = radius_m / 111_320
    dlon = radius_m / (111_320 * math.cos(math.radians(lat)))
    return f"{lat - dlat:.6f},{lon - dlon:.6f},{lat + dlat:.6f},{lon + dlon:.6f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bbox", help="south,west,north,east")
    ap.add_argument("--around", help="lat,lon — used with --radius")
    ap.add_argument("--radius", type=float, default=5000,
                    help="metres, when using --around (default 5000)")
    ap.add_argument("--out", default="data/sample/environment.json")
    ap.add_argument("--merge", action="store_true",
                    help="Add to the existing file rather than replacing it.")
    args = ap.parse_args()

    if args.around:
        lat, lon = (float(x) for x in args.around.split(","))
        bbox = bbox_around(lat, lon, args.radius)
    elif args.bbox:
        bbox = args.bbox
    else:
        raise SystemExit("Give either --bbox or --around. See --help.")

    print(f"Asking OpenStreetMap for observing infrastructure in {bbox} ...")
    features = fetch(bbox)

    out = Path(args.out)
    if args.merge and out.exists():
        existing = json.loads(out.read_text())
        seen = {f["feature_id"] for f in features}
        features += [f for f in existing if f["feature_id"] not in seen]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(features, indent=2) + "\n")

    counts: dict[str, int] = {}
    for f in features:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1

    print(f"\nWrote {len(features)} features to {out}")
    for kind, n in sorted(counts.items()):
        print(f"  {kind:10s} {n}")

    if not features:
        print("\nNothing found. Either the area genuinely has none mapped, or — far")
        print("more likely — OpenStreetMap coverage there is thin. That is worth")
        print("saying out loud when you teach: absence of data is not absence of")
        print("cameras.")
    print("\nNow load it:  python -m backend.load_sample")


if __name__ == "__main__":
    main()
