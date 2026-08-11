"""
The Dwell: Privacy Lab backend.

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

import argparse
import os
import secrets
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session

from . import (analysis, assessment, auth, config, context_feed, course, db,
               environment)
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


_env_index_cache: environment.FeatureIndex | None = None


def load_environment(conn) -> environment.FeatureIndex:
    """
    Observing infrastructure, indexed once and reused.

    This is reference data about places — it never changes during a course and
    is the same for every participant — so rebuilding the index on each request
    would be pure waste.
    """
    global _env_index_cache
    if _env_index_cache is None:
        features = [
            environment.Feature(
                feature_id=r["feature_id"], kind=r["kind"], lat=r["lat"],
                lon=r["lon"], name=r["name"] or "", source=r["source"] or "")
            for r in conn.execute(
                "SELECT feature_id, kind, lat, lon, name, source "
                "FROM environment_features")
        ]
        _env_index_cache = environment.FeatureIndex(features)
    return _env_index_cache


CONTEXT_DIR = config.BASE_DIR / "data" / "context"
_context_cache: list[dict] | None = None


def load_context() -> list[dict]:
    """Area context, read once. Prepared before a course, never fetched live."""
    global _context_cache
    if _context_cache is None:
        _context_cache = context_feed.load_items(CONTEXT_DIR)
    return _context_cache


# Cohort-wide group detection, memoised for as long as the data is unchanged.
#
# Small and deliberately dumb: one entry, invalidated by a fingerprint of the
# points that went into it. There is no expiry, because there is nothing to
# expire — if the data has not changed, neither has the answer, and if it has,
# the fingerprint no longer matches. A wipe, a withdrawal or a new upload all
# change it.
_GROUP_CACHE: dict[str, object] = {"key": None, "value": None}


def _cohort_groups(all_points: dict, labels: dict) -> dict:
    key = tuple(sorted((pid, len(pts), pts[-1].ts.isoformat() if pts else "")
                       for pid, pts in all_points.items()))
    if _GROUP_CACHE["key"] != key:
        _GROUP_CACHE["value"] = assessment.detect_groups(all_points, labels)
        _GROUP_CACHE["key"] = key
    return _GROUP_CACHE["value"]


def analyse_day(points: list[Point], places_ref: list[dict],
                env_index: environment.FeatureIndex | None = None,
                day: str | None = None) -> dict:
    """Run the full pipeline for one day and return everything the UI needs."""
    stops = analysis.detect_stops(points)
    analysis.attach_poi_context(stops, places_ref)
    clustered = analysis.cluster_places(stops)
    inferred = analysis.infer_day(points, stops, clustered)
    exposure = (environment.assess_exposure(points, stops, env_index)
                if env_index else {"available": False})
    context = (context_feed.match_to_day(stops, day, load_context())
               if day else {"available": False})

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
        "assessment": inferred,
        "exposure": exposure,
        "context": context,
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
    env_index = load_environment(conn)
    today = analyse_day(load_points(conn, participant_id, day), places_ref, env_index, day)

    prior = []
    for d in all_days:
        if d >= day:
            break
        prior.append(analyse_day(load_points(conn, participant_id, d), places_ref, env_index, d))

    day_index = all_days.index(day) if day in all_days else 0

    # The participant's own points across every day so far, for the personal
    # signature. Loaded before the connection closes.
    own_points = load_points(conn, participant_id)
    conn.close()

    # Pattern of life, personal signature and anomaly all describe the
    # participant's own behaviour, so they are safe to show them. Association
    # and group analysis are deliberately absent: they would disclose other
    # participants' movements to somebody never given the right to see them.
    history = prior + [today]
    for entry, d in zip(history, all_days[:len(history)]):
        entry.setdefault("day", d)

    return jsonify({
        "participant_id": participant_id,
        "day": day,
        "day_number": day_index + 1,
        "days_available": all_days,
        **today,
        "comparison": analysis.compare_with_prior(today, prior),
        "pattern_of_life": assessment.assess_pattern_of_life(history),
        "signature": assessment.assess_signature(own_points, history),
        "anomaly": assessment.assess_anomaly(today, prior),
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
    username = body.get("username", "")
    ip = auth.client_ip()
    conn = get_conn()

    # Refuse to even check the password once there have been too many recent
    # failures. Without this, the login protecting participants' movement could
    # be guessed at indefinitely.
    wait = auth.login_blocked(conn, username, ip)
    if wait:
        db.audit(conn, username or "unknown", "login_blocked", f"from {ip}")
        conn.close()
        response = jsonify({
            "error": f"Too many failed attempts. Try again in "
                     f"{max(1, wait // 60)} minute(s).",
        })
        response.headers["Retry-After"] = str(wait)
        return response, 429

    ok = auth.check_instructor(conn, username, body.get("password", ""))
    auth.record_login_attempt(conn, username, ip, ok)

    if ok:
        session["instructor"] = username
        db.audit(conn, username, "instructor_login", f"from {ip}")
    else:
        db.audit(conn, username or "unknown", "instructor_login_failed", f"from {ip}")
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
    env_index = load_environment(conn)
    all_days = days_for(conn, participant_id)
    today = analyse_day(load_points(conn, participant_id, day), places_ref, env_index, day)
    prior = [analyse_day(load_points(conn, participant_id, d), places_ref, env_index, d)
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

    pattern = assessment.assess_pattern_of_life(per_day)

    # Association analysis is instructor-only and never reaches a participant's
    # own reveal: it is other participants' movements by implication, and only
    # instructors were disclosed as able to see those.
    others = {
        r["participant_id"]: load_points(conn, r["participant_id"])
        for r in conn.execute(
            "SELECT DISTINCT participant_id FROM pings WHERE participant_id != ?",
            (participant_id,))
    }
    labels = {
        r["participant_id"]: r["display_label"]
        for r in conn.execute("SELECT participant_id, display_label FROM participants")
    }
    associations = assessment.assess_associations(
        participant_id, all_points, others, labels)

    # Recurring small groups across the whole cohort — the thing a third party
    # watching for a week would actually notice, given participants move about
    # in groups by design.
    #
    # The answer is the same for every participant, since it describes the whole
    # cohort and is only filtered afterwards. Recomputing it once per participant
    # was doing twelve times the necessary work on the slowest thing in the
    # dashboard, which is felt most on the kind of low-powered machine somebody
    # is most likely to be demoing from.
    groups = _cohort_groups(dict(others, **{participant_id: all_points}), labels)
    groups = dict(groups)
    groups["groups"] = [g for g in groups.get("groups", [])
                        if participant_id in g["members"]]
    groups["available"] = bool(groups["groups"])
    # The narrative has to be rebuilt after filtering, or it would describe the
    # strongest group in the whole cohort rather than the strongest group this
    # participant is actually in.
    groups["narrative"] = assessment._group_narrative(groups["groups"])

    signature = assessment.assess_signature(all_points, per_day)
    conn.close()

    return jsonify({
        "participant_id": participant_id,
        "days": all_days,
        "per_day": per_day,
        "week_places": [p.as_dict() for p in week_places],
        "recurring_places": recurring,
        "week_assessment": week_assessment,
        "pattern_of_life": pattern,
        "signature": signature,
        "associations": associations,
        "groups": groups,
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

    # The timezone the course is actually running in, taken as the one most
    # participants' phones report. The dashboard formats every time in this zone
    # rather than in whatever zone the instructor's laptop happens to be set to —
    # otherwise a machine left on UTC would tell the room somebody went to dinner
    # at one in the morning.
    # Participants' own phones win: they are the ground truth for where the
    # course is actually happening. The configured location is the fallback for
    # before anybody has registered, which is exactly when a dashboard is being
    # set up and most needs to look right.
    tz_row = conn.execute(
        "SELECT timezone, COUNT(*) AS n FROM participants "
        "WHERE timezone IS NOT NULL AND timezone != '' "
        "GROUP BY timezone ORDER BY n DESC LIMIT 1").fetchone()
    location = course.get_location(conn)
    conn.close()

    return jsonify({
        "at": at.isoformat(),
        "course_timezone": (tz_row["timezone"] if tz_row
                            else location["timezone"]),
        "course_location": location,
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


@app.get("/api/instructor/environment")
@auth.instructor_required
def instructor_environment():
    """Observing infrastructure, for drawing as toggleable map overlays."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT feature_id, kind, lat, lon, name, source FROM environment_features"
    ).fetchall()
    conn.close()
    features = [
        environment.Feature(
            feature_id=r["feature_id"], kind=r["kind"], lat=r["lat"], lon=r["lon"],
            name=r["name"] or "", source=r["source"] or "").as_dict()
        for r in rows
    ]
    by_kind: dict[str, int] = {}
    for f in features:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    return jsonify({
        "features": features,
        "counts": by_kind,
        "kinds": {k: {"label": v["label"], "observes": v["observes"],
                      "operator": v["operator"], "range_m": v["range_m"]}
                  for k, v in environment.FEATURE_KINDS.items()},
    })


@app.post("/api/instructor/environment/import")
@auth.instructor_required
def import_environment():
    """
    Add observing infrastructure from an uploaded file.

    Accepts a WiGLE-style wardrive CSV export, or the project's own JSON. This
    is how a course brings in Wi-Fi and Bluetooth observations without the
    server ever querying an outside service — the instructor obtains the extract
    themselves and uploads it, so no participant coordinate ever leaves here.
    """
    body = request.get_json(silent=True) or {}
    raw = body.get("content", "")
    label = (body.get("source") or "uploaded").strip()[:40]
    replace = bool(body.get("replace_source"))

    if not raw or len(raw) > 6_000_000:
        return jsonify({"error": "Send a non-empty file smaller than 6 MB."}), 400

    features = _parse_environment_upload(raw, label)
    if not features:
        return jsonify({
            "error": "No usable rows found. Expected a WiGLE CSV export with "
                     "latitude/longitude columns, or this project's JSON format.",
        }), 400

    conn = get_conn()
    if replace:
        conn.execute("DELETE FROM environment_features WHERE source = ?", (label,))
    conn.executemany(
        "INSERT OR REPLACE INTO environment_features "
        "(feature_id, kind, lat, lon, name, source) VALUES (?,?,?,?,?,?)",
        [(f["feature_id"], f["kind"], f["lat"], f["lon"], f["name"], f["source"])
         for f in features])
    conn.commit()
    db.audit(conn, session["instructor"], "environment_imported",
             f"{len(features)} features from '{label}'")
    conn.close()

    global _env_index_cache
    _env_index_cache = None      # rebuilt on next use

    kinds: dict[str, int] = {}
    for f in features:
        kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    return jsonify({"imported": len(features), "kinds": kinds, "source": label}), 201


def _parse_environment_upload(raw: str, label: str) -> list[dict]:
    """
    Read either this project's JSON or a WiGLE CSV export.

    WiGLE's export begins with a version banner line, then a header row. Columns
    vary between versions, so latitude and longitude are located by name rather
    than by position.
    """
    import csv as _csv
    import io
    import json as _json

    text = raw.strip()
    features: list[dict] = []

    if text.startswith("["):
        try:
            for i, item in enumerate(_json.loads(text), start=1):
                lat, lon = float(item["lat"]), float(item["lon"])
                features.append({
                    "feature_id": item.get("feature_id") or f"{label}_{i:06d}",
                    "kind": item.get("kind", "wifi"),
                    "lat": round(lat, 6), "lon": round(lon, 6),
                    "name": str(item.get("name", ""))[:120],
                    "source": label,
                })
        except (ValueError, KeyError, TypeError):
            return []
        return features

    lines = text.splitlines()
    # Skip WiGLE's "WigleWifi-1.6,appRelease=..." preamble if present.
    start = 1 if lines and lines[0].lower().startswith("wiglewifi") else 0
    reader = _csv.DictReader(io.StringIO("\n".join(lines[start:])))
    if not reader.fieldnames:
        return []

    lower = {name.lower().strip(): name for name in reader.fieldnames}

    def pick(*candidates):
        for c in candidates:
            if c in lower:
                return lower[c]
        return None

    lat_col = pick("currentlatitude", "latitude", "lat", "trilat")
    lon_col = pick("currentlongitude", "longitude", "lon", "lng", "trilong")
    name_col = pick("ssid", "name", "label")
    type_col = pick("type")
    if not lat_col or not lon_col:
        return []

    for i, row in enumerate(reader, start=1):
        try:
            lat, lon = float(row[lat_col]), float(row[lon_col])
        except (TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
            continue
        rec_type = (row.get(type_col) or "").strip().upper() if type_col else ""
        kind = "wifi" if rec_type in ("", "WIFI") else (
            "wifi" if rec_type.startswith("BT") or rec_type.startswith("BLE") else "wifi")
        features.append({
            "feature_id": f"{label}_{i:06d}",
            "kind": kind,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            # Network names are shown to instructors only, and a wardrive
            # capture is a record of somebody's router rather than of a person.
            "name": (row.get(name_col) or "")[:120] if name_col else "",
            "source": label,
        })
        if len(features) > 60_000:
            break
    return features


# --------------------------------------------------------------------------
# Course location
# --------------------------------------------------------------------------
#
# Where the course is being taught, which decides where the dashboard opens and
# which timezone times are read out in. Milwaukee until somebody says otherwise.
# See backend/course.py for why geocoding here does not contradict the promise
# that participant locations are never sent anywhere.

@app.get("/api/instructor/course")
@auth.instructor_required
def get_course():
    conn = get_conn()
    location = course.get_location(conn)
    conn.close()
    return jsonify({"location": location, "timezones": course.COMMON_TIMEZONES})


@app.post("/api/instructor/course")
@auth.instructor_required
def set_course():
    body = request.get_json(silent=True) or {}
    conn = get_conn()
    try:
        if body.get("reset"):
            location = course.reset_location(conn)
            detail = "reset to default"
        else:
            location = course.set_location(
                conn,
                name=body.get("name", ""),
                lat=body.get("lat"),
                lon=body.get("lon"),
                tz_name=body.get("timezone", ""),
                zoom=body.get("zoom", 14))
            detail = f"{location['name']} ({location['lat']}, {location['lon']})"
    except course.LocationError as exc:
        conn.close()
        return jsonify({"error": str(exc)}), 400
    db.audit(conn, session["instructor"], "course_location_set", detail)
    conn.commit()
    conn.close()
    return jsonify({"location": location})


@app.get("/api/instructor/course/geocode")
@auth.instructor_required
def geocode_course():
    """Look up a place name. Instructor action, at setup, never automatic."""
    try:
        return jsonify({"results": course.geocode(request.args.get("q", ""))})
    except course.LocationError as exc:
        # 200 with an error field: this is an expected outcome an instructor
        # needs to read, not a fault in the request they made.
        return jsonify({"results": [], "error": str(exc)})


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


def in_container() -> bool:
    """
    Are we inside Docker or a similar container?

    This matters more than it looks. Inside a container, 127.0.0.1 means the
    container's own loopback, which nothing outside it can reach — not even
    with `docker run -p 5000:5000`, because the port mapping forwards to the
    container's external interface and the server is not listening there.

    The symptom is a server that says it is running, answers nothing, and gives
    the browser an empty response. There is no way to guess that from the
    outside, so it is worth detecting.
    """
    if Path("/.dockerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text()
    except OSError:
        return False
    return any(m in cgroup for m in ("docker", "kubepods", "containerd", "lxc"))


def _lan_address() -> str | None:
    """This machine's address on the network it would use to reach outward.

    Connecting a UDP socket sends no packets; it only asks the routing table
    which local address would be used, which on a laptop is its wifi address.
    """
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 53))          # nothing is sent to it
        address = probe.getsockname()[0]
        probe.close()
        return address
    except OSError:
        return None


def main(argv: list[str] | None = None) -> None:
    """
    Start the development server.

    Accepts --host and --port because those are what everybody types, having
    used every other Python web server. Silently ignoring them — as this script
    used to — produces a server bound somewhere the person did not ask for,
    while printing an address that looks like agreement.
    """
    parser = argparse.ArgumentParser(
        prog=".venv/bin/python -m backend.app",
        description="Run the Dwell: Privacy Lab server.")
    parser.add_argument(
        "--host", default=os.getenv("DWELL_BIND"),
        help="Address to listen on. Defaults to 127.0.0.1, or 0.0.0.0 inside a "
             "container, where localhost is unreachable from outside. "
             "Also settable as DWELL_BIND.")
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("DWELL_PORT", "5000")),
        help="Port to listen on (default 5000). Also settable as DWELL_PORT.")
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress the startup banner and per-request logging. Used by "
             "start.py, which has already said everything this would repeat.")
    args = parser.parse_args(argv)

    if args.quiet:
        # start.py has printed the address and the login already. Repeating it,
        # under a red warning about development servers, is noise to somebody
        # who only wants the demo running — and that warning is aimed at people
        # deploying this, who are reading docs/hosting.md rather than this line.
        #
        # Done by silencing the two things that print, rather than by setting
        # WERKZEUG_RUN_MAIN: that makes werkzeug believe it is the reloader's
        # child process, whereupon it looks for an inherited socket that does
        # not exist and dies with a KeyError.
        import logging
        import flask.cli
        flask.cli.show_server_banner = lambda *a, **k: None
        logging.getLogger("werkzeug").setLevel(logging.ERROR)

    containerised = in_container()
    host = args.host
    if host is None:
        # Localhost by default: this server has an instructor login and
        # participant data on it, and binding to every interface by accident on
        # a conference network is not a thing to do quietly.
        #
        # Inside a container that reasoning inverts. The container is already an
        # isolation boundary, nothing reaches in except a port the person
        # publishing it chose, and localhost-only means the server cannot work
        # at all. Defaulting to unreachable is not the safe option, it is the
        # broken one.
        host = "0.0.0.0" if containerised else "127.0.0.1"

    if args.quiet:
        app.run(host=host, port=args.port, debug=False)
        return

    print(f"\n  Dwell: Privacy Lab — listening on {host}:{args.port}")

    if containerised and host == "0.0.0.0":
        print("\n  Container detected, so listening on all interfaces — inside a")
        print("  container, 127.0.0.1 cannot be reached from the host even with")
        print("  a published port.")
        print(f"\n  Start the container with:  -p {args.port}:{args.port}")
        print(f"  Then open on the host:     http://127.0.0.1:{args.port}\n")
    elif host not in ("127.0.0.1", "localhost"):
        print("\n  Open this on the other device, on the same network:")
        print(f"      http://{_lan_address() or '<this machine>'}:{args.port}\n")
        print("  Anyone who can reach that address gets the login page, so do")
        print("  not leave the demo password in place on a shared network.\n")
    else:
        print(f"  Open http://127.0.0.1:{args.port} on this machine.")
        print("  Use --host 0.0.0.0 to reach it from another device.\n")

    app.run(host=host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
