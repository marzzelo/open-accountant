"""SQL dialect helpers and logical-to-physical table mapping."""

import re

PREFIXED_TABLES = {
    "auth_sessions",
    "projection_series",
    "recurring_transaction_tags",
    "recurring_transactions",
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


def _prefixed_table_name(table_name: str) -> str:
    return f"oacc_{table_name}"


def backend_name(conn=None) -> str:
    # Retained for API compatibility; PostgreSQL is the only backend.
    return "postgresql"


def month_bucket_sql(conn, column_name: str) -> str:
    return f"TO_CHAR({column_name}, 'YYYY-MM')"


def recent_months_filter_sql(conn, column_name: str, months: int) -> str:
    return (
        f"{column_name} >= date_trunc('month', CURRENT_DATE "
        f"- INTERVAL '{months} months')"
    )


def ci_order_sql(conn, column_name: str) -> str:
    return f"LOWER({column_name}), {column_name}"


def _translate_query(query: str, backend: str = "postgresql") -> str:
    translated = query.replace("?", "%s")
    for table_name in sorted(PREFIXED_TABLES, key=len, reverse=True):
        translated = re.sub(
            rf"(?<!oacc_)\b{table_name}\b",
            _prefixed_table_name(table_name),
            translated,
        )
    return translated
