"""
routers/types.py — Account types (read-only; seeded at startup).
"""
from fastapi import APIRouter, HTTPException
from database import get_db
from models import TypeOut

router = APIRouter()


@router.get("/types", response_model=list[TypeOut])
def list_types():
    with get_db() as conn:
        rows = conn.execute("SELECT id, name FROM types ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@router.get("/types/{type_id}", response_model=TypeOut)
def get_type(type_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT id, name FROM types WHERE id = ?", (type_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Type not found")
    return dict(row)
