# Area context

Public, dated, located items — local news, event listings, transit disruptions —
that give a movement trail its meaning. A cluster of stationary points means one
thing if there was a concert there and another if there was a protest.

Drop `.json` files here. Format:

```json
[
  {
    "title": "Street festival closes Water Street",
    "date": "2026-09-16",
    "time": "18:00",
    "lat": 43.0421, "lon": -87.9089,
    "place": "Water Street",
    "kind": "event",
    "source": "Milwaukee Journal Sentinel",
    "url": "https://example.org/story"
  }
]
```

`lat`/`lon` are optional — items without them are treated as city-wide for that
day.

Generate a starting set with:

```bash
python3 tools/fetch_area_context.py --city "Milwaukee, WI"
```

**This is context about places and events, never about people.** Nothing here
searches for posts by or about participants, and nothing matches anybody to a
social media account. See `docs/environment-layers.md` for why that line is
drawn where it is.
