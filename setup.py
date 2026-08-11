#!/usr/bin/env python3
"""
Set up Dwell: Privacy Lab.

Normally started by the `./setup` script (macOS and Linux) or `setup.cmd`
(Windows), so that nobody has to know this file exists.

Seven stages, four questions, and everything else done for you. Written against
the standard library alone, so it runs on whatever Python is already on the
machine before anything at all is installed.

Nothing here ever prints a stack trace. When something goes wrong the person
gets what happened, why it matters, what to do next, and where the detailed log
is. The log has everything; the screen has only what helps.
"""

from __future__ import annotations

import getpass
import json
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
DATA = HERE / "data" / "local"
SETTINGS = DATA / "course.json"
SAMPLE = HERE / "data" / "sample"
LOG = DATA / "setup-log.txt"

STAGES = 7
W = 66


# ==========================================================================
# The log, and talking to a person
# ==========================================================================

# Values that must never be written to the log, registered as they are created.
# Belt and braces: the account command below no longer passes the password as an
# argument at all, but a log is exactly the kind of file that gets emailed
# around, so anything secret is redacted on the way in as well.
_NEVER_LOG: list[str] = []


def never_log(value: str) -> None:
    if value and len(value) >= 6:
        _NEVER_LOG.append(value)


def log(message: str) -> None:
    """Everything, in detail, for diagnostics. Never shown unless asked for."""
    for secret in _NEVER_LOG:
        message = message.replace(secret, "[redacted]")
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  {message}\n")
    except OSError:
        pass


def rule() -> None:
    print("  " + "─" * W)


def say(text: str = "") -> None:
    print(f"  {text}" if text else "")


def good(text: str) -> None:
    print(f"    ✓ {text}")
    log(f"OK: {text}")


def note(text: str) -> None:
    print(f"    · {text}")
    log(f"note: {text}")


def stage(number: int, name: str) -> None:
    print()
    print(f"  [{number}/{STAGES}] {name}")
    log(f"===== stage {number}/{STAGES}: {name}")


def fail(what: str, why: str, next_step: str, detail: str = "") -> None:
    """
    End the run with the four things a person needs, and nothing else.

    A stack trace answers a question nobody in this audience is asking. It goes
    in the log, where whoever helps them can read it.
    """
    if detail:
        log(f"FAILURE DETAIL:\n{detail}")
    print()
    rule()
    print()
    say("Setup could not finish.")
    say()
    say(f"  What went wrong:  {what}")
    say()
    say("  Why it matters:")
    for line in why.splitlines():
        say(f"    {line}")
    say()
    say("  What to do next:")
    for line in next_step.splitlines():
        say(f"    {line}")
    say()
    say("  Detailed log for whoever helps you:")
    say(f"    {LOG}")
    say()
    say("  Nothing on your computer was left half-finished.")
    print()
    rule()
    print()
    sys.exit(1)


def ask(question: str, default: str = "") -> str:
    prompt = f"\n  {question}\n"
    if default:
        prompt += f"  (press Enter for “{default}”)\n"
    prompt += "  > "
    while True:
        try:
            answer = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            fail("Setup was cancelled.",
                 "Nothing was configured, so Dwell is not ready to use.",
                 "Run the setup command again when you are ready.")
        if answer:
            return answer
        if default:
            return default
        say("  Please type an answer.")


def choose(question: str, options: list[tuple[str, str]]) -> str:
    say()
    say(question)
    say()
    for i, (_key, label) in enumerate(options, 1):
        say(f"    {i}.  {label}")
    while True:
        raw = ask("Type the number of your choice")
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        say(f"  Please type a number between 1 and {len(options)}.")


def yes_no(question: str, default_yes: bool = True) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        raw = ask(f"{question} {suffix}", "yes" if default_yes else "no").lower()
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        say("  Please answer yes or no.")


def run(cmd: list[str], stdin_text: str | None = None,
        **kw) -> subprocess.CompletedProcess:
    """Run something, log all of it, show none of it."""
    log(f"$ {' '.join(str(c) for c in cmd)}")
    if stdin_text is not None:
        log("  (a secret was supplied on standard input, not logged)")
    result = subprocess.run([str(c) for c in cmd], capture_output=True,
                            text=True, input=stdin_text, **kw)
    if result.stdout:
        log(f"  stdout: {result.stdout.strip()[:4000]}")
    if result.stderr:
        log(f"  stderr: {result.stderr.strip()[:4000]}")
    log(f"  exit: {result.returncode}")
    return result


# ==========================================================================
# Reference data
# ==========================================================================

TIMEZONES = [
    ("America/New_York", "Eastern — New York, Atlanta, Miami, Detroit"),
    ("America/Chicago", "Central — Chicago, Milwaukee, Dallas, Minneapolis"),
    ("America/Denver", "Mountain — Denver, Salt Lake City, Albuquerque"),
    ("America/Phoenix", "Arizona — Phoenix, Tucson (no daylight saving)"),
    ("America/Los_Angeles", "Pacific — Los Angeles, Seattle, San Francisco"),
    ("America/Anchorage", "Alaska — Anchorage, Juneau"),
    ("Pacific/Honolulu", "Hawaii — Honolulu"),
]

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

WORDS = """anchor amber atlas basin beacon birch camber canvas cedar cinder
copper cotton dial ember fathom flint garnet gravel harbor hazel indigo ivory
jasper kettle lantern ledger linen marble meadow nickel orchard pewter pier
quarry quill ribbon rooster saddle sable timber thistle umber velvet walnut
willow zephyr""".split()


def suggest_password() -> str:
    return "-".join(secrets.choice(WORDS) for _ in range(4)) + f"-{secrets.randbelow(90) + 10}"


def find_city(text: str):
    key = re.sub(r"[^a-z ]", "", text.lower().split(",")[0]).strip()
    if key in CITIES:
        return CITIES[key]
    matches = [c for c in CITIES if key and (key in c or c in key)]
    return CITIES[matches[0]] if len(matches) == 1 else None


def parse_coordinates(text: str):
    parts = re.split(r"[,\s]+", text.strip())
    if len(parts) != 2:
        return None
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None


# ==========================================================================
# [1/7] Checking your computer
# ==========================================================================

def describe_os() -> dict:
    system = platform.system()
    facts = {
        "system": system,
        "release": platform.release(),
        "machine": platform.machine(),
        "friendly": {"Darwin": "macOS", "Windows": "Windows",
                     "Linux": "Linux"}.get(system, system),
    }
    if system == "Darwin":
        facts["friendly"] = f"macOS {platform.mac_ver()[0] or ''}".strip()
    elif system == "Linux":
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("PRETTY_NAME="):
                    facts["friendly"] = line.split("=", 1)[1].strip('"')
                    break
        except OSError:
            pass
    elif system == "Windows":
        facts["friendly"] = f"Windows {platform.release()}"
    return facts


def package_manager(osinfo: dict) -> tuple[str, str] | None:
    """What could install missing software here, if anything."""
    if osinfo["system"] == "Darwin" and shutil.which("brew"):
        return ("brew", "Homebrew")
    if osinfo["system"] == "Linux":
        if shutil.which("apt-get"):
            return ("apt", "apt")
        if shutil.which("dnf"):
            return ("dnf", "dnf")
    if osinfo["system"] == "Windows" and shutil.which("winget"):
        return ("winget", "winget")
    return None


def python_help(osinfo: dict) -> str:
    if osinfo["system"] == "Darwin":
        return ("Install it from https://www.python.org/downloads\n"
                "Choose the big yellow “Download for macOS” button.")
    if osinfo["system"] == "Windows":
        return ("Install it from https://www.python.org/downloads\n"
                "IMPORTANT: on the first screen of the installer, tick\n"
                "“Add python.exe to PATH” before clicking Install.")
    return ("On Ubuntu or Debian:   sudo apt install python3 python3-venv\n"
            "On Fedora:             sudo dnf install python3")


def stage_check_computer() -> dict:
    stage(1, "Checking your computer")
    osinfo = describe_os()
    log(f"platform: {platform.platform()}  python: {sys.version}")
    good(f"{osinfo['friendly']} ({osinfo['machine']})")

    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if sys.version_info < (3, 10):
        fail(f"The version of Python on this computer is too old "
             f"(you have {version}).",
             "Dwell needs Python 3.10 or newer. Older versions are missing\n"
             "things it relies on, so it cannot run at all.",
             python_help(osinfo) + "\n\nThen run the setup command again.")
    good(f"Python {version}")

    try:
        free_gb = shutil.disk_usage(HERE).free / 1_000_000_000
    except OSError:
        free_gb = 999.0
    if free_gb < 0.5:
        fail(f"This disk has only {free_gb:.1f} GB free.",
             "Setup needs about half a gigabyte for the software and the\n"
             "practice data. It would run out part way through.",
             "Delete some files, empty the wastebasket, and run setup again.")
    good(f"{free_gb:.0f} GB free disk space")

    probe = HERE / ".dwell-write-test"
    try:
        probe.write_text("x")
        probe.unlink()
    except OSError as exc:
        fail("This folder cannot be written to.",
             "Setup has to save the course settings and database here, and\n"
             "it is not allowed to.",
             "Move this folder somewhere you own — your Documents folder is\n"
             "a good choice — and run setup again from there.",
             detail=str(exc))
    good("This folder can be written to")

    missing = []
    for module in ("venv", "sqlite3", "ssl"):
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        return dict(osinfo, missing_modules=missing)
    good("Python has everything it needs")
    return dict(osinfo, missing_modules=[])


# ==========================================================================
# [2/7] Installing required software
# ==========================================================================

def stage_install_prereqs(osinfo: dict) -> None:
    stage(2, "Installing required software")

    missing = osinfo.get("missing_modules", [])
    if not missing:
        note("Nothing missing — skipping.")
        return

    names = ", ".join(missing)
    pm = package_manager(osinfo)
    say()
    say(f"  Part of Python is missing from this computer: {names}")
    say("  On some Linux systems these come as a separate package.")

    if pm and pm[0] in ("apt", "dnf"):
        pkg = "python3-venv python3-full" if pm[0] == "apt" else "python3-libs"
        command = (f"sudo apt-get install -y {pkg}" if pm[0] == "apt"
                   else f"sudo dnf install -y {pkg}")
        say()
        say(f"  This can usually be fixed by running:")
        say(f"      {command}")
        say()
        say("  That needs your computer's administrator password, which is why")
        say("  setup will not run it for you without asking.")
        if yes_no("  Would you like setup to run it now?", default_yes=False):
            say()
            say("  Running it — you may be asked for your password.")
            result = subprocess.run(command.split())
            log(f"prereq install exit: {result.returncode}")
            if result.returncode == 0:
                good("Installed.")
                return
        fail(f"A required part of Python is missing ({names}).",
             "Setup cannot create the private workspace the software needs\n"
             "without it.",
             f"Run this, then run setup again:\n    {command}")

    fail(f"A required part of Python is missing ({names}).",
         "Setup cannot continue without it.",
         python_help(osinfo) + "\n\nThen run the setup command again.")


# ==========================================================================
# [3/7] Setting up Dwell
# ==========================================================================

def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def stage_setup(osinfo: dict) -> Path:
    stage(3, "Setting up Dwell")

    python = venv_python()
    if python.exists() and run([python, "-c", "import sys"]).returncode != 0:
        note("The previous setup was incomplete — starting it again.")
        shutil.rmtree(VENV, ignore_errors=True)
        python = venv_python()

    if not python.exists():
        note("Creating a private workspace (about ten seconds)...")
        result = run([sys.executable, "-m", "venv", str(VENV)])
        if result.returncode != 0:
            pm = package_manager(osinfo)
            hint = ("Run this, then run setup again:\n"
                    "    sudo apt-get install -y python3-venv"
                    if pm and pm[0] == "apt"
                    else python_help(osinfo))
            fail("A private workspace for Dwell could not be created.",
                 "Dwell keeps the software it needs in its own folder so it\n"
                 "cannot disturb anything else on your computer. Without that\n"
                 "folder there is nowhere to install anything.",
                 hint, detail=result.stderr)
        good("Private workspace created")
        python = venv_python()
    else:
        good("Private workspace already exists")

    if run([python, "-c", "import flask"]).returncode != 0:
        note("Downloading the software Dwell needs (about a minute)...")
        result = run([python, "-m", "pip", "install", "-q", "-r",
                      str(HERE / "requirements.txt")])
        if result.returncode != 0:
            offline = "network" in (result.stderr or "").lower() or \
                      "resolve" in (result.stderr or "").lower() or \
                      "timed out" in (result.stderr or "").lower()
            fail("The software Dwell needs could not be downloaded.",
                 "Dwell needs two small pieces of software from the internet.\n"
                 "Without them the course server cannot start.",
                 ("Check this computer is connected to the internet, then run\n"
                  "setup again." if offline else
                  "Check your internet connection and try again. If you are on\n"
                  "a work network, it may be blocking the download — try a\n"
                  "different network."),
                 detail=result.stderr)
        good("Software downloaded")
    else:
        good("Software already installed")

    # Node is only needed much later, to build the phone app. Reported, never
    # required, because most people setting this up will never build an app.
    node = shutil.which("node")
    if node:
        version = run([node, "--version"]).stdout.strip()
        good(f"Node {version} found — the phone app can be built on this computer")
    else:
        note("Node is not installed. That is fine — it is only needed if you")
        note("later build the app for participants' phones.")
    return python


# ==========================================================================
# [4/7] Creating secure credentials
# ==========================================================================

def ask_questions() -> dict:
    say()
    rule()
    say()
    say("  A few questions about your course. Four of them.")

    course_name = ask("What is this course called?", default="Privacy Lab")

    say()
    say("  Which town or city is the course in?")
    say("  A name like “Milwaukee”, or coordinates like “43.0389, -87.9065”.")
    while True:
        place = ask("Town or city")
        coords = parse_coordinates(place)
        if coords:
            lat, lon = coords
            city_name, guessed_tz = f"{lat}, {lon}", None
            break
        found = find_city(place)
        if found:
            lat, lon, guessed_tz = found
            city_name = place.title()
            break
        say()
        say(f"  “{place}” is not in the built-in list of cities.")
        say("  You can type coordinates instead: search the place on any map,")
        say("  right-click it, and copy the two numbers. For example:")
        say("      43.0389, -87.9065")

    if guessed_tz:
        label = next(l for k, l in TIMEZONES if k == guessed_tz)
        say()
        say(f"  {city_name} uses: {label}")
        timezone_name = guessed_tz if choose(
            "Is that right?",
            [("yes", "Yes, that's right"),
             ("no", "No, let me choose")]) == "yes" else choose(
            "Which timezone is the course in?", TIMEZONES)
    else:
        timezone_name = choose("Which timezone is the course in?", TIMEZONES)

    return {"course_name": course_name, "city": city_name,
            "lat": lat, "lon": lon, "timezone": timezone_name}


def ask_account() -> tuple[str, str]:
    """
    The instructor sign-in, chosen with the person rather than for them.

    A suggested password is offered because a good one is hard to invent on the
    spot, and because this one gets read aloud across a room. Anything they
    type instead is checked for length only — telling somebody their password
    needs a symbol produces worse passwords, not better ones.
    """
    say()
    rule()
    say()
    say("  Now your sign-in for the teaching dashboard.")
    say("  This is what you will use to see the course data.")

    default_user = re.sub(r"[^a-z0-9]", "", (os.getenv("USER") or "instructor").lower())
    while True:
        username = ask("What name would you like to sign in with?",
                       default=default_user or "instructor")
        username = re.sub(r"\s+", "", username.lower())
        if username == "instructor":
            say()
            say("  “instructor” is the name used by the published example")
            say("  account, so it is the first thing anyone would try.")
            say("  Please pick something else.")
            continue
        if len(username) >= 2:
            break
        say("  Please use at least two characters.")

    suggested = suggest_password()
    say()
    say("  A password has been generated for you:")
    say()
    say(f"        {suggested}")
    say()
    say("  It is made of ordinary words so it can be read aloud accurately,")
    say("  and it is strong enough to publish the web address of.")

    if yes_no("  Use this password?", default_yes=True):
        never_log(suggested)
        return username, suggested

    while True:
        say()
        try:
            typed = getpass.getpass("  Type a password (it will not appear on screen)\n  > ")
            again = getpass.getpass("  Type it once more\n  > ")
        except (EOFError, KeyboardInterrupt):
            print()
            fail("Setup was cancelled.",
                 "No sign-in was created, so Dwell cannot be used yet.",
                 "Run the setup command again when you are ready.")
        if typed != again:
            say("  Those did not match. Let's try again.")
            continue
        if len(typed) < 10:
            say("  Please use at least 10 characters. Three or four ordinary")
            say("  words together is both easier to remember and harder to guess")
            say("  than something short and complicated.")
            continue
        if typed == "demo-password":
            say("  That is the published example password. Please pick another.")
            continue
        never_log(typed)
        return username, typed


def stage_credentials(answers: dict) -> tuple[str, str]:
    stage(4, "Creating secure credentials")

    DATA.mkdir(parents=True, exist_ok=True)
    secret_path = DATA / "secret_key"
    if secret_path.exists():
        good("Security key already in place")
    else:
        try:
            fd = os.open(secret_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as fh:
                fh.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
        except OSError as exc:
            fail("The security key could not be saved.",
                 "This key is what keeps someone else from forging a sign-in\n"
                 "and reading participants' movements.",
                 "Check you have permission to write to this folder, then run\n"
                 "setup again.", detail=str(exc))
        good("Security key generated (48 random characters, never shown)")

    username, password = ask_account()
    good(f"Sign-in prepared for “{username}”")

    settings = {
        "setup_complete": True,
        "course_name": answers["course_name"],
        "course_location": {
            "name": answers["city"], "lat": answers["lat"], "lon": answers["lon"],
            "zoom": 14, "timezone": answers["timezone"],
        },
        "DWELL_PUBLIC_URL": "",
    }
    SETTINGS.write_text(json.dumps(settings, indent=2) + "\n")
    good("Course settings saved")
    return username, password


# ==========================================================================
# [5/7] Checking the database
# ==========================================================================

def stage_database(python: Path, answers: dict, username: str, password: str) -> None:
    stage(5, "Checking the database")

    if not (SAMPLE / "pings.csv").exists():
        note("Inventing a week of practice data (about twenty seconds)...")
        result = run([python, str(HERE / "tools" / "generate_sample_data.py"),
                      "--use-course-location", "--out", str(SAMPLE)], cwd=HERE)
        if result.returncode != 0:
            fail("The practice data could not be created.",
                 "Without it the dashboard would be empty, so there would be\n"
                 "nothing to learn the software on before the course.",
                 "Run setup again. If it fails a second time, send the log\n"
                 "file to whoever set this up for you.", detail=result.stderr)
        good("Practice data created")
    else:
        good("Practice data already present")

    script = (
        "import json, pathlib, sys\n"
        "from backend import db, course, load_sample\n"
        "conn = db.connect(); db.init_db(conn)\n"
        "existing = conn.execute('SELECT COUNT(*) FROM pings').fetchone()[0]\n"
        "conn.close()\n"
        "if not existing:\n"
        "    load_sample.load(with_demo_login=False)\n"
        "conn = db.connect(); db.init_db(conn)\n"
        f"loc = json.loads(pathlib.Path({str(SETTINGS)!r}).read_text())['course_location']\n"
        "course.set_location(conn, loc['name'], loc['lat'], loc['lon'],\n"
        "                    loc['timezone'], loc['zoom'])\n"
        "conn.close()\n"
        "print('DBOK')\n"
    )
    result = run([python, "-c", script], cwd=HERE)
    if result.returncode != 0 or "DBOK" not in (result.stdout or ""):
        if "RealDataPresent" in (result.stderr or ""):
            fail("This computer already holds data from a real course.",
                 "Setup would have replaced it with practice data, deleting\n"
                 "everything those participants have collected. It stopped\n"
                 "instead, and nothing was changed.",
                 "If you want to start a new course, first erase the old one\n"
                 "from the dashboard's “Data & teardown” screen.",
                 detail=result.stderr)
        fail("The course database could not be prepared.",
             "This is where everything the course records is kept. Without it\n"
             "Dwell cannot store or show anything.",
             "Run setup again. If it fails a second time, send the log file\n"
             "to whoever set this up for you.", detail=result.stderr)
    good("Course database created and checked")
    good(f"Map centred on {answers['city']}")

    # The sign-in, and removal of the published example account. Done in one
    # step so there is no moment where both exist.
    # The password arrives on standard input rather than as an argument.
    # Arguments are visible to anybody who can run `ps` while the command is
    # running, which on a shared machine is everybody.
    account_script = (
        "import sys\n"
        "password = sys.stdin.readline().rstrip('\\n')\n"
        "from backend import db, auth\n"
        "conn = db.connect(); db.init_db(conn)\n"
        "conn.execute('DELETE FROM instructors WHERE username = ?', ('instructor',))\n"
        "auth.create_instructor(conn, sys.argv[1], password)\n"
        "db.audit(conn, 'setup', 'instructor_created', sys.argv[1])\n"
        "conn.commit()\n"
        "rows = [r[0] for r in conn.execute('SELECT username FROM instructors')]\n"
        "conn.close()\n"
        "assert 'instructor' not in rows, 'example account still present'\n"
        "assert sys.argv[1] in rows, 'sign-in was not created'\n"
        "print('ACCOUNTOK')\n"
    )
    result = run([python, "-c", account_script, username], cwd=HERE,
                 stdin_text=password + "\n")
    if result.returncode != 0 or "ACCOUNTOK" not in (result.stdout or ""):
        fail("Your sign-in could not be created.",
             "Without it there is no way to open the teaching dashboard.",
             "Run setup again. If it fails a second time, send the log file\n"
             "to whoever set this up for you.", detail=result.stderr)
    good("Your sign-in created, and the published example account removed")


# ==========================================================================
# [6/7] Running tests
# ==========================================================================

def stage_tests(python: Path) -> None:
    stage(6, "Running tests")
    note("Checking that every part of Dwell works. This takes about a minute.")
    result = run([python, str(HERE / "verify.py")], cwd=HERE)
    out = result.stdout or ""

    passed = next((l.strip() for l in out.splitlines()
                   if "checks passed" in l), "")
    skipped = [l.strip().lstrip("– ").strip()
               for l in out.splitlines() if l.strip().startswith("–")]

    if result.returncode != 0:
        problems = [l.strip() for l in out.splitlines() if l.strip().startswith("✗")]
        fail("Some of Dwell's own tests did not pass.",
             "These tests check the parts that protect participants — that\n"
             "one person cannot see another's data, and that the map hides\n"
             "places too few people visited. Running a course on software\n"
             "failing these would put real people's data at risk.",
             "Send the log file below to whoever set this up for you.\n"
             "Do not run a course until these pass.",
             detail="\n".join(problems) + "\n\n" + out[-3000:])

    good(passed or "All checks passed")
    for line in skipped:
        note(f"Skipped: {line}")
    if skipped:
        note("(Skipped checks need extra tools that a course does not.)")


# ==========================================================================
# [7/7] Starting Dwell
# ==========================================================================

def free_port(start: int = 5000) -> int | None:
    for port in range(start, start + 20):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.3)
        taken = probe.connect_ex(("127.0.0.1", port)) == 0
        probe.close()
        if not taken:
            return port
    return None


def health_check(port: int, tries: int = 40) -> tuple[bool, str]:
    """Ask the running server whether it is actually alive and serving."""
    import urllib.error
    import urllib.request
    last = "no response"
    for _ in range(tries):
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health", timeout=2) as resp:
                body = resp.read(200).decode("utf-8", "replace")
                if resp.status == 200 and "ok" in body:
                    # And the dashboard itself, not just the health route.
                    with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/", timeout=5) as page:
                        if page.status == 200 and b"Dwell" in page.read(4000):
                            return True, "server and dashboard both responding"
                    return False, "the server answered but the dashboard did not"
                last = f"unexpected reply: {resp.status}"
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last = str(exc)
        time.sleep(0.5)
    return False, last


def stage_start(python: Path, answers: dict, username: str, password: str) -> int:
    stage(7, "Starting Dwell")

    port = free_port()
    if port is None:
        fail("Every port Dwell could use is already busy.",
             "Dwell needs one to serve the dashboard to your browser.",
             "Restart your computer and run setup again. If that does not\n"
             "help, another program is using ports 5000 to 5019.")
    if port != 5000:
        note(f"Port 5000 was busy, using {port} instead.")

    log(f"starting server on port {port}")
    server = subprocess.Popen(
        [str(python), "-m", "backend.app", "--host", "127.0.0.1",
         "--port", str(port), "--quiet"],
        cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    note("Starting the course server...")
    ok, detail = health_check(port)
    if not ok:
        output = ""
        if server.poll() is not None:
            output = (server.stdout.read() or "")[:3000]
        server.terminate()
        fail("Dwell started but did not answer.",
             "The software installed correctly, but the part that serves the\n"
             "dashboard to your browser is not responding. Until it does,\n"
             "there is nothing to open.",
             "Run setup again. If it fails a second time, send the log file\n"
             "to whoever set this up for you.",
             detail=f"health check: {detail}\n\nserver output:\n{output}")
    good(f"Health check passed — {detail}")

    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
    log("health check server stopped")

    print()
    rule()
    print()
    say(f"  Dwell is ready.  “{answers['course_name']}”")
    say()
    say("  Write these down now. The password is not shown again.")
    say()
    say(f"        Sign in as :  {username}")
    say(f"        Password   :  {password}")
    say()
    say(f"        Course city:  {answers['city']}")
    print()
    rule()
    print()
    say("  To start teaching with it, run this in the same folder:")
    say()
    if os.name == "nt":
        say("        dwell start")
    else:
        say("        ./dwell start")
    say()
    say("  It prints a web address. Open that, sign in with the details")
    say("  above, and you have the dashboard with a week of practice data.")
    say()
    say("  When you need real phones to reach it, run:")
    say()
    say("        ./dwell deploy" if os.name != "nt" else "        dwell deploy")
    print()
    rule()
    print()
    return 0


# ==========================================================================

def already_set_up() -> bool:
    try:
        return bool(json.loads(SETTINGS.read_text()).get("setup_complete"))
    except (OSError, ValueError):
        return False


def main() -> int:
    log("=" * 60)
    log(f"setup started  argv={sys.argv}")

    print()
    rule()
    print()
    say("  Dwell: Privacy Lab — setup")
    say()
    say("  This gets everything ready for your course. It asks a few")
    say("  questions and does the rest itself, then checks that it worked.")
    say()
    say("  It takes about three minutes.")
    print()
    rule()

    if already_set_up():
        if choose("Dwell has already been set up on this computer.",
                  [("keep", "Leave it as it is"),
                   ("redo", "Set it up again, replacing the course settings")]) == "keep":
            say()
            say("  Nothing changed.")
            say(f"  To start it:  {'dwell start' if os.name == 'nt' else './dwell start'}")
            print()
            return 0

    osinfo = stage_check_computer()
    stage_install_prereqs(osinfo)
    python = stage_setup(osinfo)
    answers = ask_questions()
    username, password = stage_credentials(answers)
    stage_database(python, answers, username, password)
    stage_tests(python)
    return stage_start(python, answers, username, password)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n  Setup was cancelled. Nothing was left half-finished.\n")
        sys.exit(1)
    except SystemExit:
        raise
    except Exception:
        # Nothing unexpected reaches the screen as a stack trace. It goes in the
        # log, and the person gets something they can act on.
        log("UNEXPECTED ERROR:\n" + traceback.format_exc())
        fail("Something unexpected went wrong.",
             "Setup hit a problem it did not know how to explain, so it\n"
             "stopped rather than leaving Dwell half-configured.",
             "Send the log file below to whoever set this up for you. It\n"
             "contains exactly what happened.")
