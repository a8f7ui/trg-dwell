# Offline maps

How to make the dashboard draw maps without depending on an internet map
service. Takes about 15 minutes, costs nothing.

**Optional, and it is not how you get street maps.** Read the next section
before deciding whether you need this at all.

---

## You already have street maps

**Satellite** and **Street map** are both built into the dashboard. They sit in
the layer switcher at the top right of the map, which is open by default, and
you flip between them with one click. Nothing to install, nothing to download,
no account, no API key. That is true of a fresh clone on a laptop and of a
hosted server alike.

Both come from Esri, which serves them free with attribution. Place-name labels
are drawn over the satellite imagery and switched off automatically over the
street map, which draws its own.

Use whichever suits the moment. Satellite shows what a place looks like; the
street map shows what it *is*. A participant's evening reads very differently
over a photograph of rooftops than over named roads and labelled buildings, and
being able to switch mid-explanation is worth more than picking one.

---

## What *this page* is for, and what it will not fix

This page is about **independence from the internet**, not about streets.

Both built-in basemaps are fetched from Esri's servers. If a venue's wifi is
slow, filtered, or blocks unfamiliar domains, the map area goes blank — awkward,
since the map is the lesson.

An **offline map** is a single file containing an entire area's streets. You put
it on the server, and the dashboard draws from it directly — it appears in the
same layer switcher as a third choice, *Street map, offline*, alongside the two
that are always there.

It is not in the repository, because it is large and specific to wherever a
course is being run. That is the only reason. Everything needed to *use* one is
already built in and vendored, including the renderer.

**Be clear about what this does and does not solve:**

- **It helps** when the connection is slow, congested, or filters unfamiliar
  domains — a common state of affairs on conference and campus wifi.
- **It does not help** if there is no connection at all, because the dashboard
  itself is loaded from your server. If the venue has no internet, you cannot
  reach the server either.
- **It does fully solve both** if you run the server on the instructor's laptop
  on the local network instead of hosting it. In that setup, with an offline map
  installed, nothing needs the internet at all.

It is **street maps, not satellite imagery.** There is no free, redistributable
source of satellite imagery at building resolution — Esri's terms do not permit
caching their tiles, and open satellite data such as Sentinel-2 is far too
coarse to show a building. So the offline option shows streets, blocks and place
names. For teaching a movement trail, that is usually clearer than imagery
anyway.

Unlike the two online basemaps, the offline map is **drawn in the browser from
vector data** rather than fetched as pictures. That means it follows the
dashboard's appearance: pale under the Field skin, dark under Console, switching
with everything else.

---

## Step 1 — Download a map of your area

1. Go to <https://app.protomaps.com/downloads/small_map>.
2. Drag the box over the area your course covers. **Include everything**: the
   venue, the hotels people are staying in, the restaurants they will walk to.
   A box roughly 20 km across is plenty for a city-centre course.
3. Set the maximum zoom to **15**. Lower and individual streets will not be
   drawn; higher and the file becomes much larger for little gain.
4. Download. You get a single `.pmtiles` file.

Protomaps builds these from OpenStreetMap and publishes them under an open
licence, so this is a legitimate download rather than scraping somebody's tile
server.

**Expect roughly 20–150 MB** for a city-sized area at zoom 15.

---

## Step 2 — Put it on the server

Copy the file into `data/basemap/` in the project folder.

On PythonAnywhere, use the **Files** tab to upload it into
`/home/YOURNAME/trg-dwell/data/basemap/`.

> **Watch the disk.** The free PythonAnywhere plan gives you 512 MB in total,
> shared with the code and the course database. A 150 MB map is comfortable; a
> 400 MB one is not. If the file is large, tighten the box rather than the zoom.

---

## Step 3 — Check it covers what you need

```bash
python3 tools/check_basemap.py
```

It reads the file's own header and tells you the area and zoom range it holds:

```
milwaukee.pmtiles
  size          : 84.2 MB
  contains      : vector (MVT), 184,320 tiles
  covers        : 21 km x 20 km
  bounding box  : 42.9500,-88.0200 to 43.1300,-87.8300
  zoom range    : 0–15 (the whole world down to streets and buildings)
```

To confirm a specific place is inside it — your venue, say — pass its
coordinates:

```bash
python3 tools/check_basemap.py --at 43.0389 -87.9065
```

This is worth doing. Drawing the box slightly wrong is easy, and the failure
shows up as a blank corner of the map during a session rather than as an error.

---

## Step 4 — Use it

Reload the dashboard. The layer control in the top-right corner now offers
**Offline map** alongside Satellite and Street map. Pick it.

Nothing else changes: tracks, stops, hexagons and the replay clock all work
exactly the same.

If the option does not appear, the server did not find a `.pmtiles` file in
`data/basemap/`. Check the filename ends in `.pmtiles` and that it is in that
folder.

---

## Running entirely offline

If you want a course that needs no internet at all — a venue with no usable
wifi, or a deliberately air-gapped exercise — run the server on the instructor's
laptop rather than hosting it:

1. Install an offline map as above.
2. Start the server so the local network can reach it:
   `.venv/bin/python -m backend.app --host 0.0.0.0` (or run gunicorn bound to
   `0.0.0.0`).
3. Point the phones at the laptop's address on the local network, e.g.
   `http://192.168.1.42:5000`, in the app's Settings screen.

Two honest caveats before you do this:

- That address is plain `http://`, not `https://`, so participant tokens cross
  the local wifi unencrypted. On a private network for one week that is a
  considered trade rather than a mistake, but it *is* a trade, and it should be
  a deliberate decision rather than an accident.
- Everyone must be on the same wifi for the whole course, including in the
  evenings — which usually defeats the purpose, since the interesting data comes
  from where people go *after* the session ends.

For most courses, hosting the server publicly and installing an offline map for
the tiles is the better combination.
