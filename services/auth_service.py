"""Authentication and session management services."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import app_config

from services.errors import ConflictError, NotFoundError, ValidationError

PASSWORD_HASH_PREFIX = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dt(value) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    normalized = str(value or "").strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if not normalized:
        raise ValidationError("Invalid session timestamp")
    parsed = datetime.fromisoformat(normalized)
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _serialize_user(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "is_active": bool(row["is_active"]),
        "created_at": _iso(_parse_dt(row["created_at"])),
    }


def _hash_password(password: str, salt: bytes | None = None) -> str:
    actual_salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=actual_salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join(
        [
            PASSWORD_HASH_PREFIX,
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.b64encode(actual_salt).decode("ascii"),
            base64.b64encode(derived).decode("ascii"),
        ]
    )


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, n_value, r_value, p_value, salt_b64, digest_b64 = encoded_hash.split(
            "$", 5
        )
    except ValueError as exc:
        raise ValidationError("Invalid password hash format") from exc

    if algorithm != PASSWORD_HASH_PREFIX:
        raise ValidationError("Unsupported password hash algorithm")

    salt = base64.b64decode(salt_b64.encode("ascii"))
    expected_digest = base64.b64decode(digest_b64.encode("ascii"))
    actual_digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=int(n_value),
        r=int(r_value),
        p=int(p_value),
        dklen=len(expected_digest),
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _remember_window(remember_me: bool) -> timedelta:
    days = (
        app_config.auth_session_days_remember_me()
        if remember_me
        else app_config.auth_session_days_default()
    )
    return timedelta(days=days)


def cleanup_expired_sessions(conn):
    conn.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (_iso(_utc_now()),))


def bootstrap_admin_if_needed(conn):
    count_row = conn.execute("SELECT COUNT(*) AS user_count FROM users").fetchone()
    if int(count_row["user_count"]) > 0:
        return False

    username = app_config.auth_bootstrap_admin_username()
    password = app_config.auth_bootstrap_admin_password()
    if not username or not password:
        return False

    now = _iso(_utc_now())
    conn.execute(
        """
        INSERT INTO users (username, password_hash, is_admin, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (username.strip(), _hash_password(password), True, True, now, now),
    )
    return True


def auth_bootstrap_status(conn) -> dict:
    count_row = conn.execute("SELECT COUNT(*) AS user_count FROM users").fetchone()
    has_users = int(count_row["user_count"]) > 0
    if has_users:
        return {"requires_setup": False, "message": None}
    if (
        app_config.auth_bootstrap_admin_username()
        and app_config.auth_bootstrap_admin_password()
    ):
        return {"requires_setup": False, "message": None}
    return {
        "requires_setup": True,
        "message": (
            "Authentication is enabled but no admin user exists. "
            "Set AUTH_BOOTSTRAP_ADMIN_USERNAME and AUTH_BOOTSTRAP_ADMIN_PASSWORD."
        ),
    }


def authenticate_user(conn, username: str, password: str) -> dict:
    row = conn.execute(
        """
        SELECT id, username, password_hash, is_admin, is_active, created_at
        FROM users
        WHERE LOWER(username) = LOWER(?)
        """,
        (username.strip(),),
    ).fetchone()
    if not row or not bool(row["is_active"]):
        raise ValidationError("Invalid username or password")
    if not _verify_password(password, row["password_hash"]):
        raise ValidationError("Invalid username or password")
    return _serialize_user(row)


def create_session(conn, user_id: int, remember_me: bool) -> dict:
    cleanup_expired_sessions(conn)
    token = secrets.token_urlsafe(32)
    now = _utc_now()
    expires_at = _iso(now + _remember_window(remember_me))
    now_iso = _iso(now)
    conn.execute(
        """
        INSERT INTO auth_sessions (user_id, token_hash, expires_at, remember_me, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, _token_hash(token), expires_at, remember_me, now_iso, now_iso),
    )
    return {"token": token, "expires_at": expires_at, "remember_me": remember_me}


def get_session(conn, token: str):
    cleanup_expired_sessions(conn)
    row = conn.execute(
        """
        SELECT s.id AS session_id, s.user_id, s.expires_at, s.remember_me,
               u.id AS id, u.username, u.is_admin, u.is_active, u.created_at
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
        """,
        (_token_hash(token),),
    ).fetchone()
    if not row:
        raise NotFoundError("Session not found")

    if not bool(row["is_active"]):
        conn.execute("DELETE FROM auth_sessions WHERE id = ?", (row["session_id"],))
        raise ValidationError("User is inactive")

    expires_at = _parse_dt(row["expires_at"])
    if expires_at <= _utc_now():
        conn.execute("DELETE FROM auth_sessions WHERE id = ?", (row["session_id"],))
        raise NotFoundError("Session expired")

    conn.execute(
        "UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?",
        (_iso(_utc_now()), row["session_id"]),
    )

    return {
        "user": _serialize_user(row),
        "expires_at": _iso(expires_at),
        "remember_me": bool(row["remember_me"]),
    }


def delete_session(conn, token: str):
    conn.execute(
        "DELETE FROM auth_sessions WHERE token_hash = ?", (_token_hash(token),)
    )


def delete_sessions_for_user(conn, user_id: int):
    conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))


def list_users(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, username, is_admin, is_active, created_at FROM users ORDER BY username"
    ).fetchall()
    return [_serialize_user(row) for row in rows]


def get_user(conn, user_id: int) -> dict:
    row = conn.execute(
        "SELECT id, username, is_admin, is_active, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        raise NotFoundError("User not found")
    return _serialize_user(row)


def _ensure_valid_username(username: str) -> str:
    normalized_username = username.strip()
    if not normalized_username:
        raise ValidationError("Username is required")
    if len(normalized_username) < 3:
        raise ValidationError("Username must be at least 3 characters")
    return normalized_username


def _active_admin_count(conn) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS count FROM users WHERE is_admin = ? AND is_active = ?",
        (True, True),
    ).fetchone()
    return int(row["count"])


def create_user(conn, username: str, password: str, is_admin: bool = False) -> dict:
    normalized_username = _ensure_valid_username(username)
    if len(password or "") < 8:
        raise ValidationError("Password must be at least 8 characters")
    now = _iso(_utc_now())
    try:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, is_admin, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (normalized_username, _hash_password(password), is_admin, True, now, now),
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise ConflictError("Username already exists") from exc
        raise

    row = conn.execute(
        "SELECT id, username, is_admin, is_active, created_at FROM users WHERE LOWER(username) = LOWER(?)",
        (normalized_username,),
    ).fetchone()
    return _serialize_user(row)


def update_user(
    conn, user_id: int, username: str, is_admin: bool, actor_user_id: int
) -> dict:
    user = get_user(conn, user_id)
    normalized_username = _ensure_valid_username(username)

    if user_id == actor_user_id and not is_admin:
        raise ValidationError("You cannot remove admin access from your own account")

    if user["is_admin"] and not is_admin and _active_admin_count(conn) <= 1:
        raise ValidationError("At least one active admin account is required")

    now = _iso(_utc_now())
    try:
        conn.execute(
            "UPDATE users SET username = ?, is_admin = ?, updated_at = ? WHERE id = ?",
            (normalized_username, is_admin, now, user_id),
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise ConflictError("Username already exists") from exc
        raise

    return get_user(conn, user_id)


def update_user_password(conn, user_id: int, password: str) -> dict:
    if len(password or "") < 8:
        raise ValidationError("Password must be at least 8 characters")

    user = get_user(conn, user_id)
    now = _iso(_utc_now())
    conn.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        (_hash_password(password), now, user_id),
    )
    delete_sessions_for_user(conn, user_id)
    return get_user(conn, user_id)


def update_user_status(conn, user_id: int, is_active: bool, actor_user_id: int) -> dict:
    user = get_user(conn, user_id)
    if not is_active:
        if user_id == actor_user_id:
            raise ValidationError("You cannot deactivate your own account")
        if user["is_admin"] and _active_admin_count(conn) <= 1:
            raise ValidationError("At least one active admin account is required")

    now = _iso(_utc_now())
    conn.execute(
        "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
        (is_active, now, user_id),
    )
    if not is_active:
        delete_sessions_for_user(conn, user_id)
    return get_user(conn, user_id)


def delete_user(conn, user_id: int, actor_user_id: int) -> dict:
    user = get_user(conn, user_id)
    if user_id == actor_user_id:
        raise ValidationError("You cannot delete your own account")

    if user["is_admin"] and user["is_active"] and _active_admin_count(conn) <= 1:
        raise ValidationError("At least one active admin account is required")

    delete_sessions_for_user(conn, user_id)
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return user
