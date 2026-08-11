# Offline maps

Put `.pmtiles` files here to let the dashboard draw maps without reaching the
internet for tiles.

The files themselves are not in the repository — they are large and specific to
wherever a course is being run. See [`docs/offline-maps.md`](../../docs/offline-maps.md)
for how to obtain one, and run `python3 tools/check_basemap.py` afterwards to
confirm it covers the area you need.

Anything you drop here is ignored by git.
