#!/usr/bin/env python3
"""
Build an area-context file from public RSS feeds.

    python3 tools/fetch_area_context.py --feed https://example.org/local/rss \
        --days 2026-09-14:2026-09-18 --out data/context/milwaukee.json

Reads public news feeds and writes dated items in the format the backend loads.
Items arrive without coordinates, so they are treated as city-wide; add lat/lon
by hand for the handful that matter — a street festival, a protest, a stadium
event — since those are the ones that actually explain a stop.

This fetches feeds about a PLACE. It does not search for anything about a
person, and it must not be adapted to. See docs/environment-layers.md.

Run it before the course. The server never fetches during one, so no participant
location is ever sent anywhere to look something up.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree


def parse_feed(url: str) -> list[dict]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "dwell-privacy-lab/1.0 (course teaching tool)"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            root = ElementTree.fromstring(resp.read())
    except (urllib.error.URLError, ElementTree.ParseError) as exc:
        print(f"  could not read {url}: {exc}")
        return []

    items = []
    # RSS <item> and Atom <entry> both handled.
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue
        get = lambda n: next(
            (c.text for c in node if c.tag.rsplit("}", 1)[-1] == n and c.text), "")
        title = (get("title") or "").strip()
        when = (get("pubDate") or get("published") or get("updated") or "").strip()
        if not title or not when:
            continue
        date = _to_date(when)
        if not date:
            continue
        items.append({
            "title": title, "date": date, "kind": "news",
            "source": url, "url": (get("link") or "").strip(),
        })
    return items


def _to_date(value: str) -> str | None:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", value)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--feed", action="append", default=[], help="RSS/Atom URL; repeatable")
    ap.add_argument("--days", help="Keep only this range, as YYYY-MM-DD:YYYY-MM-DD")
    ap.add_argument("--out", default="data/context/area-context.json")
    args = ap.parse_args()

    if not args.feed:
        raise SystemExit("Give at least one --feed. See --help.")

    items: list[dict] = []
    for url in args.feed:
        print(f"Reading {url} ...")
        items += parse_feed(url)

    if args.days and ":" in args.days:
        lo, hi = args.days.split(":", 1)
        items = [i for i in items if lo <= i["date"] <= hi]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, indent=2) + "\n")
    print(f"\nWrote {len(items)} items to {out}")
    print("Add lat/lon by hand to the few that would explain a stop — a festival,")
    print("a protest, a stadium event. The rest stay city-wide, which is fine.")


if __name__ == "__main__":
    main()
