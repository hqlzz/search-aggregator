from app.db import get_db, search_items


def test_search_items_prefers_summary_as_excerpt(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    with app.app_context():
        results = search_items("示例内容 2")

    assert len(results) == 1
    assert results[0]["excerpt"] == "用于初始化数据库的示例条目 2"
    assert results[0]["excerpt_source"] == "summary"


def test_search_items_falls_back_to_content_excerpt_when_summary_missing(app, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    long_content = (
        "这是一段用于片段展示的很长正文，前面先放一些铺垫内容，"
        "然后让 snippet keyword 在这里出现，后面还有一些补充说明用于截断展示，"
        "这里继续补充很多很多无关说明用于拉长正文，让搜索片段在截断前不需要包含最终结尾提醒。"
        "结尾内容不应该完整显示在搜索结果卡片里。"
    )

    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE items SET summary = NULL, content = ? WHERE slug = ?",
            (long_content, "sample-item-2"),
        )
        db.commit()

        results = search_items("snippet keyword")

    assert len(results) == 1
    assert results[0]["excerpt_source"] == "content"
    assert "snippet keyword 在这里出现" in results[0]["excerpt"]
    assert "结尾内容不应该完整显示在搜索结果卡片里。" not in results[0]["excerpt"]


def test_search_page_renders_content_excerpt_when_summary_missing(client, runner):
    init_result = runner.invoke(args=["init-db"])
    assert init_result.exit_code == 0

    long_content = (
        "这是一段用于片段展示的很长正文，前面先放一些铺垫内容，"
        "然后让 snippet keyword 在这里出现，后面还有一些补充说明用于截断展示，"
        "这里继续补充很多很多无关说明用于拉长正文，让搜索片段在截断前不需要包含最终结尾提醒。"
        "结尾内容不应该完整显示在搜索结果卡片里。"
    )

    with client.application.app_context():
        db = get_db()
        db.execute(
            "UPDATE items SET summary = NULL, content = ? WHERE slug = ?",
            (long_content, "sample-item-2"),
        )
        db.commit()

    response = client.get("/search?q=snippet keyword")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "示例条目 2" in html
    assert "snippet keyword 在这里出现" in html
    assert "结尾内容不应该完整显示在搜索结果卡片里。" not in html
