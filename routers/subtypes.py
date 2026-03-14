"""
routers/subtypes.py — Subtype CRUD.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from database import get_db
from models import SubtypeIn, SubtypeUpdate, SubtypeOut

router = APIRouter()


def _row_to_out(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "type_id": row["type_id"],
        "type_name": row["type_name"],
    }


@router.get("/subtypes", response_model=list[SubtypeOut])
def list_subtypes(type_id: Optional[int] = None):
    with get_db() as conn:
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
    return [_row_to_out(r) for r in rows]


@router.get("/subtypes/{subtype_id}", response_model=SubtypeOut)
def get_subtype(subtype_id: int):
    with get_db() as conn:
        row = conn.execute(
            """SELECT s.id, s.name, s.type_id, t.name AS type_name
               FROM subtypes s JOIN types t ON s.type_id = t.id
               WHERE s.id = ?""",
            (subtype_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Subtype not found")
    return _row_to_out(row)


@router.post("/subtypes", response_model=SubtypeOut, status_code=201)
def create_subtype(data: SubtypeIn):
    with get_db() as conn:
        # Validate type exists
        if not conn.execute("SELECT 1 FROM types WHERE id = ?", (data.type_id,)).fetchone():
            raise HTTPException(400, f"Type {data.type_id} does not exist")
        try:
            cur = conn.execute(
                "INSERT INTO subtypes (name, type_id) VALUES (?, ?)",
                (data.name.strip(), data.type_id),
            )
            sid = cur.lastrowid
        except Exception as e:
            raise HTTPException(409, f"Subtype already exists: {e}")
        row = conn.execute(
            """SELECT s.id, s.name, s.type_id, t.name AS type_name
               FROM subtypes s JOIN types t ON s.type_id = t.id WHERE s.id = ?""",
            (sid,),
        ).fetchone()
    return _row_to_out(row)


@router.put("/subtypes/{subtype_id}", response_model=SubtypeOut)
def update_subtype(subtype_id: int, data: SubtypeUpdate):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM subtypes WHERE id = ?", (subtype_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Subtype not found")
        name = data.name.strip() if data.name else row["name"]
        type_id = data.type_id if data.type_id else row["type_id"]
        conn.execute(
            "UPDATE subtypes SET name = ?, type_id = ? WHERE id = ?",
            (name, type_id, subtype_id),
        )
        row = conn.execute(
            """SELECT s.id, s.name, s.type_id, t.name AS type_name
               FROM subtypes s JOIN types t ON s.type_id = t.id WHERE s.id = ?""",
            (subtype_id,),
        ).fetchone()
    return _row_to_out(row)


@router.delete("/subtypes/{subtype_id}", status_code=204)
def delete_subtype(subtype_id: int):
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM subtypes WHERE id = ?", (subtype_id,)).fetchone():
            raise HTTPException(404, "Subtype not found")
        in_use = conn.execute(
            "SELECT COUNT(*) FROM accounts WHERE subtype_id = ?", (subtype_id,)
        ).fetchone()[0]
        if in_use:
            raise HTTPException(409, f"Subtype is used by {in_use} account(s)")
        conn.execute("DELETE FROM subtypes WHERE id = ?", (subtype_id,))
