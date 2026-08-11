#!/usr/bin/env python3
"""
Check an offline map file, and say what it actually covers.

Offline maps are downloaded by drawing a box on a website, which is easy to get
wrong — the wrong city, or a box that stops short of the hotel everybody is
staying in. This reads the file's own header and tells you, in plain terms, the
area and zoom range it holds, so you find out now rather than in the classroom.

    python3 tools/check_basemap.py
    python3 tools/check_basemap.py data/basemap/milwaukee.pmtiles

With no argument it checks every map installed in data/basemap/.

Nothing is downloaded and nothing is sent anywhere; it only reads the first 127
bytes of a local file. See docs/offline-maps.md for how to obtain one.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

BASEMAP_DIR = Path(__file__).resolve().parent.parent / "data" / "basemap"

TILE_TYPES = {0: "unknown", 1: "vector (MVT)", 2: "PNG", 3: "JPEG", 4: "WebP", 5: "AVIF"}

# Rough guide to what a zoom level shows, for people who do not think in zooms.
ZOOM_MEANING = {
    0: "the whole world", 5: "a country", 8: "a region",
    10: "a city", 12: "a district", 14: "streets",
    15: "streets and buildings", 16: "individual buildings",
}


def describe_zoom(z: int) -> str:
    best = max((k for k in ZOOM_MEANING if k <= z), default=0)
    return ZOOM_MEANING[best]


def read_header(path: Path) -> dict:
    with path.open("rb") as fh:
        head = fh.read(127)
    if len(head) < 127 or head[:7] != b"PMTiles":
        raise ValueError("This is not a PMTiles file (its header does not match).")
    version = head[7]
    if version != 3:
        raise ValueError(f"PMTiles version {version} — this tool expects version 3.")

    min_zoom, max_zoom = head[100], head[101]
    min_lon, min_lat, max_lon, max_lat = struct.unpack_from("<iiii", head, 102)
    tile_type = head[99]
    addressed = struct.unpack_from("<Q", head, 72)[0]

    return {
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "west": min_lon / 1e7,
        "south": min_lat / 1e7,
        "east": max_lon / 1e7,
        "north": max_lat / 1e7,
        "tile_type": TILE_TYPES.get(tile_type, f"type {tile_type}"),
        "tiles": addressed,
        "size_mb": path.stat().st_size / 1_048_576,
    }


def covers(info: dict, lat: float, lon: float) -> bool:
    return (info["south"] <= lat <= info["north"]
            and info["west"] <= lon <= info["east"])


def report(path: Path) -> bool:
    print(f"\n{path.name}")
    try:
        info = read_header(path)
    except ValueError as exc:
        print(f"  PROBLEM  {exc}")
        return False

    width_km = (info["east"] - info["west"]) * 111 * 0.86   # rough, mid-latitude
    height_km = (info["north"] - info["south"]) * 111

    print(f"  size          : {info['size_mb']:.1f} MB")
    print(f"  contains      : {info['tile_type']}, {info['tiles']:,} tiles")
    print(f"  covers        : {abs(width_km):.0f} km x {abs(height_km):.0f} km")
    print(f"  bounding box  : {info['south']:.4f},{info['west']:.4f} "
          f"to {info['north']:.4f},{info['east']:.4f}")
    print(f"  zoom range    : {info['min_zoom']}–{info['max_zoom']} "
          f"({describe_zoom(info['min_zoom'])} down to {describe_zoom(info['max_zoom'])})")

    ok = True
    if info["max_zoom"] < 14:
        print("  WARNING       : maximum zoom is below 14, so individual streets will")
        print("                  not be drawn. Re-download with a higher maximum zoom.")
        ok = False
    if info["tile_type"] != "vector (MVT)":
        print("  WARNING       : this is not vector data; the dashboard expects vector.")
        ok = False
    return ok


def main() -> None:
    args = sys.argv[1:]
    if args:
        paths = [Path(a) for a in args]
    else:
        if not BASEMAP_DIR.exists():
            raise SystemExit(
                f"No offline maps installed.\n"
                f"Put a .pmtiles file in {BASEMAP_DIR}\n"
                f"See docs/offline-maps.md for how to get one.")
        paths = sorted(BASEMAP_DIR.glob("*.pmtiles"))
        if not paths:
            raise SystemExit(
                f"No .pmtiles files in {BASEMAP_DIR}\n"
                f"See docs/offline-maps.md for how to get one.")

    all_ok = True
    for path in paths:
        if not path.exists():
            print(f"\n{path}\n  PROBLEM  file not found")
            all_ok = False
            continue
        all_ok &= report(path)

    print("\nTo check a specific place is inside the map — say your venue — pass its")
    print("coordinates:  python3 tools/check_basemap.py --at LAT LON")
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    if "--at" in sys.argv:
        i = sys.argv.index("--at")
        try:
            lat, lon = float(sys.argv[i + 1]), float(sys.argv[i + 2])
        except (IndexError, ValueError):
            raise SystemExit("Usage: python3 tools/check_basemap.py --at LAT LON")
        found = False
        for p in sorted(BASEMAP_DIR.glob("*.pmtiles")):
            try:
                info = read_header(p)
            except ValueError:
                continue
            inside = covers(info, lat, lon)
            found |= inside
            print(f"  {p.name}: {'COVERS' if inside else 'does not cover'} {lat}, {lon}")
        raise SystemExit(0 if found else 1)
    main()
