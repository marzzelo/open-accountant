import app_config
import app_version
import json

from database import get_db, init_db, table_columns, table_exists


TEST_BOARD_IMAGE_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9kAAAAASUVORK5CYII="
)


def _accounts_by_name(client):
    response = client.get("/api/accounts")
    assert response.status_code == 200
    return {item["name"]: item for item in response.json()}


def test_unauthenticated_requests_require_login(raw_client):
    accounts_response = raw_client.get("/api/accounts")
    assert accounts_response.status_code == 401

    session_response = raw_client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False


def test_login_sets_cookie_and_allows_authenticated_requests(raw_client):
    login_response = raw_client.post(
        "/api/auth/login",
        json={
            "username": app_config.auth_bootstrap_admin_username(),
            "password": app_config.auth_bootstrap_admin_password(),
            "remember_me": True,
        },
    )
    assert login_response.status_code == 200
    payload = login_response.json()
    assert payload["authenticated"] is True
    assert payload["user"]["username"] == app_config.auth_bootstrap_admin_username()
    assert payload["remember_me"] is True
    assert app_config.auth_cookie_name() in raw_client.cookies

    accounts_response = raw_client.get("/api/accounts")
    assert accounts_response.status_code == 200


def test_session_endpoint_returns_real_user_id_when_multiple_sessions_exist(
    client, raw_client
):
    login_response = raw_client.post(
        "/api/auth/login",
        json={
            "username": app_config.auth_bootstrap_admin_username(),
            "password": app_config.auth_bootstrap_admin_password(),
            "remember_me": False,
        },
    )
    assert login_response.status_code == 200

    session_response = raw_client.get("/api/auth/session")
    assert session_response.status_code == 200
    session_payload = session_response.json()
    assert session_payload["authenticated"] is True
    assert (
        session_payload["user"]["username"]
        == app_config.auth_bootstrap_admin_username()
    )
    assert session_payload["user"]["id"] == 1


def test_logout_invalidates_session_cookie(raw_client):
    login_response = raw_client.post(
        "/api/auth/login",
        json={
            "username": app_config.auth_bootstrap_admin_username(),
            "password": app_config.auth_bootstrap_admin_password(),
            "remember_me": False,
        },
    )
    assert login_response.status_code == 200

    logout_response = raw_client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["authenticated"] is False

    accounts_response = raw_client.get("/api/accounts")
    assert accounts_response.status_code == 401


def test_admin_can_create_deactivate_and_reset_user_password(client, raw_client):
    create_response = client.post(
        "/api/auth/users",
        json={
            "username": "alice",
            "password": "alice-pass-123",
            "is_admin": False,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["username"] == "alice"
    assert created["is_active"] is True

    update_response = client.put(
        f"/api/auth/users/{created['id']}",
        json={"username": "alice-edited", "is_admin": True},
    )
    assert update_response.status_code == 200
    updated_user = update_response.json()
    assert updated_user["username"] == "alice-edited"
    assert updated_user["is_admin"] is True

    list_response = client.get("/api/auth/users")
    assert list_response.status_code == 200
    assert any(item["username"] == "alice-edited" for item in list_response.json())

    login_response = raw_client.post(
        "/api/auth/login",
        json={
            "username": "alice-edited",
            "password": "alice-pass-123",
            "remember_me": False,
        },
    )
    assert login_response.status_code == 200
    raw_client.post("/api/auth/logout")

    password_response = client.put(
        f"/api/auth/users/{created['id']}/password",
        json={"password": "alice-new-pass-456"},
    )
    assert password_response.status_code == 200

    relogin_response = raw_client.post(
        "/api/auth/login",
        json={
            "username": "alice-edited",
            "password": "alice-new-pass-456",
            "remember_me": False,
        },
    )
    assert relogin_response.status_code == 200

    delete_response = client.delete(f"/api/auth/users/{created['id']}")
    assert delete_response.status_code == 204

    session_response = raw_client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["authenticated"] is False

    accounts_response = raw_client.get("/api/accounts")
    assert accounts_response.status_code == 401

    list_response = client.get("/api/auth/users")
    assert list_response.status_code == 200
    assert not any(item["username"] == "alice-edited" for item in list_response.json())

    blocked_login = raw_client.post(
        "/api/auth/login",
        json={
            "username": "alice-edited",
            "password": "alice-new-pass-456",
            "remember_me": False,
        },
    )
    assert blocked_login.status_code == 401


def test_admin_cannot_deactivate_self(client):
    users_response = client.get("/api/auth/users")
    assert users_response.status_code == 200
    admin_user = next(
        item
        for item in users_response.json()
        if item["username"] == app_config.auth_bootstrap_admin_username()
    )

    deactivate_response = client.put(
        f"/api/auth/users/{admin_user['id']}/status",
        json={"is_active": False},
    )
    assert deactivate_response.status_code == 400


def test_admin_cannot_remove_own_admin_access(client):
    users_response = client.get("/api/auth/users")
    assert users_response.status_code == 200
    admin_user = next(
        item
        for item in users_response.json()
        if item["username"] == app_config.auth_bootstrap_admin_username()
    )

    update_response = client.put(
        f"/api/auth/users/{admin_user['id']}",
        json={"username": admin_user["username"], "is_admin": False},
    )
    assert update_response.status_code == 400


def test_admin_cannot_delete_self(client):
    users_response = client.get("/api/auth/users")
    assert users_response.status_code == 200
    admin_user = next(
        item
        for item in users_response.json()
        if item["username"] == app_config.auth_bootstrap_admin_username()
    )

    delete_response = client.delete(f"/api/auth/users/{admin_user['id']}")
    assert delete_response.status_code == 400


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
    assert new_account["properties"]["liquidity_profile"] == "quick"
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
    assert account_response.json()["properties"]["liquidity_profile"] == "quick"

    salary_response = client.get(f"/api/accounts/{accounts['Salary']['id']}")
    assert salary_response.status_code == 200
    assert salary_response.json()["balance"] == 100.0

    with get_db() as conn:
        columns = set(table_columns(conn, "accounts"))
    assert "balance" not in columns


def test_account_image_round_trip_and_default_fallback(client):
    create_response = client.post(
        "/api/accounts",
        json={
            "name": "Illustrated Savings",
            "type_id": 1,
            "subtype_id": 2,
            "description": "Account with board image",
            "initial_balance": 25.0,
            "properties": json.dumps({"board_image_url": TEST_BOARD_IMAGE_DATA_URL}),
        },
    )
    assert create_response.status_code == 201

    created_account = create_response.json()
    assert created_account["properties"]["board_image_url"].startswith(
        "data:image/png;base64,"
    )

    update_response = client.put(
        f"/api/accounts/{created_account['id']}",
        json={"description": "Updated board image account"},
    )
    assert update_response.status_code == 200
    assert (
        update_response.json()["properties"]["board_image_url"]
        == created_account["properties"]["board_image_url"]
    )

    accounts = _accounts_by_name(client)
    bank_response = client.get(f"/api/accounts/{accounts['Bank']['id']}")
    assert bank_response.status_code == 200
    assert (
        bank_response.json()["properties"]["board_image_url"]
        == "/images/account-tile-default.svg"
    )


def test_init_db_bootstraps_single_database_schema(isolated_paths):
    app_config.load()
    init_db()

    expected_tables = {
        "settings",
        "types",
        "subtypes",
        "accounts",
        "transactions",
        "recurring_transactions",
        "recurring_transaction_tags",
        "users",
        "auth_sessions",
    }

    with get_db() as conn:
        missing = {name for name in expected_tables if not table_exists(conn, name)}
        account_columns = set(table_columns(conn, "accounts"))
        tx_columns = set(table_columns(conn, "transactions"))
        recurring_columns = set(table_columns(conn, "recurring_transactions"))
        projection_series_columns = set(table_columns(conn, "projection_series"))

    assert missing == set()
    assert "balance" not in account_columns
    assert {
        "original_amount",
        "original_currency",
        "fx_rate",
        "fx_source",
    } <= tx_columns
    assert {
        "alert_day",
        "alert_active",
        "enabled",
        "last_posted_period",
        "last_transaction_id",
    } <= recurring_columns
    assert "enabled" in projection_series_columns
    assert "period_months" in projection_series_columns
    assert "confirmed" in projection_series_columns


def test_recurring_transactions_crud_count_and_post_copy_tags(client):
    accounts = _accounts_by_name(client)
    tag_response = client.post(
        "/api/tags",
        json={"name": "Rent", "color": "#F97316"},
    )
    assert tag_response.status_code == 201
    tag = tag_response.json()

    create_response = client.post(
        "/api/recurring-transactions",
        json={
            "debit_account": accounts["Groceries"]["id"],
            "credit_account": accounts["Bank"]["id"],
            "amount": 750.0,
            "description": "Monthly rent",
            "alert_day": 1,
            "alert_active": True,
            "enabled": True,
            "tag_ids": [tag["id"]],
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["description"] == "Monthly rent"
    assert created["is_active"] is True
    assert created["tags"][0]["name"] == "Rent"

    count_response = client.get("/api/recurring-transactions/active-count")
    assert count_response.status_code == 200
    assert count_response.json()["count"] >= 1

    active_response = client.get("/api/recurring-transactions?filter=active")
    assert active_response.status_code == 200
    assert any(item["id"] == created["id"] for item in active_response.json())

    post_response = client.post(
        f"/api/recurring-transactions/{created['id']}/post",
        json={
            "original_amount": 800.0,
            "original_currency": "ARS",
            "date": "2026-04-30 10:00:00",
        },
    )
    assert post_response.status_code == 200
    posted = post_response.json()
    assert posted["transaction"]["amount"] == 800.0
    assert posted["transaction"]["tags"][0]["name"] == "Rent"
    assert posted["recurring"]["last_transaction_id"] == posted["transaction"]["id"]
    assert posted["recurring"]["is_active"] is False

    inactive_response = client.get("/api/recurring-transactions?filter=active")
    assert inactive_response.status_code == 200
    assert all(item["id"] != created["id"] for item in inactive_response.json())

    second_post_response = client.post(
        f"/api/recurring-transactions/{created['id']}/post",
        json={"original_amount": 810.0, "original_currency": "ARS"},
    )
    assert second_post_response.status_code == 200
    assert second_post_response.json()["transaction"]["amount"] == 810.0


def test_recurring_transactions_can_be_marked_done_without_posting(client):
    accounts = _accounts_by_name(client)
    create_response = client.post(
        "/api/recurring-transactions",
        json={
            "debit_account": accounts["Utilities"]["id"],
            "credit_account": accounts["Bank"]["id"],
            "amount": 95.0,
            "description": "Manual utility payment",
            "alert_day": 1,
            "alert_active": True,
            "enabled": True,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["is_active"] is True

    before_transactions = client.get("/api/transactions").json()
    mark_response = client.post(
        f"/api/recurring-transactions/{created['id']}/mark-done",
        json={},
    )
    assert mark_response.status_code == 200
    marked = mark_response.json()
    assert marked["is_active"] is False
    assert marked["last_posted_period"]
    assert marked["last_transaction_id"] is None

    after_transactions = client.get("/api/transactions").json()
    assert len(after_transactions) == len(before_transactions)


def test_projection_series_can_be_toggled_via_api(client):
    create_response = client.post(
        "/api/projections/series",
        json={
            "name": "Bonus",
            "type": "income",
            "start_date": "2026-07-01",
            "months": 3,
            "monthly_amount": 300.0,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["enabled"] is True
    assert created["period_months"] == 1
    assert created["confirmed"] is False

    disable_response = client.put(
        f"/api/projections/series/{created['id']}",
        json={"enabled": False},
    )
    assert disable_response.status_code == 200
    assert disable_response.json()["enabled"] is False

    list_response = client.get("/api/projections/series")
    assert list_response.status_code == 200
    listed = next(item for item in list_response.json() if item["id"] == created["id"])
    assert listed["enabled"] is False
    assert listed["period_months"] == 1
    assert listed["confirmed"] is False


def test_projection_series_can_be_confirmed_via_api(client):
    create_response = client.post(
        "/api/projections/series",
        json={
            "name": "Salary floor",
            "type": "income",
            "start_date": "2026-07-01",
            "months": 3,
            "monthly_amount": 300.0,
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    assert created["confirmed"] is False

    confirm_response = client.put(
        f"/api/projections/series/{created['id']}",
        json={"confirmed": True},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["confirmed"] is True


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

    pdf_response = client.get("/api/reports/export/pdf?report=journal")
    assert pdf_response.status_code == 200
    assert "application/pdf" in pdf_response.headers["content-type"]
    assert "libro_diario.pdf" in pdf_response.headers["content-disposition"]
    assert pdf_response.content.startswith(b"%PDF-")


def test_ledger_pdf_export_returns_a_pdf_file(client):
    accounts = _accounts_by_name(client)
    bank_account = accounts["Bank"]
    salary_account = accounts["Salary"]

    tx_response = client.post(
        "/api/transactions",
        json={
            "debit_account": bank_account["id"],
            "credit_account": salary_account["id"],
            "amount": 250.0,
            "description": "Monthly salary",
        },
    )
    assert tx_response.status_code == 201

    pdf_response = client.get(
        f"/api/reports/export/pdf?report=ledger&account_id={bank_account['id']}"
    )
    assert pdf_response.status_code == 200
    assert "application/pdf" in pdf_response.headers["content-type"]
    assert (
        f"libro_mayor_{bank_account['id']}.pdf"
        in pdf_response.headers["content-disposition"]
    )
    assert pdf_response.content.startswith(b"%PDF-")


def test_balance_exports_honor_hide_accounts_and_zero_balance_filters(client):
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

    csv_response = client.get(
        "/api/reports/export/csv?report=balance&hide_accounts=true&show_zero_balance=false"
    )
    assert csv_response.status_code == 200
    csv_body = csv_response.text
    assert "Asset,Bank,,250.0" in csv_body
    assert "Bank,250.0" not in csv_body
    assert "Grocery" not in csv_body
    assert "Income,Salary,,250.0" in csv_body

    pdf_response = client.get(
        "/api/reports/export/pdf?report=balance&hide_accounts=true&show_zero_balance=false"
    )
    assert pdf_response.status_code == 200
    assert "application/pdf" in pdf_response.headers["content-type"]


def test_balance_endpoint_honors_hide_accounts_and_zero_balance_filters(client):
    accounts = _accounts_by_name(client)

    tx_response = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Bank"]["id"],
            "credit_account": accounts["Salary"]["id"],
            "amount": 300.0,
            "description": "Monthly salary",
        },
    )
    assert tx_response.status_code == 201

    response = client.get(
        "/api/reports/balance?hide_accounts=true&show_zero_balance=false"
    )
    assert response.status_code == 200

    payload = response.json()
    asset_group = next(group for group in payload["groups"] if group["type_id"] == 1)
    income_group = next(group for group in payload["groups"] if group["type_id"] == 3)

    assert all(subgroup["items"] == [] for subgroup in asset_group["subgroups"])
    assert all(subgroup["items"] == [] for subgroup in income_group["subgroups"])
    assert any(subgroup["subtotal"] == 300.0 for subgroup in asset_group["subgroups"])
    assert all(group["type_id"] != 4 for group in payload["groups"])


def test_balance_endpoint_honors_type_ids_filter(client):
    accounts = _accounts_by_name(client)

    tx_response = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Bank"]["id"],
            "credit_account": accounts["Salary"]["id"],
            "amount": 150.0,
            "description": "Monthly salary",
        },
    )
    assert tx_response.status_code == 201

    response = client.get("/api/reports/balance?type_ids=1,3")
    assert response.status_code == 200

    payload = response.json()
    assert {group["type_id"] for group in payload["groups"]} == {1, 3}
    assert payload["total_activo"] == 150.0
    assert payload["total_ingreso"] == 150.0
    assert payload["total_pasivo"] == 0.0
    assert payload["total_patrimonio"] == 0.0


def test_create_transaction_persists_fx_traceability_fields(client):
    app_config.set_value("finance", "usd_official_buy_ars", "1100.00")
    accounts = _accounts_by_name(client)

    tx_response = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Bank"]["id"],
            "credit_account": accounts["Salary"]["id"],
            "original_amount": 10.0,
            "original_currency": "USD",
            "fx_source": "USD_BUY",
            "description": "Salary in USD",
        },
    )
    assert tx_response.status_code == 201

    payload = tx_response.json()
    assert payload["amount"] == 11000.0
    assert payload["original_amount"] == 10.0
    assert payload["original_currency"] == "USD"
    assert payload["fx_rate"] == 1100.0
    assert payload["fx_source"] == "USD_BUY"

    journal_response = client.get("/api/reports/journal")
    assert journal_response.status_code == 200
    journal_row = journal_response.json()[0]
    assert journal_row["original_amount"] == 10.0
    assert journal_row["original_currency"] == "USD"
    assert journal_row["fx_rate"] == 1100.0
    assert journal_row["fx_source"] == "USD_BUY"


def test_tags_crud_and_tag_filtered_reports(client):
    accounts = _accounts_by_name(client)

    groceries_tag = client.post(
        "/api/tags",
        json={"name": "Groceries", "color": "#16A34A"},
    )
    assert groceries_tag.status_code == 201
    groceries = groceries_tag.json()

    travel_tag = client.post(
        "/api/tags",
        json={"name": "Travel", "color": "#2563EB"},
    )
    assert travel_tag.status_code == 201
    travel = travel_tag.json()

    salary_tx = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Bank"]["id"],
            "credit_account": accounts["Salary"]["id"],
            "amount": 1000.0,
            "description": "Salary tagged",
            "tag_ids": [travel["id"]],
        },
    )
    assert salary_tx.status_code == 201
    assert salary_tx.json()["tags"][0]["name"] == "Travel"

    grocery_tx = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Groceries"]["id"],
            "credit_account": accounts["Bank"]["id"],
            "amount": 250.0,
            "description": "Weekly groceries",
            "tag_ids": [groceries["id"]],
        },
    )
    assert grocery_tx.status_code == 201

    tags_response = client.get("/api/tags")
    assert tags_response.status_code == 200
    tags_by_name = {item["name"]: item for item in tags_response.json()}
    assert tags_by_name["Groceries"]["transaction_count"] == 1
    assert tags_by_name["Travel"]["transaction_count"] == 1

    filtered_transactions = client.get(f"/api/transactions?tag_ids={groceries['id']}")
    assert filtered_transactions.status_code == 200
    filtered_payload = filtered_transactions.json()
    assert len(filtered_payload) == 1
    assert filtered_payload[0]["description"] == "Weekly groceries"

    filtered_journal = client.get(f"/api/reports/journal?tag_ids={groceries['id']}")
    assert filtered_journal.status_code == 200
    journal_payload = filtered_journal.json()
    assert len(journal_payload) == 1
    assert journal_payload[0]["tags_label"] == "Groceries"

    filtered_stats = client.get(f"/api/reports/stats?tag_ids={groceries['id']}")
    assert filtered_stats.status_code == 200
    stats_payload = filtered_stats.json()
    assert stats_payload["summary"]["total_expense"] == 250.0
    assert stats_payload["summary"]["total_income"] == 0.0

    update_tag = client.put(
        f"/api/tags/{groceries['id']}",
        json={"name": "Food", "color": "#15803D"},
    )
    assert update_tag.status_code == 200
    assert update_tag.json()["name"] == "Food"

    delete_tag = client.delete(f"/api/tags/{travel['id']}")
    assert delete_tag.status_code == 204


def test_update_transaction_recalculates_amount_from_edited_fx_fields(client):
    app_config.set_value("finance", "usd_official_buy_ars", "1100.00")
    accounts = _accounts_by_name(client)

    create_response = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Bank"]["id"],
            "credit_account": accounts["Salary"]["id"],
            "original_amount": 10.0,
            "original_currency": "USD",
            "fx_source": "USD_BUY",
            "description": "Salary in USD",
        },
    )
    assert create_response.status_code == 201
    tx_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/transactions/{tx_id}",
        json={
            "original_amount": 12.0,
            "original_currency": "USD",
            "fx_source": "USD_BUY",
            "fx_rate": 1000.0,
            "description": "Salary adjusted",
        },
    )
    assert update_response.status_code == 200

    payload = update_response.json()
    assert payload["amount"] == 12000.0
    assert payload["original_amount"] == 12.0
    assert payload["original_currency"] == "USD"
    assert payload["fx_rate"] == 1000.0
    assert payload["fx_source"] == "USD_BUY"
    assert payload["description"] == "Salary adjusted"

    bank_response = client.get(f"/api/accounts/{accounts['Bank']['id']}")
    assert bank_response.status_code == 200
    assert bank_response.json()["balance"] == 12000.0

    salary_response = client.get(f"/api/accounts/{accounts['Salary']['id']}")
    assert salary_response.status_code == 200
    assert salary_response.json()["balance"] == 12000.0


def test_update_transaction_allows_changing_credit_and_debit_accounts(client):
    accounts = _accounts_by_name(client)

    create_response = client.post(
        "/api/transactions",
        json={
            "debit_account": accounts["Bank"]["id"],
            "credit_account": accounts["Salary"]["id"],
            "amount": 100.0,
            "description": "Initial classification",
        },
    )
    assert create_response.status_code == 201
    tx_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/transactions/{tx_id}",
        json={
            "debit_account": accounts["Groceries"]["id"],
            "credit_account": accounts["Capital"]["id"],
            "amount": 100.0,
            "description": "Reclassified transaction",
        },
    )
    assert update_response.status_code == 200

    payload = update_response.json()
    assert payload["debit_account"] == accounts["Groceries"]["id"]
    assert payload["debit_name"] == "Groceries"
    assert payload["credit_account"] == accounts["Capital"]["id"]
    assert payload["credit_name"] == "Capital"
    assert payload["description"] == "Reclassified transaction"

    bank_response = client.get(f"/api/accounts/{accounts['Bank']['id']}")
    assert bank_response.status_code == 200
    assert bank_response.json()["balance"] == 0.0

    salary_response = client.get(f"/api/accounts/{accounts['Salary']['id']}")
    assert salary_response.status_code == 200
    assert salary_response.json()["balance"] == 0.0

    groceries_response = client.get(f"/api/accounts/{accounts['Groceries']['id']}")
    assert groceries_response.status_code == 200
    assert groceries_response.json()["balance"] == 100.0

    capital_response = client.get(f"/api/accounts/{accounts['Capital']['id']}")
    assert capital_response.status_code == 200
    assert capital_response.json()["balance"] == 100.0


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
    assert "summary" in stats
    assert stats["summary"]["top_expense_share"] is None
    assert "total_runway_months" in stats["summary"]
    assert "avg_monthly_income_recent" in stats["summary"]
    assert "income_evolution" in stats
    assert "expense_evolution" in stats
    assert "account_stats" in stats
    assert isinstance(stats["account_stats"], list)
    assert "liability_evolution" in stats
    assert "net_worth_evolution" in stats


def test_settings_config_and_preferences_persist_in_main_database(
    client, isolated_paths
):
    config_response = client.get("/api/settings/config")
    assert config_response.status_code == 200
    assert "current_book" not in config_response.json()["general"]
    assert config_response.json()["finance"]["usd_official_buy_ars"] == "0.00"

    update_config = client.put(
        "/api/settings/config",
        json={
            "general": {"host": "0.0.0.0", "port": "6001"},
            "app": {"name": "PostgreSQL Settings", "language": "en"},
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
    assert config_json["app"]["name"] == "PostgreSQL Settings"
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
        "board_view_mode": "compact",
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

    with get_db() as conn:
        settings_rows = [
            (row["section"], row["key"], row["value"])
            for row in conn.execute(
                "SELECT section, key, value FROM settings ORDER BY section, key"
            ).fetchall()
        ]
    assert ("general", "port", "6001") in settings_rows
    assert ("app", "language", "en") in settings_rows
    assert ("finance", "usd_official_buy_ars", "1366.00") in settings_rows
    assert ("finance", "usd_official_sell_ars", "1417.00") in settings_rows
    assert ("finance", "usd_blue_buy_ars", "1405.00") in settings_rows
    assert ("finance", "usd_blue_sell_ars", "1425.00") in settings_rows
    assert ("finance", "usd_card_ars", "1842.10") in settings_rows
    assert (
        "finance",
        "usd_official_last_update",
        "2026-03-16T11:16:04.488756-03:00",
    ) in settings_rows

    with get_db() as conn:
        preference_keys = [
            row["key"]
            for row in conn.execute(
                "SELECT key FROM user_preferences ORDER BY key"
            ).fetchall()
        ]
    assert not any(key.startswith("finance_") for key in preference_keys)
    assert "show_zero_balance_accounts" in preference_keys
    assert "report_sort_directions" in preference_keys
    assert "common_transactions_pins" in preference_keys


def test_user_preferences_are_global_in_single_database(client):
    preferences = {
        "show_zero_balance_accounts": True,
        "board_view_mode": "compact",
        "report_sort_directions": {"journal": "asc", "ledger": "asc", "txlist": "desc"},
    }
    response = client.put("/api/settings/preferences", json=preferences)
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

    assert client.get("/api/settings/preferences").json() == preferences
    assert (
        client.get("/api/settings/config").json()["finance"]
        == finance_config["finance"]
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
