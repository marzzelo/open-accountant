import app_version
import sqlite3


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


def test_settings_config_and_preferences_persist_in_sqlite(client, isolated_paths):
    config_response = client.get("/api/settings/config")
    assert config_response.status_code == 200
    assert config_response.json()["general"]["port"] == "5999"
    assert config_response.json()["app"]["language"] == "es"

    update_config = client.put(
        "/api/settings/config",
        json={
            "general": {"host": "0.0.0.0", "port": "6001"},
            "app": {"name": "SQLite Settings", "language": "en"},
        },
    )
    assert update_config.status_code == 200

    config_json = client.get("/api/settings/config").json()
    assert config_json["general"]["host"] == "0.0.0.0"
    assert config_json["general"]["port"] == "6001"
    assert config_json["app"]["name"] == "SQLite Settings"
    assert config_json["app"]["language"] == "en"

    pref_payload = {
        "finance_usd_official_buy_ars": "1366.00",
        "finance_usd_official_last_update": "2026-03-16T11:16:04.488756-03:00",
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

    book_db = isolated_paths / "data" / "home.db"
    with sqlite3.connect(book_db) as conn:
        rows = conn.execute(
            "SELECT key, value FROM user_preferences ORDER BY key"
        ).fetchall()
    assert any(row[0] == "finance_usd_official_buy_ars" for row in rows)
    assert any(row[0] == "finance_usd_official_last_update" for row in rows)
    assert any(row[0] == "show_zero_balance_accounts" for row in rows)
    assert any(row[0] == "report_sort_directions" for row in rows)
    assert any(row[0] == "common_transactions_pins" for row in rows)


def test_user_preferences_are_scoped_per_book(client):
    home_prefs = {
        "finance_usd_official_buy_ars": "1366.00",
        "finance_usd_official_last_update": "2026-03-16T11:16:04.488756-03:00",
        "show_zero_balance_accounts": True,
        "report_sort_directions": {"journal": "asc", "ledger": "asc", "txlist": "desc"},
    }
    response = client.put("/api/settings/preferences", json=home_prefs)
    assert response.status_code == 200

    create_book = client.post("/api/books", json={"name": "biz", "basic_seed": False})
    assert create_book.status_code == 200

    select_biz = client.post("/api/books/select", json={"name": "biz"})
    assert select_biz.status_code == 200
    assert client.get("/api/settings/preferences").json() == {}

    biz_prefs = {
        "finance_usd_official_buy_ars": "1380.50",
        "finance_usd_official_last_update": "2026-03-17T09:00:00-03:00",
        "show_zero_balance_accounts": False,
        "report_sort_directions": {"journal": "desc"},
    }
    update_biz = client.put("/api/settings/preferences", json=biz_prefs)
    assert update_biz.status_code == 200

    select_home = client.post("/api/books/select", json={"name": "home"})
    assert select_home.status_code == 200
    assert client.get("/api/settings/preferences").json() == home_prefs


def test_settings_finance_endpoint_returns_official_usd_buy_rate(client, monkeypatch):
    import routers.settings as settings_router

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'{"oficial":{"value_avg":1391,"value_sell":1416,"value_buy":1366},'
                b'"last_update":"2026-03-16T11:16:04.488756-03:00"}'
            )

    monkeypatch.setattr(
        settings_router, "urlopen", lambda *args, **kwargs: FakeResponse()
    )

    response = client.get("/api/settings/finance/usd-official")
    assert response.status_code == 200
    assert response.json()["value_buy"] == 1366
    assert response.json()["last_update"] == "2026-03-16T11:16:04.488756-03:00"
