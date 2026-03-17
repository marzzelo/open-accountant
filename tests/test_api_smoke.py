import app_config
import app_version
import json
import sqlite3

from database import init_db


def _accounts_by_name(client):
    response = client.get("/api/accounts")
    assert response.status_code == 200
    return {item["name"]: item for item in response.json()}


def test_seed_data_is_available(client):
    types_response = client.get("/api/types")
    assert types_response.status_code == 200
    assert [item["name"] for item in types_response.json()] == [
        "Asset",
        "Liability",
        "Income",
        "Expense",
        "Equity",
    ]

    accounts = _accounts_by_name(client)
    assert "Bank" in accounts
    assert "Salary" in accounts
    assert "Capital" in accounts

    version_response = client.get("/api/version")
    assert version_response.status_code == 200
    version_data = version_response.json()
    assert version_data == app_version.version_payload()


def test_create_account_and_transaction_updates_balances(client):
    create_response = client.post(
        "/api/accounts",
        json={
            "name": "Emergency Fund",
            "type_id": 1,
            "subtype_id": 2,
            "description": "Savings buffer",
            "initial_balance": 50.0,
            "properties": "{}",
        },
    )
    assert create_response.status_code == 201

    new_account = create_response.json()
    accounts = _accounts_by_name(client)

    tx_response = client.post(
        "/api/transactions",
        json={
            "debit_account": new_account["id"],
            "credit_account": accounts["Salary"]["id"],
            "amount": 100.0,
            "description": "Seed savings",
        },
    )
    assert tx_response.status_code == 201

    account_response = client.get(f"/api/accounts/{new_account['id']}")
    assert account_response.status_code == 200
    assert account_response.json()["balance"] == 150.0

    salary_response = client.get(f"/api/accounts/{accounts['Salary']['id']}")
    assert salary_response.status_code == 200
    assert salary_response.json()["balance"] == 100.0

    with sqlite3.connect(app_config.get_db_path()) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()
        }
    assert "balance" not in columns


def test_init_db_migrates_legacy_accounts_table_without_balance_column(isolated_paths):
    home_db = isolated_paths / "data" / "home.db"
    home_db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(home_db) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;

            CREATE TABLE types (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE subtypes (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                type_id INTEGER NOT NULL REFERENCES types(id) ON DELETE RESTRICT,
                UNIQUE(name, type_id)
            );

            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                type_id INTEGER NOT NULL REFERENCES types(id) ON DELETE RESTRICT,
                subtype_id INTEGER REFERENCES subtypes(id) ON DELETE SET NULL,
                description TEXT NOT NULL DEFAULT '',
                initial_balance REAL NOT NULL DEFAULT 0.0,
                balance REAL NOT NULL DEFAULT 0.0,
                properties TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debit_account INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
                credit_account INTEGER NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
                amount REAL NOT NULL CHECK(amount > 0),
                description TEXT NOT NULL DEFAULT '',
                date TEXT NOT NULL DEFAULT (datetime('now')),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            INSERT INTO types (id, name) VALUES (1, 'Asset');
            INSERT INTO types (id, name) VALUES (3, 'Income');
            INSERT INTO accounts (id, name, type_id, description, initial_balance, balance, properties)
            VALUES (1, 'Legacy Cash', 1, 'legacy', 50.0, 999.0, '{}');
            INSERT INTO accounts (id, name, type_id, description, initial_balance, balance, properties)
            VALUES (2, 'Legacy Income', 3, 'legacy', 0.0, 999.0, '{}');
            INSERT INTO transactions (debit_account, credit_account, amount, description, date)
            VALUES (1, 2, 75.0, 'Legacy tx', '2026-03-17 09:00:00');
            """
        )

    app_config.load()
    init_db()

    with sqlite3.connect(home_db) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()
        }
        legacy_cash = conn.execute(
            "SELECT name, initial_balance, properties FROM accounts WHERE id = 1"
        ).fetchone()

    assert "balance" not in columns
    assert legacy_cash == ("Legacy Cash", 50.0, "{}")

    from main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        response = test_client.get("/api/accounts/1")

    assert response.status_code == 200
    assert response.json()["balance"] == 125.0


def test_reports_and_csv_export_work_for_basic_journal_flow(client):
    accounts = _accounts_by_name(client)

    tx_response = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Bank"]["id"],
            "credit_account": accounts["Salary"]["id"],
            "amount": 250.0,
            "description": "Monthly salary",
        },
    )
    assert tx_response.status_code == 201

    balance_response = client.get("/api/reports/balance")
    assert balance_response.status_code == 200
    balance_data = balance_response.json()
    assert balance_data["total_activo"] == 250.0
    assert balance_data["total_ingreso"] == 250.0
    assert balance_data["equation_check"] == 0.0

    export_response = client.get("/api/reports/export/csv?report=journal")
    assert export_response.status_code == 200
    assert "text/csv" in export_response.headers["content-type"]
    body = export_response.text
    assert "Monthly salary" in body
    assert "Bank" in body
    assert "Salary" in body


def test_list_accounts_returns_recent_movements_and_monthly_history(client):
    accounts = _accounts_by_name(client)
    dates = [
        "2026-03-14 09:00:00",
        "2026-03-15 09:00:00",
        "2026-03-16 09:00:00",
        "2026-03-17 09:00:00",
    ]

    for index, tx_date in enumerate(dates, start=1):
        response = client.post(
            "/api/transactions",
            json={
                "debit_account": accounts["Bank"]["id"],
                "credit_account": accounts["Salary"]["id"],
                "amount": 100.0 * index,
                "description": f"Salary batch {index}",
                "date": tx_date,
            },
        )
        assert response.status_code == 201

    accounts_response = client.get("/api/accounts")
    assert accounts_response.status_code == 200
    payload = {item["name"]: item for item in accounts_response.json()}

    bank = payload["Bank"]
    assert len(bank["last_movements"]) == 3
    assert bank["last_movements"][0]["description"] == "Salary batch 4"
    assert bank["last_movements"][0]["role"] == "debit"
    assert bank["last_movements"][0]["counterpart"] == "Salary"
    assert any(row["month"] == "2026-03" for row in bank["monthly_history"])


def test_stats_net_expense_subtypes_ignore_fully_reversed_movements(client):
    accounts = _accounts_by_name(client)

    create_subtype = client.post(
        "/api/subtypes",
        json={"name": "Temp Expenses", "type_id": 4},
    )
    assert create_subtype.status_code == 201
    subtype = create_subtype.json()

    create_account = client.post(
        "/api/accounts",
        json={
            "name": "Fake Expense",
            "type_id": 4,
            "subtype_id": subtype["id"],
            "description": "Temporary expense bucket",
            "initial_balance": 0.0,
            "properties": "{}",
        },
    )
    assert create_account.status_code == 201
    expense_account = create_account.json()

    debit_expense = client.post(
        "/api/transactions",
        json={
            "debit_account": expense_account["id"],
            "credit_account": accounts["Capital"]["id"],
            "amount": 10000.0,
            "description": "Temporary expense entry",
        },
    )
    assert debit_expense.status_code == 201

    reverse_expense = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Capital"]["id"],
            "credit_account": expense_account["id"],
            "amount": 10000.0,
            "description": "Temporary expense reversal",
        },
    )
    assert reverse_expense.status_code == 201

    stats_response = client.get("/api/reports/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()

    assert all(
        row["subtype"] != "Temp Expenses" for row in stats["expenses_by_subtype"]
    )
    assert stats["monthly_cashflow"][0]["gastos"] == 0.0


def test_settings_config_and_preferences_persist_in_sqlite(client, isolated_paths):
    config_response = client.get("/api/settings/config")
    assert config_response.status_code == 200
    assert config_response.json()["general"]["port"] == "5999"
    assert config_response.json()["app"]["language"] == "es"
    assert config_response.json()["finance"]["usd_official_buy_ars"] == "0.00"

    update_config = client.put(
        "/api/settings/config",
        json={
            "general": {"host": "0.0.0.0", "port": "6001"},
            "app": {"name": "SQLite Settings", "language": "en"},
            "finance": {
                "usd_official_buy_ars": "1366.00",
                "usd_official_sell_ars": "1417.00",
                "usd_blue_buy_ars": "1405.00",
                "usd_blue_sell_ars": "1425.00",
                "usd_card_ars": "1842.10",
                "usd_official_last_update": "2026-03-16T11:16:04.488756-03:00",
            },
        },
    )
    assert update_config.status_code == 200

    config_json = client.get("/api/settings/config").json()
    assert config_json["general"]["host"] == "0.0.0.0"
    assert config_json["general"]["port"] == "6001"
    assert config_json["app"]["name"] == "SQLite Settings"
    assert config_json["app"]["language"] == "en"
    assert config_json["finance"]["usd_official_buy_ars"] == "1366.00"
    assert config_json["finance"]["usd_official_sell_ars"] == "1417.00"
    assert config_json["finance"]["usd_blue_buy_ars"] == "1405.00"
    assert config_json["finance"]["usd_blue_sell_ars"] == "1425.00"
    assert config_json["finance"]["usd_card_ars"] == "1842.10"
    assert (
        config_json["finance"]["usd_official_last_update"]
        == "2026-03-16T11:16:04.488756-03:00"
    )

    pref_payload = {
        "show_zero_balance_accounts": True,
        "report_sort_directions": {"journal": "asc", "ledger": "desc", "txlist": "asc"},
        "common_transactions_pins": {
            "1|2|salary": {
                "signature": "1|2|salary",
                "creditId": 1,
                "debitId": 2,
                "description": "salary",
                "lastDate": "2026-03-15 10:30:00",
                "pinned": True,
            }
        },
    }
    update_prefs = client.put("/api/settings/preferences", json=pref_payload)
    assert update_prefs.status_code == 200

    prefs_response = client.get("/api/settings/preferences")
    assert prefs_response.status_code == 200
    assert prefs_response.json() == pref_payload

    meta_db = isolated_paths / "data" / "app_meta.sqlite3"
    with sqlite3.connect(meta_db) as conn:
        rows = conn.execute(
            "SELECT section, key, value FROM app_settings ORDER BY section, key"
        ).fetchall()
    assert ("general", "port", "6001") in rows
    assert ("app", "language", "en") in rows
    assert ("finance", "usd_official_buy_ars", "1366.00") in rows
    assert ("finance", "usd_official_sell_ars", "1417.00") in rows
    assert ("finance", "usd_blue_buy_ars", "1405.00") in rows
    assert ("finance", "usd_blue_sell_ars", "1425.00") in rows
    assert ("finance", "usd_card_ars", "1842.10") in rows
    assert (
        "finance",
        "usd_official_last_update",
        "2026-03-16T11:16:04.488756-03:00",
    ) in rows

    book_db = isolated_paths / "data" / "home.db"
    with sqlite3.connect(book_db) as conn:
        rows = conn.execute(
            "SELECT key, value FROM user_preferences ORDER BY key"
        ).fetchall()
    assert not any(row[0].startswith("finance_") for row in rows)
    assert any(row[0] == "show_zero_balance_accounts" for row in rows)
    assert any(row[0] == "report_sort_directions" for row in rows)
    assert any(row[0] == "common_transactions_pins" for row in rows)


def test_user_preferences_are_scoped_per_book(client):
    home_prefs = {
        "show_zero_balance_accounts": True,
        "report_sort_directions": {"journal": "asc", "ledger": "asc", "txlist": "desc"},
    }
    response = client.put("/api/settings/preferences", json=home_prefs)
    assert response.status_code == 200

    finance_config = {
        "finance": {
            "usd_official_buy_ars": "1366.00",
            "usd_official_sell_ars": "1417.00",
            "usd_blue_buy_ars": "1405.00",
            "usd_blue_sell_ars": "1425.00",
            "usd_card_ars": "1842.10",
            "usd_official_last_update": "2026-03-16T11:16:04.488756-03:00",
        }
    }
    assert client.put("/api/settings/config", json=finance_config).status_code == 200

    create_book = client.post("/api/books", json={"name": "biz", "basic_seed": False})
    assert create_book.status_code == 200

    select_biz = client.post("/api/books/select", json={"name": "biz"})
    assert select_biz.status_code == 200
    assert client.get("/api/settings/preferences").json() == {}
    assert (
        client.get("/api/settings/config").json()["finance"]
        == finance_config["finance"]
    )

    biz_prefs = {
        "show_zero_balance_accounts": False,
        "report_sort_directions": {"journal": "desc"},
    }
    update_biz = client.put("/api/settings/preferences", json=biz_prefs)
    assert update_biz.status_code == 200

    select_home = client.post("/api/books/select", json={"name": "home"})
    assert select_home.status_code == 200
    assert client.get("/api/settings/preferences").json() == home_prefs
    assert (
        client.get("/api/settings/config").json()["finance"]
        == finance_config["finance"]
    )


def test_legacy_finance_preferences_are_migrated_to_global_config(
    client, isolated_paths
):
    legacy_finance_prefs = {
        "finance_usd_official_buy_ars": "1366.00",
        "finance_usd_official_sell_ars": "1417.00",
        "finance_usd_blue_buy_ars": "1405.00",
        "finance_usd_blue_sell_ars": "1425.00",
        "finance_usd_card_ars": "1842.10",
        "finance_usd_official_last_update": "2026-03-16T11:16:04.488756-03:00",
    }
    response = client.put("/api/settings/preferences", json=legacy_finance_prefs)
    assert response.status_code == 200
    assert response.json()["preferences"] == {}

    config_json = client.get("/api/settings/config").json()
    assert config_json["finance"]["usd_official_buy_ars"] == "1366.00"
    assert config_json["finance"]["usd_official_sell_ars"] == "1417.00"
    assert config_json["finance"]["usd_blue_buy_ars"] == "1405.00"
    assert config_json["finance"]["usd_blue_sell_ars"] == "1425.00"
    assert config_json["finance"]["usd_card_ars"] == "1842.10"
    assert (
        config_json["finance"]["usd_official_last_update"]
        == "2026-03-16T11:16:04.488756-03:00"
    )

    book_db = isolated_paths / "data" / "home.db"
    with sqlite3.connect(book_db) as conn:
        rows = conn.execute("SELECT key FROM user_preferences ORDER BY key").fetchall()
    assert not any(row[0].startswith("finance_") for row in rows)


def test_startup_migrates_legacy_finance_preferences_to_global_config(isolated_paths):
    home_db = isolated_paths / "data" / "home.db"
    home_db.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(home_db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.executemany(
            "INSERT INTO user_preferences (key, value) VALUES (?, ?)",
            [
                ("finance_usd_official_buy_ars", json.dumps("1366.00")),
                ("finance_usd_official_sell_ars", json.dumps("1417.00")),
                ("finance_usd_blue_buy_ars", json.dumps("1405.00")),
                ("finance_usd_blue_sell_ars", json.dumps("1425.00")),
                ("finance_usd_card_ars", json.dumps("1842.10")),
                (
                    "finance_usd_official_last_update",
                    json.dumps("2026-03-16T11:16:04.488756-03:00"),
                ),
            ],
        )

    app_config.load()

    config_json = app_config.get_all()
    assert config_json["finance"]["usd_official_buy_ars"] == "1366.00"
    assert config_json["finance"]["usd_official_sell_ars"] == "1417.00"
    assert config_json["finance"]["usd_blue_buy_ars"] == "1405.00"
    assert config_json["finance"]["usd_blue_sell_ars"] == "1425.00"
    assert config_json["finance"]["usd_card_ars"] == "1842.10"
    assert (
        config_json["finance"]["usd_official_last_update"]
        == "2026-03-16T11:16:04.488756-03:00"
    )


def test_settings_finance_endpoint_returns_usd_rates(client, monkeypatch):
    import routers.settings as settings_router

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'{"oficial":{"value_avg":1391,"value_sell":1416,"value_buy":1366},'
                b'"blue":{"value_avg":1415,"value_sell":1425,"value_buy":1405},'
                b'"last_update":"2026-03-16T11:16:04.488756-03:00"}'
            )

    monkeypatch.setattr(
        settings_router, "urlopen", lambda *args, **kwargs: FakeResponse()
    )

    response = client.get("/api/settings/finance/usd-rates")
    assert response.status_code == 200
    assert response.json()["official_buy"] == 1366
    assert response.json()["official_sell"] == 1416
    assert response.json()["blue_buy"] == 1405
    assert response.json()["blue_sell"] == 1425
    assert response.json()["card"] == 1840.8
    assert response.json()["last_update"] == "2026-03-16T11:16:04.488756-03:00"
