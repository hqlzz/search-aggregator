import click
from flask import current_app
from flask.cli import with_appcontext

from .db import (
    RSS_SOURCE_TYPE,
    get_admin_status_snapshot,
    get_db,
    has_bootstrapped_tables,
    is_safe_external_url,
)
from .runtime_config import DEFAULT_ADMIN_PASSWORD, DEFAULT_SECRET_KEY


def get_invalid_enabled_rss_source_count():
    snapshot = get_admin_status_snapshot()
    if not snapshot["database_ready"]:
        return 0

    rows = get_db().execute(
        """
        SELECT base_url
        FROM sources
        WHERE enabled = 1
          AND lower(source_type) = ?
        """,
        (RSS_SOURCE_TYPE,),
    ).fetchall()
    return sum(1 for row in rows if not is_safe_external_url((row["base_url"] or "").strip()))


def build_check(label, status, message):
    return {
        "label": label,
        "status": status,
        "message": message,
    }


def get_release_readiness_snapshot():
    status_snapshot = get_admin_status_snapshot()
    checks = []

    if current_app.config.get("SECRET_KEY") == DEFAULT_SECRET_KEY:
        checks.append(build_check("SECRET_KEY", "error", "SECRET_KEY 仍为默认值"))
    else:
        checks.append(build_check("SECRET_KEY", "ok", "SECRET_KEY 已配置"))

    if current_app.config.get("ADMIN_PASSWORD") == DEFAULT_ADMIN_PASSWORD:
        checks.append(build_check("ADMIN_PASSWORD", "error", "ADMIN_PASSWORD 仍为默认值"))
    else:
        checks.append(build_check("ADMIN_PASSWORD", "ok", "ADMIN_PASSWORD 已配置"))

    if not status_snapshot["database_ready"]:
        checks.append(build_check("数据库", "error", "数据库尚未初始化"))
    else:
        checks.append(build_check("数据库", "ok", "数据库已初始化"))

    if status_snapshot["fts_ready"]:
        checks.append(build_check("FTS", "ok", "FTS 索引已就绪"))
    else:
        checks.append(build_check("FTS", "error", "FTS 索引未就绪"))

    if status_snapshot["enabled_source_count"] > 0:
        checks.append(build_check("来源", "ok", f"已启用 {status_snapshot['enabled_source_count']} 个来源"))
    else:
        checks.append(build_check("来源", "error", "没有已启用的数据源"))

    if status_snapshot["published_item_count"] > 0:
        checks.append(build_check("公开内容", "ok", f"已有 {status_snapshot['published_item_count']} 条公开条目"))
    else:
        checks.append(build_check("公开内容", "error", "没有任何公开条目"))

    invalid_rss_source_count = get_invalid_enabled_rss_source_count()
    if invalid_rss_source_count > 0:
        checks.append(
            build_check(
                "RSS 来源",
                "error",
                f"{invalid_rss_source_count} 个已启用 RSS 来源缺少有效地址",
            )
        )
    else:
        checks.append(build_check("RSS 来源", "ok", "已启用 RSS 来源地址检查通过"))

    if status_snapshot["draft_item_count"] > 0:
        checks.append(
            build_check(
                "草稿内容",
                "warning",
                f"仍有 {status_snapshot['draft_item_count']} 条草稿待审核发布",
            )
        )
    else:
        checks.append(build_check("草稿内容", "ok", "当前没有待审核草稿"))

    blocking_issues = [check["message"] for check in checks if check["status"] == "error"]
    warning_issues = [check["message"] for check in checks if check["status"] == "warning"]

    return {
        "ready_for_launch": not blocking_issues,
        "checks": checks,
        "blocking_issues": blocking_issues,
        "warning_issues": warning_issues,
    }


def build_smoke_check(label, passed, message):
    return {
        "label": label,
        "status": "ok" if passed else "error",
        "message": message,
    }


def _check_response_status(response, expected_status):
    return response.status_code == expected_status


def get_release_smoke_snapshot():
    client = current_app.test_client()
    checks = []

    health_response = client.get("/health")
    health_ok = _check_response_status(health_response, 200) and health_response.get_json().get("status") == "ok"
    checks.append(build_smoke_check("健康检查", health_ok, f"/health 返回 {health_response.status_code}"))

    index_response = client.get("/")
    index_ok = _check_response_status(index_response, 200)
    checks.append(build_smoke_check("首页", index_ok, f"/ 返回 {index_response.status_code}"))

    login_page = client.get("/admin/login")
    login_page_ok = _check_response_status(login_page, 200)
    checks.append(build_smoke_check("后台登录页", login_page_ok, f"/admin/login 返回 {login_page.status_code}"))

    login_response = client.post("/admin/login", data={"password": current_app.config["ADMIN_PASSWORD"]})
    login_ok = login_response.status_code == 302
    checks.append(build_smoke_check("后台登录", login_ok, f"后台登录返回 {login_response.status_code}"))

    admin_response = client.get("/admin")
    admin_ok = _check_response_status(admin_response, 200)
    checks.append(build_smoke_check("后台首页", admin_ok, f"/admin 返回 {admin_response.status_code}"))

    admin_status_response = client.get("/admin/status")
    admin_status_ok = (
        _check_response_status(admin_status_response, 200)
        and "上线前检查" in admin_status_response.get_data(as_text=True)
    )
    checks.append(build_smoke_check("后台状态页", admin_status_ok, f"/admin/status 返回 {admin_status_response.status_code}"))

    readiness_response = client.get("/health/ready")
    readiness_payload = readiness_response.get_json() or {}
    readiness_ok = _check_response_status(readiness_response, 200) and readiness_payload.get("ready") is True
    checks.append(
        build_smoke_check(
            "就绪检查接口",
            readiness_ok,
            f"/health/ready 返回 {readiness_response.status_code}",
        )
    )

    if has_bootstrapped_tables():
        search_response = client.get("/search?q=示例")
        search_ok = _check_response_status(search_response, 200) and "共找到" in search_response.get_data(as_text=True)
        checks.append(build_smoke_check("站内搜索", search_ok, f"/search 返回 {search_response.status_code}"))

        detail_response = client.get("/items/sample-item-1")
        detail_ok = _check_response_status(detail_response, 200)
        checks.append(build_smoke_check("详情页", detail_ok, f"/items/sample-item-1 返回 {detail_response.status_code}"))

    blocking_issues = [check["message"] for check in checks if check["status"] == "error"]
    return {
        "passed": not blocking_issues,
        "checks": checks,
        "blocking_issues": blocking_issues,
    }


@click.command("check-release")
@with_appcontext
def check_release_command():
    snapshot = get_release_readiness_snapshot()
    click.echo(f"Release readiness: {'READY' if snapshot['ready_for_launch'] else 'NOT READY'}")
    for check in snapshot["checks"]:
        click.echo(f"[{check['status']}] {check['label']}: {check['message']}")

    if snapshot["blocking_issues"]:
        raise click.ClickException(f"发现 {len(snapshot['blocking_issues'])} 个阻塞项")


@click.command("smoke-test")
@with_appcontext
def smoke_test_command():
    snapshot = get_release_smoke_snapshot()
    click.echo(f"Smoke test: {'PASS' if snapshot['passed'] else 'FAIL'}")
    for check in snapshot["checks"]:
        click.echo(f"[{check['status']}] {check['label']}: {check['message']}")

    if snapshot["blocking_issues"]:
        raise click.ClickException(f"发现 {len(snapshot['blocking_issues'])} 个冒烟检查失败项")


def init_app(app):
    app.cli.add_command(check_release_command)
    app.cli.add_command(smoke_test_command)
