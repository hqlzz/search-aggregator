import shutil
import uuid
from importlib import reload
from pathlib import Path

from app import create_app
import run


def make_workspace_temp_dir():
    parent = Path.cwd() / ".test_tmp"
    parent.mkdir(exist_ok=True)
    temp_dir = parent / f"config-{uuid.uuid4().hex}"
    temp_dir.mkdir()
    return temp_dir


def test_create_app_loads_instance_config_and_environment(monkeypatch):
    temp_dir = make_workspace_temp_dir()
    instance_path = temp_dir
    (instance_path / "config.py").write_text(
        "ADMIN_PASSWORD = 'file-admin'\nPREFERRED_URL_SCHEME = 'https'\n",
        encoding="utf-8",
    )
    custom_database = temp_dir / "custom.sqlite"
    monkeypatch.setenv("SEARCH_AGGREGATOR_SECRET_KEY", "env-secret")
    monkeypatch.setenv("SEARCH_AGGREGATOR_DATABASE", str(custom_database))
    monkeypatch.setenv("SEARCH_AGGREGATOR_TRUST_PROXY", "1")

    app = create_app(instance_path=str(instance_path))

    assert app.config["SECRET_KEY"] == "env-secret"
    assert app.config["DATABASE"] == str(custom_database)
    assert app.config["ADMIN_PASSWORD"] == "file-admin"
    assert app.config["PREFERRED_URL_SCHEME"] == "https"
    assert Path(app.instance_path).exists()
    assert app.wsgi_app.__class__.__name__ == "ProxyFix"
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_create_app_test_config_overrides_environment(monkeypatch):
    temp_dir = make_workspace_temp_dir()
    instance_path = temp_dir
    monkeypatch.setenv("SEARCH_AGGREGATOR_SECRET_KEY", "env-secret")

    app = create_app(
        test_config={
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "ADMIN_PASSWORD": "test-admin",
        },
        instance_path=str(instance_path),
    )

    assert app.config["TESTING"] is True
    assert app.config["SECRET_KEY"] == "test-secret"
    assert app.config["ADMIN_PASSWORD"] == "test-admin"
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_get_run_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("SEARCH_AGGREGATOR_HOST", "127.0.0.1")
    monkeypatch.setenv("SEARCH_AGGREGATOR_PORT", "9999")
    monkeypatch.setenv("SEARCH_AGGREGATOR_DEBUG", "true")

    reloaded_run = reload(run)
    settings = reloaded_run.get_run_settings()

    assert settings == {
        "host": "127.0.0.1",
        "port": 9999,
        "debug": True,
    }
