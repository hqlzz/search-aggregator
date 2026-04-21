def test_smoke_test_cli_fails_before_init_db(app, runner):
    app.config["SECRET_KEY"] = "prod-secret"
    app.config["ADMIN_PASSWORD"] = "prod-admin"

    result = runner.invoke(args=["smoke-test"])

    assert result.exit_code != 0
    assert "Smoke test: FAIL" in result.output
    assert "[ok] 健康检查: /health 返回 200" in result.output
    assert "[error] 就绪检查接口: /health/ready 返回 503" in result.output


def test_smoke_test_cli_passes_after_secure_bootstrap(app, runner):
    app.config["SECRET_KEY"] = "prod-secret"
    app.config["ADMIN_PASSWORD"] = "prod-admin"
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    result = runner.invoke(args=["smoke-test"])

    assert result.exit_code == 0
    assert "Smoke test: PASS" in result.output
    assert "[ok] 后台登录: 后台登录返回 302" in result.output
    assert "[ok] 站内搜索: /search 返回 200" in result.output
    assert "[ok] 详情页: /items/sample-item-1 返回 200" in result.output
