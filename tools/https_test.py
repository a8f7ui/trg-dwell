#!/usr/bin/env python3
"""
Does this actually work over HTTPS?

    python3 tools/https_test.py

Starts the real server over real TLS, on a throwaway database, and drives it:
the dashboard, a sign-in, the sign-in cookie, and the phone's API. Everything
here is exercised over an encrypted connection rather than read out of a
configuration file, because configuration has been right while the thing itself
was broken more than once.

What this proves and what it does not
-------------------------------------
The certificate is self-signed and generated for this run, so what is proven is
that *this software* behaves correctly when it is served over HTTPS: that the
sign-in cookie is marked Secure, that the phone's API works over TLS, that the
dashboard loads.

What it does not prove is that a particular web host is configured correctly, or
that a certificate from a real authority is trusted by a real phone. That needs
the actual host, and `docs/REAL_DEPLOYMENT_STATUS.md` records it as unproven
rather than pretending otherwise.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}" + (f"\n          {detail}" if detail else ""))
        failures.append(name)
    return ok


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_certificate(into: Path) -> tuple[Path, Path]:
    """A self-signed certificate for 127.0.0.1, valid for a day."""
    cert, key = into / "cert.pem", into / "key.pem"
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(key), "-out", str(cert), "-days", "1",
         "-subj", "/CN=127.0.0.1",
         "-addext", "subjectAltName=IP:127.0.0.1"],
        check=True, capture_output=True)
    return cert, key


class Client:
    """
    An HTTPS client that trusts exactly one certificate.

    Trusting the run's own certificate rather than disabling verification keeps
    the test honest: a server presenting the wrong certificate still fails.
    """

    def __init__(self, base: str, cafile: Path):
        self.base = base.rstrip("/")
        context = ssl.create_default_context(cafile=str(cafile))
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context),
            urllib.request.HTTPCookieProcessor(self.jar))
        self.last_headers = None

    def call(self, method: str, path: str, body: dict | None = None,
             token: str = "") -> tuple[int, object]:
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers=headers)
        try:
            with self.opener.open(req, timeout=20) as resp:
                self.last_headers = resp.headers
                raw = resp.read()
                try:
                    return resp.status, json.loads(raw)
                except ValueError:
                    return resp.status, raw
        except urllib.error.HTTPError as exc:
            self.last_headers = exc.headers
            return exc.code, exc.read()


def main() -> int:
    if not shutil.which("openssl"):
        print("\n  Skipped: openssl is not installed, so no certificate can be "
              "made.\n")
        return 0

    work = Path(tempfile.mkdtemp(prefix="dwell-https-"))
    port = free_port()
    base = f"https://127.0.0.1:{port}"
    password = "tls-check-" + os.urandom(6).hex()

    print("\n  Over a real TLS connection\n")

    python = HERE / ".venv" / ("Scripts/python.exe" if os.name == "nt"
                               else "bin/python")
    if not python.exists():
        python = Path(sys.executable)

    server = None
    try:
        cert, key = make_certificate(work)

        env = dict(os.environ,
                   DWELL_DB=str(work / "course.db"),
                   # The server is told its own public address, which is what
                   # switches the sign-in cookie to HTTPS-only. Getting this
                   # wrong is the failure this whole file is here to catch.
                   DWELL_PUBLIC_URL=base,
                   DWELL_SETTINGS=str(work / "none.json"))

        seed = subprocess.run(
            [str(python), "-m", "backend.load_sample", "--with-login",
             "--password-stdin"],
            input=password + "\n", capture_output=True, text=True,
            cwd=HERE, env=env)
        if not check("a throwaway course is prepared", seed.returncode == 0,
                     (seed.stderr or "").strip()[:400]):
            return 1

        runner = (
            "import ssl, sys\n"
            "from backend.app import app\n"
            "context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)\n"
            f"context.load_cert_chain({str(cert)!r}, {str(key)!r})\n"
            f"app.run(host='127.0.0.1', port={port}, ssl_context=context,\n"
            "        debug=False, use_reloader=False)\n"
        )
        server = subprocess.Popen([str(python), "-c", runner], cwd=HERE, env=env,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True)

        client = Client(base, cert)
        started = False
        for _ in range(60):
            if server.poll() is not None:
                break
            try:
                status, _ = client.call("GET", "/health")
                if status == 200:
                    started = True
                    break
            except Exception:                       # noqa: BLE001
                pass
            time.sleep(0.5)

        if not check("the server starts and answers over HTTPS", started,
                     (server.stdout.read()[:600] if server.poll() is not None
                      else "no answer in 30 seconds")):
            return 1

        # --- the dashboard ---------------------------------------------------
        status, body = client.call("GET", "/")
        check("the dashboard loads over HTTPS",
              status == 200 and b"Dwell" in (body if isinstance(body, bytes)
                                             else b""),
              f"got HTTP {status}")

        # --- signing in ------------------------------------------------------
        status, _ = client.call("POST", "/api/instructor/login",
                                {"username": "instructor", "password": "wrong"})
        check("a wrong password is still refused over HTTPS", status == 401,
              f"got HTTP {status}")

        status, _ = client.call("POST", "/api/instructor/login",
                                {"username": "instructor", "password": password})
        signed_in = check("signing in works over HTTPS", status == 200,
                          f"got HTTP {status}")

        # --- the cookie ------------------------------------------------------
        # Read from the Set-Cookie header rather than from configuration: the
        # question is what the browser was actually told.
        set_cookie = ""
        if client.last_headers:
            set_cookie = "; ".join(client.last_headers.get_all("Set-Cookie") or [])
        check("the sign-in cookie is marked Secure",
              "secure" in set_cookie.lower(),
              f"Set-Cookie was: {set_cookie or '(none sent)'}")
        check("the sign-in cookie is marked HttpOnly",
              "httponly" in set_cookie.lower(),
              f"Set-Cookie was: {set_cookie or '(none sent)'}")
        check("the sign-in cookie restricts cross-site use",
              "samesite" in set_cookie.lower(),
              f"Set-Cookie was: {set_cookie or '(none sent)'}")

        if signed_in:
            status, people = client.call("GET", "/api/instructor/participants")
            check("instructor data loads over HTTPS",
                  status == 200 and isinstance(people, list) and people,
                  f"got HTTP {status}")

        # --- the phone -------------------------------------------------------
        status, reg = client.call("POST", "/api/v1/participants", {
            "consent_version": "https-check",
            "consented_at": "2026-09-15T08:00:00Z",
            "os_name": "https-check"})
        registered = check("a phone can register over HTTPS", status == 201,
                           f"got HTTP {status}")
        if registered and isinstance(reg, dict):
            token = reg.get("token", "")
            status, ack = client.call("POST", "/api/v1/pings", {"pings": [{
                "ts": "2026-09-15T18:00:00Z", "lat": 43.0389, "lon": -87.9065,
                "accuracy_m": 10, "collection_mode": "background"}]},
                token=token)
            check("a phone can upload over HTTPS",
                  status == 201 and isinstance(ack, dict)
                  and ack.get("accepted") == 1,
                  f"got HTTP {status}: {ack}")

            status, _ = client.call("GET", "/api/v1/me/reveal", token="not-a-token")
            check("a bad device token is refused over HTTPS", status == 401,
                  f"got HTTP {status}")

        # --- plain HTTP to a TLS port -----------------------------------------
        # A phone or browser that forgets the s must not get a working plain
        # connection. The server speaks TLS only, so the attempt fails rather
        # than quietly succeeding in the clear.
        plain_worked = False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health",
                                        timeout=5) as resp:
                plain_worked = resp.status == 200
        except Exception:                           # noqa: BLE001
            plain_worked = False
        check("plain HTTP does not work against the HTTPS port", not plain_worked,
              "an unencrypted request succeeded")

        # --- what the phone app would be told ---------------------------------
        env_file = HERE / "app" / ".env"
        if env_file.exists():
            written = env_file.read_text()
            check("the phone app's configured address is HTTPS",
                  "EXPO_PUBLIC_DWELL_SERVER=https://" in written,
                  "app/.env points somewhere that is not https://")
        else:
            print("  ----  the phone app has no address configured yet "
                  "(run `dwell app` after deploying)")

    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        shutil.rmtree(work, ignore_errors=True)

    print()
    if failures:
        print(f"  {len(failures)} check(s) FAILED\n")
        return 1
    print("  All HTTPS checks passed, against a certificate made for this run.")
    print("  This says the software is correct over TLS. It does not say a\n"
          "  particular web host is.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
