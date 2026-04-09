import pytest
from fastapi.testclient import TestClient

import app_config
from main import app


@pytest.fixture()
def isolated_paths(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    db_path = data_dir / "open_accountant.db"
    config_path = tmp_path / "config.ini"
    env_path = tmp_path / ".env"
    env_example_path = tmp_path / ".env.example"

    config_path.write_text(
        "[general]\n"
        "host = 127.0.0.1\n"
        "port = 5999\n\n"
        "[app]\n"
        "name = Open Accountant Test\n"
        "language = es\n",
        encoding="utf-8",
    )

    env_example_path.write_text(
        "SECRET_KEY=test-secret\nOPENAI_API_KEY=\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(app_config, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_config, "CONFIG_PATH", config_path)
    monkeypatch.setattr(app_config, "ENV_PATH", env_path)
    monkeypatch.setattr(app_config, "ENV_EXAMPLE_PATH", env_example_path)
    monkeypatch.setenv(app_config.DATABASE_URL_ENV, f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv(app_config.AUTH_ENABLED_ENV, "true")
    monkeypatch.setenv(app_config.AUTH_BOOTSTRAP_ADMIN_USERNAME_ENV, "admin")
    monkeypatch.setenv(app_config.AUTH_BOOTSTRAP_ADMIN_PASSWORD_ENV, "admin-secret")
    monkeypatch.setenv(app_config.AUTH_SESSION_DAYS_DEFAULT_ENV, "1")
    monkeypatch.setenv(app_config.AUTH_SESSION_DAYS_REMEMBER_ME_ENV, "30")
    monkeypatch.setenv(app_config.AUTH_COOKIE_SECURE_ENV, "false")

    return tmp_path


@pytest.fixture()
def raw_client(isolated_paths):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def client(raw_client):
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/auth/login",
            json={
                "username": app_config.auth_bootstrap_admin_username(),
                "password": app_config.auth_bootstrap_admin_password(),
                "remember_me": False,
            },
        )
        assert response.status_code == 200
        yield test_client
