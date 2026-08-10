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

def instructor_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("instructor"):
            return jsonify({"error": "Instructor login required."}), 401
        return fn(*args, **kwargs)
    return wrapper
