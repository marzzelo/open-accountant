"""Database package exports for PostgreSQL-backed runtime data."""

from db.balances import (
    DEBIT_NORMAL,
    balance_delta,
    compute_balance,
    compute_filtered_balance,
)
from db.connection import (
    DatabaseConnection,
    connect_db,
    db_dep,
    get_db,
    is_unique_violation,
)
from db.dialect import (
    PREFIXED_TABLES,
    backend_name,
    ci_order_sql,
    month_bucket_sql,
    recent_months_filter_sql,
)
from db.preferences import get_user_preferences, update_user_preferences
from db.schema import POSTGRES_SCHEMA, init_db, table_columns, table_exists

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
