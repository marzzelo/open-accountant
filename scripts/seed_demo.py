#!/usr/bin/env python3
"""
seed_demo.py — Create a demo accounting book (data/home.db) with
               realistic but fully anonymized example data (English).

Run from the project root:
    python3 scripts/seed_demo.py [--db data/home.db] [--force]
"""
import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT   = Path(__file__).parent.parent
DB_DIR = ROOT / "data"

# ── Schema (kept in sync with database.py) ───────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS types (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subtypes (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    type_id INTEGER NOT NULL REFERENCES types(id)
);
CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    type_id         INTEGER NOT NULL REFERENCES types(id),
    subtype_id      INTEGER REFERENCES subtypes(id),
    description     TEXT,
    initial_balance REAL NOT NULL DEFAULT 0.0
);
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    description TEXT,
    amount      REAL NOT NULL,
    debit_id    INTEGER NOT NULL REFERENCES accounts(id),
    credit_id   INTEGER NOT NULL REFERENCES accounts(id)
);
"""

TYPES = [
    (1, "Asset"),
    (2, "Liability"),
    (3, "Income"),
    (4, "Expense"),
    (5, "Equity"),
]

SUBTYPES = [
    # Asset
    (1,  "Current Asset",     1),
    (2,  "Bank",              1),
    (3,  "Investments",       1),
    (4,  "Fixed Asset",       1),
    # Liability
    (5,  "Current Liability", 2),
    (6,  "Long-term Debt",    2),
    # Income
    (7,  "Salary",            3),
    (8,  "Other Income",      3),
    (9,  "Interest",          3),
    (10, "Dividends",         3),
    # Expense
    (11, "Automobile",        4),
    (12, "Groceries",         4),
    (13, "Housing",           4),
    (14, "Taxes",             4),
    (15, "Utilities",         4),
    (16, "Entertainment",     4),
    (17, "Current Expenses",  4),
    # Equity
    (18, "Net Worth",         5),
]

# (name, type_id, subtype_id, description, initial_balance)
ACCOUNTS = [
    # ── Assets ──────────────────────────────────────────────
    ("Cash",              1,  1, "Cash on hand",                     450.00),
    ("Checking Account",  1,  2, "Main checking account",          2_350.00),
    ("Savings Account",   1,  2, "High-yield savings account",     8_500.00),
    ("E-Wallet",          1,  2, "Digital payment wallet",           180.00),
    ("Investment Fund A", 1,  3, "Diversified equity fund",       12_000.00),
    # ── Liabilities ─────────────────────────────────────────
    ("Credit Card",       2,  5, "General-purpose credit card",      650.00),
    ("Personal Loan",     2,  6, "Bank personal loan",             5_000.00),
    # ── Income ──────────────────────────────────────────────
    ("Monthly Salary",    3,  7, "Employment salary",                  0.00),
    ("Freelance Income",  3,  8, "Project-based freelance work",       0.00),
    ("Fund Dividends",    3, 10, "Dividend distributions",             0.00),
    # ── Expenses ────────────────────────────────────────────
    ("Rent",              4, 13, "Monthly apartment rent",             0.00),
    ("Grocery Shopping",  4, 12, "Supermarket and food store",         0.00),
    ("Fuel",              4, 11, "Vehicle fuel",                       0.00),
    ("Electricity",       4, 15, "Electric utility bill",              0.00),
    ("Internet & Phone",  4, 15, "Telecom services bundle",            0.00),
    ("Streaming",         4, 16, "Online video / music services",      0.00),
    ("Public Transit",    4, 11, "Bus and subway passes",              0.00),
    ("Restaurant",        4, 17, "Meals outside home",                 0.00),
    ("Health Insurance",  4, 17, "Monthly health plan premium",        0.00),
    # ── Equity ──────────────────────────────────────────────
    ("Net Worth",         5, 18, "Personal equity",                    0.00),
]


def _dt(days_ago: int, hour: int = 9, minute: int = 0) -> str:
    d = datetime.now() - timedelta(days=days_ago)
    return d.replace(hour=hour, minute=minute, second=0).strftime("%Y-%m-%d %H:%M:%S")


def build_transactions(acc: dict) -> list[tuple]:
    """
    Return list of (date, description, amount, debit_id, credit_id).
    acc maps account name → id.
    """
    txs = []

    def add(days_ago, desc, amount, debit, credit, hour=9, minute=0):
        txs.append((_dt(days_ago, hour, minute), desc, amount,
                    acc[debit], acc[credit]))

    # ── Last month paycheck ─────────────────────────────────────────────────
    add(38, "Salary — previous month",            3_200.00, "Checking Account", "Monthly Salary")
    add(35, "Rent payment — previous month",      1_100.00, "Rent",             "Checking Account")
    add(33, "Weekly grocery run",                   145.00, "Grocery Shopping", "Cash")
    add(32, "Electric bill — previous month",        68.50, "Electricity",      "Checking Account")
    add(31, "Telecom bill — previous month",         42.00, "Internet & Phone", "Checking Account")
    add(30, "Streaming subscription",                15.99, "Streaming",        "Credit Card")
    add(29, "Fuel top-up",                           55.00, "Fuel",             "Cash")
    add(28, "Weekly grocery run",                   132.00, "Grocery Shopping", "Credit Card")
    add(27, "Bus pass — monthly",                    28.00, "Public Transit",   "E-Wallet")
    add(27, "Transfer to savings",                  400.00, "Savings Account",  "Checking Account")
    add(26, "Lunch — work area",                     18.50, "Restaurant",       "E-Wallet")
    add(25, "Health insurance premium",              95.00, "Health Insurance", "Checking Account")
    add(24, "Fuel top-up",                           50.00, "Fuel",             "Cash")
    add(22, "Freelance project — partial payment",  750.00, "Checking Account", "Freelance Income")
    add(21, "Weekly grocery run",                   119.75, "Grocery Shopping", "Credit Card")
    add(20, "Credit card payment",                  400.00, "Credit Card",      "Checking Account")
    add(19, "Restaurant — dinner out",               42.00, "Restaurant",       "E-Wallet")

    # ── Current month ───────────────────────────────────────────────────────
    add( 8, "Salary — current month",             3_200.00, "Checking Account", "Monthly Salary")
    add( 7, "Rent payment — current month",       1_100.00, "Rent",             "Checking Account")
    add( 6, "Electricity bill — current month",      71.20, "Electricity",      "Checking Account")
    add( 6, "Telecom bill — current month",          42.00, "Internet & Phone", "Checking Account")
    add( 5, "Weekly grocery run",                   138.60, "Grocery Shopping", "Credit Card")
    add( 5, "Streaming subscription",                15.99, "Streaming",        "Credit Card")
    add( 4, "Bus pass — monthly",                    28.00, "Public Transit",   "E-Wallet")
    add( 4, "Fuel top-up",                           52.00, "Fuel",             "Cash")
    add( 3, "Fund dividend received",                85.00, "Checking Account", "Fund Dividends")
    add( 3, "Transfer to savings",                  500.00, "Savings Account",  "Checking Account")
    add( 3, "Investment contribution",             1_000.00, "Investment Fund A","Checking Account")
    add( 2, "Weekly grocery run",                   127.40, "Grocery Shopping", "Cash")
    add( 2, "Health insurance premium",              95.00, "Health Insurance", "Checking Account")
    add( 1, "Restaurant — team lunch",               35.00, "Restaurant",       "E-Wallet")
    add( 1, "Credit card payment",                  250.00, "Credit Card",      "Checking Account")

    return txs


def seed(db_path: Path, force: bool = False):
    if db_path.exists():
        if not force:
            print(f"  ⚠  {db_path} already exists. Use --force to overwrite.")
            return False
        db_path.unlink()
        print(f"  ✓  Removed existing {db_path.name}")

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)

    for tid, name in TYPES:
        conn.execute("INSERT INTO types (id, name) VALUES (?, ?)", (tid, name))

    for sid, name, type_id in SUBTYPES:
        conn.execute("INSERT INTO subtypes (id, name, type_id) VALUES (?, ?, ?)",
                     (sid, name, type_id))

    acc_ids: dict[str, int] = {}
    for name, type_id, subtype_id, desc, balance in ACCOUNTS:
        cur = conn.execute(
            "INSERT INTO accounts (name, type_id, subtype_id, description, initial_balance) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, type_id, subtype_id, desc, balance),
        )
        acc_ids[name] = cur.lastrowid

    for date, desc, amount, debit_id, credit_id in build_transactions(acc_ids):
        conn.execute(
            "INSERT INTO transactions (date, description, amount, debit_id, credit_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (date, desc, amount, debit_id, credit_id),
        )

    conn.commit()
    conn.close()

    n_acc = len(ACCOUNTS)
    n_tx  = len(build_transactions(acc_ids))
    print(f"  ✓  {db_path.name} created: {n_acc} accounts, {n_tx} transactions")
    return True


def main():
    parser = argparse.ArgumentParser(description="Seed the Open Accountant demo database.")
    parser.add_argument("--db",    default=str(DB_DIR / "home.db"),
                        help="Output SQLite file (default: data/home.db)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing database")
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nOpen Accountant — demo seed")
    print(f"  Target: {db_path}")
    seed(db_path, force=args.force)
    print()


if __name__ == "__main__":
    main()
