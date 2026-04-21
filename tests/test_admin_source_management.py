import re

import pytest

from app.db import ManualImportValidationError, create_source, update_source


def extract_csrf_token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_create_source_defaults_wikipedia_base_url(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        created_source = create_source(
            name="Wikipedia EN",
            slug="wikipedia-en",
            source_type="Wikipedia",
            base_url="",
            enabled=True,
            notes="聚合测试来源",
        )

    assert created_source["id"] > 0
    assert created_source["name"] == "Wikipedia EN"
    assert created_source["slug"] == "wikipedia-en"
    assert created_source["source_type"] == "wikipedia"
    assert created_source["base_url"] == "https://en.wikipedia.org"
    assert created_source["enabled"] == 1
    assert created_source["notes"] == "聚合测试来源"


def test_create_source_defaults_hackernews_base_url(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        created_source = create_source(
            name="Hacker News",
            slug="hacker-news",
            source_type="hackernews",
            base_url="",
            enabled=True,
            notes="聚合测试来源",
        )

    assert created_source["source_type"] == "hackernews"
    assert created_source["base_url"] == "https://hn.algolia.com"


def test_create_source_requires_base_url_for_rss(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            create_source(
                name="Tech Feed",
                slug="tech-feed",
                source_type="rss",
                base_url="",
                enabled=True,
                notes="RSS 测试来源",
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.errors == ["RSS 来源地址不能为空"]


def test_create_source_rejects_unsupported_source_type(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            create_source(
                name="RSS 聚合源",
                slug="rss-feed",
                source_type="atom",
                base_url="https://example.com/feed.xml",
                enabled=True,
                notes="",
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.errors == ["来源类型仅支持 manual、rss、wikipedia 或 hackernews"]


def test_update_source_defaults_wikipedia_base_url_when_blank(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        updated_source = update_source(
            "example-source-a",
            name="Wikipedia CN",
            slug="wikipedia-cn",
            source_type="wikipedia",
            base_url="",
            enabled=True,
            notes="切换到聚合源",
        )

    assert updated_source["slug"] == "wikipedia-cn"
    assert updated_source["source_type"] == "wikipedia"
    assert updated_source["base_url"] == "https://en.wikipedia.org"


def test_admin_create_source_flow_redirects_to_edit_page(admin_client, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    form_page = admin_client.get("/admin/sources/new")
    assert form_page.status_code == 200
    csrf_token = extract_csrf_token(form_page.get_data(as_text=True))

    response = admin_client.post(
        "/admin/sources/new",
        data={
            "csrf_token": csrf_token,
            "name": "Wikipedia EN",
            "slug": "wikipedia-en",
            "source_type": "wikipedia",
            "base_url": "",
            "enabled": "1",
            "notes": "聚合测试来源",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "来源已创建" in html
    assert "Wikipedia EN（wikipedia-en / wikipedia）" in html
    assert 'value="https://en.wikipedia.org"' in html
    assert 'value="wikipedia" selected' in html


def test_admin_create_source_preserves_validation_errors(admin_client, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    form_page = admin_client.get("/admin/sources/new")
    csrf_token = extract_csrf_token(form_page.get_data(as_text=True))

    response = admin_client.post(
        "/admin/sources/new",
        data={
            "csrf_token": csrf_token,
            "name": "RSS 聚合源",
            "slug": "rss-feed",
            "source_type": "atom",
            "base_url": "https://example.com/feed.xml",
            "enabled": "1",
            "notes": "暂未支持",
        },
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "来源类型仅支持 manual、rss、wikipedia 或 hackernews" in html
    assert 'value="RSS 聚合源"' in html
    assert 'value="rss-feed"' in html
    assert '>atom</option>' not in html
