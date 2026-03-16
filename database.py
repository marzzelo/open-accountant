"""
database.py — SQLite connection, schema, seed data, and balance helpers.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# DB_PATH is now dynamic — resolved via app_config at runtime

# Account types where DEBIT increases the balance (normal debit balance)
DEBIT_NORMAL = {1, 4}  # 1=Activo, 4=Gasto

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS types (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS subtypes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
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
    balance         REAL NOT NULL DEFAULT 0.0,
    properties      TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    debit_account  INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    credit_account INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount         REAL NOT NULL CHECK(amount > 0),
    description    TEXT NOT NULL DEFAULT '',
    date           TEXT NOT NULL DEFAULT (datetime('now')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_preferences (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tx_debit  ON transactions(debit_account);
CREATE INDEX IF NOT EXISTS idx_tx_credit ON transactions(credit_account);
CREATE INDEX IF NOT EXISTS idx_tx_date   ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_acc_type  ON accounts(type_id);
"""

SEED_TYPES = [
    (1, "Asset"),
    (2, "Liability"),
    (3, "Income"),
    (4, "Expense"),
    (5, "Equity"),
]

SEED_SUBTYPES = [
    # Asset
    (1, "Current Asset", 1),
    (2, "Bank", 1),
    (3, "Investments", 1),
    (4, "Fixed Asset", 1),
    # Liability
    (5, "Current Liability", 2),
    (6, "Long-term Debt", 2),
    # Income
    (7, "Salary", 3),
    (8, "Other Income", 3),
    (9, "Interest", 3),
    (10, "Dividends", 3),
    # Expense
    (11, "Automobile", 4),
    (12, "Groceries", 4),
    (13, "Housing", 4),
    (14, "Taxes", 4),
    (15, "Utilities", 4),
    (16, "Entertainment", 4),
    (17, "Current Expenses", 4),
    # Equity
    (18, "Net Worth", 5),
]

# (name, type_id, subtype_id, description, initial_balance)
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


@contextmanager
def get_db():
    import app_config

    conn = sqlite3.connect(str(app_config.get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def balance_delta(type_id: int, role: str, amount: float) -> float:
    """Return the signed delta to apply to account.balance for a transaction."""
    if type_id in DEBIT_NORMAL:
        return amount if role == "debit" else -amount
    else:
        return -amount if role == "debit" else amount


def compute_filtered_balance(
    conn,
    account_id: int,
    type_id: int,
    initial_balance: float,
    from_date: str,
    to_date: str,
) -> float:
    """Recalculate account balance for a date range."""
    row = conn.execute(
        """
        SELECT
            COALESCE(SUM(CASE WHEN debit_account  = ? THEN amount ELSE 0 END), 0) AS total_debit,
            COALESCE(SUM(CASE WHEN credit_account = ? THEN amount ELSE 0 END), 0) AS total_credit
        FROM transactions
        WHERE (debit_account = ? OR credit_account = ?)
          AND date BETWEEN ? AND ?
        """,
        (account_id, account_id, account_id, account_id, from_date, to_date),
    ).fetchone()

    td, tc = row["total_debit"], row["total_credit"]
    if type_id in DEBIT_NORMAL:
        return initial_balance + td - tc
    else:
        return initial_balance - td + tc


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
            DO UPDATE SET value = excluded.value, updated_at = datetime('now')
            """,
            (key, _serialize_preference(value)),
        )
    return get_user_preferences(conn)


def init_db():
    import app_config

    app_config.get_db_path().parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(SCHEMA)
        for tid, name in SEED_TYPES:
            conn.execute(
                "INSERT OR IGNORE INTO types (id, name) VALUES (?, ?)", (tid, name)
            )
        for sid, name, type_id in SEED_SUBTYPES:
            conn.execute(
                "INSERT OR IGNORE INTO subtypes (id, name, type_id) VALUES (?, ?, ?)",
                (sid, name, type_id),
            )
        count = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        if count == 0:
            for name, tid, stid, desc, init_bal in SEED_ACCOUNTS:
                conn.execute(
                    """INSERT INTO accounts
                       (name, type_id, subtype_id, description, initial_balance, balance)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (name, tid, stid, desc, init_bal, init_bal),
                )
