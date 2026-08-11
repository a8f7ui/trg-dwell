"""
Two quite different kinds of access control.

**Instructors** log in with a username and password. Their accounts are created
from the command line — there is no sign-up page, because the only people who
should be able to see participant movement are the teaching team.

**Participants** never log in at all. Their phone is issued a random token when
it registers, and that token only ever unlocks that one participant's own data.
There is deliberately no way for a participant token to read anybody else's
information, and no participant endpoint accepts an arbitrary participant ID.

Passwords are stored as scrypt hashes. Tokens are stored as SHA-256 hashes, so
somebody who steals the database file still cannot pretend to be a participant's
phone.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import jsonify, request, session

from . import db

# scrypt cost parameters. Deliberately slow, so that guessing passwords in bulk
# is expensive.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DK_LEN = 32


# --------------------------------------------------------------------------
# Instructor passwords
# --------------------------------------------------------------------------

def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                        n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DK_LEN)
    return dk.hex(), salt.hex()


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    candidate, _ = hash_password(password, bytes.fromhex(salt_hex))
    # Constant-time comparison, so timing does not leak how much of the hash
    # matched.
    return hmac.compare_digest(candidate, password_hash)


def create_instructor(conn: sqlite3.Connection, username: str, password: str) -> None:
    pw_hash, salt = hash_password(password)
    conn.execute(
        "INSERT OR REPLACE INTO instructors (username, password_hash, salt, created_at) "
        "VALUES (?, ?, ?, ?)",
        (username, pw_hash, salt, db.now_iso()),
    )
    conn.commit()


def check_instructor(conn: sqlite3.Connection, username: str, password: str) -> bool:
    row = conn.execute(
        "SELECT password_hash, salt FROM instructors WHERE username = ?", (username,)
    ).fetchone()
    if row is None:
        # Still do the work, so that a missing username takes as long to reject
        # as a wrong password and cannot be detected by timing.
        hash_password(password)
        return False
    return verify_password(password, row["password_hash"], row["salt"])


# --------------------------------------------------------------------------
# Participant device tokens
# --------------------------------------------------------------------------

def new_participant_token() -> tuple[str, str]:
    """Return (token to give the device, hash to store)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def participant_from_request(conn: sqlite3.Connection) -> str | None:
    """
    Identify the calling phone from its bearer token.

    Returns the participant ID, or None. Note that the ID comes from the token,
    never from anything the caller supplied — so a phone cannot ask for another
    participant's data by changing a value in the request.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    row = conn.execute(
        "SELECT participant_id FROM participants WHERE token_hash = ?",
        (hash_token(header[7:].strip()),),
    ).fetchone()
    return row["participant_id"] if row else None


# --------------------------------------------------------------------------
# Route decorators
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Slowing down password guessing
# --------------------------------------------------------------------------
#
# scrypt already makes each guess cost something, but "something" is still
# thousands of attempts an hour. This login opens a map of where participants
# have been, so guessing has to be stopped rather than merely taxed.

LOCKOUT_WINDOW_SECONDS = 15 * 60
MAX_FAILURES_PER_USERNAME = 8
MAX_FAILURES_PER_IP = 25


def record_login_attempt(conn: sqlite3.Connection, username: str,
                         ip: str, ok: bool) -> None:
    conn.execute(
        "INSERT INTO login_attempts (ts, username, ip, ok) VALUES (?, ?, ?, ?)",
        (db.now_iso(), username, ip, 1 if ok else 0),
    )
    conn.commit()


def login_blocked(conn: sqlite3.Connection, username: str, ip: str) -> int:
    """
    Return the number of seconds a caller must wait, or 0 if they may try.

    Counts recent failures both for the username being targeted and for the
    source address, so neither spraying one password across many usernames nor
    hammering a single account gets very far.
    """
    since = (datetime.now(timezone.utc)
             - timedelta(seconds=LOCKOUT_WINDOW_SECONDS)).isoformat()

    by_user = conn.execute(
        "SELECT COUNT(*) AS n FROM login_attempts "
        "WHERE ok = 0 AND username = ? AND ts >= ?", (username, since)
    ).fetchone()["n"]
    by_ip = conn.execute(
        "SELECT COUNT(*) AS n FROM login_attempts "
        "WHERE ok = 0 AND ip = ? AND ts >= ?", (ip, since)
    ).fetchone()["n"]

    if by_user < MAX_FAILURES_PER_USERNAME and by_ip < MAX_FAILURES_PER_IP:
        return 0

    oldest = conn.execute(
        "SELECT MIN(ts) AS t FROM login_attempts "
        "WHERE ok = 0 AND (username = ? OR ip = ?) AND ts >= ?",
        (username, ip, since)
    ).fetchone()["t"]
    if not oldest:
        return 0
    elapsed = (datetime.now(timezone.utc)
               - datetime.fromisoformat(oldest)).total_seconds()
    return max(1, int(LOCKOUT_WINDOW_SECONDS - elapsed))


def client_ip() -> str:
    """
    The caller's address, trusting the proxy header only for its first entry.

    Hosts terminate HTTPS in front of the app, so remote_addr would otherwise be
    the proxy for every request and the per-address limit would lock out
    everybody at once.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def instructor_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("instructor"):
            return jsonify({"error": "Instructor login required."}), 401
        return fn(*args, **kwargs)
    return wrapper
