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
    assert version_data["tag"] == "v1.0.0"
    assert version_data["version"] == "1.0.0"
    assert version_data["full_title"] == "Open Accountant v1.0.0"


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
