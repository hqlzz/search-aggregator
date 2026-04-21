import shutil
import uuid
from pathlib import Path

import pytest

from app import create_app


@pytest.fixture
def app():
    workspace_root = Path(r"D:\codex\search-aggregator")
    temp_root = workspace_root / ".test_tmp" if workspace_root.exists() else Path.cwd() / ".test_tmp"
    temp_root.mkdir(exist_ok=True)
    temp_dir = temp_root / uuid.uuid4().hex
    temp_dir.mkdir()
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(temp_dir / "test.sqlite"),
        }
    )

    yield app

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def admin_client(app, client):
    app.config["ADMIN_PASSWORD"] = "test-admin-password"
    response = client.post("/admin/login", data={"password": "test-admin-password"})
    assert response.status_code == 302
    return client
