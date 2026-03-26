#!/usr/bin/env python3
"""
seed_demo.py - Create a rich demo accounting book with three months of
sample data, including USD-origin transactions and FX metadata.

Run from the project root:
    python scripts/seed_demo.py [--db data/sample.db] [--force]
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "data"
DEFAULT_DB_PATH = DB_DIR / "sample.db"
AUTO_REPLACE_PREFIX = "sample.db"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import SCHEMA, SEED_SUBTYPES, SEED_TYPES

MARKET_RATES = [
    {
        "USD_BUY": 1048.0,
        "USD_SELL": 1067.0,
        "BLUE_BUY": 1102.0,
        "BLUE_SELL": 1124.0,
        "USD_CARD": 1387.1,
    },
    {
        "USD_BUY": 1076.0,
        "USD_SELL": 1094.0,
        "BLUE_BUY": 1140.0,
        "BLUE_SELL": 1162.0,
        "USD_CARD": 1422.2,
    },
    {
        "USD_BUY": 1098.0,
        "USD_SELL": 1116.0,
        "BLUE_BUY": 1168.0,
        "BLUE_SELL": 1190.0,
        "USD_CARD": 1450.8,
    },
]


# (name, type_id, subtype_id, description, initial_balance, properties)
ACCOUNTS = [
    (
        "Cash Reserve",
        1,
        1,
        "Cash kept for daily purchases and ATM withdrawals",
        250_000.00,
        {"liquidity_profile": "quick"},
    ),
    (
        "Operating Checking",
        1,
        2,
        "Primary operating account used for salary and recurring payments",
        3_800_000.00,
        {"liquidity_profile": "quick"},
    ),
    (
        "Emergency Savings",
        1,
        2,
        "Emergency reserve separated from daily operating cash",
        7_500_000.00,
        {"liquidity_profile": "current"},
    ),
    (
        "Travel Wallet",
        1,
        2,
        "Digital wallet used for transport, meals, and small discretionary spend",
        180_000.00,
        {"liquidity_profile": "quick"},
    ),
    (
        "Brokerage USD",
        1,
        3,
        "Investment account holding long-term market exposure",
        4_200_000.00,
        {"liquidity_profile": "non_current"},
    ),
    (
        "Used Car",
        1,
        4,
        "Vehicle used for commuting and family trips",
        3_100_000.00,
        {"liquidity_profile": "non_current"},
    ),
    (
        "Credit Card",
        2,
        5,
        "General-purpose card used for groceries, subscriptions, and travel",
        420_000.00,
        {"liability_term": "current"},
    ),
    (
        "Personal Loan",
        2,
        6,
        "Remaining principal on a medium-term bank loan",
        5_800_000.00,
        {"liability_term": "long_term"},
    ),
    ("Monthly Salary", 3, 7, "Primary employment income", 0.00, {}),
    ("Freelance Income", 3, 8, "Project-based consulting work", 0.00, {}),
    ("Fund Dividends", 3, 10, "Quarterly and monthly dividend cash flow", 0.00, {}),
    (
        "Rent",
        4,
        13,
        "Monthly apartment rent",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Grocery Shopping",
        4,
        12,
        "Food and household essentials",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Fuel",
        4,
        11,
        "Vehicle fuel and parking",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Utilities",
        4,
        15,
        "Electricity, gas, and water",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Internet & Phone",
        4,
        15,
        "Home internet and mobile plan",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Streaming",
        4,
        16,
        "Video and music subscriptions",
        0.00,
        {"expense_profile": "discretionary"},
    ),
    (
        "Public Transit",
        4,
        11,
        "Bus and subway cards",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Restaurant",
        4,
        17,
        "Meals outside the home",
        0.00,
        {"expense_profile": "discretionary"},
    ),
    (
        "Health Insurance",
        4,
        17,
        "Monthly health insurance premium",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Travel & Leisure",
        4,
        16,
        "Getaways, short trips, and leisure bookings",
        0.00,
        {"expense_profile": "discretionary"},
    ),
    (
        "Taxes & Fees",
        4,
        14,
        "Municipal fees and recurring taxes",
        0.00,
        {"expense_profile": "essential"},
    ),
    (
        "Net Worth",
        5,
        18,
        "Opening equity balancing the seeded asset and liability positions",
        12_810_000.00,
        {},
    ),
]


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return year, month


def _last_day_of_month(year: int, month: int) -> int:
    next_year, next_month = _shift_month(year, month, 1)
    first_next = datetime(next_year, next_month, 1)
    return (first_next - datetime.resolution).day


def _month_datetime(
    month_index: int, day: int, hour: int = 9, minute: int = 0
) -> datetime:
    now = datetime.now()
    year, month = _shift_month(now.year, now.month, month_index - 2)
    safe_day = min(day, _last_day_of_month(year, month))
    return datetime(year, month, safe_day, hour, minute, 0)


def _month_label(month_index: int) -> str:
    return _month_datetime(month_index, 1).strftime("%b %Y")


def _booked_from_usd(month_index: int, original_amount: float, fx_source: str) -> float:
    return round(float(original_amount) * MARKET_RATES[month_index][fx_source], 2)


def _cleanup_database_files(db_path: Path) -> int:
    removed = 0
    for candidate in (db_path, Path(f"{db_path}-shm"), Path(f"{db_path}-wal")):
        if candidate.exists():
            candidate.unlink()
            removed += 1
    return removed


def build_transactions(account_ids: dict[str, int]) -> list[tuple]:
    """
    Return rows shaped for the current transactions table:
        (debit_account, credit_account, amount, original_amount,
         original_currency, fx_rate, fx_source, description, date)
    """

    transactions: list[tuple] = []

    def add_usd(
        month_index: int,
        day: int,
        description: str,
        original_amount: float,
        debit: str,
        credit: str,
        fx_source: str,
        hour: int = 9,
        minute: int = 0,
    ):
        fx_rate = MARKET_RATES[month_index][fx_source]
        transactions.append(
            (
                account_ids[debit],
                account_ids[credit],
                round(original_amount * fx_rate, 2),
                round(original_amount, 2),
                "USD",
                fx_rate,
                fx_source,
                description,
                _month_datetime(month_index, day, hour, minute).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            )
        )

    def add_ars(
        month_index: int,
        day: int,
        description: str,
        amount: float,
        debit: str,
        credit: str,
        hour: int = 9,
        minute: int = 0,
    ):
        rounded = round(amount, 2)
        transactions.append(
            (
                account_ids[debit],
                account_ids[credit],
                rounded,
                rounded,
                "ARS",
                1.0,
                None,
                description,
                _month_datetime(month_index, day, hour, minute).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            )
        )

    salary = [3200.00, 3200.00, 3350.00]
    freelance = [640.00, 780.00, 930.00]
    dividends = [96.00, 104.00, 112.00]
    rent = [980.00, 980.00, 995.00]
    utilities = [72.00, 68.00, 81.00]
    internet = [45.00, 46.00, 47.00]
    health = [105.00, 108.00, 109.00]
    transit = [22.00, 24.00, 24.00]
    streaming = [15.99, 15.99, 17.49]
    loan_payment = [180.00, 180.00, 180.00]
    savings_transfer = [260.00, 310.00, 360.00]
    investment_contribution = [420.00, 500.00, 650.00]
    credit_card_payment = [330.00, 360.00, 410.00]
    wallet_topup = [70.00, 90.00, 110.00]
    cash_withdrawal = [120.00, 135.00, 145.00]
    taxes = [0.00, 72.00, 0.00]
    travel = [0.00, 185.00, 225.00]
    groceries = [
        [86.00, 92.00, 79.00, 88.00],
        [84.00, 95.00, 82.00, 91.00],
        [87.00, 98.00, 85.00, 93.00],
    ]
    restaurants = [
        [24.00, 36.00],
        [29.00, 41.00],
        [31.00, 45.00],
    ]
    fuel = [
        [44.00, 39.00],
        [46.00, 42.00],
        [49.00, 44.00],
    ]

    for month_index in range(3):
        label = _month_label(month_index)
        direct_rate = MARKET_RATES[month_index]["USD_BUY"]

        add_usd(
            month_index,
            2,
            f"Salary deposit ({label})",
            salary[month_index],
            "Operating Checking",
            "Monthly Salary",
            "USD_BUY",
            9,
            30,
        )
        add_ars(
            month_index,
            3,
            f"Wallet top-up from checking ({label})",
            _booked_from_usd(month_index, wallet_topup[month_index], "USD_BUY"),
            "Travel Wallet",
            "Operating Checking",
            12,
            0,
        )
        add_ars(
            month_index,
            3,
            f"ATM cash withdrawal ({label})",
            _booked_from_usd(month_index, cash_withdrawal[month_index], "USD_BUY"),
            "Cash Reserve",
            "Operating Checking",
            12,
            30,
        )
        add_usd(
            month_index,
            4,
            f"Apartment rent ({label})",
            rent[month_index],
            "Rent",
            "Operating Checking",
            "BLUE_SELL",
            10,
            0,
        )
        add_usd(
            month_index,
            5,
            f"Utilities payment ({label})",
            utilities[month_index],
            "Utilities",
            "Operating Checking",
            "USD_SELL",
            9,
            15,
        )
        add_usd(
            month_index,
            5,
            f"Internet and phone bill ({label})",
            internet[month_index],
            "Internet & Phone",
            "Operating Checking",
            "USD_SELL",
            16,
            20,
        )
        add_usd(
            month_index,
            6,
            f"Weekly groceries - card ({label})",
            groceries[month_index][0],
            "Grocery Shopping",
            "Credit Card",
            "USD_CARD",
            18,
            45,
        )
        add_usd(
            month_index,
            7,
            f"Transit card recharge ({label})",
            transit[month_index],
            "Public Transit",
            "Travel Wallet",
            "USD_SELL",
            8,
            40,
        )
        add_usd(
            month_index,
            8,
            f"Fuel top-up - station A ({label})",
            fuel[month_index][0],
            "Fuel",
            "Cash Reserve",
            "USD_SELL",
            19,
            10,
        )
        add_usd(
            month_index,
            10,
            f"Weekly groceries - cash ({label})",
            groceries[month_index][1],
            "Grocery Shopping",
            "Cash Reserve",
            "USD_SELL",
            11,
            30,
        )
        add_usd(
            month_index,
            12,
            f"Health insurance premium ({label})",
            health[month_index],
            "Health Insurance",
            "Operating Checking",
            "USD_SELL",
            9,
            5,
        )
        add_usd(
            month_index,
            13,
            f"Freelance project settlement ({label})",
            freelance[month_index],
            "Operating Checking",
            "Freelance Income",
            "USD_BUY",
            15,
            0,
        )
        add_ars(
            month_index,
            15,
            f"Transfer to emergency savings ({label})",
            round(savings_transfer[month_index] * direct_rate, 2),
            "Emergency Savings",
            "Operating Checking",
            10,
            10,
        )
        add_ars(
            month_index,
            16,
            f"Credit card payment ({label})",
            round(credit_card_payment[month_index] * direct_rate, 2),
            "Credit Card",
            "Operating Checking",
            13,
            20,
        )
        add_ars(
            month_index,
            18,
            f"Monthly investment contribution ({label})",
            round(investment_contribution[month_index] * direct_rate, 2),
            "Brokerage USD",
            "Operating Checking",
            14,
            35,
        )
        add_usd(
            month_index,
            20,
            f"Weekly groceries - card refill ({label})",
            groceries[month_index][2],
            "Grocery Shopping",
            "Credit Card",
            "USD_CARD",
            19,
            0,
        )
        add_usd(
            month_index,
            21,
            f"Fund dividend distribution ({label})",
            dividends[month_index],
            "Operating Checking",
            "Fund Dividends",
            "USD_BUY",
            10,
            45,
        )
        add_usd(
            month_index,
            22,
            f"Restaurant outing ({label})",
            restaurants[month_index][0],
            "Restaurant",
            "Travel Wallet",
            "USD_SELL",
            21,
            15,
        )
        add_usd(
            month_index,
            24,
            f"Streaming services ({label})",
            streaming[month_index],
            "Streaming",
            "Credit Card",
            "USD_CARD",
            7,
            50,
        )
        add_usd(
            month_index,
            25,
            f"Fuel top-up - station B ({label})",
            fuel[month_index][1],
            "Fuel",
            "Operating Checking",
            "USD_SELL",
            18,
            20,
        )
        add_usd(
            month_index,
            26,
            f"Weekly groceries - wallet ({label})",
            groceries[month_index][3],
            "Grocery Shopping",
            "Travel Wallet",
            "USD_SELL",
            13,
            5,
        )
        add_ars(
            month_index,
            27,
            f"Personal loan installment ({label})",
            round(loan_payment[month_index] * direct_rate, 2),
            "Personal Loan",
            "Operating Checking",
            9,
            55,
        )
        add_usd(
            month_index,
            28,
            f"Dinner with friends ({label})",
            restaurants[month_index][1],
            "Restaurant",
            "Credit Card",
            "USD_CARD",
            22,
            10,
        )

        if taxes[month_index] > 0:
            add_usd(
                month_index,
                28,
                f"Municipal fees ({label})",
                taxes[month_index],
                "Taxes & Fees",
                "Operating Checking",
                "USD_SELL",
                8,
                25,
            )

        if travel[month_index] > 0:
            add_usd(
                month_index,
                29,
                f"Weekend getaway booking ({label})",
                travel[month_index],
                "Travel & Leisure",
                "Credit Card",
                "USD_CARD",
                20,
                40,
            )

    transactions.sort(key=lambda row: row[-1])
    return transactions


def seed(db_path: Path, force: bool = False) -> bool:
    auto_replace = db_path.name.startswith(AUTO_REPLACE_PREFIX)
    if (
        db_path.exists()
        or Path(f"{db_path}-shm").exists()
        or Path(f"{db_path}-wal").exists()
    ):
        if not (force or auto_replace):
            print(f"  !  {db_path} already exists. Use --force to overwrite.")
            return False
        removed = _cleanup_database_files(db_path)
        print(f"  +  Removed {removed} existing database file(s) for {db_path.name}")

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

    account_ids: dict[str, int] = {}
    for name, type_id, subtype_id, description, initial_balance, properties in ACCOUNTS:
        cursor = conn.execute(
            """
            INSERT INTO accounts (
                name, type_id, subtype_id, description, initial_balance, properties
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                type_id,
                subtype_id,
                description,
                initial_balance,
                json.dumps(properties, ensure_ascii=True, separators=(",", ":")),
            ),
        )
        account_ids[name] = cursor.lastrowid

    transactions = build_transactions(account_ids)
    conn.executemany(
        """
        INSERT INTO transactions (
            debit_account,
            credit_account,
            amount,
            original_amount,
            original_currency,
            fx_rate,
            fx_source,
            description,
            date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        transactions,
    )

    conn.commit()
    conn.close()

    print(
        f"  +  {db_path.name} created with {len(ACCOUNTS)} accounts and "
        f"{len(transactions)} transactions across three months"
    )
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Seed the Open Accountant sample database."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Output SQLite file (default: data/sample.db)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing database target",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    print("\nOpen Accountant - sample seed")
    print(f"  Target: {db_path}")
    seed(db_path, force=args.force)
    print()


if __name__ == "__main__":
    main()
