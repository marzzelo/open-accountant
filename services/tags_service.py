"""Tag service functions for CRUD and transaction assignment."""

from typing import Iterable

from database import ci_order_sql, is_unique_violation
from models import TagOut, TagSummary
from services.errors import ConflictError, NotFoundError, ValidationError
from services.helpers import require_row, serialize_temporal_value

DEFAULT_TAG_COLOR = "#3B82F6"


def normalize_tag_ids(tag_ids: Iterable[int] | None) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()

    for raw_tag_id in tag_ids or []:
        try:
            tag_id = int(raw_tag_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Invalid tag id") from exc

        if tag_id <= 0:
            raise ValidationError("Invalid tag id")
        if tag_id in seen:
            continue
        seen.add(tag_id)
        normalized.append(tag_id)

    return normalized


def build_transaction_tag_filter(
    tx_alias: str, tag_ids: Iterable[int] | None
) -> tuple[str, list[int]]:
    normalized = normalize_tag_ids(tag_ids)
    if not normalized:
        return "", []

    placeholders = ",".join("?" for _ in normalized)
    return (
        f"EXISTS (SELECT 1 FROM transaction_tags tt "
        f"WHERE tt.transaction_id = {tx_alias}.id AND tt.tag_id IN ({placeholders}))",
        normalized,
    )


def _row_to_tag_summary(row) -> TagSummary:
    return TagSummary(id=row["id"], name=row["name"], color=row["color"])


def _row_to_tag_out(row) -> TagOut:
    return TagOut(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        color=row["color"],
        created_at=serialize_temporal_value(row["created_at"]),
        updated_at=serialize_temporal_value(row["updated_at"]),
        transaction_count=row["transaction_count"],
    )


def _ensure_tag_ids_exist(conn, tag_ids: list[int]):
    if not tag_ids:
        return

    placeholders = ",".join("?" for _ in tag_ids)
    rows = conn.execute(
        f"SELECT id FROM tags WHERE id IN ({placeholders})",
        tag_ids,
    ).fetchall()
    found = {row["id"] for row in rows}
    missing = [tag_id for tag_id in tag_ids if tag_id not in found]
    if missing:
        raise NotFoundError(f"Tag not found: {missing[0]}")


def list_tags(conn) -> list[TagOut]:
    order_sql = ci_order_sql(conn, "t.name")
    rows = conn.execute(
        f"""
        SELECT t.id, t.user_id, t.name, t.color, t.created_at, t.updated_at,
               COUNT(tt.transaction_id) AS transaction_count
        FROM tags t
        LEFT JOIN transaction_tags tt ON tt.tag_id = t.id
        GROUP BY t.id
        ORDER BY {order_sql}, t.id
        """
    ).fetchall()
    return [_row_to_tag_out(row) for row in rows]


def get_tag(conn, tag_id: int) -> TagOut:
    row = require_row(
        conn,
        """
        SELECT t.id, t.user_id, t.name, t.color, t.created_at, t.updated_at,
               COUNT(tt.transaction_id) AS transaction_count
        FROM tags t
        LEFT JOIN transaction_tags tt ON tt.tag_id = t.id
        WHERE t.id = ?
        GROUP BY t.id
        """,
        (tag_id,),
        "Tag not found",
        NotFoundError,
    )
    return _row_to_tag_out(row)


def create_tag(conn, data) -> TagOut:
    try:
        row = conn.execute(
            "INSERT INTO tags (user_id, name, color) VALUES (?, ?, ?) RETURNING id",
            (
                data.user_id,
                data.name.strip(),
                (data.color or DEFAULT_TAG_COLOR).upper(),
            ),
        )
    except Exception as exc:
        if not is_unique_violation(exc):
            raise
        raise ConflictError("A tag with that name already exists") from exc

    return get_tag(conn, row.fetchone()["id"])


def update_tag(conn, tag_id: int, data) -> TagOut:
    current = require_row(
        conn,
        "SELECT id, user_id, name, color FROM tags WHERE id = ?",
        (tag_id,),
        "Tag not found",
        NotFoundError,
    )
    next_name = data.name.strip() if data.name is not None else current["name"]
    next_color = (data.color or current["color"] or DEFAULT_TAG_COLOR).upper()
    next_user_id = data.user_id if data.user_id is not None else current["user_id"]

    try:
        conn.execute(
            """
            UPDATE tags
            SET user_id = ?, name = ?, color = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (next_user_id, next_name, next_color, tag_id),
        )
    except Exception as exc:
        if not is_unique_violation(exc):
            raise
        raise ConflictError("A tag with that name already exists") from exc

    return get_tag(conn, tag_id)


def delete_tag(conn, tag_id: int):
    require_row(
        conn,
        "SELECT id FROM tags WHERE id = ?",
        (tag_id,),
        "Tag not found",
        NotFoundError,
    )
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))


def replace_transaction_tags(conn, tx_id: int, tag_ids: Iterable[int] | None):
    normalized = normalize_tag_ids(tag_ids)
    _ensure_tag_ids_exist(conn, normalized)

    conn.execute("DELETE FROM transaction_tags WHERE transaction_id = ?", (tx_id,))
    if not normalized:
        return

    conn.executemany(
        "INSERT INTO transaction_tags (transaction_id, tag_id) VALUES (?, ?)",
        [(tx_id, tag_id) for tag_id in normalized],
    )


def get_transaction_tags_map(
    conn, tx_ids: Iterable[int]
) -> dict[int, list[TagSummary]]:
    normalized_tx_ids = [int(tx_id) for tx_id in tx_ids if tx_id is not None]
    if not normalized_tx_ids:
        return {}

    placeholders = ",".join("?" for _ in normalized_tx_ids)
    order_sql = ci_order_sql(conn, "t.name")
    rows = conn.execute(
        f"""
        SELECT tt.transaction_id, t.id, t.name, t.color
        FROM transaction_tags tt
        JOIN tags t ON t.id = tt.tag_id
        WHERE tt.transaction_id IN ({placeholders})
        ORDER BY {order_sql}, t.id
        """,
        normalized_tx_ids,
    ).fetchall()

    tag_map: dict[int, list[TagSummary]] = {tx_id: [] for tx_id in normalized_tx_ids}
    for row in rows:
        tag_map.setdefault(row["transaction_id"], []).append(_row_to_tag_summary(row))
    return tag_map
