"""
Configuration for the Dwell: Privacy Lab backend.

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
# Settings written by the setup wizard
# --------------------------------------------------------------------------
#
# The wizard writes one small file. Nothing else reads it, nobody edits it by
# hand, and its existence is what lets a non-technical person configure this
# without ever meeting an environment variable.
#
# Precedence is environment variable, then this file, then the built-in
# default. Hosting platforms that prefer environment variables therefore keep
# working unchanged, and override the file when both are present.

_SETTINGS_PATH = Path(
    os.getenv("DWELL_SETTINGS",
              BASE_DIR / "data" / "local" / "course.json"))


def _load_settings() -> dict:
    try:
        import json
        return json.loads(_SETTINGS_PATH.read_text())
    except (OSError, ValueError):
        return {}


SETTINGS = _load_settings()


def setting(name: str, default: str = "") -> str:
    """An environment variable, or what setup wrote, or the default."""
    from_env = os.getenv(name)
    if from_env:
        return from_env
    value = SETTINGS.get(name)
    return str(value) if value not in (None, "") else default


SETUP_COMPLETE = bool(SETTINGS.get("setup_complete"))
COURSE_NAME = SETTINGS.get("course_name", "")


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

# SQLite: a single file. No database server to run, and wiping the course data
# at the end is a matter of deleting rows (or the file).
DB_PATH = Path(setting("DWELL_DB") or (BASE_DIR / "data" / "local" / "course.db"))

# --------------------------------------------------------------------------
# Privacy settings
# --------------------------------------------------------------------------

# k-anonymity threshold for the whole-course aggregate map.
#
# A map cell is only drawn if at least this many DIFFERENT participants were
# seen inside it. If four people visited a cell and the threshold is five,
# that cell is hidden entirely. This stops the "aggregate" view from
# quietly identifying an individual — if only one person ever went somewhere,
# showing that place on an aggregate map tells you exactly where that one
# person was.
K_ANONYMITY_THRESHOLD = int(os.getenv("DWELL_K", "5"))

# Size of the aggregate map cells. Kept on the old 8/9/10 scale so the
# dashboard's size selector is unchanged.
# 9 is roughly a 200 m cell — small enough to show real patterns, large
# enough that a cell is not a single building.
H3_RESOLUTION = int(os.getenv("DWELL_H3_RES", "9"))

# How long participant data is kept. The course runs, then everything goes.
# This is a backstop; instructors also have an explicit "wipe everything"
# control, which is the intended way to tear down.
RETENTION_DAYS = int(os.getenv("DWELL_RETENTION_DAYS", "14"))

# The app never stores a participant's name, email or phone number. This
# constant exists to be grepped for by anyone checking that claim.
STORES_DIRECT_IDENTIFIERS = False

# --------------------------------------------------------------------------
# Stop detection
# --------------------------------------------------------------------------
#
# The app collects in the background, but a phone still does not report
# continuously: both platforms throttle location heavily when somebody is
# sitting still, and suspend background apps from time to time. So these
# thresholds stay forgiving, and every dwell time we report is explicitly
# labelled as *observed* dwell — a floor on the real figure, not an estimate
# of it.

# Points staying within this many metres of each other count as "not moving".
# Roughly matches phone GPS accuracy in a built-up area.
STOP_ROAM_RADIUS_M = float(os.getenv("DWELL_STOP_RADIUS", "60"))

# A stationary run must last at least this long to count as a stop.
STOP_MIN_DWELL_S = float(os.getenv("DWELL_STOP_MIN_DWELL", "90"))

# If two consecutive points are further apart in time than this, they are not
# treated as part of the same stop, and we do not invent a dwell across the gap.
#
# Set to 30 minutes because that is how background location actually behaves:
# when somebody sits still, both platforms throttle reporting hard to save
# battery, so quarter-hour gaps between points are normal and do NOT mean the
# person went anywhere. Two points 20 m apart either side of a 15-minute silence
# are good evidence of staying put. Beyond half an hour we stop assuming.
STOP_MAX_GAP_S = float(os.getenv("DWELL_STOP_MAX_GAP", "1800"))

# Stops closer together than this across the week are treated as the same place.
# Kept tight: in a dense city centre a generous radius quietly merges the cafe,
# the shop next door and the office above them into one invented "place".
PLACE_CLUSTER_RADIUS_M = float(os.getenv("DWELL_PLACE_RADIUS", "50"))

# A stop is matched to a nearby place of interest within this distance. Beyond
# it we say we don't know, rather than guessing. Phone GPS in a built-up area is
# good to roughly 10-25 m, so this allows for that error without reaching so far
# that it starts picking up whatever happens to be across the street.
POI_MATCH_RADIUS_M = float(os.getenv("DWELL_POI_RADIUS", "45"))

# --------------------------------------------------------------------------
# Instructor dashboard
# --------------------------------------------------------------------------

# The public address this server is reachable at, e.g.
# "https://yourname.pythonanywhere.com". Used to decide whether login cookies
# should be marked HTTPS-only. Leave unset for local development.
PUBLIC_URL = setting("DWELL_PUBLIC_URL")

# Login cookies are marked "secure" — meaning the browser will only ever send
# them over HTTPS — as soon as this server knows it is being served over HTTPS.
# Setting this on a plain-HTTP local machine would break logging in, hence the
# check rather than a hard-coded True.
SESSION_COOKIE_SECURE = PUBLIC_URL.startswith("https://")


def get_secret_key() -> str:
    """
    The key used to sign instructor login sessions.

    Anybody who knows this value can forge a login and read participant
    movement, so it must be random and it must be secret.

    Rather than ask a non-technical person to generate and configure one — a
    step that is easy to skip, and silently dangerous when skipped — this
    generates a random key on first run and stores it beside the database with
    owner-only permissions. Setting DWELL_SECRET_KEY overrides it, which is what
    you want on a host with a proper secrets mechanism.
    """
    from_env = setting("DWELL_SECRET_KEY")
    if from_env:
        return from_env

    key_path = Path(DB_PATH).parent / "secret_key"
    if key_path.exists():
        return key_path.read_text().strip()

    import secrets

    key_path.parent.mkdir(parents=True, exist_ok=True)

    # Created with O_EXCL so that exactly one process can win.
    #
    # The obvious version — check whether the file exists, then write it — is a
    # race, and it fires precisely where it hurts: several web-server workers
    # starting at the same moment each find no key and each write a different
    # one. Measured before this fix, six simultaneous workers produced four
    # different keys, which logs instructors out at random as their requests
    # land on different workers.
    candidate = secrets.token_urlsafe(48)
    try:
        fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        # Another worker got there first. Its key is the real one.
        return key_path.read_text().strip()
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(candidate)
    except OSError:
        os.close(fd)
        raise
    return candidate


SECRET_KEY = get_secret_key()

# A participant counts as "currently visible" on the live map if we have heard
# from them within this many seconds.
LIVE_WINDOW_S = int(os.getenv("DWELL_LIVE_WINDOW", "300"))
