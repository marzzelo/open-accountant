"""Subtype service functions."""

from typing import Optional

from models import SubtypeIn, SubtypeOut, SubtypeUpdate

from services.errors import ConflictError, NotFoundError, ValidationError
from services.helpers import model_from_row, require_row


def row_to_out(row) -> SubtypeOut:
    return model_from_row(SubtypeOut, row)


def list_subtypes(conn, type_id: Optional[int] = None) -> list[SubtypeOut]:
    if type_id:
        rows = conn.execute(
            """SELECT s.id, s.name, s.type_id, t.name AS type_name
               FROM subtypes s JOIN types t ON s.type_id = t.id
               WHERE s.type_id = ? ORDER BY s.name""",
            (type_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT s.id, s.name, s.type_id, t.name AS type_name
               FROM subtypes s JOIN types t ON s.type_id = t.id
               ORDER BY s.type_id, s.name"""
        ).fetchall()
    return [row_to_out(row) for row in rows]


def get_subtype(conn, subtype_id: int) -> SubtypeOut:
    row = require_row(
        conn,
        """SELECT s.id, s.name, s.type_id, t.name AS type_name
           FROM subtypes s JOIN types t ON s.type_id = t.id
           WHERE s.id = ?""",
        (subtype_id,),
        "Subtype not found",
        NotFoundError,
    )
    return row_to_out(row)


def _validate_type_exists(conn, type_id: int):
    require_row(
        conn,
        "SELECT 1 FROM types WHERE id = ?",
        (type_id,),
        f"Type {type_id} does not exist",
        ValidationError,
    )


def create_subtype(conn, data: SubtypeIn) -> SubtypeOut:
    _validate_type_exists(conn, data.type_id)
    try:
        row = conn.execute(
            "INSERT INTO subtypes (name, type_id) VALUES (?, ?) RETURNING id",
            (data.name.strip(), data.type_id),
        )
    except Exception as exc:
        raise ConflictError(f"Subtype already exists: {exc}") from exc
    return get_subtype(conn, row.fetchone()["id"])


def update_subtype(conn, subtype_id: int, data: SubtypeUpdate) -> SubtypeOut:
    row = require_row(
        conn,
        "SELECT * FROM subtypes WHERE id = ?",
        (subtype_id,),
        "Subtype not found",
        NotFoundError,
    )

    name = data.name.strip() if data.name else row["name"]
    type_id = data.type_id if data.type_id else row["type_id"]
    _validate_type_exists(conn, type_id)

    try:
        conn.execute(
            "UPDATE subtypes SET name = ?, type_id = ? WHERE id = ?",
            (name, type_id, subtype_id),
        )
    except Exception as exc:
        raise ConflictError(f"Subtype already exists: {exc}") from exc
    return get_subtype(conn, subtype_id)


def delete_subtype(conn, subtype_id: int):
    require_row(
        conn,
        "SELECT 1 FROM subtypes WHERE id = ?",
        (subtype_id,),
        "Subtype not found",
        NotFoundError,
    )
    in_use = conn.execute(
        "SELECT COUNT(*) AS in_use FROM accounts WHERE subtype_id = ?", (subtype_id,)
    ).fetchone()["in_use"]
    if in_use:
        raise ConflictError(f"Subtype is used by {in_use} account(s)")
    conn.execute("DELETE FROM subtypes WHERE id = ?", (subtype_id,))
