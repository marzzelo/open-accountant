"""Shared pytest fixtures.

Open Accountant requires PostgreSQL for its runtime data. Tests therefore
expect a live PostgreSQL instance reachable via one of:

    OACC_TEST_DATABASE_URL   (preferred — lets CI pin a dedicated test DB)
    DATABASE_URL

Each test runs against an isolated PostgreSQL schema so parallel/sequential
runs never share state. The schema is created before the test, used via a
``search_path`` override, and dropped after the test completes.
"""

import os
import secrets

import psycopg
import pytest
from fastapi.testclient import TestClient

import app_config
from main import app


TEST_DATABASE_URL_ENV = "OACC_TEST_DATABASE_URL"
TEST_ENV_DEFAULTS = {
    app_config.AUTH_ENABLED_ENV: "true",
    app_config.AUTH_BOOTSTRAP_ADMIN_USERNAME_ENV: "admin",
    app_config.AUTH_BOOTSTRAP_ADMIN_PASSWORD_ENV: "admin-secret",
    app_config.AUTH_SESSION_DAYS_DEFAULT_ENV: "1",
    app_config.AUTH_SESSION_DAYS_REMEMBER_ME_ENV: "30",
    app_config.AUTH_COOKIE_SECURE_ENV: "false",
}


def _resolve_base_database_url() -> str:
    for env_name in (TEST_DATABASE_URL_ENV, app_config.DATABASE_URL_ENV):
        value = os.environ.get(env_name, "").strip()
        if value:
            return value
    return ""


@pytest.fixture(scope="session")
def _base_database_url() -> str:
    url = _resolve_base_database_url()
    if not url:
        pytest.skip(
            f"PostgreSQL connection URL not configured. Set "
            f"{TEST_DATABASE_URL_ENV} or {app_config.DATABASE_URL_ENV}."
        )
    return url


def _append_search_path(url: str, schema: str) -> str:
    # libpq's ``options`` URI parameter needs ``=`` and ``,`` percent-encoded.
    option = f"-c search_path={schema},public"
    encoded = (
        option.replace("%", "%25")
        .replace(" ", "%20")
        .replace("=", "%3D")
        .replace(",", "%2C")
    )
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options={encoded}"


def _apply_test_env(monkeypatch, scoped_url: str) -> None:
    monkeypatch.setenv(app_config.DATABASE_URL_ENV, scoped_url)
    for env_name, value in TEST_ENV_DEFAULTS.items():
        monkeypatch.setenv(env_name, value)


@pytest.fixture()
def isolated_paths(tmp_path, monkeypatch, _base_database_url):
    data_dir = tmp_path / "data"
    env_path = tmp_path / ".env"
    env_example_path = tmp_path / ".env.example"

    env_example_path.write_text(
        "SECRET_KEY=test-secret\nOPENAI_API_KEY=\n",
        encoding="utf-8",
    )

    schema_name = f"oacc_test_{secrets.token_hex(6)}"

    with psycopg.connect(_base_database_url, autocommit=True) as admin_conn:
        admin_conn.execute(f'CREATE SCHEMA "{schema_name}"')

    scoped_url = _append_search_path(_base_database_url, schema_name)

    monkeypatch.setattr(app_config, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_config, "ENV_PATH", env_path)
    monkeypatch.setattr(app_config, "ENV_EXAMPLE_PATH", env_example_path)
    _apply_test_env(monkeypatch, scoped_url)

    try:
        yield tmp_path
    finally:
        with psycopg.connect(_base_database_url, autocommit=True) as admin_conn:
            admin_conn.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')


@pytest.fixture()
def raw_client(isolated_paths):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def client(isolated_paths):
    # Separate TestClient so admin cookies are not affected by logins/logouts
    # performed through ``raw_client`` in the same test.
    with TestClient(app) as admin_client:
        response = admin_client.post(
            "/api/auth/login",
            json={
                "username": app_config.auth_bootstrap_admin_username(),
                "password": app_config.auth_bootstrap_admin_password(),
                "remember_me": False,
            },
        )
        assert response.status_code == 200
        yield admin_client
