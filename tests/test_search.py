from app.db import (
    get_db,
    get_item_detail,
    get_recent_items,
    get_search_category_options,
    get_search_source_options,
    search_items,
)


def test_search_items_returns_seeded_matches_using_fts(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        results = search_items('示例内容 3')

    assert len(results) == 1
    assert results[0]['title'] == '示例条目 3'
    assert results[0]['source_name'] == '示例站点 B'


def test_search_items_handles_special_characters_without_crashing(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        results = search_items('"示例内容 2')

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]['title'] == '示例条目 2'


def test_search_items_can_filter_by_source_slug(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        results = search_items('示例内容', source_slug='example-source-b')

    assert len(results) == 1
    assert results[0]['slug'] == 'sample-item-3'
    assert all(item['source_slug'] == 'example-source-b' for item in results)


def test_get_search_source_options_returns_enabled_sources_with_published_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        options = get_search_source_options()

    assert options == [
        {'name': '示例站点 A', 'slug': 'example-source-a'},
        {'name': '示例站点 B', 'slug': 'example-source-b'},
    ]


def test_get_search_source_options_excludes_disabled_sources(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        db.execute("UPDATE sources SET enabled = 0 WHERE slug = ?", ('example-source-b',))
        db.commit()

        options = get_search_source_options()

    assert options == [
        {'name': '示例站点 A', 'slug': 'example-source-a'},
    ]


def test_get_search_source_options_excludes_sources_with_only_unpublished_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        db.execute("UPDATE items SET status = 'draft' WHERE source_id = (SELECT id FROM sources WHERE slug = ?)", ('example-source-b',))
        db.commit()

        options = get_search_source_options()

    assert options == [
        {'name': '示例站点 A', 'slug': 'example-source-a'},
    ]


def test_get_search_category_options_returns_categories_with_published_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        options = get_search_category_options()

    assert options == [
        {'name': '示例分类', 'slug': 'example-category'},
    ]


def test_search_items_can_filter_by_category_slug(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?)",
            ('第二分类', 'second-category'),
        )
        second_category_id = db.execute(
            "SELECT id FROM categories WHERE slug = ?",
            ('second-category',),
        ).fetchone()[0]
        db.execute(
            "UPDATE items SET category_id = ? WHERE slug = ?",
            (second_category_id, 'sample-item-3'),
        )
        db.commit()

        results = search_items('示例内容', category_slug='second-category')

    assert len(results) == 1
    assert results[0]['slug'] == 'sample-item-3'
    assert results[0]['category_slug'] == 'second-category'


def test_get_search_category_options_excludes_categories_with_only_unpublished_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        db.execute("UPDATE items SET status = 'draft'")
        db.commit()

        options = get_search_category_options()

    assert options == []


def test_search_items_rebuilds_fts_index_for_existing_rows(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        source_id = db.execute("SELECT id FROM sources WHERE slug = ?", ('example-source-a',)).fetchone()[0]
        category_id = db.execute("SELECT id FROM categories WHERE slug = ?", ('example-category',)).fetchone()[0]
        db.execute(
            """
            INSERT INTO items (source_id, category_id, title, slug, summary, content, external_url, author)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                category_id,
                '旧数据条目',
                'legacy-item',
                '通过 rebuild 重建索引的旧数据',
                '旧数据内容关键字',
                'https://example.com/legacy',
                '迁移脚本',
            ),
        )
        db.commit()
        db.execute("DELETE FROM item_search")
        db.commit()
        runner.invoke(args=['init-db'])
        results = search_items('旧数据内容关键字')

    assert len(results) == 1
    assert results[0]['title'] == '旧数据条目'


def test_get_item_detail_returns_joined_item_data(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        item = get_item_detail('sample-item-2')

    assert item is not None
    assert item['title'] == '示例条目 2'
    assert item['slug'] == 'sample-item-2'
    assert item['summary'] == '用于初始化数据库的示例条目 2'
    assert item['content'] == '示例内容 2'
    assert item['external_url'] == 'https://example.com/a/2'
    assert item['source_name'] == '示例站点 A'
    assert item['category_name'] == '示例分类'


def test_unpublished_items_are_excluded_from_recent_items_search_and_detail(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        source_id = db.execute("SELECT id FROM sources WHERE slug = ?", ('example-source-a',)).fetchone()[0]
        category_id = db.execute("SELECT id FROM categories WHERE slug = ?", ('example-category',)).fetchone()[0]
        db.execute(
            """
            INSERT INTO items (
                source_id, category_id, title, slug, summary, content, external_url, author, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                category_id,
                '未发布条目',
                'draft-item',
                '不应出现在列表或搜索中',
                '隐藏关键字 only-draft-match',
                'https://example.com/draft',
                '编辑部',
                'draft',
            ),
        )
        db.commit()

        recent_items = get_recent_items(limit=10)
        search_results = search_items('only-draft-match')
        unpublished_item = get_item_detail('draft-item')

    assert all(item['slug'] != 'draft-item' for item in recent_items)
    assert search_results == []
    assert unpublished_item is None


def test_search_page_shows_matching_results(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容 2')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '搜索结果' in html
    assert '共找到 1 条结果' in html
    assert '示例条目 2' in html
    assert '示例站点 A' in html


def test_search_page_renders_source_filter_options(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '按来源筛选' in html
    assert '<option value="example-source-a">示例站点 A</option>' in html
    assert '<option value="example-source-b">示例站点 B</option>' in html


def test_search_page_filters_results_and_preserves_selected_source(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容&source=example-source-b')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '共找到 1 条结果' in html
    assert '示例条目 3' in html
    assert '示例条目 1' not in html
    assert 'option value="example-source-b" selected' in html
    assert '当前筛选来源：示例站点 B' in html


def test_homepage_renders_source_filter_options(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '按来源筛选' in html
    assert 'name="source"' in html
    assert 'value="example-source-a"' in html


def test_homepage_renders_search_mode_options(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '搜索模式' in html
    assert 'value="local" selected' in html
    assert '站内搜索' in html
    assert 'value="aggregate"' in html
    assert '聚合搜索' in html


def test_search_page_shows_placeholder_when_aggregate_mode_is_selected(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=测试关键词&mode=aggregate')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '当前搜索模式：聚合搜索' in html
    assert '聚合搜索功能开发中，后续将支持外部搜索源接入。' in html
    assert '共找到 0 条结果' in html
    assert '示例条目' not in html
    assert 'value="aggregate" selected' in html


def test_search_page_ignores_unknown_source_filter(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容&source=missing-source')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '共找到 3 条结果' in html
    assert '当前筛选来源：' not in html
    assert 'option value="" selected' in html


def test_search_page_renders_category_filter_options(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '按分类筛选' in html
    assert '<option value="example-category">示例分类</option>' in html


def test_search_page_filters_results_and_preserves_selected_category(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with client.application.app_context():
        db = get_db()
        db.execute(
            "INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?)",
            ('第二分类', 'second-category'),
        )
        second_category_id = db.execute(
            "SELECT id FROM categories WHERE slug = ?",
            ('second-category',),
        ).fetchone()[0]
        db.execute(
            "UPDATE items SET category_id = ? WHERE slug = ?",
            (second_category_id, 'sample-item-3'),
        )
        db.commit()

    response = client.get('/search?q=示例内容&category=second-category')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '共找到 1 条结果' in html
    assert '示例条目 3' in html
    assert '示例条目 1' not in html
    assert 'option value="second-category" selected' in html
    assert '当前筛选分类：第二分类' in html


def test_search_page_ignores_unknown_category_filter(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容&category=unknown-category')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '共找到 3 条结果' in html
    assert '当前筛选分类：' not in html
    assert 'id="results-category"' in html
    assert 'option value="" selected' in html


def test_search_page_handles_empty_query_without_hitting_database(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=   ')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '请输入关键词后再搜索。' in html
    assert '共找到 0 条结果' in html


def test_search_page_shows_no_results_message_for_unmatched_query(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=完全不存在的关键词')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '没有找到匹配的条目，请尝试其他关键词。' in html
    assert '共找到 0 条结果' in html


def test_item_detail_page_renders_full_information(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/items/sample-item-3')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '示例条目 3' in html
    assert '示例站点 B' in html
    assert '示例分类' in html
    assert '用于初始化数据库的示例条目 3' in html
    assert '示例内容 3' in html
    assert 'https://example.com/b/3' in html
    assert '查看原文' in html


def test_item_detail_page_returns_404_for_missing_slug(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/items/missing-item')

    assert response.status_code == 404


def test_item_detail_page_returns_404_for_unpublished_slug(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with client.application.app_context():
        db = get_db()
        source_id = db.execute("SELECT id FROM sources WHERE slug = ?", ('example-source-a',)).fetchone()[0]
        category_id = db.execute("SELECT id FROM categories WHERE slug = ?", ('example-category',)).fetchone()[0]
        db.execute(
            """
            INSERT INTO items (
                source_id, category_id, title, slug, summary, content, external_url, author, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                category_id,
                '未发布详情条目',
                'draft-detail-item',
                '详情页不可见',
                '隐藏详情内容',
                'https://example.com/draft-detail',
                '编辑部',
                'draft',
            ),
        )
        db.commit()

    response = client.get('/items/draft-detail-item')

    assert response.status_code == 404


def test_homepage_and_search_results_include_detail_links(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    homepage_response = client.get('/')
    search_response = client.get('/search?q=示例内容 2')

    homepage_html = homepage_response.get_data(as_text=True)
    search_html = search_response.get_data(as_text=True)

    assert '/items/sample-item-3' in homepage_html
    assert '/items/sample-item-2' in search_html


def test_homepage_and_search_do_not_render_detail_links_for_unpublished_items(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with client.application.app_context():
        db = get_db()
        source_id = db.execute("SELECT id FROM sources WHERE slug = ?", ('example-source-b',)).fetchone()[0]
        category_id = db.execute("SELECT id FROM categories WHERE slug = ?", ('example-category',)).fetchone()[0]
        db.execute(
            """
            INSERT INTO items (
                source_id, category_id, title, slug, summary, content, external_url, author, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                category_id,
                '隐藏链接条目',
                'hidden-link-item',
                '不应暴露详情链接',
                '隐藏检索词 hidden-link-keyword',
                'https://example.com/hidden-link',
                '编辑部',
                'draft',
            ),
        )
        db.commit()

    homepage_response = client.get('/')
    search_response = client.get('/search?q=hidden-link-keyword')

    homepage_html = homepage_response.get_data(as_text=True)
    search_html = search_response.get_data(as_text=True)

    assert 'hidden-link-item' not in homepage_html
    assert '/items/hidden-link-item' not in homepage_html
    assert '隐藏链接条目' not in search_html
    assert '/items/hidden-link-item' not in search_html
    assert '共找到 0 条结果' in search_html
