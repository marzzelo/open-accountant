"""Book management service functions."""

import io
import re
import sqlite3

import app_config
from database import SCHEMA, SEED_SUBTYPES, SEED_TYPES, init_db

from services.errors import ConflictError, NotFoundError, ValidationError

BASIC_ACCOUNTS = [
    ("Cash", 1, None, "Cash on hand", 0.0),
    ("Bank", 1, None, "Bank account", 0.0),
    ("Credit Card", 2, None, "Credit card", 0.0),
    ("Capital", 5, None, "Net worth / equity", 0.0),
    ("Salary", 3, None, "Employment income", 0.0),
    ("Grocery", 4, None, "Food and grocery expenses", 0.0),
]


def safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", name).lower()


def create_book_db(name: str, basic: bool = True):
    db_path = app_config.get_db_path(name)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    for type_id, type_name in SEED_TYPES:
        conn.execute(
            "INSERT OR IGNORE INTO types (id, name) VALUES (?, ?)",
            (type_id, type_name),
        )
    for subtype_id, subtype_name, type_id in SEED_SUBTYPES:
        conn.execute(
            "INSERT OR IGNORE INTO subtypes (id, name, type_id) VALUES (?, ?, ?)",
            (subtype_id, subtype_name, type_id),
        )
    if basic:
        for (
            account_name,
            type_id,
            subtype_id,
            description,
            initial_balance,
        ) in BASIC_ACCOUNTS:
            conn.execute(
                "INSERT INTO accounts (name, type_id, subtype_id, description, initial_balance) "
                "VALUES (?, ?, ?, ?, ?)",
                (account_name, type_id, subtype_id, description, initial_balance),
            )
    conn.commit()
    conn.close()


def list_books() -> list[dict[str, object]]:
    current = app_config.current_book()
    return [
        {"name": db_file.stem, "current": db_file.stem == current}
        for db_file in sorted(app_config.DATA_DIR.glob("*.db"))
    ]


def create_book(name: str, basic_seed: bool = True) -> dict:
    safe = safe_name(name)
    if not safe:
        raise ValidationError("Nombre de contabilidad invalido")
    db_path = app_config.get_db_path(safe)
    if db_path.exists():
        raise ConflictError(f"La contabilidad '{safe}' ya existe")
    create_book_db(safe, basic_seed)
    return {"ok": True, "name": safe}


def select_book(name: str) -> dict:
    db_path = app_config.get_db_path(name)
    if not db_path.exists():
        raise NotFoundError(f"Contabilidad '{name}' no encontrada")
    app_config.set_current_book(name)
    init_db()
    return {"ok": True, "current": name}


def rename_book(name: str, new_name: str) -> dict:
    safe_new = safe_name(new_name)
    if not safe_new:
        raise ValidationError("Nombre invalido")
    old_path = app_config.get_db_path(name)
    new_path = app_config.get_db_path(safe_new)
    if not old_path.exists():
        raise NotFoundError("Contabilidad no encontrada")
    if new_path.exists():
        raise ConflictError(f"Ya existe una contabilidad con el nombre '{safe_new}'")
    old_path.rename(new_path)
    if app_config.current_book() == name:
        app_config.set_current_book(safe_new)
    return {"ok": True, "name": safe_new}


def delete_book(name: str) -> dict:
    if name == app_config.current_book():
        raise ValidationError("No se puede eliminar la contabilidad activa")
    db_path = app_config.get_db_path(name)
    if not db_path.exists():
        raise NotFoundError("Contabilidad no encontrada")
    db_path.unlink()
    return {"ok": True}


def backup_book(name: str) -> str:
    db_path = app_config.get_db_path(name)
    if not db_path.exists():
        raise NotFoundError("Contabilidad no encontrada")
    conn = sqlite3.connect(str(db_path))
    buf = io.StringIO()
    for line in conn.iterdump():
        buf.write(line + "\n")
    conn.close()
    return buf.getvalue()


def import_book_from_sql(name: str, content: bytes) -> dict:
    safe = safe_name(name)
    if not safe:
        raise ValidationError("Nombre de contabilidad invalido")

    db_path = app_config.get_db_path(safe)
    if db_path.exists():
        raise ConflictError(f"Ya existe una contabilidad con el nombre '{safe}'")

    try:
        sql = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("El archivo no es texto UTF-8 valido") from exc

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(sql)
        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        db_path.unlink(missing_ok=True)
        raise ValidationError(f"Error al ejecutar SQL: {exc}") from exc
    finally:
        conn.close()

    check = sqlite3.connect(str(db_path))
    tables = {
        row[0]
        for row in check.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    check.close()
    expected = {"accounts", "transactions", "types", "subtypes"}
    if not expected.issubset(tables):
        db_path.unlink(missing_ok=True)
        raise ValidationError(
            f"El SQL no contiene las tablas requeridas: {expected - tables}"
        )

    return {"ok": True, "name": safe}
