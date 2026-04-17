"""PostgreSQL connection helpers and translated connection wrapper."""

from contextlib import contextmanager
from typing import Any

from db.dialect import _translate_query

try:
    import psycopg
    from psycopg.errors import IntegrityError as PsycopgIntegrityError
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    PsycopgIntegrityError = None
    dict_row = None


class DatabaseConnection:
    """Thin adapter around a psycopg connection that translates queries."""

    backend = "postgresql"

    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False

    def execute(self, query: str, params: Any = ()):
        return self._conn.execute(_translate_query(query), params)

    def executemany(self, query: str, params_seq):
        translated_query = _translate_query(query)
        with self._conn.cursor() as cursor:
            cursor.executemany(translated_query, params_seq)
            return cursor

    def executescript(self, script: str):
        for statement in (part.strip() for part in script.split(";")):
            if statement:
                self._conn.execute(statement)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def _database_url() -> str:
    import app_config

    url = app_config.database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Open Accountant requires a PostgreSQL "
            "connection URL (e.g. postgresql://user:pass@host:5432/dbname)."
        )
    return url


def connect_db() -> DatabaseConnection:
    if psycopg is None:
        raise RuntimeError(
            "PostgreSQL support requires psycopg. Install requirements.txt again."
        )

    conn = psycopg.connect(_database_url(), row_factory=dict_row)
    return DatabaseConnection(conn)


@contextmanager
def get_db():
    conn = connect_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_dep():
    """FastAPI dependency that yields a managed database connection."""
    with get_db() as conn:
        yield conn


def is_unique_violation(exc: Exception) -> bool:
    return bool(PsycopgIntegrityError and isinstance(exc, PsycopgIntegrityError))
