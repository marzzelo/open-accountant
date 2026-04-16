"""
database.py — database connection, schema bootstrap, and balance helpers.
"""

import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import unquote

try:
    import psycopg
    from psycopg.errors import IntegrityError as PsycopgIntegrityError
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover
    psycopg = None
    PsycopgIntegrityError = None
    dict_row = None


DEBIT_NORMAL = {1, 4}  # 1=Asset, 4=Expense

PREFIXED_TABLES = {
    "auth_sessions",
    "projection_series",
    "transaction_tags",
    "user_preferences",
    "users",
    "transactions",
    "subtypes",
    "accounts",
    "settings",
    "types",
    "tags",
}

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    section    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (section, key)
);

CREATE TABLE IF NOT EXISTS types (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subtypes (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    type_id INTEGER NOT NULL REFERENCES types(id) ON DELETE RESTRICT,
    UNIQUE(name, type_id)
);

CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    type_id         INTEGER NOT NULL REFERENCES types(id) ON DELETE RESTRICT,
    subtype_id      INTEGER REFERENCES subtypes(id) ON DELETE SET NULL,
    description     TEXT NOT NULL DEFAULT '',
    initial_balance REAL NOT NULL DEFAULT 0.0,
    properties      TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    debit_account     INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    credit_account    INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount            REAL NOT NULL CHECK(amount > 0),
    original_amount   REAL NOT NULL CHECK(original_amount > 0),
    original_currency TEXT NOT NULL DEFAULT 'ARS',
    fx_rate           REAL NOT NULL DEFAULT 1.0 CHECK(fx_rate > 0),
    fx_source         TEXT,
    description       TEXT NOT NULL DEFAULT '',
    date              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT,
    name       TEXT NOT NULL COLLATE NOCASE UNIQUE,
    color      TEXT NOT NULL DEFAULT '#3B82F6',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transaction_tags (
    transaction_id INTEGER NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    tag_id         INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (transaction_id, tag_id)
);

CREATE TABLE IF NOT EXISTS user_preferences (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    remember_me INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projection_series (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    type           TEXT NOT NULL CHECK(type IN ('income','expense')),
    start_date     TEXT NOT NULL,
    months         INTEGER NOT NULL CHECK(months >= 1),
    enabled        INTEGER NOT NULL DEFAULT 1,
    monthly_amount REAL NOT NULL CHECK(monthly_amount > 0),
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tx_debit ON transactions(debit_account);
CREATE INDEX IF NOT EXISTS idx_tx_credit ON transactions(credit_account);
CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_acc_type ON accounts(type_id);
CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE INDEX IF NOT EXISTS idx_transaction_tags_tag ON transaction_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);
"""

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS oacc_settings (
    section     TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (section, key)
);

CREATE TABLE IF NOT EXISTS oacc_types (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS oacc_subtypes (
    id      INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name    TEXT NOT NULL,
    type_id INTEGER NOT NULL REFERENCES oacc_types(id) ON DELETE RESTRICT,
    UNIQUE(name, type_id)
);

CREATE TABLE IF NOT EXISTS oacc_accounts (
    id              INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    type_id         INTEGER NOT NULL REFERENCES oacc_types(id) ON DELETE RESTRICT,
    subtype_id      INTEGER REFERENCES oacc_subtypes(id) ON DELETE SET NULL,
    description     TEXT NOT NULL DEFAULT '',
    initial_balance DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    properties      TEXT NOT NULL DEFAULT '{}',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oacc_transactions (
    id                INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    debit_account     INTEGER NOT NULL REFERENCES oacc_accounts(id) ON DELETE RESTRICT,
    credit_account    INTEGER NOT NULL REFERENCES oacc_accounts(id) ON DELETE RESTRICT,
    amount            DOUBLE PRECISION NOT NULL CHECK(amount > 0),
    original_amount   DOUBLE PRECISION NOT NULL CHECK(original_amount > 0),
    original_currency TEXT NOT NULL DEFAULT 'ARS',
    fx_rate           DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK(fx_rate > 0),
    fx_source         TEXT,
    description       TEXT NOT NULL DEFAULT '',
    date              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oacc_tags (
    id         INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id    TEXT,
    name       TEXT NOT NULL,
    color      TEXT NOT NULL DEFAULT '#3B82F6',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oacc_transaction_tags (
    transaction_id INTEGER NOT NULL REFERENCES oacc_transactions(id) ON DELETE CASCADE,
    tag_id         INTEGER NOT NULL REFERENCES oacc_tags(id) ON DELETE CASCADE,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (transaction_id, tag_id)
);

CREATE TABLE IF NOT EXISTS oacc_user_preferences (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oacc_users (
    id            INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    username      TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oacc_auth_sessions (
    id           INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES oacc_users(id) ON DELETE CASCADE,
    token_hash   TEXT NOT NULL UNIQUE,
    expires_at   TEXT NOT NULL,
    remember_me  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oacc_projection_series (
    id             INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name           TEXT NOT NULL,
    type           TEXT NOT NULL CHECK(type IN ('income', 'expense')),
    start_date     DATE NOT NULL,
    months         INTEGER NOT NULL CHECK(months >= 1),
    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    monthly_amount DOUBLE PRECISION NOT NULL CHECK(monthly_amount > 0),
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS oacc_idx_tx_debit ON oacc_transactions(debit_account);
CREATE INDEX IF NOT EXISTS oacc_idx_tx_credit ON oacc_transactions(credit_account);
CREATE INDEX IF NOT EXISTS oacc_idx_tx_date ON oacc_transactions(date);
CREATE INDEX IF NOT EXISTS oacc_idx_acc_type ON oacc_accounts(type_id);
CREATE INDEX IF NOT EXISTS oacc_idx_tags_name ON oacc_tags(LOWER(name));
CREATE UNIQUE INDEX IF NOT EXISTS oacc_idx_tags_name_unique ON oacc_tags(LOWER(name));
CREATE INDEX IF NOT EXISTS oacc_idx_transaction_tags_tag ON oacc_transaction_tags(tag_id);
CREATE UNIQUE INDEX IF NOT EXISTS oacc_idx_users_username_unique ON oacc_users(LOWER(username));
CREATE INDEX IF NOT EXISTS oacc_idx_auth_sessions_user_id ON oacc_auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS oacc_idx_auth_sessions_expires_at ON oacc_auth_sessions(expires_at);
"""

SEED_TYPES = [
    (1, "Asset"),
    (2, "Liability"),
    (3, "Income"),
    (4, "Expense"),
    (5, "Equity"),
]

SEED_SUBTYPES = [
    (1, "Current Asset", 1),
    (2, "Bank", 1),
    (3, "Investments", 1),
    (4, "Fixed Asset", 1),
    (5, "Current Liability", 2),
    (6, "Long-term Debt", 2),
    (7, "Salary", 3),
    (8, "Other Income", 3),
    (9, "Interest", 3),
    (10, "Dividends", 3),
    (11, "Automobile", 4),
    (12, "Groceries", 4),
    (13, "Housing", 4),
    (14, "Taxes", 4),
    (15, "Utilities", 4),
    (16, "Entertainment", 4),
    (17, "Current Expenses", 4),
    (18, "Net Worth", 5),
]

SEED_ACCOUNTS = [
    ("Cash", 1, 1, "Cash on hand", 0.0),
    ("Bank", 1, 2, "Main bank account", 0.0),
    ("Digital Wallet", 1, 2, "Digital wallet", 0.0),
    ("Credit Card", 2, 5, "Credit card", 0.0),
    ("Salary", 3, 7, "Salary income", 0.0),
    ("Other Income", 3, 8, "Miscellaneous income", 0.0),
    ("Groceries", 4, 12, "Supermarket and food", 0.0),
    ("Utilities", 4, 15, "Power, water, gas, internet", 0.0),
    ("Transport", 4, 11, "Fuel and transport", 0.0),
    ("Capital", 5, 18, "Personal equity", 0.0),
]


def _prefixed_table_name(table_name: str) -> str:
    return f"oacc_{table_name}"


def _database_url() -> str:
    import app_config

    return app_config.database_url()


def backend_name(conn=None) -> str:
    if conn is not None and hasattr(conn, "backend"):
        return conn.backend

    url = _database_url().lower()
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        return "postgresql"
    return "sqlite"


def month_bucket_sql(conn, column_name: str) -> str:
    if backend_name(conn) == "postgresql":
        return f"TO_CHAR({column_name}, 'YYYY-MM')"
    return f"strftime('%Y-%m', {column_name})"


def recent_months_filter_sql(conn, column_name: str, months: int) -> str:
    if backend_name(conn) == "postgresql":
        return f"{column_name} >= date_trunc('month', CURRENT_DATE - INTERVAL '{months} months')"
    return f"{column_name} >= date('now', '-{months} months', 'start of month')"


def ci_order_sql(conn, column_name: str) -> str:
    if backend_name(conn) == "postgresql":
        return f"LOWER({column_name}), {column_name}"
    return f"{column_name} COLLATE NOCASE"


def _sqlite_path_from_url(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise ValueError(f"Unsupported sqlite URL: {url}")
    return Path(unquote(url[len("sqlite:///") :]))


def _translate_query(query: str, backend: str) -> str:
    translated = query
    if backend == "postgresql":
        translated = translated.replace("?", "%s")
        for table_name in sorted(PREFIXED_TABLES, key=len, reverse=True):
            translated = re.sub(
                rf"(?<!oacc_)\b{table_name}\b",
                _prefixed_table_name(table_name),
                translated,
            )
    return translated


class DatabaseConnection:
    def __init__(self, backend: str, conn):
        self.backend = backend
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
        return self._conn.execute(_translate_query(query, self.backend), params)

    def executemany(self, query: str, params_seq):
        translated_query = _translate_query(query, self.backend)
        if self.backend == "sqlite":
            return self._conn.executemany(translated_query, params_seq)

        with self._conn.cursor() as cursor:
            cursor.executemany(translated_query, params_seq)
            return cursor

    def executescript(self, script: str):
        if self.backend == "sqlite":
            return self._conn.executescript(script)

        for statement in (part.strip() for part in script.split(";")):
            if statement:
                self._conn.execute(statement)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def connect_db() -> DatabaseConnection:
    backend = backend_name()
    url = _database_url()

    if backend == "sqlite":
        db_path = _sqlite_path_from_url(url)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return DatabaseConnection(backend, conn)

    if psycopg is None:
        raise RuntimeError(
            "PostgreSQL support requires psycopg. Install requirements.txt again."
        )

    conn = psycopg.connect(url, row_factory=dict_row)
    return DatabaseConnection(backend, conn)


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


def is_unique_violation(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    if PsycopgIntegrityError and isinstance(exc, PsycopgIntegrityError):
        return True
    return False


def balance_delta(type_id: int, role: str, amount: float) -> float:
    if type_id in DEBIT_NORMAL:
        return amount if role == "debit" else -amount
    return -amount if role == "debit" else amount


def compute_balance(
    conn,
    account_id: int,
    type_id: int,
    initial_balance: float,
    from_date: str | None = None,
    to_date: str | None = None,
    tag_ids: list[int] | None = None,
) -> float:
    params: tuple[Any, ...] = (account_id, account_id, account_id, account_id)
    date_filter = ""
    if from_date is not None and to_date is not None:
        date_filter = "\n          AND date BETWEEN ? AND ?"
        params += (from_date, to_date)

    tag_filter = ""
    if tag_ids:
        placeholders = ",".join("?" for _ in tag_ids)
        tag_filter = (
            f"\n          AND EXISTS (\n              SELECT 1 FROM transaction_tags tt\n"
            f"              WHERE tt.transaction_id = transactions.id\n"
            f"                AND tt.tag_id IN ({placeholders})\n          )"
        )
        params += tuple(tag_ids)

    row = conn.execute(
        f"""
        SELECT
            COALESCE(SUM(CASE WHEN debit_account = ? THEN amount ELSE 0 END), 0) AS total_debit,
            COALESCE(SUM(CASE WHEN credit_account = ? THEN amount ELSE 0 END), 0) AS total_credit
        FROM transactions
        WHERE (debit_account = ? OR credit_account = ?){date_filter}{tag_filter}
        """,
        params,
    ).fetchone()

    total_debit = row["total_debit"]
    total_credit = row["total_credit"]
    if type_id in DEBIT_NORMAL:
        return initial_balance + total_debit - total_credit
    return initial_balance - total_debit + total_credit


def compute_filtered_balance(
    conn,
    account_id: int,
    type_id: int,
    initial_balance: float,
    from_date: str,
    to_date: str,
    tag_ids: list[int] | None = None,
) -> float:
    return compute_balance(
        conn, account_id, type_id, initial_balance, from_date, to_date, tag_ids
    )


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


def table_exists(conn, table_name: str) -> bool:
    if backend_name(conn) == "postgresql":
        actual_name = _prefixed_table_name(table_name)
        row = conn.execute(
            """
            SELECT 1 AS exists_flag
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = ?
            """,
            (actual_name,),
        ).fetchone()
        return bool(row)

    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return bool(row)


def table_columns(conn, table_name: str) -> list[str]:
    if backend_name(conn) == "postgresql":
        actual_name = _prefixed_table_name(table_name)
        rows = conn.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ?
            ORDER BY ordinal_position
            """,
            (actual_name,),
        ).fetchall()
        return [row["column_name"] for row in rows]

    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row["name"] for row in rows]


def _postgres_column_metadata(conn, table_name: str, column_name: str):
    return conn.execute(
        """
        SELECT is_identity, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ?
          AND column_name = ?
        """,
        (_prefixed_table_name(table_name), column_name),
    ).fetchone()


def _postgres_column_uses_sequence(row) -> bool:
    if not row:
        return False
    if row["is_identity"] == "YES":
        return True
    default = row["column_default"] or ""
    return "nextval(" in default


def _ensure_postgres_identity_column(conn, table_name: str, column_name: str = "id"):
    if backend_name(conn) != "postgresql":
        return

    row = _postgres_column_metadata(conn, table_name, column_name)
    if not row or _postgres_column_uses_sequence(row):
        return

    actual_name = _prefixed_table_name(table_name)
    conn.execute(
        f'ALTER TABLE "{actual_name}" ALTER COLUMN "{column_name}" '
        "ADD GENERATED BY DEFAULT AS IDENTITY"
    )


def _reset_postgres_sequence(conn, table_name: str, column_name: str = "id"):
    if backend_name(conn) != "postgresql":
        return

    row = _postgres_column_metadata(conn, table_name, column_name)
    if not _postgres_column_uses_sequence(row):
        return

    actual_name = _prefixed_table_name(table_name)
    next_val = conn.execute(
        f'SELECT COALESCE(MAX("{column_name}"), 0) + 1 AS next_val '
        f'FROM "{actual_name}"'
    ).fetchone()["next_val"]
    conn.execute(
        f"SELECT setval(pg_get_serial_sequence('{actual_name}', '{column_name}'), ?, false)",
        (next_val,),
    )


def _ensure_projection_series_enabled_column(conn):
    columns = set(table_columns(conn, "projection_series"))
    if "enabled" in columns:
        return

    if backend_name(conn) == "postgresql":
        actual_name = _prefixed_table_name("projection_series")
        conn.execute(
            f'ALTER TABLE "{actual_name}" ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE'
        )
        return

    conn.execute(
        "ALTER TABLE projection_series ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
    )


def init_db():
    schema = POSTGRES_SCHEMA if backend_name() == "postgresql" else SQLITE_SCHEMA
    with get_db() as conn:
        conn.executescript(schema)
        _ensure_postgres_identity_column(conn, "subtypes")
        _ensure_projection_series_enabled_column(conn)
        for type_id, type_name in SEED_TYPES:
            conn.execute(
                "INSERT INTO types (id, name) VALUES (?, ?) ON CONFLICT(id) DO NOTHING",
                (type_id, type_name),
            )
        for subtype_id, subtype_name, type_id in SEED_SUBTYPES:
            conn.execute(
                """
                INSERT INTO subtypes (id, name, type_id)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (subtype_id, subtype_name, type_id),
            )
        _reset_postgres_sequence(conn, "subtypes")

        count_row = conn.execute(
            "SELECT COUNT(*) AS account_count FROM accounts"
        ).fetchone()
        if int(count_row["account_count"]) == 0:
            for (
                name,
                type_id,
                subtype_id,
                description,
                initial_balance,
            ) in SEED_ACCOUNTS:
                conn.execute(
                    """
                    INSERT INTO accounts
                        (name, type_id, subtype_id, description, initial_balance)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (name, type_id, subtype_id, description, initial_balance),
                )
