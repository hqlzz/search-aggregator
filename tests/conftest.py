import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    app = create_app({
        'TESTING': True,
        'DATABASE': str(tmp_path / 'test.sqlite'),
    })

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def admin_client(app, client):
    app.config['ADMIN_PASSWORD'] = 'test-admin-password'
    response = client.post('/admin/login', data={'password': 'test-admin-password'})
    assert response.status_code == 302
    return client
