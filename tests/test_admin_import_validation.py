import re

import pytest

from app.db import ManualImportValidationError, create_manual_import_item, update_draft_item


def extract_csrf_token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_create_manual_import_item_is_bootstrap_safe_before_init_db(app):
    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            create_manual_import_item(
                source_slug="example-source-a",
                category_slug="",
                title="未初始化导入",
                summary="一段摘要",
                content="",
                external_url="",
            )

    assert exc_info.value.status_code == 503
    assert exc_info.value.errors == ["数据库尚未初始化，暂时无法导入条目"]


def test_admin_import_post_is_bootstrap_safe_before_init_db(admin_client):
    form_page = admin_client.get("/admin/import")
    csrf_token = extract_csrf_token(form_page.get_data(as_text=True))

    response = admin_client.post(
        "/admin/import",
        data={
            "csrf_token": csrf_token,
            "source_slug": "example-source-a",
            "category_slug": "",
            "title": "未初始化导入",
            "summary": "一段摘要",
            "content": "",
            "external_url": "",
        },
    )

    assert response.status_code == 503
    assert "数据库尚未初始化，暂时无法导入条目" in response.get_data(as_text=True)


def test_create_manual_import_item_requires_meaningful_content(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            create_manual_import_item(
                source_slug="example-source-a",
                category_slug="example-category",
                title="空内容草稿",
                summary="   ",
                content="",
                external_url=" ",
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.errors == ["摘要、正文或外链至少填写一项"]


def test_admin_import_post_shows_meaningful_content_error_and_preserves_values(admin_client, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    form_page = admin_client.get("/admin/import")
    csrf_token = extract_csrf_token(form_page.get_data(as_text=True))

    response = admin_client.post(
        "/admin/import",
        data={
            "csrf_token": csrf_token,
            "source_slug": "example-source-a",
            "category_slug": "example-category",
            "title": "空内容草稿",
            "summary": "   ",
            "content": "",
            "external_url": " ",
        },
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "摘要、正文或外链至少填写一项" in html
    assert 'value="空内容草稿"' in html
    assert 'value="example-source-a" selected' in html
    assert 'value="example-category" selected' in html


def test_update_draft_item_requires_meaningful_content(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        created = create_manual_import_item(
            source_slug="example-source-a",
            category_slug="example-category",
            title="可编辑草稿",
            summary="初始摘要",
            content="",
            external_url="",
        )

        with pytest.raises(ManualImportValidationError) as exc_info:
            update_draft_item(
                created["slug"],
                source_slug="example-source-a",
                category_slug="example-category",
                title="可编辑草稿",
                summary="",
                content=" ",
                external_url="",
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.errors == ["摘要、正文或外链至少填写一项"]
