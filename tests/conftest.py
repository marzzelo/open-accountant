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

    return tmp_path


@pytest.fixture()
def client(isolated_paths):
    with TestClient(app) as test_client:
        yield test_client
