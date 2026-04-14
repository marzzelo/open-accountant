"""Pull data from the Heroku PostgreSQL database into the local PostgreSQL.

Both source and target use oacc_* tables.  Auth tables (users, auth_sessions)
are skipped by default.

Usage:
    # Auto-fetch Heroku URL via CLI, local from DATABASE_URL env var:
    python scripts/sync_from_heroku.py

    # Explicit URLs:
    python scripts/sync_from_heroku.py \\
        --heroku-url "postgres://..." \\
        --local-url  "postgresql://user:pass@localhost:5432/mydb"

    # Include auth tables:
    python scripts/sync_from_heroku.py --include-auth

    # Dry-run — test both connections and show row counts without writing:
    python scripts/sync_from_heroku.py --dry-run
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Allow importing project modules from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database

# ── Table ordering (respects FK dependencies) ─────────────────────────────────

DATA_TABLES = [
    "settings",
    "types",
    "subtypes",
    "accounts",
    "transactions",
    "tags",
    "transaction_tags",
    "user_preferences",
    "projection_series",
]

AUTH_TABLES = [
    "users",
    "auth_sessions",
]

DEFAULT_APP_NAME = "open-accountant"
DEFAULT_LOCAL_URL = "postgresql://postgres@localhost:5432/open_accountant"


# ── Helpers ────────────────────────────────────────────────────────────────────


def _resolve_heroku_cli() -> str | None:
    """Resolve a runnable Heroku CLI path across platforms."""
    candidates = ["heroku"]
    if sys.platform == "win32":
        candidates.extend(["heroku.cmd", "heroku.exe", "heroku.bat"])

    for candidate in candidates:
        cli_path = shutil.which(candidate)
        if cli_path:
            return cli_path

    return None


def _format_heroku_cli_error(stderr: str) -> str:
    """Translate common Heroku CLI failures into actionable script errors."""
    details = stderr.strip()
    lowered = details.lower()

    auth_markers = (
        "invalid credentials",
        "unauthorized",
        "press any key to open up the browser to login",
        "setrawmode",
    )
    if any(marker in lowered for marker in auth_markers):
        message = (
            "ERROR: Heroku CLI authentication failed. Run `heroku login` in an "
            "interactive terminal, set HEROKU_API_KEY, or pass --heroku-url directly."
        )
        if details:
            return f"{message}\n  {details}"
        return message

    if details:
        return f"ERROR: Could not get DATABASE_URL from Heroku.\n  {details}"
    return "ERROR: Could not get DATABASE_URL from Heroku."


def _get_heroku_database_url(app_name: str) -> str:
    """Retrieve DATABASE_URL from Heroku CLI."""
    heroku_cli = _resolve_heroku_cli()
    if not heroku_cli:
        print(
            "ERROR: 'heroku' CLI not found.  Install it or pass --heroku-url directly."
        )
        sys.exit(1)

    try:
        result = subprocess.run(
            [heroku_cli, "config:get", "DATABASE_URL", "--app", app_name],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        print("ERROR: heroku CLI timed out (login required?).")
        sys.exit(1)

    url = result.stdout.strip()
    if result.returncode != 0 or not url:
        print(_format_heroku_cli_error(result.stderr))
        sys.exit(1)
    return url


def _connect_postgres(url: str, *, readonly: bool = False):
    """Open a psycopg (v3) connection from a DATABASE_URL."""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print('ERROR: psycopg is not installed.  Run: pip install "psycopg[binary]"')
        sys.exit(1)

    # Heroku gives postgres:// but psycopg needs postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    conn = psycopg.connect(url, row_factory=dict_row, autocommit=True)
    if readonly:
        conn.execute("SET default_transaction_read_only = ON")
    return conn


def _mask_url(url: str) -> str:
    """Show only the last 25 chars of the URL for logging."""
    return "...%s" % url[-25:] if len(url) > 30 else url


def _verify_tables(pg_conn, tables: list[str], *, label: str = "") -> dict[str, int]:
    """Check that each oacc_* table exists and return row counts."""
    counts: dict[str, int] = {}
    missing: list[str] = []
    for table in tables:
        remote_name = f"oacc_{table}"
        row = pg_conn.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = %s)",
            (remote_name,),
        ).fetchone()
        if not row["exists"]:
            missing.append(remote_name)
            continue
        row = pg_conn.execute(f'SELECT COUNT(*) AS cnt FROM "oacc_{table}"').fetchone()
        counts[table] = row["cnt"]

    if missing:
        print(f"  WARNING ({label}): Missing tables: {', '.join(missing)}")
        for m in missing:
            local_name = m.replace("oacc_", "")
            if local_name in tables:
                tables.remove(local_name)
    return counts


def _fetch_all_rows(pg_conn, table: str) -> tuple[list[str], list[tuple]]:
    """Fetch all rows from oacc_{table}. Returns (columns, rows)."""
    cur = pg_conn.execute(f'SELECT * FROM "oacc_{table}" ORDER BY 1')
    if cur.description is None:
        return [], []
    columns = [desc.name for desc in cur.description]
    rows = [tuple(row_dict[col] for col in columns) for row_dict in cur.fetchall()]
    return columns, rows


def _clear_local_tables(pg_conn, tables: list[str]):
    """Truncate local oacc_* tables in reverse FK order."""
    for table in reversed(tables):
        pg_conn.execute(f'TRUNCATE TABLE "oacc_{table}" CASCADE')


def _insert_rows(pg_conn, table: str, columns: list[str], rows: list[tuple]) -> int:
    """Insert rows into local oacc_{table}."""
    if not rows:
        return 0
    col_sql = ", ".join(f'"{c}"' for c in columns)
    placeholders = ", ".join(f"%({c})s" for c in columns)
    query = f'INSERT INTO "oacc_{table}" ({col_sql}) VALUES ({placeholders})'
    dict_rows = [dict(zip(columns, row)) for row in rows]
    with pg_conn.cursor() as cur:
        cur.executemany(query, dict_rows)
    return len(rows)


def _reset_sequences(pg_conn, tables: list[str]):
    """Reset IDENTITY sequences to max(id)+1 for tables that use GENERATED AS IDENTITY."""
    for table in tables:
        oacc = f"oacc_{table}"
        # Check if table has an identity column named 'id'
        row = pg_conn.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.columns "
            "  WHERE table_schema = 'public' AND table_name = %s "
            "    AND column_name = 'id' AND is_identity = 'YES'"
            ")",
            (oacc,),
        ).fetchone()
        if not row["exists"]:
            continue
        row = pg_conn.execute(
            f'SELECT COALESCE(MAX(id), 0) + 1 AS next_val FROM "{oacc}"'
        ).fetchone()
        pg_conn.execute(
            f'ALTER TABLE "{oacc}" ALTER COLUMN id RESTART WITH {row["next_val"]}'
        )
        print(f"  oacc_{table}: sequence → {row['next_val']}")


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Sync local PostgreSQL from Heroku PostgreSQL (oacc_* tables)."
    )
    parser.add_argument(
        "--heroku-url",
        help="Heroku PostgreSQL URL. If omitted, fetched via `heroku config:get`.",
    )
    parser.add_argument(
        "--local-url",
        default=DEFAULT_LOCAL_URL,
        help=f"Local PostgreSQL URL (default: {DEFAULT_LOCAL_URL}).",
    )
    parser.add_argument(
        "--app",
        default=DEFAULT_APP_NAME,
        help=f"Heroku app name for CLI lookup (default: {DEFAULT_APP_NAME}).",
    )
    parser.add_argument(
        "--include-auth",
        action="store_true",
        help="Also sync users and auth_sessions tables.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test both connections and show row counts without writing.",
    )
    args = parser.parse_args()

    # ── Resolve Heroku URL ──
    heroku_url = args.heroku_url
    if not heroku_url:
        print(f"Fetching DATABASE_URL from Heroku app '{args.app}' ...")
        heroku_url = _get_heroku_database_url(args.app)
    print(f"  Heroku:  {_mask_url(heroku_url)}")
    print(f"  Local:   {_mask_url(args.local_url)}")

    # ── Build table list ──
    tables = list(DATA_TABLES)
    if args.include_auth:
        tables.extend(AUTH_TABLES)

    # ── Connect to Heroku (read-only) ──
    print("\nConnecting to Heroku PostgreSQL ...")
    heroku_conn = _connect_postgres(heroku_url, readonly=True)
    print("  Connected OK.")

    # ── Connect to local ──
    print("Connecting to local PostgreSQL ...")
    local_conn = _connect_postgres(args.local_url)
    print("  Connected OK.")

    # ── Ensure local schema exists ──
    print("\nEnsuring local schema ...")
    local_conn.execute(database.POSTGRES_SCHEMA)
    print("  Schema OK.")

    # ── Verify tables on both sides ──
    print("\nVerifying Heroku oacc_* tables ...")
    heroku_counts = _verify_tables(heroku_conn, tables, label="heroku")
    print("  Heroku row counts:")
    total = 0
    for t in tables:
        n = heroku_counts.get(t, 0)
        total += n
        print(f"    oacc_{t:25s} {n:>7,} rows")
    print(f"    {'':25s} {total:>7,} total")

    if not heroku_counts:
        print("\nNo accessible tables on Heroku. Aborting.")
        heroku_conn.close()
        local_conn.close()
        sys.exit(1)

    print("\nVerifying local oacc_* tables ...")
    local_counts = _verify_tables(local_conn, list(tables), label="local")
    print("  Local row counts (before sync):")
    for t in tables:
        n = local_counts.get(t, 0)
        print(f"    oacc_{t:25s} {n:>7,} rows")

    if args.dry_run:
        print("\n--dry-run: No local changes made.")
        heroku_conn.close()
        local_conn.close()
        return

    # ── Fetch all remote data ──
    print("\nFetching Heroku data ...")
    remote_data: dict[str, tuple[list[str], list[tuple]]] = {}
    for table in tables:
        if table not in heroku_counts:
            continue
        columns, rows = _fetch_all_rows(heroku_conn, table)
        remote_data[table] = (columns, rows)
        print(f"  oacc_{table}: {len(rows)} rows, {len(columns)} columns")
    heroku_conn.close()
    print("  Heroku connection closed.")

    # ── Write to local ──
    tables_to_sync = [t for t in tables if t in remote_data]

    try:
        local_conn.execute("BEGIN")

        print(f"\nClearing {len(tables_to_sync)} local tables ...")
        _clear_local_tables(local_conn, tables_to_sync)

        print("Inserting Heroku data ...")
        for table in tables_to_sync:
            columns, rows = remote_data[table]
            n = _insert_rows(local_conn, table, columns, rows)
            print(f"  oacc_{table:25s} → {n:>7,} rows")

        print("Resetting identity sequences ...")
        _reset_sequences(local_conn, tables_to_sync)

        local_conn.execute("COMMIT")
        print("\n✔ Sync complete.")

    except Exception as exc:
        local_conn.execute("ROLLBACK")
        print(f"\nERROR during sync: {exc}")
        print("  Transaction rolled back — local DB unchanged.")
        raise
    finally:
        local_conn.close()


if __name__ == "__main__":
    main()
