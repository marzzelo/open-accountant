"""Compatibility shim for the split `db` package.

This module preserves the historical `import database` /
`from database import ...` surface while the implementation now lives under
`db`.
"""

from db import (  # noqa: F401
    DEBIT_NORMAL,
    POSTGRES_SCHEMA,
    PREFIXED_TABLES,
    DatabaseConnection,
    backend_name,
    balance_delta,
    ci_order_sql,
    compute_balance,
    compute_filtered_balance,
    connect_db,
    db_dep,
    get_db,
    get_user_preferences,
    is_unique_violation,
    month_bucket_sql,
    recent_months_filter_sql,
    table_columns,
    table_exists,
    update_user_preferences,
)
from db.schema import init_db as _init_db


def init_db():
    return _init_db(get_db_func=get_db)


__all__ = [
    "DEBIT_NORMAL",
    "DatabaseConnection",
    "POSTGRES_SCHEMA",
    "PREFIXED_TABLES",
    "backend_name",
    "balance_delta",
    "ci_order_sql",
    "compute_balance",
    "compute_filtered_balance",
    "connect_db",
    "db_dep",
    "get_db",
    "get_user_preferences",
    "init_db",
    "is_unique_violation",
    "month_bucket_sql",
    "recent_months_filter_sql",
    "table_columns",
    "table_exists",
    "update_user_preferences",
]
