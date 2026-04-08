"""One-off migration from legacy SQLite files to the PostgreSQL oacc_* schema."""

import argparse
import os
import sqlite3
from pathlib import Path

import app_config
import database


TABLE_COPY_ORDER = [
    "types",
    "subtypes",
    "accounts",
    "transactions",
    "tags",
    "transaction_tags",
    "user_preferences",
    "projection_series",
]


def _iter_sqlite_rows(conn: sqlite3.Connection, query: str, params=()):
    conn.row_factory = sqlite3.Row
    for row in conn.execute(query, params).fetchall():
        yield dict(row)


def _sqlite_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _exec_script(conn, script: str):
    for statement in (part.strip() for part in script.split(";")):
        if statement:
            conn.execute(statement)


def _ensure_target_schema(database_url: str):
    os.environ[app_config.DATABASE_URL_ENV] = database_url
    with database.connect_db() as _:
        pass

    conn = database.connect_db()
    try:
        _exec_script(conn, database.POSTGRES_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def _clear_target(conn):
    conn.execute(
        """
        TRUNCATE TABLE
            oacc_transaction_tags,
            oacc_transactions,
            oacc_tags,
            oacc_accounts,
            oacc_projection_series,
            oacc_user_preferences,
            oacc_subtypes,
            oacc_types,
            oacc_settings
        RESTART IDENTITY CASCADE
        """
    )


def _migrate_settings(target_conn, meta_db: Path | None, book_db: Path):
    inserted = 0

    if meta_db and meta_db.exists():
        with sqlite3.connect(str(meta_db)) as meta_conn:
            table = meta_conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'app_settings'"
            ).fetchone()
            if table:
                rows = list(
                    _iter_sqlite_rows(
                        meta_conn,
                        "SELECT section, key, value FROM app_settings ORDER BY section, key",
                    )
                )
                for row in rows:
                    target_conn.execute(
                        """
                        INSERT INTO settings (section, key, value)
                        VALUES (?, ?, ?)
                        ON CONFLICT(section, key)
                        DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                        """,
                        (row["section"], row["key"], row["value"]),
                    )
                    inserted += 1

    finance_keys = tuple(app_config.FINANCE_PREFERENCE_TO_CONFIG_KEY.keys())
    with sqlite3.connect(str(book_db)) as legacy_conn:
        has_preferences = legacy_conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user_preferences'"
        ).fetchone()
        if has_preferences and finance_keys:
            placeholders = ",".join("?" for _ in finance_keys)
            rows = list(
                _iter_sqlite_rows(
                    legacy_conn,
                    f"SELECT key, value FROM user_preferences WHERE key IN ({placeholders})",
                    finance_keys,
                )
            )
            for row in rows:
                config_key = app_config.FINANCE_PREFERENCE_TO_CONFIG_KEY[row["key"]]
                target_conn.execute(
                    """
                    INSERT INTO settings (section, key, value)
                    VALUES ('finance', ?, ?)
                    ON CONFLICT(section, key)
                    DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                    """,
                    (config_key, row["value"].strip('"')),
                )
                inserted += 1

    for section, values in app_config._DEFAULTS.items():
        for key, value in values.items():
            target_conn.execute(
                """
                INSERT INTO settings (section, key, value)
                VALUES (?, ?, ?)
                ON CONFLICT(section, key) DO NOTHING
                """,
                (section, key, value),
            )

    return inserted


def _copy_simple_table(target_conn, sqlite_conn, table_name: str):
    if not _sqlite_table_exists(sqlite_conn, table_name):
        return 0

    rows = list(_iter_sqlite_rows(sqlite_conn, f"SELECT * FROM {table_name}"))
    if not rows:
        return 0

    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)

    if table_name == "transaction_tags":
        conflict_sql = "ON CONFLICT DO NOTHING"
    else:
        conflict_sql = "ON CONFLICT DO NOTHING"

    target_conn.executemany(
        f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholders}) {conflict_sql}",
        [tuple(row[column] for column in columns) for row in rows],
    )
    return len(rows)


def _migrate_book_data(target_conn, book_db: Path):
    counts: dict[str, int] = {}
    with sqlite3.connect(str(book_db)) as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        for table_name in TABLE_COPY_ORDER:
            if table_name == "user_preferences":
                if not _sqlite_table_exists(sqlite_conn, table_name):
                    counts[table_name] = 0
                    continue

                rows = list(
                    _iter_sqlite_rows(
                        sqlite_conn,
                        "SELECT * FROM user_preferences ORDER BY key",
                    )
                )
                filtered_rows = [
                    row
                    for row in rows
                    if row["key"] not in app_config.FINANCE_PREFERENCE_TO_CONFIG_KEY
                ]
                if filtered_rows:
                    target_conn.executemany(
                        """
                        INSERT INTO user_preferences (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key)
                        DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                        """,
                        [
                            (row["key"], row["value"], row["updated_at"])
                            for row in filtered_rows
                        ],
                    )
                counts[table_name] = len(filtered_rows)
                continue

            counts[table_name] = _copy_simple_table(
                target_conn, sqlite_conn, table_name
            )

    return counts


def _reset_identity_sequences(target_conn):
    for table_name in ["accounts", "transactions", "tags", "projection_series"]:
        actual_name = f"oacc_{table_name}"
        target_conn.execute(
            "SELECT setval(pg_get_serial_sequence(?, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM "
            + actual_name,
            (actual_name,),
        )


def migrate(database_url: str, book_db: Path, meta_db: Path | None, clear_target: bool):
    if not book_db.exists():
        raise FileNotFoundError(f"SQLite source not found: {book_db}")

    _ensure_target_schema(database_url)
    os.environ[app_config.DATABASE_URL_ENV] = database_url
    with database.get_db() as target_conn:
        if clear_target:
            _clear_target(target_conn)

        settings_rows = _migrate_settings(target_conn, meta_db, book_db)
        table_counts = _migrate_book_data(target_conn, book_db)
        _reset_identity_sequences(target_conn)

    return settings_rows, table_counts


def main():
    parser = argparse.ArgumentParser(
        description="Migrate legacy Open Accountant SQLite data into PostgreSQL."
    )
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL DATABASE_URL target, for example postgresql://user:pass@host:5432/dbname",
    )
    parser.add_argument(
        "--book-db",
        default=str(app_config.DATA_DIR / "home.db"),
        help="Legacy SQLite accounting database to migrate",
    )
    parser.add_argument(
        "--meta-db",
        default=str(app_config.DATA_DIR / "app_meta.sqlite3"),
        help="Legacy SQLite metadata database with app_settings",
    )
    parser.add_argument(
        "--clear-target",
        action="store_true",
        help="Truncate existing oacc_* tables before importing",
    )
    args = parser.parse_args()

    settings_rows, table_counts = migrate(
        database_url=args.database_url,
        book_db=Path(args.book_db),
        meta_db=Path(args.meta_db) if args.meta_db else None,
        clear_target=args.clear_target,
    )

    print("Migration completed")
    print(f"  Settings rows: {settings_rows}")
    for table_name, count in table_counts.items():
        print(f"  {table_name}: {count}")


if __name__ == "__main__":
    main()
