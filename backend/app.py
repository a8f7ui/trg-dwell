"""
The What Your Phone Knows backend.

Route groups, and who can reach them:

  /api/v1/...          The participant's own phone. Authenticated by a device
                       token. Can only ever touch that participant's own data.
  /api/instructor/...  The teaching team. Requires a login. Can see participant
                       movement and the whole-course aggregate.
  /                    The instructor dashboard (static files).

The separation is deliberate and worth stating plainly: a participant sees only
themselves, and instructors cannot see anything a participant was not told about
on the consent screen.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, request, send_from_directory, session

from . import analysis, auth, config, db
from .analysis import Point

DASHBOARD_DIR = config.BASE_DIR / "dashboard"

app = Flask(__name__, static_folder=None)
app.secret_key = config.SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # JavaScript cannot read the login cookie
    SESSION_COOKIE_SAMESITE="Lax",  # limits cross-site request forgery
    # Once served over HTTPS, the browser must never send the login cookie over
    # plain HTTP. Off locally, because it would break logging in over http://.
    SESSION_COOKIE_SECURE=config.SESSION_COOKIE_SECURE,
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,   # reject absurdly large uploads
)


def get_conn():
    conn = db.connect()
    db.init_db(conn)
    return conn


def parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_points(conn, participant_id: str, day: str | None = None) -> list[Point]:
    sql = ("SELECT ts, lat, lon, accuracy_m, session_id, battery_pct, connection, "
           "collection_mode FROM pings WHERE participant_id = ?")
    params: list = [participant_id]
    if day:
        sql += " AND substr(ts, 1, 10) = ?"
        params.append(day)
    sql += " ORDER BY ts"
    return [
        Point(ts=parse_ts(r["ts"]), lat=r["lat"], lon=r["lon"],
              accuracy_m=r["accuracy_m"] or 0.0, session_id=r["session_id"] or "",
              battery_pct=r["battery_pct"], connection=r["connection"] or "",
              collection_mode=r["collection_mode"] or "")
        for r in conn.execute(sql, params)
    ]


def load_places(conn) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT poi_id, name, kind, lat, lon FROM places")]


def analyse_day(points: list[Point], places_ref: list[dict]) -> dict:
    """Run the full pipeline for one day and return everything the UI needs."""
    stops = analysis.detect_stops(points)
    analysis.attach_poi_context(stops, places_ref)
    clustered = analysis.cluster_places(stops)
    assessment = analysis.infer_day(points, stops, clustered)

    # Group the trail into the separate windows when the app was open, so the
    # map can draw them as distinct segments instead of joining them with a
    # straight line across a gap nobody observed.
    segments: list[list[dict]] = []
    current: list[dict] = []
    for a, b in zip(points, points[1:] + points[-1:]):
        current.append({"ts": a.ts.isoformat(), "lat": a.lat, "lon": a.lon,
                        "accuracy_m": a.accuracy_m})
        if (b.ts - a.ts).total_seconds() > config.STOP_MAX_GAP_S:
            segments.append(current)
            current = []
    if current:
        segments.append(current)

    return {
        "point_count": len(points),
        "trail_segments": segments,
        "stops": [s.as_dict() for s in stops],
        "places": [p.as_dict() for p in clustered],
        "assessment": assessment,
    }


def days_for(conn, participant_id: str) -> list[str]:
    return [r["d"] for r in conn.execute(
        "SELECT DISTINCT substr(ts, 1, 10) AS d FROM pings "
        "WHERE participant_id = ? ORDER BY d", (participant_id,))]


# ==========================================================================
# Participant API — a phone, acting for itself only
# ==========================================================================

@app.post("/api/v1/participants")
def register_participant():
    """
    Register a device at the moment consent is given.

    The body carries no name, email or phone number, because the server has
    nowhere to put them.
    """
    body = request.get_json(silent=True) or {}
    if not body.get("consent_version") or not body.get("consented_at"):
        return jsonify({"error": "Registration requires a recorded consent."}), 400

    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) AS n FROM participants").fetchone()["n"]
    participant_id = f"p_{n + 1:03d}_{secrets.token_hex(4)}"
    token, token_hash = auth.new_participant_token()

    conn.execute(
        "INSERT INTO participants (participant_id, display_label, device_model, "
        "os_name, os_version, screen_w, screen_h, timezone, language, joined_at, "
        "consent_version, consented_at, token_hash) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (participant_id, f"Participant {n + 1:02d}", body.get("device_model"),
         body.get("os_name"), body.get("os_version"), body.get("screen_w"),
         body.get("screen_h"), body.get("timezone"), body.get("language"),
         db.now_iso(), body.get("consent_version"), body.get("consented_at"),
         token_hash),
    )
    conn.commit()
    db.audit(conn, participant_id, "consent_given", body.get("consent_version", ""))
    conn.close()

    return jsonify({"participant_id": participant_id, "token": token}), 201


@app.post("/api/v1/pings")
def upload_pings():
    """Receive a batch of location points from the phone that owns the token."""
    conn = get_conn()
    participant_id = auth.participant_from_request(conn)
    if not participant_id:
        conn.close()
        return jsonify({"error": "Unknown or missing device token."}), 401

    body = request.get_json(silent=True) or {}
    points = body.get("pings", [])
    if not isinstance(points, list):
        conn.close()
        return jsonify({"error": "Expected a list of pings."}), 400

    received = db.now_iso()
    rows = []
    for p in points:
        try:
            mode = p.get("collection_mode")
            rows.append((participant_id, p.get("session_id"), parse_ts(p["ts"]).isoformat(),
                         float(p["lat"]), float(p["lon"]),
                         float(p.get("accuracy_m") or 0), p.get("battery_pct"),
                         p.get("connection"),
                         mode if mode in ("background", "foreground") else None,
                         received))
        except (KeyError, TypeError, ValueError):
            continue    # skip malformed points rather than failing the batch

    conn.executemany(
        "INSERT INTO pings (participant_id, session_id, ts, lat, lon, accuracy_m, "
        "battery_pct, connection, collection_mode, received_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("UPDATE participants SET last_seen_at = ? WHERE participant_id = ?",
                 (received, participant_id))
    conn.commit()
    conn.close()
    return jsonify({"accepted": len(rows), "rejected": len(points) - len(rows)}), 201


@app.get("/api/v1/me/reveal")
def my_reveal():
    """The daily reveal, for the phone that owns the token and nobody else."""
    conn = get_conn()
    participant_id = auth.participant_from_request(conn)
    if not participant_id:
        conn.close()
        return jsonify({"error": "Unknown or missing device token."}), 401

    all_days = days_for(conn, participant_id)
    day = request.args.get("day") or (all_days[-1] if all_days else None)
    if not day:
        conn.close()
        return jsonify({"error": "No data collected yet."}), 404

    places_ref = load_places(conn)
    today = analyse_day(load_points(conn, participant_id, day), places_ref)

    prior = []
    for d in all_days:
        if d >= day:
            break
        prior.append(analyse_day(load_points(conn, participant_id, d), places_ref))

    day_index = all_days.index(day) if day in all_days else 0
    conn.close()

    return jsonify({
        "participant_id": participant_id,
        "day": day,
        "day_number": day_index + 1,
        "days_available": all_days,
        **today,
        "comparison": analysis.compare_with_prior(today, prior),
        "agency_step": analysis.agency_step(day_index),
    })


@app.post("/api/v1/me/withdraw")
def withdraw():
    """
    One tap: stop collecting, and delete everything already collected.

    This is a real delete, not a flag. After this call the server holds no
    location data for the caller, and the audit log records that it happened.
    """
    conn = get_conn()
    participant_id = auth.participant_from_request(conn)
    if not participant_id:
        conn.close()
        return jsonify({"error": "Unknown or missing device token."}), 401

    deleted = db.delete_participant(conn, participant_id, actor=participant_id)
    conn.close()
    return jsonify({
        "withdrawn": True,
        "participant_id": participant_id,
        "location_points_deleted": deleted,
        "message": (f"Your data has been deleted: {deleted} location points removed. "
                    f"Collection has stopped. Nothing about you remains on the server."),
    })


# ==========================================================================
# Instructor API — requires login
# ==========================================================================

@app.post("/api/instructor/login")
def instructor_login():
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    ok = auth.check_instructor(conn, body.get("username", ""), body.get("password", ""))
    if ok:
        session["instructor"] = body["username"]
        db.audit(conn, body["username"], "instructor_login")
    conn.close()
    if not ok:
        return jsonify({"error": "Incorrect username or password."}), 401
    return jsonify({"ok": True, "username": session["instructor"]})


@app.post("/api/instructor/logout")
def instructor_logout():
    session.pop("instructor", None)
    return jsonify({"ok": True})


@app.get("/api/instructor/session")
def instructor_session():
    return jsonify({"logged_in": bool(session.get("instructor")),
                    "username": session.get("instructor")})


@app.get("/api/instructor/participants")
@auth.instructor_required
def list_participants():
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.participant_id, p.display_label, p.device_model, p.os_name,
               p.os_version, p.timezone, p.language, p.joined_at, p.last_seen_at,
               COUNT(g.ping_id) AS ping_count,
               MIN(g.ts) AS first_ping, MAX(g.ts) AS last_ping,
               COUNT(DISTINCT substr(g.ts, 1, 10)) AS day_count
        FROM participants p LEFT JOIN pings g USING (participant_id)
        GROUP BY p.participant_id ORDER BY p.participant_id
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/instructor/participant/<participant_id>/day/<day>")
@auth.instructor_required
def participant_day(participant_id: str, day: str):
    conn = get_conn()
    places_ref = load_places(conn)
    all_days = days_for(conn, participant_id)
    today = analyse_day(load_points(conn, participant_id, day), places_ref)
    prior = [analyse_day(load_points(conn, participant_id, d), places_ref)
             for d in all_days if d < day]
    day_index = all_days.index(day) if day in all_days else 0
    conn.close()
    return jsonify({
        "participant_id": participant_id, "day": day,
        "days_available": all_days, **today,
        "comparison": analysis.compare_with_prior(today, prior),
        "agency_step": analysis.agency_step(day_index),
    })


@app.get("/api/instructor/participant/<participant_id>/week")
@auth.instructor_required
def participant_week(participant_id: str):
    """The whole course for one participant: every day, plus what recurs."""
    conn = get_conn()
    places_ref = load_places(conn)
    all_days = days_for(conn, participant_id)

    per_day, all_stops, all_points = [], [], []
    for d in all_days:
        pts = load_points(conn, participant_id, d)
        all_points.extend(pts)
        stops = analysis.detect_stops(pts)
        analysis.attach_poi_context(stops, places_ref)
        all_stops.extend(stops)
        clustered = analysis.cluster_places(stops)
        per_day.append({
            "day": d,
            "point_count": len(pts),
            "stop_count": len(stops),
            "places": [p.as_dict() for p in clustered],
            "assessment": analysis.infer_day(pts, stops, clustered),
        })

    # Pooling stops across the whole week is what exposes a routine: the places
    # somebody returns to, day after day.
    week_places = analysis.cluster_places(all_stops)
    recurring = [p.as_dict() for p in week_places if len(p.days) >= 2]
    week_assessment = analysis.infer_day(all_points, all_stops, week_places)
    conn.close()

    return jsonify({
        "participant_id": participant_id,
        "days": all_days,
        "per_day": per_day,
        "week_places": [p.as_dict() for p in week_places],
        "recurring_places": recurring,
        "week_assessment": week_assessment,
        "summary": (
            f"Across {len(all_days)} day(s), {len(week_places)} distinct places were "
            f"observed, {len(recurring)} of them on more than one day. Places somebody "
            f"returns to repeatedly are what turn scattered dots into a routine."
        ),
    })


@app.get("/api/instructor/aggregate")
@auth.instructor_required
def aggregate():
    """Whole-course hex map, with k-anonymity suppression."""
    k = request.args.get("k", type=int)
    resolution = request.args.get("resolution", type=int)
    day = request.args.get("day")

    conn = get_conn()
    sql = "SELECT participant_id, lat, lon FROM pings"
    params: list = []
    if day:
        sql += " WHERE substr(ts, 1, 10) = ?"
        params.append(day)
    rows = [dict(r) for r in conn.execute(sql, params)]
    total_participants = conn.execute(
        "SELECT COUNT(*) AS n FROM participants").fetchone()["n"]
    conn.close()

    result = analysis.hex_aggregate(rows, resolution=resolution, k=k)
    result["total_pings"] = len(rows)
    result["total_participants"] = total_participants
    result["day"] = day
    return jsonify(result)


@app.get("/api/instructor/live")
def live():
    """
    Where participants were at a given moment.

    `at` drives a replay clock, so the same endpoint powers both a live view
    during a real course and a scrubbable replay of a finished one.
    """
    if not session.get("instructor"):
        return jsonify({"error": "Instructor login required."}), 401

    at_raw = request.args.get("at")
    window = request.args.get("window", type=int) or config.LIVE_WINDOW_S
    at = parse_ts(at_raw) if at_raw else datetime.now(timezone.utc)
    since = at - timedelta(seconds=window)

    conn = get_conn()
    rows = conn.execute("""
        SELECT p.participant_id, p.display_label, g.lat, g.lon, g.ts, g.battery_pct,
               g.connection, g.accuracy_m
        FROM pings g JOIN participants p USING (participant_id)
        WHERE g.ts <= ? AND g.ts >= ?
        ORDER BY g.ts
    """, (at.isoformat(), since.isoformat())).fetchall()
    conn.close()

    # Keep only each participant's most recent point inside the window.
    latest: dict[str, dict] = {}
    for r in rows:
        latest[r["participant_id"]] = {
            "participant_id": r["participant_id"],
            "label": r["display_label"],
            "lat": r["lat"], "lon": r["lon"], "ts": r["ts"],
            "battery_pct": r["battery_pct"], "connection": r["connection"],
            "accuracy_m": r["accuracy_m"],
            "age_seconds": round((at - parse_ts(r["ts"])).total_seconds()),
        }

    return jsonify({
        "at": at.isoformat(),
        "window_seconds": window,
        "visible": list(latest.values()),
        "visible_count": len(latest),
    })


@app.get("/api/instructor/monitoring")
@auth.instructor_required
def monitoring():
    """
    Throughput and totals.

    Like the live map, this accepts `at`, so during a replay the figures
    describe the moment being replayed rather than right now. With no `at` it
    reports on the present, which is what a live course wants.
    """
    at_raw = request.args.get("at")
    window = request.args.get("window", type=int) or 300
    at = parse_ts(at_raw) if at_raw else datetime.now(timezone.utc)
    since = at - timedelta(seconds=window)

    conn = get_conn()
    totals = conn.execute(
        "SELECT COUNT(*) AS pings, COUNT(DISTINCT participant_id) AS people, "
        "MIN(ts) AS first_ts, MAX(ts) AS last_ts FROM pings").fetchone()
    participants = conn.execute(
        "SELECT COUNT(*) AS n FROM participants").fetchone()["n"]

    recent = conn.execute(
        "SELECT COUNT(*) AS n, COUNT(DISTINCT participant_id) AS people FROM pings "
        "WHERE ts <= ? AND ts >= ?", (at.isoformat(), since.isoformat())).fetchone()

    span_days = conn.execute(
        "SELECT COUNT(DISTINCT substr(ts,1,10)) AS n FROM pings").fetchone()["n"]
    conn.close()

    return jsonify({
        "at": at.isoformat(),
        "window_seconds": window,
        "participants_registered": participants,
        "participants_with_data": totals["people"] or 0,
        "participants_active_in_window": recent["people"] or 0,
        "total_pings": totals["pings"] or 0,
        "days_of_data": span_days or 0,
        "first_ping": totals["first_ts"],
        "last_ping": totals["last_ts"],
        "pings_in_window": recent["n"] or 0,
        "pings_per_second": round((recent["n"] or 0) / window, 3),
        "k_anonymity_threshold": config.K_ANONYMITY_THRESHOLD,
        "retention_days": config.RETENTION_DAYS,
    })


@app.post("/api/instructor/wipe")
@auth.instructor_required
def wipe():
    """Teardown control. Requires typing the confirmation phrase."""
    body = request.get_json(silent=True) or {}
    if body.get("confirm") != "DELETE ALL DATA":
        return jsonify({
            "error": "Confirmation phrase required.",
            "hint": 'Send {"confirm": "DELETE ALL DATA"} to proceed.',
        }), 400
    conn = get_conn()
    result = db.wipe_all_data(conn, actor=session["instructor"])
    conn.close()
    return jsonify({"wiped": True, **result})


@app.get("/api/instructor/audit")
@auth.instructor_required
def audit_log():
    conn = get_conn()
    rows = conn.execute(
        "SELECT ts, actor, action, detail FROM audit_log ORDER BY id DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ==========================================================================
# Static dashboard + health
# ==========================================================================

@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/")
def index():
    return send_from_directory(DASHBOARD_DIR, "index.html")


@app.get("/<path:filename>")
def dashboard_files(filename: str):
    return send_from_directory(DASHBOARD_DIR, filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
