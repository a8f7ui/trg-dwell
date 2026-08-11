#!/usr/bin/env python3
"""
Start the demo. One command, nothing to know beforehand.

    python3 start.py

That is the whole thing. It sets up whatever is missing, skips whatever is
already done, and prints one address to open.

Why this file exists
--------------------
Getting this running used to take about nine steps: create a virtual
environment, work out that `python` and `python3` and `.venv/bin/python` are
three different programs, install dependencies, watch one of them try to
compile a C++ build system, generate sample data, load it, create a login,
work out which address to bind to, and start the server. Every one of those is
a place to get stuck, and the people this project is *for* are not the people
who enjoy getting unstuck.

So this does all of it. It is written against the standard library only, so it
runs on the plain `python3` that is already on the machine, before anything is
installed.

Safe to run again at any time. It checks each step rather than repeating it.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
SAMPLE = HERE / "data" / "sample"
FIRST_PORT = 5000


# --------------------------------------------------------------------------
# Saying things
# --------------------------------------------------------------------------

def step(message: str) -> None:
    print(f"  {message}", flush=True)


def done(message: str) -> None:
    print(f"  ✓ {message}", flush=True)


def fail(message: str, detail: str = "") -> None:
    print(f"\n  Could not continue: {message}\n", file=sys.stderr)
    if detail:
        print(f"{detail}\n", file=sys.stderr)
    sys.exit(1)


# --------------------------------------------------------------------------
# The steps
# --------------------------------------------------------------------------

def venv_python() -> Path:
    """Where the virtual environment's interpreter lives on this platform."""
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def ensure_venv() -> Path:
    """
    A private place to install dependencies, created if it is not there.

    Rebuilt from scratch if it exists but is broken, which happens when a
    half-finished install was interrupted — a state that otherwise produces
    confusing errors much later on.
    """
    python = venv_python()
    if python.exists():
        try:
            subprocess.run([str(python), "-c", "import sys"],
                           check=True, capture_output=True)
            return python
        except (subprocess.CalledProcessError, OSError):
            step("The existing setup is broken; rebuilding it.")
            shutil.rmtree(VENV, ignore_errors=True)

    step("Setting up a private Python environment (once, about 10 seconds)...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(VENV)],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        fail("could not create a Python environment.",
             (exc.stderr or "") +
             "\n  On Debian or Ubuntu this usually means one more package:\n"
             "      apt-get install -y python3-venv")
    except OSError as exc:
        fail(f"could not create a Python environment: {exc}")

    done("Python environment ready.")
    return venv_python()


def have(python: Path, module: str) -> bool:
    result = subprocess.run([str(python), "-c", f"import {module}"],
                            capture_output=True)
    return result.returncode == 0


def ensure_dependencies(python: Path) -> None:
    """
    Install what the server needs.

    Two pure-Python packages, so this either works or the machine has no network
    — there is no longer a dependency here that can fail to build.
    """
    if have(python, "flask"):
        return

    step("Installing what the server needs (once, about a minute)...")
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "-q",
         "-r", str(HERE / "requirements.txt")],
        capture_output=True, text=True)
    if result.returncode != 0:
        fail("could not install the dependencies.", (result.stderr or "").strip())
    done("Dependencies installed.")


def ensure_sample_data(python: Path) -> None:
    if (SAMPLE / "pings.csv").exists():
        return
    step("Inventing a week of sample data (about 20 seconds)...")
    result = subprocess.run(
        [str(python), str(HERE / "tools" / "generate_sample_data.py"),
         "--out", str(SAMPLE)],
        capture_output=True, text=True)
    if result.returncode != 0:
        fail("could not generate the sample data.", (result.stderr or "").strip())
    done("Sample data ready.")


def ensure_loaded(python: Path) -> None:
    """Put the sample data into the database, if the database is empty."""
    check = subprocess.run(
        [str(python), "-c",
         "from backend import db;c=db.connect();db.init_db(c);"
         "print(c.execute('SELECT COUNT(*) FROM pings').fetchone()[0])"],
        capture_output=True, text=True, cwd=HERE)
    if check.returncode == 0 and check.stdout.strip().isdigit():
        if int(check.stdout.strip()) > 0:
            return

    step("Loading the sample data...")
    result = subprocess.run([str(python), "-m", "backend.load_sample"],
                            capture_output=True, text=True, cwd=HERE)
    if result.returncode != 0:
        fail("could not load the sample data.", (result.stderr or "").strip())
    done("Sample data loaded.")


def in_container() -> bool:
    """
    Inside Docker, 127.0.0.1 is the container's own loopback and unreachable
    from outside — even with a published port. Detected so the server listens
    somewhere that can actually be opened.
    """
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text()
    except OSError:
        return False
    return any(m in cgroup for m in ("docker", "kubepods", "containerd", "lxc"))


def free_port(start: int) -> int | None:
    """The first port from `start` that nothing is already using."""
    for port in range(start, start + 20):
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.3)
        taken = probe.connect_ex(("127.0.0.1", port)) == 0
        probe.close()
        if not taken:
            return port
    return None


# --------------------------------------------------------------------------

def main() -> None:
    print("\n  Dwell: Privacy Lab\n")

    if sys.version_info < (3, 10):
        fail(f"this needs Python 3.10 or newer, and this is "
             f"{sys.version_info.major}.{sys.version_info.minor}.")

    python = ensure_venv()
    ensure_dependencies(python)
    ensure_sample_data(python)
    ensure_loaded(python)

    port = free_port(FIRST_PORT)
    if port is None:
        fail("every port from 5000 upwards is already in use.")
    if port != FIRST_PORT:
        step(f"Port {FIRST_PORT} was busy, using {port} instead.")

    containerised = in_container()
    host = "0.0.0.0" if containerised else "127.0.0.1"

    print("\n  " + "-" * 56)
    print("\n  Open this in a browser:\n")
    print(f"      http://127.0.0.1:{port}\n")
    print("  Log in with:      instructor  /  demo-password\n")
    if containerised:
        print(f"  (Running in a container. Start it with -p {port}:{port} for")
        print("   that address to work from outside.)\n")
    print("  Press Ctrl-C here to stop the server.")
    print("\n  " + "-" * 56 + "\n")

    # Hand over to the server. Replacing this process rather than spawning a
    # child means Ctrl-C reaches the server directly, with no wrapper left
    # behind holding the port open.
    os.chdir(HERE)
    args = [str(python), "-m", "backend.app",
            "--host", host, "--port", str(port), "--quiet"]
    try:
        os.execv(str(python), args)
    except OSError:
        # execv is not available everywhere; fall back to running it as a child.
        try:
            subprocess.run(args, cwd=HERE)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Stopped.\n")
