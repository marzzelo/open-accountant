"""
routers/books.py — Multi-book management.

Endpoints:
  GET    /api/books                  List all accounting books
  POST   /api/books                  Create a new book (with basic seed accounts)
  POST   /api/books/select           Switch active book
  PUT    /api/books/{name}/rename    Rename a book
  DELETE /api/books/{name}           Delete a book (cannot delete active)
  GET    /api/books/{name}/backup    Download SQL dump
"""
import io
import re
import sqlite3

import app_config
from database import SCHEMA, SEED_TYPES, SEED_SUBTYPES, init_db
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()

# Basic seed accounts for new books (minimal, language-neutral)
_BASIC_ACCOUNTS = [
    # (name, type_id, subtype_id_or_None, description, initial_balance)
    ("Cash",         1, None, "Cash on hand",              0.0),
    ("Bank",         1, None, "Bank account",              0.0),
    ("Credit Card",  2, None, "Credit card",               0.0),
    ("Capital",      5, None, "Net worth / equity",        0.0),
    ("Salary",       3, None, "Employment income",         0.0),
    ("Grocery",      4, None, "Food and grocery expenses", 0.0),
]


def _safe_name(name: str) -> str:
    """Sanitize book name to safe filename (alphanumeric, dash, underscore)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", name).lower()


def _create_book_db(name: str, basic: bool = True):
    """Create a new SQLite DB with schema, seed types/subtypes and optional basic accounts."""
    db_path = app_config.get_db_path(name)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    for tid, tname in SEED_TYPES:
        conn.execute("INSERT OR IGNORE INTO types (id, name) VALUES (?, ?)", (tid, tname))
    for sid, sname, type_id in SEED_SUBTYPES:
        conn.execute(
            "INSERT OR IGNORE INTO subtypes (id, name, type_id) VALUES (?, ?, ?)",
            (sid, sname, type_id),
        )
    if basic:
        for aname, tid, stid, desc, init_bal in _BASIC_ACCOUNTS:
            conn.execute(
                "INSERT INTO accounts (name, type_id, subtype_id, description, initial_balance, balance) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (aname, tid, stid, desc, init_bal, init_bal),
            )
    conn.commit()
    conn.close()


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/books")
def list_books():
    cur = app_config.current_book()
    books = []
    for db_file in sorted(app_config.DATA_DIR.glob("*.db")):
        books.append({"name": db_file.stem, "current": db_file.stem == cur})
    return books


class CreateBookRequest(BaseModel):
    name: str
    basic_seed: bool = True


@router.post("/books")
def create_book(req: CreateBookRequest):
    safe = _safe_name(req.name)
    if not safe:
        raise HTTPException(400, "Nombre de contabilidad inválido")
    db_path = app_config.get_db_path(safe)
    if db_path.exists():
        raise HTTPException(409, f"La contabilidad '{safe}' ya existe")
    _create_book_db(safe, req.basic_seed)
    return {"ok": True, "name": safe}


class SelectBookRequest(BaseModel):
    name: str


@router.post("/books/select")
def select_book(req: SelectBookRequest):
    db_path = app_config.get_db_path(req.name)
    if not db_path.exists():
        raise HTTPException(404, f"Contabilidad '{req.name}' no encontrada")
    app_config.set_current_book(req.name)
    init_db()   # ensure schema is current
    return {"ok": True, "current": req.name}


class RenameBookRequest(BaseModel):
    new_name: str


@router.put("/books/{name}/rename")
def rename_book(name: str, req: RenameBookRequest):
    safe_new = _safe_name(req.new_name)
    if not safe_new:
        raise HTTPException(400, "Nombre inválido")
    old_path = app_config.get_db_path(name)
    new_path = app_config.get_db_path(safe_new)
    if not old_path.exists():
        raise HTTPException(404, "Contabilidad no encontrada")
    if new_path.exists():
        raise HTTPException(409, f"Ya existe una contabilidad con el nombre '{safe_new}'")
    old_path.rename(new_path)
    if app_config.current_book() == name:
        app_config.set_current_book(safe_new)
    return {"ok": True, "name": safe_new}


@router.delete("/books/{name}")
def delete_book(name: str):
    if name == app_config.current_book():
        raise HTTPException(400, "No se puede eliminar la contabilidad activa")
    db_path = app_config.get_db_path(name)
    if not db_path.exists():
        raise HTTPException(404, "Contabilidad no encontrada")
    db_path.unlink()
    return {"ok": True}


@router.get("/books/{name}/backup")
def backup_book(name: str):
    db_path = app_config.get_db_path(name)
    if not db_path.exists():
        raise HTTPException(404, "Contabilidad no encontrada")
    conn = sqlite3.connect(str(db_path))
    buf = io.StringIO()
    for line in conn.iterdump():
        buf.write(line + "\n")
    conn.close()
    return Response(
        content=buf.getvalue(),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={name}.sql"},
    )


@router.post("/books/import")
async def import_book(
    name: str          = Form(..., description="Nombre para la contabilidad importada"),
    file: UploadFile   = File(..., description="Archivo .sql generado por el respaldo"),
):
    """Restore a previously backed-up SQL file into a new accounting book."""
    safe = _safe_name(name)
    if not safe:
        raise HTTPException(400, "Nombre de contabilidad inválido")

    db_path = app_config.get_db_path(safe)
    if db_path.exists():
        raise HTTPException(409, f"Ya existe una contabilidad con el nombre '{safe}'")

    content = await file.read()
    try:
        sql = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "El archivo no es texto UTF-8 válido")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(sql)
        conn.commit()
    except sqlite3.Error as e:
        conn.close()
        db_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Error al ejecutar SQL: {e}")
    finally:
        conn.close()

    # Verify the imported DB has expected tables
    check = sqlite3.connect(str(db_path))
    tables = {r[0] for r in check.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    check.close()
    expected = {"accounts", "transactions", "types", "subtypes"}
    if not expected.issubset(tables):
        db_path.unlink(missing_ok=True)
        raise HTTPException(400, f"El SQL no contiene las tablas requeridas: {expected - tables}")

    return {"ok": True, "name": safe}
