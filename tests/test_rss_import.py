import re

import pytest

from app.db import ManualImportValidationError, create_source, get_db
from app.feed_import import sync_enabled_rss_sources, sync_rss_source


RSS_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Feed</title>
    <item>
      <title>First Feed Item</title>
      <link>https://example.com/posts/1</link>
      <description>First summary from feed.</description>
      <author>alice@example.com (Alice)</author>
    </item>
    <item>
      <title>Second Feed Item</title>
      <link>https://example.com/posts/2</link>
      <description><![CDATA[Second <strong>summary</strong> from feed.]]></description>
    </item>
  </channel>
</rss>
"""

SECOND_RSS_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Second Feed</title>
    <item>
      <title>Third Feed Item</title>
      <link>https://example.com/other/3</link>
      <description>Third summary from feed.</description>
    </item>
  </channel>
</rss>
"""


def extract_csrf_token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def insert_rss_source(app):
    return insert_named_rss_source(
        app,
        name="Example RSS",
        slug="example-rss",
        base_url="https://example.com/feed.xml",
    )


def insert_named_rss_source(app, *, name, slug, base_url, enabled=True):
    with app.app_context():
        return create_source(
            name=name,
            slug=slug,
            source_type="rss",
            base_url=base_url,
            enabled=enabled,
            notes="RSS test source",
        )


def test_sync_rss_source_imports_new_drafts_and_skips_duplicates(app, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_rss_source(app)

    monkeypatch.setattr("app.feed_import.fetch_feed_text", lambda url, timeout=5: RSS_FEED_XML)

    with app.app_context():
        first_result = sync_rss_source("example-rss")
        second_result = sync_rss_source("example-rss")
        rows = get_db().execute(
            """
            SELECT title, external_url, summary, status
            FROM items
            WHERE source_id = (SELECT id FROM sources WHERE slug = ?)
            ORDER BY id ASC
            """,
            ("example-rss",),
        ).fetchall()

    assert first_result["created_count"] == 2
    assert first_result["skipped_count"] == 0
    assert second_result["created_count"] == 0
    assert second_result["skipped_count"] == 2
    assert [dict(row) for row in rows] == [
        {
            "title": "First Feed Item",
            "external_url": "https://example.com/posts/1",
            "summary": "First summary from feed.",
            "status": "draft",
        },
        {
            "title": "Second Feed Item",
            "external_url": "https://example.com/posts/2",
            "summary": "Second summary from feed.",
            "status": "draft",
        },
    ]


def test_sync_rss_source_rejects_non_rss_source(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            sync_rss_source("example-source-a")

    assert exc_info.value.status_code == 409
    assert exc_info.value.errors == ["仅支持抓取 rss 类型来源"]


def test_sync_rss_source_handles_invalid_feed(app, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_rss_source(app)

    monkeypatch.setattr("app.feed_import.fetch_feed_text", lambda url, timeout=5: "not xml")

    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            sync_rss_source("example-rss")

    assert exc_info.value.status_code == 502
    assert exc_info.value.errors == ["RSS 解析失败，来源内容格式无效"]


def test_admin_sync_rss_source_flow_shows_success_message(admin_client, app, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_rss_source(app)

    edit_page = admin_client.get("/admin/sources/example-rss/edit")
    csrf_token = extract_csrf_token(edit_page.get_data(as_text=True))
    monkeypatch.setattr("app.feed_import.fetch_feed_text", lambda url, timeout=5: RSS_FEED_XML)

    response = admin_client.post(
        "/admin/sources/example-rss/sync",
        data={"csrf_token": csrf_token},
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "RSS 抓取完成：新增 2 条草稿，跳过 0 条重复内容。" in html
    assert "当前来源：Example RSS（example-rss / rss）" in html

    with app.app_context():
        draft_count = get_db().execute(
            """
            SELECT COUNT(*)
            FROM items
            WHERE source_id = (SELECT id FROM sources WHERE slug = ?)
              AND status = 'draft'
            """,
            ("example-rss",),
        ).fetchone()[0]

    assert draft_count == 2


def test_sync_enabled_rss_sources_collects_results_and_errors(app, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_named_rss_source(
        app,
        name="Example RSS",
        slug="example-rss",
        base_url="https://example.com/feed.xml",
    )
    insert_named_rss_source(
        app,
        name="Second RSS",
        slug="second-rss",
        base_url="https://example.com/second.xml",
    )
    insert_named_rss_source(
        app,
        name="Disabled RSS",
        slug="disabled-rss",
        base_url="https://example.com/disabled.xml",
        enabled=False,
    )

    def fake_fetch_feed_text(url, timeout=5):
        if url.endswith("/feed.xml"):
            return RSS_FEED_XML
        if url.endswith("/second.xml"):
            raise ManualImportValidationError(["RSS 抓取失败，请稍后再试"], 502)
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.feed_import.fetch_feed_text", fake_fetch_feed_text)

    with app.app_context():
        summary = sync_enabled_rss_sources()

    assert summary["source_count"] == 2
    assert summary["success_count"] == 1
    assert summary["failure_count"] == 1
    assert summary["created_count"] == 2
    assert summary["skipped_count"] == 0
    assert len(summary["results"]) == 1
    assert summary["results"][0]["source_slug"] == "example-rss"
    assert summary["errors"] == [
        {
            "source_slug": "second-rss",
            "source_name": "Second RSS",
            "message": "RSS 抓取失败，请稍后再试",
        }
    ]


def test_admin_sync_enabled_rss_sources_flow_shows_summary(admin_client, app, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_rss_source(app)

    dashboard_page = admin_client.get("/admin")
    csrf_token = extract_csrf_token(dashboard_page.get_data(as_text=True))
    monkeypatch.setattr("app.feed_import.fetch_feed_text", lambda url, timeout=5: RSS_FEED_XML)

    response = admin_client.post(
        "/admin/sources/sync",
        data={"csrf_token": csrf_token},
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "RSS 批量抓取完成：同步 1 个来源，新增 2 条草稿，跳过 0 条内容。" in html


def test_sync_rss_cli_command_reports_summary(app, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_named_rss_source(
        app,
        name="Example RSS",
        slug="example-rss",
        base_url="https://example.com/feed.xml",
    )
    insert_named_rss_source(
        app,
        name="Second RSS",
        slug="second-rss",
        base_url="https://example.com/second.xml",
    )

    def fake_fetch_feed_text(url, timeout=5):
        if url.endswith("/feed.xml"):
            return RSS_FEED_XML
        if url.endswith("/second.xml"):
            return SECOND_RSS_FEED_XML
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("app.feed_import.fetch_feed_text", fake_fetch_feed_text)

    result = runner.invoke(args=["sync-rss"])

    assert result.exit_code == 0
    assert "已同步 2 个 RSS 来源" in result.output
    assert "新增 3 条草稿" in result.output
    assert "跳过 0 条内容" in result.output
