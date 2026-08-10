#!/usr/bin/env python3
"""
Check that the mobile app and the backend actually agree.

The app and the server are written in different languages and cannot be
typechecked against each other, so this replays exactly the four requests the
app makes — the same paths, the same JSON shapes as `app/src/api.ts` — against a
running server and checks the responses are what the app expects.

Run the backend first, then:

    python3 tools/contract_test.py [http://localhost:5000]

It creates a throwaway participant and deletes it again at the end, so it is
safe to run against a live course server, though there is rarely a reason to.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:5000"

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}{(' — ' + detail) if detail else ''}")


def call(method: str, path: str, body: dict | None = None,
         token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except json.JSONDecodeError:
            return e.code, {}
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach {BASE}: {e.reason}\n"
                         f"Start the backend first:  .venv/bin/python -m backend.app")


print(f"Checking the app/backend contract against {BASE}\n")

# ---------------------------------------------------------------- health
status, _ = call("GET", "/health")
check("server is up", status == 200, f"got {status}")

# ---------------------------------------------------------------- register
# Exactly the payload app/src/api.ts register() sends.
consented_at = datetime.now(timezone.utc).isoformat()
status, reg = call("POST", "/api/v1/participants", {
    "consent_version": "contract-test",
    "consented_at": consented_at,
    "device_model": "Pixel 8",
    "os_name": "Android",
    "os_version": "14",
    "screen_w": 412,
    "screen_h": 915,
    "timezone": "America/Chicago",
    "language": "en-US",
})
check("register returns 201", status == 201, f"got {status}")
check("register returns a participant_id", bool(reg.get("participant_id")))
check("register returns a token", bool(reg.get("token")))
token = reg.get("token", "")
participant_id = reg.get("participant_id", "")

# Registration must refuse to proceed without a recorded consent.
status, _ = call("POST", "/api/v1/participants", {"device_model": "X"})
check("register without consent is refused", status == 400, f"got {status}")

# ---------------------------------------------------------------- upload
# Exactly the ping shape app/src/storage.ts QueuedPing produces.
now = datetime.now(timezone.utc)
pings = [{
    "ts": (now - timedelta(minutes=i)).isoformat(),
    "lat": 30.2672 + i * 0.0004,
    "lon": -97.7431 + i * 0.0004,
    "accuracy_m": 12.5,
    "battery_pct": 74,
    "connection": "wifi",
    "collection_mode": "background" if i % 2 else "foreground",
} for i in range(10)]

status, up = call("POST", "/api/v1/pings", {"pings": pings}, token=token)
check("upload returns 201", status == 201, f"got {status}")
check("upload accepted all 10 points", up.get("accepted") == 10, f"got {up.get('accepted')}")

status, _ = call("POST", "/api/v1/pings", {"pings": pings}, token="not-a-real-token")
check("upload with a bad token is refused", status == 401, f"got {status}")

status, _ = call("POST", "/api/v1/pings", {"pings": pings})
check("upload with no token is refused", status == 401, f"got {status}")

# Malformed points should be skipped, not fail the whole batch.
status, up = call("POST", "/api/v1/pings", {"pings": [
    {"ts": now.isoformat(), "lat": 30.0, "lon": -97.0},
    {"lat": "nonsense"},
]}, token=token)
check("a malformed point is skipped, not fatal",
      status == 201 and up.get("accepted") == 1 and up.get("rejected") == 1,
      f"got {up}")

# ---------------------------------------------------------------- reveal
status, rev = call("GET", "/api/v1/me/reveal", token=token)
check("reveal returns 200", status == 200, f"got {status}")
check("reveal is for the calling participant",
      rev.get("participant_id") == participant_id,
      f"got {rev.get('participant_id')}")

for field in ("trail_segments", "stops", "places", "assessment",
              "comparison", "agency_step", "day_number", "days_available"):
    check(f"reveal includes '{field}'", field in rev)

assessment = rev.get("assessment", {})
check("assessment includes coverage", "coverage" in assessment)
check("assessment includes findings", "findings" in assessment)
check("assessment includes caveats", "caveats" in assessment)
check("coverage reports background share",
      "background_pct" in assessment.get("coverage", {}))

agency = rev.get("agency_step", {})
check("agency step has all three parts",
      all(k in agency for k in ("title", "detail", "what_would_have_changed")))

status, _ = call("GET", "/api/v1/me/reveal", token="not-a-real-token")
check("reveal with a bad token is refused", status == 401, f"got {status}")

# ---------------------------------------------------------------- withdraw
status, wd = call("POST", "/api/v1/me/withdraw", token=token)
check("withdraw returns 200", status == 200, f"got {status}")
check("withdraw reports how many points were deleted",
      isinstance(wd.get("location_points_deleted"), int)
      and wd["location_points_deleted"] >= 11,
      f"got {wd.get('location_points_deleted')}")
check("withdraw returns a message for the participant", bool(wd.get("message")))

# The token must be dead afterwards — this is the claim that matters most.
status, _ = call("GET", "/api/v1/me/reveal", token=token)
check("the token stops working after withdrawal", status == 401, f"got {status}")

status, _ = call("POST", "/api/v1/pings", {"pings": pings}, token=token)
check("no more points can be uploaded after withdrawal", status == 401, f"got {status}")

# ---------------------------------------------------------------- result
print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
