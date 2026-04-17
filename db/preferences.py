"""User preference persistence helpers."""

import json


def _serialize_preference(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _deserialize_preference(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def get_user_preferences(conn) -> dict:
    rows = conn.execute(
        "SELECT key, value FROM user_preferences ORDER BY key"
    ).fetchall()
    return {row["key"]: _deserialize_preference(row["value"]) for row in rows}


def update_user_preferences(conn, preferences: dict) -> dict:
    for key, value in preferences.items():
        conn.execute(
            """
            INSERT INTO user_preferences (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (key, _serialize_preference(value)),
        )
    return get_user_preferences(conn)
