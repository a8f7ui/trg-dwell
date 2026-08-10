"""
Configuration for the What Your Phone Knows backend.

Every value that affects privacy is here, in one place, with a plain-language
comment. That is deliberate: a reviewer, an instructor or a suspicious
participant should be able to read this single file and understand what the
system does and does not do.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

# SQLite: a single file. No database server to run, and wiping the course data
# at the end is a matter of deleting rows (or the file).
DB_PATH = Path(os.getenv("WYPK_DB", BASE_DIR / "data" / "local" / "course.db"))

# --------------------------------------------------------------------------
# Privacy settings
# --------------------------------------------------------------------------

# k-anonymity threshold for the whole-course aggregate map.
#
# A map hexagon is only drawn if at least this many DIFFERENT participants were
# seen inside it. If four people visited a hexagon and the threshold is five,
# that hexagon is hidden entirely. This stops the "aggregate" view from
# quietly identifying an individual — if only one person ever went somewhere,
# showing that place on an aggregate map tells you exactly where that one
# person was.
K_ANONYMITY_THRESHOLD = int(os.getenv("WYPK_K", "5"))

# Size of the aggregate map hexagons (H3 resolution).
# 9 is roughly a 200 m hexagon — small enough to show real patterns, large
# enough that a hexagon is not a single building.
H3_RESOLUTION = int(os.getenv("WYPK_H3_RES", "9"))

# How long participant data is kept. The course runs, then everything goes.
# This is a backstop; instructors also have an explicit "wipe everything"
# control, which is the intended way to tear down.
RETENTION_DAYS = int(os.getenv("WYPK_RETENTION_DAYS", "14"))

# The app never stores a participant's name, email or phone number. This
# constant exists to be grepped for by anyone checking that claim.
STORES_DIRECT_IDENTIFIERS = False

# --------------------------------------------------------------------------
# Stop detection
# --------------------------------------------------------------------------
#
# Adapted for sparse data. Because the app only collects while it is open on
# screen, we never see a full continuous day — we see short windows. So these
# thresholds are deliberately more forgiving than a background tracker's would
# be, and every dwell time we report is explicitly labelled as *observed*
# dwell, which is a floor on the real figure, not an estimate of it.

# Points staying within this many metres of each other count as "not moving".
# Roughly matches phone GPS accuracy in a built-up area.
STOP_ROAM_RADIUS_M = float(os.getenv("WYPK_STOP_RADIUS", "60"))

# A stationary run must last at least this long to count as a stop.
STOP_MIN_DWELL_S = float(os.getenv("WYPK_STOP_MIN_DWELL", "90"))

# If two consecutive points are further apart in time than this, they are not
# treated as part of the same stop — the app was probably closed in between,
# and we must not invent a dwell across a gap we did not observe.
STOP_MAX_GAP_S = float(os.getenv("WYPK_STOP_MAX_GAP", "600"))

# Stops closer together than this across the week are treated as the same place.
# Kept tight: in a dense city centre a generous radius quietly merges the cafe,
# the shop next door and the office above them into one invented "place".
PLACE_CLUSTER_RADIUS_M = float(os.getenv("WYPK_PLACE_RADIUS", "50"))

# A stop is matched to a nearby place of interest within this distance. Beyond
# it we say we don't know, rather than guessing. Phone GPS in a built-up area is
# good to roughly 10-25 m, so this allows for that error without reaching so far
# that it starts picking up whatever happens to be across the street.
POI_MATCH_RADIUS_M = float(os.getenv("WYPK_POI_RADIUS", "45"))

# --------------------------------------------------------------------------
# Instructor dashboard
# --------------------------------------------------------------------------

# Secret used to sign login sessions. MUST be set to a random value in any real
# deployment; the fallback exists only so the local demo runs out of the box.
SECRET_KEY = os.getenv("WYPK_SECRET_KEY", "dev-only-not-for-real-use")

# A participant counts as "currently visible" on the live map if we have heard
# from them within this many seconds.
LIVE_WINDOW_S = int(os.getenv("WYPK_LIVE_WINDOW", "300"))
