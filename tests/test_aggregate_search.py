from app.aggregate import clear_aggregate_cache, search_aggregate_items
from app.db import get_db, get_enabled_aggregate_sources


def insert_wikipedia_source(app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO sources (name, slug, source_type, base_url, enabled, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "Wikipedia",
                "wikipedia-en",
                "wikipedia",
                "https://en.wikipedia.org",
                1,
                "Aggregate search provider",
            ),
        )
        db.commit()


def insert_hackernews_source(app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO sources (name, slug, source_type, base_url, enabled, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "Hacker News",
                "hacker-news",
                "hackernews",
                "https://hn.algolia.com",
                1,
                "Aggregate search provider",
            ),
        )
        db.commit()


def test_get_enabled_aggregate_sources_returns_supported_enabled_sources_only(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO sources (name, slug, source_type, base_url, enabled, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Wikipedia", "wikipedia-en", "wikipedia", "https://en.wikipedia.org", 1, "Aggregate"),
        )
        db.execute(
            """
            INSERT INTO sources (name, slug, source_type, base_url, enabled, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("Wikipedia Disabled", "wikipedia-disabled", "wikipedia", "https://en.wikipedia.org", 0, "Aggregate"),
        )
        db.commit()

        aggregate_sources = get_enabled_aggregate_sources({"wikipedia"})

    assert aggregate_sources == [
        {
            "name": "Wikipedia",
            "slug": "wikipedia-en",
            "source_type": "wikipedia",
            "base_url": "https://en.wikipedia.org",
        }
    ]


def test_search_aggregate_items_parses_wikipedia_results_and_uses_cache(monkeypatch):
    clear_aggregate_cache()
    calls = []

    def fake_fetch_json(url, timeout=4):
        calls.append(url)
        return [
            "python",
            ["Python (programming language)"],
            ["High-level programming language"],
            ["https://en.wikipedia.org/wiki/Python_(programming_language)"],
        ]

    monkeypatch.setattr("app.aggregate.fetch_json", fake_fetch_json)
    source = {
        "name": "Wikipedia",
        "slug": "wikipedia-en",
        "source_type": "wikipedia",
        "base_url": "https://en.wikipedia.org",
    }

    results, errors = search_aggregate_items("python", [source], limit=5)
    cached_results, cached_errors = search_aggregate_items("python", [source], limit=5)

    assert errors == []
    assert cached_errors == []
    assert len(calls) == 1
    assert results == cached_results
    assert results == [
        {
            "title": "Python (programming language)",
            "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "excerpt": "High-level programming language",
            "source_name": "Wikipedia",
            "source_slug": "wikipedia-en",
            "provider": "wikipedia",
        }
    ]


def test_search_aggregate_items_parses_hackernews_results(monkeypatch):
    clear_aggregate_cache()

    def fake_fetch_json(url, timeout=4):
        return {
            "hits": [
                {
                    "title": "Python static typing at scale",
                    "url": "https://example.com/python-typing",
                    "author": "alice",
                    "points": 321,
                    "story_text": "A practical write-up about using typing in large Python projects.",
                }
            ]
        }

    monkeypatch.setattr("app.aggregate.fetch_json", fake_fetch_json)
    source = {
        "name": "Hacker News",
        "slug": "hacker-news",
        "source_type": "hackernews",
        "base_url": "https://hn.algolia.com",
    }

    results, errors = search_aggregate_items("python", [source], limit=5)

    assert errors == []
    assert results == [
        {
            "title": "Python static typing at scale",
            "url": "https://example.com/python-typing",
            "excerpt": "A practical write-up about using typing in large Python projects.",
            "source_name": "Hacker News",
            "source_slug": "hacker-news",
            "provider": "hackernews",
        }
    ]


def test_search_page_keeps_placeholder_when_no_aggregate_sources_configured(client, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    response = client.get("/search?q=python&mode=aggregate")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "聚合搜索功能开发中" in html
    assert "当前尚未配置可用聚合源" in html
    assert "共找到 0 条结果" in html


def test_search_page_renders_configured_aggregate_results(app, client, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_wikipedia_source(app)
    clear_aggregate_cache()

    def fake_fetch_json(url, timeout=4):
        return [
            "python",
            ["Python (programming language)"],
            ["High-level programming language"],
            ["https://en.wikipedia.org/wiki/Python_(programming_language)"],
        ]

    monkeypatch.setattr("app.aggregate.fetch_json", fake_fetch_json)

    response = client.get("/search?q=python&mode=aggregate")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "共找到 1 条结果" in html
    assert "已检索 1 个聚合源。" in html
    assert "Python (programming language)" in html
    assert "High-level programming language" in html
    assert "Wikipedia" in html
    assert "打开结果" in html
    assert "/items/" not in html


def test_search_page_renders_hackernews_results(app, client, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_hackernews_source(app)
    clear_aggregate_cache()

    def fake_fetch_json(url, timeout=4):
        return {
            "hits": [
                {
                    "title": "Python static typing at scale",
                    "url": "https://example.com/python-typing",
                    "author": "alice",
                    "points": 321,
                    "story_text": "A practical write-up about using typing in large Python projects.",
                }
            ]
        }

    monkeypatch.setattr("app.aggregate.fetch_json", fake_fetch_json)

    response = client.get("/search?q=python&mode=aggregate")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "共找到 1 条结果" in html
    assert "Hacker News" in html
    assert "Python static typing at scale" in html
    assert "A practical write-up about using typing in large Python projects." in html
    assert "打开结果" in html


def test_search_page_handles_aggregate_provider_failure_gracefully(app, client, runner, monkeypatch):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0
    insert_wikipedia_source(app)
    clear_aggregate_cache()

    def fake_fetch_json(url, timeout=4):
        raise OSError("network down")

    monkeypatch.setattr("app.aggregate.fetch_json", fake_fetch_json)

    response = client.get("/search?q=python&mode=aggregate")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "聚合搜索暂时不可用，请稍后再试。" in html
    assert "共找到 0 条结果" in html
