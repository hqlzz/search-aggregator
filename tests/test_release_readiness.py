def test_health_ready_returns_503_before_init_db(client):
    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.get_json()
    assert payload["ready"] is False
    assert "数据库尚未初始化" in payload["blocking_issues"]


def test_health_ready_returns_200_after_secure_bootstrap(app, client, runner):
    app.config["SECRET_KEY"] = "prod-secret"
    app.config["ADMIN_PASSWORD"] = "prod-admin"
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ready"] is True
    assert payload["blocking_issues"] == []


def test_check_release_cli_fails_with_default_credentials(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    result = runner.invoke(args=["check-release"])

    assert result.exit_code != 0
    assert "Release readiness: NOT READY" in result.output
    assert "SECRET_KEY 仍为默认值" in result.output
    assert "ADMIN_PASSWORD 仍为默认值" in result.output


def test_check_release_cli_passes_after_secure_bootstrap(app, runner):
    app.config["SECRET_KEY"] = "prod-secret"
    app.config["ADMIN_PASSWORD"] = "prod-admin"
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    result = runner.invoke(args=["check-release"])

    assert result.exit_code == 0
    assert "Release readiness: READY" in result.output
    assert "[ok] SECRET_KEY: SECRET_KEY 已配置" in result.output


def test_admin_status_page_shows_release_checks(admin_client, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    response = admin_client.get("/admin/status")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "上线前检查" in html
    assert "SECRET_KEY 仍为默认值" in html
    assert "仍有阻塞项" in html
