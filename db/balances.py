"""Accounting balance helpers."""

from typing import Any

DEBIT_NORMAL = {1, 4}  # 1=Asset, 4=Expense


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
