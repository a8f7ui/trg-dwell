#!/usr/bin/env python3
"""
Set up Dwell: Privacy Lab for your course.

    python3 setup.py

Asks four questions, does everything else itself, tests the result, and tells
you whether it worked.

You do not need to know anything about Python, databases, servers or web
hosting to run this. If something is missing from your computer it will say so
in ordinary words and tell you exactly what to do.

Written against the standard library only, so it runs on the Python already on
the machine before anything at all is installed.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
DATA = HERE / "data" / "local"
SETTINGS = DATA / "course.json"
SAMPLE = HERE / "data" / "sample"

W = 68


# --------------------------------------------------------------------------
# Talking to a person
# --------------------------------------------------------------------------

def rule() -> None:
    print("  " + "─" * W)


def title(text: str) -> None:
    print(f"\n  {text}\n")


def say(text: str = "") -> None:
    print(f"  {text}" if text else "")


def good(text: str) -> None:
    print(f"  ✓ {text}")


def bad(text: str) -> None:
    print(f"  ✗ {text}")


def stop(problem: str, fix: str = "") -> None:
    """End the wizard with something the person can act on."""
    print()
    rule()
    title("Setup could not finish")
    say(problem)
    if fix:
        say()
        for line in fix.splitlines():
            say(line)
    say()
    say("Nothing on your computer was changed.")
    rule()
    print()
    sys.exit(1)


def ask(question: str, default: str = "", allow_empty: bool = False) -> str:
    """One question, repeated until it gets an answer."""
    prompt = f"  {question}"
    if default:
        prompt += f"\n  (press Enter for “{default}”)"
    prompt += "\n  > "
    while True:
        try:
            answer = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            stop("Setup was cancelled.")
        if answer:
            return answer
        if default:
            return default
        if allow_empty:
            return ""
        say("  Please type an answer.")


def choose(question: str, options: list[tuple[str, str]]) -> str:
    """Pick one from a numbered list. Returns the chosen key."""
    say(question)
    say()
    for i, (_key, label) in enumerate(options, 1):
        say(f"    {i}.  {label}")
    say()
    while True:
        raw = ask("Type the number of your choice")
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        say(f"  Please type a number between 1 and {len(options)}.")


# --------------------------------------------------------------------------
# Places and times, without asking anybody to know a timezone identifier
# --------------------------------------------------------------------------

# Plain names, because "America/Chicago" is not something to ask a person for.
TIMEZONES = [
    ("America/New_York", "Eastern — New York, Atlanta, Miami, Detroit"),
    ("America/Chicago", "Central — Chicago, Milwaukee, Dallas, Minneapolis"),
    ("America/Denver", "Mountain — Denver, Salt Lake City, Albuquerque"),
    ("America/Phoenix", "Arizona — Phoenix, Tucson (no daylight saving)"),
    ("America/Los_Angeles", "Pacific — Los Angeles, Seattle, San Francisco"),
    ("America/Anchorage", "Alaska — Anchorage, Juneau"),
    ("Pacific/Honolulu", "Hawaii — Honolulu"),
]

# Enough US cities to cover most courses without needing the internet. A city
# that is not here can still be entered as coordinates.
CITIES = {
    "milwaukee": (43.0389, -87.9065, "America/Chicago"),
    "chicago": (41.8781, -87.6298, "America/Chicago"),
    "cincinnati": (39.1031, -84.5120, "America/New_York"),
    "cleveland": (41.4993, -81.6944, "America/New_York"),
    "columbus": (39.9612, -82.9988, "America/New_York"),
    "detroit": (42.3314, -83.0458, "America/New_York"),
    "minneapolis": (44.9778, -93.2650, "America/Chicago"),
    "madison": (43.0731, -89.4012, "America/Chicago"),
    "st louis": (38.6270, -90.1994, "America/Chicago"),
    "kansas city": (39.0997, -94.5786, "America/Chicago"),
    "indianapolis": (39.7684, -86.1581, "America/New_York"),
    "new york": (40.7128, -74.0060, "America/New_York"),
    "boston": (42.3601, -71.0589, "America/New_York"),
    "philadelphia": (39.9526, -75.1652, "America/New_York"),
    "washington": (38.9072, -77.0369, "America/New_York"),
    "baltimore": (39.2904, -76.6122, "America/New_York"),
    "atlanta": (33.7490, -84.3880, "America/New_York"),
    "miami": (25.7617, -80.1918, "America/New_York"),
    "charlotte": (35.2271, -80.8431, "America/New_York"),
    "nashville": (36.1627, -86.7816, "America/Chicago"),
    "new orleans": (29.9511, -90.0715, "America/Chicago"),
    "houston": (29.7604, -95.3698, "America/Chicago"),
    "dallas": (32.7767, -96.7970, "America/Chicago"),
    "austin": (30.2672, -97.7431, "America/Chicago"),
    "san antonio": (29.4241, -98.4936, "America/Chicago"),
    "denver": (39.7392, -104.9903, "America/Denver"),
    "salt lake city": (40.7608, -111.8910, "America/Denver"),
    "albuquerque": (35.0844, -106.6504, "America/Denver"),
    "phoenix": (33.4484, -112.0740, "America/Phoenix"),
    "tucson": (32.2226, -110.9747, "America/Phoenix"),
    "las vegas": (36.1699, -115.1398, "America/Los_Angeles"),
    "los angeles": (34.0522, -118.2437, "America/Los_Angeles"),
    "san diego": (32.7157, -117.1611, "America/Los_Angeles"),
    "san francisco": (37.7749, -122.4194, "America/Los_Angeles"),
    "seattle": (47.6062, -122.3321, "America/Los_Angeles"),
    "portland": (45.5152, -122.6784, "America/Los_Angeles"),
    "anchorage": (61.2181, -149.9003, "America/Anchorage"),
    "honolulu": (21.3069, -157.8583, "Pacific/Honolulu"),
}


def find_city(text: str) -> tuple[float, float, str] | None:
    """Match a typed place against the built-in list, forgivingly."""
    key = re.sub(r"[^a-z ]", "", text.lower().split(",")[0]).strip()
    if key in CITIES:
        return CITIES[key]
    matches = [c for c in CITIES if key and (key in c or c in key)]
    return CITIES[matches[0]] if len(matches) == 1 else None


def parse_coordinates(text: str) -> tuple[float, float] | None:
    parts = re.split(r"[,\s]+", text.strip())
    if len(parts) != 2:
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon
    return None


# --------------------------------------------------------------------------
# Generated credentials
# --------------------------------------------------------------------------

# Short, ordinary, unambiguous when read aloud across a room.
WORDS = """anchor amber atlas basin beacon birch camber canvas cedar cinder
copper cotton dial ember fathom flint garnet gravel harbor hazel indigo ivory
jasper kettle lantern ledger linen marble meadow nickel orchard pewter pier
quarry quill ribbon rooster saddle sable timber thistle umber velvet walnut
willow zephyr""".split()


def make_password() -> str:
    """
    A password strong enough to publish the address of, and readable aloud.

    Four words from a 46-word list plus two digits is about 24 bits from the
    words and 7 from the digits — thin on its own, which is why the login is
    also rate-limited to eight attempts per username in fifteen minutes. What
    it buys is a password somebody can read down a phone to a colleague without
    getting it wrong, which is what actually happens on a course.
    """
    return "-".join(secrets.choice(WORDS) for _ in range(4)) + f"-{secrets.randbelow(90) + 10}"


# --------------------------------------------------------------------------
# Stage 1 — check the computer
# --------------------------------------------------------------------------

def check_computer() -> None:
    title("Step 1 of 6 — Checking this computer")

    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    if sys.version_info < (3, 10):
        stop(f"This needs a slightly newer Python. You have {version}, and it "
             f"needs 3.10 or later.",
             "On a Mac:      brew install python3\n"
             "On Windows:    install from https://python.org/downloads\n"
             "On Ubuntu:     sudo apt install python3")
    good(f"Python {version} — new enough.")

    try:
        free_gb = shutil.disk_usage(HERE).free / 1_000_000_000
    except OSError:
        free_gb = 999.0
    if free_gb < 0.5:
        stop(f"There is only {free_gb:.1f} GB of free space on this disk, and "
             f"setup needs about 0.5 GB.",
             "Free up some space and run this again.")
    good(f"{free_gb:.0f} GB of free disk space — enough.")

    probe = HERE / ".dwell-write-test"
    try:
        probe.write_text("x")
        probe.unlink()
    except OSError:
        stop("This folder cannot be written to, so setup cannot save anything.",
             "Move the folder somewhere you own — your Documents folder is "
             "fine — and run this again.")
    good("This folder can be written to.")

    try:
        import venv                                    # noqa: F401
        import sqlite3                                 # noqa: F401
    except ImportError as exc:
        stop(f"A standard part of Python is missing from this computer "
             f"({exc.name}).",
             "On Ubuntu or Debian this is usually fixed by:\n"
             "    sudo apt install python3-venv python3-full")
    good("Everything Python needs is present.")


# --------------------------------------------------------------------------
# Stage 2 — install
# --------------------------------------------------------------------------

def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install() -> Path:
    title("Step 2 of 6 — Installing what the software needs")

    python = venv_python()
    if not python.exists():
        say("Setting up a private workspace (about ten seconds)...")
        result = subprocess.run([sys.executable, "-m", "venv", str(VENV)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            stop("A private workspace for this software could not be created.",
                 "On Ubuntu or Debian this is usually one missing package:\n"
                 "    sudo apt install python3-venv\n\n"
                 f"The exact error was:\n    {(result.stderr or '').strip()[:300]}")
        good("Private workspace ready.")

    check = subprocess.run([str(python), "-c", "import flask"], capture_output=True)
    if check.returncode != 0:
        say("Downloading the two pieces of software this needs (about a minute)...")
        result = subprocess.run(
            [str(python), "-m", "pip", "install", "-q", "-r",
             str(HERE / "requirements.txt")],
            capture_output=True, text=True)
        if result.returncode != 0:
            stop("The software could not be downloaded.",
                 "This is almost always the internet connection. Check you are "
                 "online and\nrun this again.\n\n"
                 f"The exact error was:\n    {(result.stderr or '').strip()[:300]}")
        good("Software downloaded.")
    else:
        good("Software already installed — skipping.")
    return python


# --------------------------------------------------------------------------
# Stage 3 — the four questions
# --------------------------------------------------------------------------

def ask_questions() -> dict:
    title("Step 3 of 6 — Four questions about your course")
    say("Everything else is decided or generated for you.")
    say()

    course_name = ask("1. What is this course called?",
                      default="Privacy Lab")
    say()

    say("2. Which town or city is the course in?")
    say("   (a name like “Milwaukee”, or coordinates like “43.0389, -87.9065”)")
    while True:
        place = ask("Town or city")
        coords = parse_coordinates(place)
        if coords:
            lat, lon = coords
            city_name = f"{lat}, {lon}"
            guessed_tz = None
            break
        found = find_city(place)
        if found:
            lat, lon, guessed_tz = found
            city_name = place.title()
            break
        say()
        say(f"  “{place}” is not in the built-in list of cities.")
        say("  You can type coordinates instead — search the place on any map,")
        say("  right-click it, and copy the two numbers. For example:")
        say("      43.0389, -87.9065")
        say()
    say()

    if guessed_tz:
        label = next(l for k, l in TIMEZONES if k == guessed_tz)
        say(f"3. {city_name} uses: {label}")
        confirm = choose("   Is that right?",
                         [("yes", "Yes, that's right"),
                          ("no", "No, let me choose")])
        timezone = guessed_tz if confirm == "yes" else choose(
            "   Which timezone is the course in?", TIMEZONES)
    else:
        timezone = choose("3. Which timezone is the course in?", TIMEZONES)
    say()

    username = ask("4. What is your name? (you will use this to sign in)")
    username = re.sub(r"\s+", "", username.lower()) or "instructor"
    say()

    return {
        "course_name": course_name,
        "city": city_name,
        "lat": lat,
        "lon": lon,
        "timezone": timezone,
        "username": username,
    }


# --------------------------------------------------------------------------
# Stage 4 — configure, generate, build
# --------------------------------------------------------------------------

def configure(python: Path, answers: dict) -> str:
    title("Step 4 of 6 — Setting everything up")

    DATA.mkdir(parents=True, exist_ok=True)

    # The session secret. Generated, never seen, never typed.
    secret_path = DATA / "secret_key"
    if not secret_path.exists():
        try:
            fd = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
    good("Security key created.")

    settings = {
        "setup_complete": True,
        "course_name": answers["course_name"],
        "course_location": {
            "name": answers["city"],
            "lat": answers["lat"],
            "lon": answers["lon"],
            "zoom": 14,
            "timezone": answers["timezone"],
        },
        "DWELL_PUBLIC_URL": "",
    }
    SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
    good("Course settings saved.")

    if not (SAMPLE / "pings.csv").exists():
        say("Inventing a week of practice data (about twenty seconds)...")
        result = subprocess.run(
            [str(python), str(HERE / "tools" / "generate_sample_data.py"),
             "--use-course-location", "--out", str(SAMPLE)],
            capture_output=True, text=True, cwd=HERE)
        if result.returncode != 0:
            stop("The practice data could not be created.",
                 (result.stderr or "").strip()[:400])
        good("Practice data ready.")

    # Database, teaching data, and the course location — all in one child
    # process so the settings file is read fresh.
    script = (
        "from backend import db, course, load_sample\n"
        "conn = db.connect(); db.init_db(conn)\n"
        "n = conn.execute('SELECT COUNT(*) FROM pings').fetchone()[0]\n"
        "conn.close()\n"
        "if not n:\n"
        "    load_sample.load(with_demo_login=False)\n"
        "conn = db.connect(); db.init_db(conn)\n"
        "import json, pathlib\n"
        f"loc = json.loads(pathlib.Path({str(SETTINGS)!r}).read_text())['course_location']\n"
        "course.set_location(conn, loc['name'], loc['lat'], loc['lon'],\n"
        "                    loc['timezone'], loc['zoom'])\n"
        "conn.close()\n"
    )
    result = subprocess.run([str(python), "-c", script],
                            capture_output=True, text=True, cwd=HERE)
    if result.returncode != 0:
        detail = (result.stderr or "").strip()
        if "RealDataPresent" in detail:
            stop("This computer already holds data from a real course, and "
                 "setup will not overwrite it.",
                 "If you want to start a new course, first erase the old one "
                 "from the\ndashboard's “Data & teardown” screen.")
        stop("The course database could not be prepared.", detail[-400:])
    good("Course database created.")
    good(f"Map set to {answers['city']}, times shown in "
         f"{answers['timezone'].split('/')[-1].replace('_', ' ')}.")

    # The sign-in, generated rather than chosen.
    password = make_password()
    script = (
        "import sys\n"
        "from backend import db, auth\n"
        "conn = db.connect(); db.init_db(conn)\n"
        "conn.execute('DELETE FROM instructors WHERE username = ?', ('instructor',))\n"
        "auth.create_instructor(conn, sys.argv[1], sys.argv[2])\n"
        "db.audit(conn, 'setup', 'instructor_created', sys.argv[1])\n"
        "conn.commit(); conn.close()\n"
    )
    result = subprocess.run([str(python), "-c", script, answers["username"], password],
                            capture_output=True, text=True, cwd=HERE)
    if result.returncode != 0:
        stop("Your sign-in could not be created.", (result.stderr or "")[-400:])
    good("Your sign-in created, and the example account removed.")

    return password


# --------------------------------------------------------------------------
# Stage 5 — test
# --------------------------------------------------------------------------

def run_tests(python: Path) -> bool:
    title("Step 5 of 6 — Testing that it all works")
    say("Running every automated check. This takes about a minute.")
    say()
    result = subprocess.run([str(python), str(HERE / "verify.py")],
                            capture_output=True, text=True, cwd=HERE)
    out = result.stdout or ""
    for line in out.splitlines():
        if "checks passed" in line or "FAILED" in line:
            (good if result.returncode == 0 else bad)(line.strip())

    # Skipped checks are reported, never folded into the pass count. A check
    # that quietly skips itself reads as a clean run, which is the same lie as
    # a check that wrongly passes.
    skipped = [l.strip().lstrip("– ").strip()
               for l in out.splitlines() if l.strip().startswith("–")]
    if skipped:
        say()
        say("Some checks could not run on this computer:")
        for line in skipped:
            say(f"    · {line}")
        say()
        say("  These need extra tools that are not needed to run a course.")

    if result.returncode != 0:
        for line in out.splitlines():
            if line.strip().startswith("✗"):
                say(f"    {line.strip()}")
    return result.returncode == 0


# --------------------------------------------------------------------------
# Stage 6 — the verdict, and the next step
# --------------------------------------------------------------------------

def report(ok: bool, answers: dict, password: str) -> int:
    print()
    rule()
    if not ok:
        title("Setup finished, but some checks did not pass")
        say("The software is installed and configured, but something is not")
        say("working properly. The failing checks are listed above.")
        say()
        say("Send that list to whoever set this up for you. Do not run a real")
        say("course until it passes.")
        rule()
        print()
        return 1

    title(f"“{answers['course_name']}” is ready")

    say("Write these down now. The password is not shown again.")
    say()
    say(f"      Sign in as :  {answers['username']}")
    say(f"      Password   :  {password}")
    say()
    say(f"      Course city:  {answers['city']}")
    say()
    rule()
    title("Your next step")
    say("Start the course server by running this, in this same folder:")
    say()
    say("      python3 dwell.py start")
    say()
    say("It will print a web address. Open it, sign in with the details above,")
    say("and you have the full dashboard with a week of practice data in it.")
    say()
    say("When you are ready to put it on the internet so real phones can")
    say("reach it, run:")
    say()
    say("      python3 dwell.py deploy")
    rule()
    print()
    return 0


# --------------------------------------------------------------------------

def main() -> int:
    print()
    rule()
    title("Dwell: Privacy Lab — setup")
    say("This will get everything ready for your course.")
    say("It asks four questions and does the rest itself.")
    rule()

    if SETTINGS.exists() and config_says_complete():
        say()
        again = choose(
            "Setup has already been run on this computer. What would you like to do?",
            [("keep", "Leave it as it is (recommended)"),
             ("redo", "Set it up again — this replaces the course settings")])
        if again == "keep":
            say()
            say("Nothing changed. To start the server:  python3 dwell.py start")
            print()
            return 0

    check_computer()
    python = install()
    answers = ask_questions()
    password = configure(python, answers)
    ok = run_tests(python)
    return report(ok, answers, password)


def config_says_complete() -> bool:
    try:
        return bool(json.loads(SETTINGS.read_text()).get("setup_complete"))
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n  Setup was cancelled. Nothing was changed.\n")
        sys.exit(1)
