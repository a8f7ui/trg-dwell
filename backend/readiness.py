"""
Is this server safe for real participants?

One place that answers that question, so `manage.py check-production`, the
`dwell ready` command and the test suite all get the same answer rather than
three drifting opinions of it.

Every check returns one of three verdicts:

  BLOCKER   something that would harm participants or make the course
            impossible. The command refuses to say "ready" while any exists.
  WARNING   something worth knowing that is not dangerous, or is only dangerous
            depending on circumstances this code cannot see.
  OK        checked, and fine.

The distinction is the whole value of the thing. A list that calls everything a
problem gets ignored, and a list that calls nothing a problem is decoration.
"""

from __future__ import annotations

import os
import socket
import sqlite3
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import auth, config, course, db

BLOCKER = "BLOCKER"
WARNING = "WARNING"
OK = "OK"


@dataclass
class Result:
    verdict: str
    condition: str      # the short name of what was checked
    detail: str         # what was found
    fix: str = ""       # what to do about it, when there is something to do

    @property
    def blocking(self) -> bool:
        return self.verdict == BLOCKER


# --------------------------------------------------------------------------
# The nine conditions
# --------------------------------------------------------------------------

def check_database_location(conn) -> list[Result]:
    """A persistent database, in a place that survives a restart."""
    out: list[Result] = []
    path = Path(config.DB_PATH)

    try:
        conn.execute("CREATE TABLE IF NOT EXISTS _writecheck (x INTEGER)")
        conn.execute("DROP TABLE _writecheck")
        conn.commit()
        out.append(Result(OK, "database is writable", str(path)))
    except sqlite3.Error as exc:
        out.append(Result(
            BLOCKER, "database is writable",
            f"{path} cannot be written to ({exc}). Nothing can be recorded.",
            "Check that the folder exists and that this account may write to it."))
        return out

    # A database under /tmp is the classic way to lose a course: everything
    # works, and then the host restarts overnight and the week is gone.
    temporary = [Path("/tmp"), Path("/var/tmp"), Path("/dev/shm")]
    if any(_is_within(path, t) for t in temporary):
        out.append(Result(
            BLOCKER, "database survives a restart",
            f"The database is at {path}, which is temporary storage. Most hosts "
            f"empty it without warning, and the whole course would be lost.",
            "Set DWELL_DB to a path on permanent storage, or leave it unset to "
            "use data/local/course.db."))
    else:
        out.append(Result(OK, "database survives a restart",
                          f"{path} is on ordinary storage."))
    return out


def check_secret(conn) -> list[Result]:
    """A persistent signing key, not one regenerated on every start."""
    if os.getenv("DWELL_SECRET_KEY") or config.SETTINGS.get("DWELL_SECRET_KEY"):
        return [Result(OK, "sign-in key is persistent",
                       "Set from configuration, so it survives a restart.")]

    key_path = Path(config.DB_PATH).parent / "secret_key"
    if not key_path.exists():
        return [Result(
            WARNING, "sign-in key is persistent",
            "No key file yet. One is generated the first time the server "
            "starts, and kept from then on.")]

    problems = []
    if _is_within(key_path, Path("/tmp")):
        problems.append(Result(
            BLOCKER, "sign-in key is persistent",
            f"The key is at {key_path}, which is temporary storage. When the "
            f"host clears it, every instructor is signed out.",
            "Set DWELL_DB to permanent storage; the key is kept beside it."))
    else:
        problems.append(Result(OK, "sign-in key is persistent",
                               f"Stored at {key_path}."))

    # Anyone who can read this file can forge an instructor sign-in.
    try:
        mode = key_path.stat().st_mode & 0o777
        if os.name != "nt" and mode & 0o077:
            problems.append(Result(
                WARNING, "sign-in key is private",
                f"The key file is readable by other accounts on this machine "
                f"(permissions {mode:o}).",
                f"chmod 600 {key_path}"))
        else:
            problems.append(Result(OK, "sign-in key is private",
                                   "Readable only by this account."))
    except OSError:
        pass
    return problems


def check_public_url(conn) -> list[Result]:
    """A public HTTPS address, which everything else about safety depends on."""
    url = config.PUBLIC_URL
    if not url:
        return [Result(
            BLOCKER, "public address is HTTPS",
            "No public address is set, so this server does not know it is "
            "reachable from outside. Sign-in cookies will not be marked "
            "HTTPS-only, and the phone app has nowhere to send data.",
            "Run:  python3 dwell.py deploy")]
    if not url.startswith("https://"):
        return [Result(
            BLOCKER, "public address is HTTPS",
            f"The address is {url}, which is not HTTPS. Instructor passwords "
            f"and participant tokens would cross the network in the clear, and "
            f"iPhones refuse plain HTTP silently — the app would look fine and "
            f"collect nothing.",
            "Use the https:// address your host gave you.")]
    return [Result(OK, "public address is HTTPS", url)]


def check_secure_cookies(conn) -> list[Result]:
    """The sign-in cookie must be HTTPS-only once there is an HTTPS address."""
    if config.PUBLIC_URL.startswith("https://") and not config.SESSION_COOKIE_SECURE:
        return [Result(
            BLOCKER, "sign-in cookie is HTTPS-only",
            "The address is HTTPS but the cookie is not marked secure, so a "
            "browser could be tricked into sending it over plain HTTP.",
            "This is a fault in the software, not your configuration. Report it.")]
    if config.SESSION_COOKIE_SECURE:
        return [Result(OK, "sign-in cookie is HTTPS-only",
                       "Set, so browsers will not send it over plain HTTP.")]
    return [Result(
        WARNING, "sign-in cookie is HTTPS-only",
        "Not set, because there is no HTTPS address yet. Correct for a laptop; "
        "not acceptable on a public server.")]


def check_production_mode(conn) -> list[Result]:
    """Not Flask's development server, and not with the debugger exposed."""
    out: list[Result] = []
    if os.getenv("FLASK_DEBUG") or os.getenv("FLASK_ENV") == "development":
        out.append(Result(
            BLOCKER, "debug mode is off",
            "FLASK_DEBUG or FLASK_ENV is set to a development value. Flask's "
            "debugger lets anybody who can reach an error page run commands on "
            "the server.",
            "Unset FLASK_DEBUG and FLASK_ENV."))
    else:
        out.append(Result(OK, "debug mode is off", "No debug flag is set."))

    # `dwell deploy` writes a WSGI file for the host to import, which is what
    # makes a host run this under its own production server rather than
    # Flask's built-in one.
    wsgi = config.BASE_DIR / "wsgi.py"
    if wsgi.exists():
        out.append(Result(OK, "runs under a real web server",
                          f"{wsgi.name} is present for the host to import."))
    else:
        out.append(Result(
            WARNING, "runs under a real web server",
            "wsgi.py is missing, so a host has nothing to import. Only matters "
            "if this is being hosted rather than run from a laptop."))
    return out


def check_no_demo_instructor(conn) -> list[Result]:
    """No account whose password is published in this project."""
    from . import load_sample

    names = [r["username"] for r in conn.execute("SELECT username FROM instructors")]
    out: list[Result] = []

    if not names:
        out.append(Result(
            BLOCKER, "somebody can sign in",
            "There are no instructor accounts, so nobody can open the "
            "dashboard.",
            ".venv/bin/python manage.py add-instructor <your-name>"))
    else:
        out.append(Result(OK, "somebody can sign in",
                          f"{len(names)} account(s): {', '.join(sorted(names))}."))

    published_user, published_password = load_sample.PUBLISHED_DEMO_LOGIN
    if published_user in names and auth.check_instructor(
            conn, published_user, published_password):
        out.append(Result(
            BLOCKER, "no published password works",
            f"The account '{published_user}' exists with the password written "
            f"in this project's public history. Anybody who has read it can "
            f"sign in and watch your participants.",
            f".venv/bin/python manage.py remove-instructor {published_user}"))
    elif published_user in names:
        out.append(Result(
            WARNING, "no published password works",
            f"An account named '{published_user}' exists. Its password is not "
            f"the published one, so this is not urgent, but a name that "
            f"identifies a person is better.",
            f".venv/bin/python manage.py remove-instructor {published_user}"))
    else:
        out.append(Result(OK, "no published password works",
                          "No account from the practice data is present."))
    return out


def check_no_sample_data(conn) -> list[Result]:
    """No invented participants mixed in with real ones."""
    from . import load_sample

    invented = conn.execute(
        "SELECT COUNT(*) AS n FROM participants WHERE consent_version = ?",
        (load_sample.SAMPLE_CONSENT_VERSION,)).fetchone()["n"]
    real = load_sample.real_participant_count(conn)

    if invented and real:
        return [Result(
            BLOCKER, "no invented participants",
            f"{invented} invented participants are mixed in with {real} real "
            f"ones. The dashboard, the aggregate map and every figure shown to "
            f"the room would be counting people who do not exist.",
            "Erase the practice data from the dashboard's “Data & teardown” "
            "screen before the course starts.")]
    if invented:
        return [Result(
            WARNING, "no invented participants",
            f"{invented} invented participants are loaded and no real ones are. "
            f"Fine while practising; clear them before the course.",
            ".venv/bin/python manage.py wipe")]
    return [Result(OK, "no invented participants",
                   f"{real} real participant(s), no practice data.")]


def check_course_location(conn) -> list[Result]:
    """The course is anchored where it is actually being taught."""
    loc = course.get_location(conn)
    if loc["is_default"]:
        return [Result(
            WARNING, "course location is set",
            f"Still the built-in default ({loc['name']}). If that is where you "
            f"are teaching, ignore this. If not, the map opens on the wrong "
            f"city and — more seriously — days are worked out in the wrong "
            f"timezone, which splits every evening reveal.",
            'manage.py set-location "Your City, State" --timezone America/...')]
    return [Result(OK, "course location is set",
                   f"{loc['name']} ({loc['timezone']}).")]


def check_server_answers(base_url: str = "") -> list[Result]:
    """
    The health endpoint and the dashboard both answer.

    Asked over the network rather than by inspecting configuration, because the
    question is whether it works, and configuration has been right while the
    server was down more than once.
    """
    base = (base_url or config.PUBLIC_URL).rstrip("/")
    if not base:
        return [Result(
            WARNING, "the server answers",
            "No address to try. Set a public address, or pass one in.")]

    out: list[Result] = []
    for path, name in [("/health", "the health check answers"),
                       ("/", "the dashboard loads")]:
        try:
            with urllib.request.urlopen(base + path, timeout=15) as resp:
                body = resp.read(2048)
                ok = resp.status == 200
                if path == "/" and b"Dwell" not in body:
                    out.append(Result(
                        BLOCKER, name,
                        f"{base}{path} answered {resp.status} but did not return "
                        f"the dashboard.",
                        "Check that the host is serving this project and not "
                        "something else."))
                    continue
                out.append(Result(
                    OK if ok else BLOCKER, name,
                    f"{base}{path} answered {resp.status}.",
                    "" if ok else "Check the host's error log."))
        except urllib.error.HTTPError as exc:
            out.append(Result(BLOCKER, name,
                              f"{base}{path} answered {exc.code}.",
                              "Check the host's error log."))
        except (urllib.error.URLError, TimeoutError, socket.timeout,
                ConnectionError) as exc:
            out.append(Result(
                BLOCKER, name,
                f"{base}{path} could not be reached ({exc}).",
                "Check that the server is running and the address is right."))
    return out


# --------------------------------------------------------------------------

def _is_within(path: Path, parent: Path) -> bool:
    try:
        Path(path).resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def run_all(conn=None, base_url: str = "", reach_server: bool = True) -> list[Result]:
    """
    Every condition, in the order somebody would want to read them.

    `reach_server` exists so the same list can be produced without a network —
    the tests need that, and so does anybody checking a server that is not
    running yet.
    """
    own_conn = conn is None
    if own_conn:
        conn = db.connect()
        db.init_db(conn)
    try:
        results: list[Result] = []
        results += check_database_location(conn)
        results += check_secret(conn)
        results += check_public_url(conn)
        results += check_secure_cookies(conn)
        results += check_production_mode(conn)
        results += check_no_demo_instructor(conn)
        results += check_no_sample_data(conn)
        results += check_course_location(conn)
        if reach_server:
            results += check_server_answers(base_url)
        return results
    finally:
        if own_conn:
            conn.close()


def is_ready(results: list[Result]) -> bool:
    return not any(r.blocking for r in results)
