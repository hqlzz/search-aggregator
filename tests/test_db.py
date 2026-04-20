import re

import pytest

from app.db import (
    ManualImportValidationError,
    PublishValidationError,
    create_manual_import_item,
    get_admin_dashboard_data,
    get_admin_edit_item,
    get_admin_edit_source,
    get_admin_status_snapshot,
    get_db,
    get_homepage_data,
    publish_item,
    update_draft_item,
    update_source,
)


def extract_csrf_token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match is not None
    return match.group(1)



def assert_status_field_value(html, label, value):
    pattern = re.compile(
        rf'<strong>{re.escape(label)}</strong>\s*<div class="admin-meta">\s*<span>{re.escape(value)}</span>',
        re.S,
    )
    assert pattern.search(html) is not None



def test_admin_requires_login_redirects_to_login_page(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/admin')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/login?next=%2Fadmin')



def test_admin_status_requires_login_redirects_to_login_page(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/admin/status')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/login?next=%2Fadmin%2Fstatus')



def test_admin_login_page_renders_form(client):
    response = client.get('/admin/login')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '后台登录' in html
    assert '管理口令' in html



def test_admin_login_rejects_invalid_password(app, client):
    app.config['ADMIN_PASSWORD'] = 'test-admin-password'

    response = client.post('/admin/login', data={'password': 'wrong-password'})

    assert response.status_code == 401
    assert '口令错误' in response.get_data(as_text=True)



def test_admin_logout_clears_session(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    login_page = admin_client.get('/admin')
    csrf_token = extract_csrf_token(login_page.get_data(as_text=True))

    response = admin_client.post('/admin/logout', data={'csrf_token': csrf_token})
    assert response.status_code == 302

    protected_response = admin_client.get('/admin')
    assert protected_response.status_code == 302
    assert '/admin/login' in protected_response.headers['Location']



def test_admin_import_post_rejects_missing_csrf_token(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.post(
        '/admin/import',
        data={
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '无 csrf 草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/no-csrf',
        },
    )

    assert response.status_code == 400
    assert '请求已失效，请刷新页面后重试' in response.get_data(as_text=True)



def test_admin_page_renders_csrf_token_in_publish_form(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True)),
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '带 token 的草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/with-csrf',
        },
    )

    response = admin_client.get('/admin')
    html = response.get_data(as_text=True)
    assert 'name="csrf_token"' in html



def test_admin_page_links_to_manual_import_entry(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '手动导入' in html
    assert 'href="/admin/import"' in html



def test_admin_page_links_to_status_page(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '系统状态' in html
    assert 'href="/admin/status"' in html



def test_admin_page_links_to_source_edit_page(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'href="/admin/sources/example-source-a/edit"' in html
    assert '编辑来源' in html



def test_admin_source_edit_page_prefills_source_fields(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin/sources/example-source-a/edit')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '编辑来源' in html
    assert '当前来源：示例站点 A（example-source-a / manual）' in html
    assert 'value="示例站点 A"' in html
    assert 'value="example-source-a"' in html
    assert 'value="manual"' in html
    assert 'value="https://example.com/a"' in html
    assert '默认种子来源 A' in html



def test_admin_source_edit_post_rejects_missing_csrf_token(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.post(
        '/admin/sources/example-source-a/edit',
        data={
            'name': '示例站点 A',
            'slug': 'example-source-a',
            'source_type': 'manual',
            'base_url': 'https://example.com/a',
            'enabled': '1',
            'notes': '默认种子来源 A',
        },
    )

    assert response.status_code == 400
    assert '请求已失效，请刷新页面后重试' in response.get_data(as_text=True)



def test_admin_source_edit_post_redirects_after_success(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    edit_page = admin_client.get('/admin/sources/example-source-a/edit')
    csrf_token = extract_csrf_token(edit_page.get_data(as_text=True))

    response = admin_client.post(
        '/admin/sources/example-source-a/edit',
        data={
            'csrf_token': csrf_token,
            'name': '示例来源 A+',
            'slug': 'example-source-a-plus',
            'source_type': 'rss',
            'base_url': 'https://example.com/a/feed',
            'notes': '已切换到 feed 入口',
        },
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/sources/example-source-a-plus/edit')

    follow_response = admin_client.get('/admin/sources/example-source-a-plus/edit')
    html = follow_response.get_data(as_text=True)
    assert '来源已保存' in html
    assert 'example-source-a-plus' in html
    assert 'rss' in html
    assert '已停用' not in html



def test_admin_source_edit_page_returns_not_found_for_missing_slug(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin/sources/missing-source/edit')

    assert response.status_code == 404
    assert '来源不存在，无法编辑' in response.get_data(as_text=True)



def test_admin_source_edit_post_shows_duplicate_slug_error_and_preserves_form_values(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/sources/example-source-a/edit').get_data(as_text=True))
    response = admin_client.post(
        '/admin/sources/example-source-a/edit',
        data={
            'csrf_token': csrf_token,
            'name': '示例来源 A+',
            'slug': 'example-source-b',
            'source_type': 'rss',
            'base_url': 'https://example.com/a/feed',
            'enabled': '1',
            'notes': 'duplicate slug attempt',
        },
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert '来源 slug 已存在，请使用其他 slug' in html
    assert 'value="示例来源 A+"' in html
    assert 'value="example-source-b"' in html
    assert 'value="https://example.com/a/feed"' in html
    assert 'duplicate slug attempt' in html
    assert 'checked' in html



def test_admin_source_edit_page_renders_unchecked_enabled_for_disabled_source(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/sources/example-source-a/edit').get_data(as_text=True))
    admin_client.post(
        '/admin/sources/example-source-a/edit',
        data={
            'csrf_token': csrf_token,
            'name': '示例来源 A+',
            'slug': 'example-source-a-plus',
            'source_type': 'rss',
            'base_url': 'https://example.com/a/feed',
            'notes': 'disabled source',
        },
    )

    response = admin_client.get('/admin/sources/example-source-a-plus/edit')
    html = response.get_data(as_text=True)
    assert 'name="enabled" value="1"' in html
    assert 'checked' not in html.split('name="enabled" value="1"', 1)[1].split('>', 1)[0]



def test_get_admin_edit_source_returns_existing_source_fields(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        source = get_admin_edit_source('example-source-a')

    assert source == {
        'name': '示例站点 A',
        'slug': 'example-source-a',
        'source_type': 'manual',
        'base_url': 'https://example.com/a',
        'enabled': 1,
        'notes': '默认种子来源 A',
    }



def test_update_source_updates_fields_and_enabled_flag(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        updated = update_source(
            'example-source-a',
            name='示例来源 A+',
            slug='example-source-a-plus',
            source_type='rss',
            base_url='https://example.com/a/feed',
            enabled=False,
            notes='已切换到 feed 入口',
        )
        row = get_db().execute(
            'SELECT name, slug, source_type, base_url, enabled, notes FROM sources WHERE id = ?',
            (updated['id'],),
        ).fetchone()

    assert updated['slug'] == 'example-source-a-plus'
    assert dict(row) == {
        'name': '示例来源 A+',
        'slug': 'example-source-a-plus',
        'source_type': 'rss',
        'base_url': 'https://example.com/a/feed',
        'enabled': 0,
        'notes': '已切换到 feed 入口',
    }



def test_update_source_rejects_missing_source_before_validation(app):
    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            update_source(
                'missing-source',
                name='新来源',
                slug='new-source',
                source_type='manual',
                base_url='https://example.com/new',
                enabled=True,
                notes='',
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.errors == ['来源不存在，无法编辑']



def test_update_source_rejects_invalid_fields_and_duplicate_slug(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            update_source(
                'example-source-a',
                name='',
                slug='example-source-b',
                source_type='',
                base_url='ftp://example.com/feed',
                enabled=True,
                notes='',
            )

    assert exc_info.value.status_code == 400
    assert exc_info.value.errors == [
        '来源名称不能为空',
        '来源 slug 不能为空',
        '来源类型不能为空',
        '来源地址仅支持 http 或 https',
        '来源 slug 已存在，请使用其他 slug',
    ]



def test_admin_status_page_shows_database_and_content_summary(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '状态页草稿',
            'summary': 'draft summary',
            'content': 'draft content',
            'external_url': 'https://example.com/status-draft',
        },
    )

    response = admin_client.get('/admin/status')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '后台系统状态' in html
    assert_status_field_value(html, '数据库状态', '数据库已初始化')
    assert_status_field_value(html, 'FTS 索引表', '已就绪')
    assert_status_field_value(html, '公开条目数', '3')
    assert_status_field_value(html, '草稿条目数', '1')
    assert_status_field_value(html, '来源总数', '2')
    assert_status_field_value(html, '已启用来源', '2')
    assert '最近更新时间' in html
    assert '暂无条目更新时间' not in html



def test_admin_status_page_is_bootstrap_safe_before_init_db(admin_client):
    response = admin_client.get('/admin/status')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '后台系统状态' in html
    assert_status_field_value(html, '数据库状态', '数据库未初始化')
    assert_status_field_value(html, 'FTS 索引表', '未就绪')
    assert_status_field_value(html, '公开条目数', '0')
    assert_status_field_value(html, '草稿条目数', '0')
    assert_status_field_value(html, '来源总数', '0')
    assert_status_field_value(html, '已启用来源', '0')
    assert_status_field_value(html, '最近更新时间', '暂无条目更新时间')



def test_get_admin_status_snapshot_returns_zeroed_state_before_init_db(app):
    with app.app_context():
        snapshot = get_admin_status_snapshot()

    assert snapshot == {
        'database_ready': False,
        'fts_ready': False,
        'source_count': 0,
        'enabled_source_count': 0,
        'published_item_count': 0,
        'draft_item_count': 0,
        'latest_item_updated_at': None,
    }



def test_get_admin_status_snapshot_reports_initialized_database_state(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        snapshot = get_admin_status_snapshot()

    assert snapshot['database_ready'] is True
    assert snapshot['fts_ready'] is True
    assert snapshot['source_count'] == 2
    assert snapshot['enabled_source_count'] == 2
    assert snapshot['published_item_count'] == 3
    assert snapshot['draft_item_count'] == 0
    assert snapshot['latest_item_updated_at'] is not None



def test_admin_import_page_shows_manual_import_form(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin/import')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '手动导入条目' in html
    assert 'name="title"' in html
    assert 'name="source_slug"' in html
    assert 'example-source-a' in html
    assert 'example-category' in html



def test_admin_import_post_redirects_after_success(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    form_page = admin_client.get('/admin/import')
    csrf_token = extract_csrf_token(form_page.get_data(as_text=True))

    response = admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': 'PRG 草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/prg-draft',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/import')

    landing = admin_client.get('/admin/import')
    html = landing.get_data(as_text=True)
    assert '已创建草稿条目' in html
    assert 'PRG 草稿' in html

    with app.app_context():
        db = get_db()
        row = db.execute(
            'SELECT title, status, external_url FROM items WHERE title = ?',
            ('PRG 草稿',),
        ).fetchone()

    assert row is not None
    assert row['status'] == 'draft'
    assert row['external_url'] == 'https://example.com/prg-draft'



def test_admin_import_post_creates_draft_item_and_shows_success(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    response = admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '后台手动导入条目',
            'summary': '来自后台表单的摘要',
            'content': '这是后台手动导入的正文。',
            'external_url': 'https://example.com/manual-import',
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '已创建草稿条目' in html
    assert '后台手动导入条目' in html

    with app.app_context():
        db = get_db()
        row = db.execute(
            'SELECT title, status, external_url FROM items WHERE title = ?',
            ('后台手动导入条目',),
        ).fetchone()

    assert row is not None
    assert row['status'] == 'draft'
    assert row['external_url'] == 'https://example.com/manual-import'



def test_admin_import_post_requires_title_and_source(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    response = admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': '',
            'category_slug': 'example-category',
            'title': '',
            'summary': '缺少标题和来源',
            'content': 'invalid payload',
            'external_url': 'https://example.com/invalid',
        },
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert '标题不能为空' in html
    assert '请选择来源' in html

    with app.app_context():
        db = get_db()
        count = db.execute('SELECT COUNT(*) FROM items').fetchone()[0]

    assert count == 3



def test_admin_dashboard_renders_edit_link_for_draft_items(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with admin_client.application.app_context():
        created_item = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='Editable Draft Item',
            summary='draft summary before edit',
            content='draft content before edit',
            external_url='https://example.com/editable-draft-item',
        )

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert f'href="/admin/items/{created_item["slug"]}/edit"' in html
    assert '编辑' in html



def test_get_admin_edit_item_returns_editable_draft_data(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        created_item = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='Editable Draft For Data Layer',
            summary='draft summary for edit helper',
            content='draft content for edit helper',
            external_url='https://example.com/edit-helper',
        )

        item = get_admin_edit_item(created_item['slug'])

    assert item == {
        'slug': created_item['slug'],
        'title': 'Editable Draft For Data Layer',
        'summary': 'draft summary for edit helper',
        'content': 'draft content for edit helper',
        'external_url': 'https://example.com/edit-helper',
        'source_slug': 'example-source-a',
        'category_slug': 'example-category',
        'status': 'draft',
    }



def test_get_admin_edit_item_bootstrap_safe_before_init_db(app):
    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            get_admin_edit_item('missing-draft')

    assert exc_info.value.errors == ['数据库尚未初始化，暂时无法编辑条目']
    assert exc_info.value.status_code == 503



def test_update_draft_item_updates_existing_draft_fields(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        created_item = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='Draft Before Data Update',
            summary='summary before data update',
            content='content before data update',
            external_url='https://example.com/before-data-update',
        )
        before_row = get_db().execute(
            'SELECT updated_at, slug, status FROM items WHERE slug = ?',
            (created_item['slug'],),
        ).fetchone()

        updated_item = update_draft_item(
            created_item['slug'],
            source_slug='example-source-b',
            category_slug='example-category',
            title='Draft After Data Update',
            summary='summary after data update',
            content='content after data update',
            external_url='https://example.com/after-data-update',
        )
        after_row = get_db().execute(
            '''
            SELECT
                items.slug,
                items.title,
                items.summary,
                items.content,
                items.external_url,
                items.status,
                items.updated_at,
                sources.slug AS source_slug,
                categories.slug AS category_slug
            FROM items
            JOIN sources ON sources.id = items.source_id
            LEFT JOIN categories ON categories.id = items.category_id
            WHERE items.slug = ?
            ''',
            (created_item['slug'],),
        ).fetchone()

    assert updated_item == {
        'slug': created_item['slug'],
        'title': 'Draft After Data Update',
        'status': 'draft',
        'external_url': 'https://example.com/after-data-update',
    }
    assert after_row is not None
    assert after_row['slug'] == created_item['slug']
    assert after_row['title'] == 'Draft After Data Update'
    assert after_row['summary'] == 'summary after data update'
    assert after_row['content'] == 'content after data update'
    assert after_row['external_url'] == 'https://example.com/after-data-update'
    assert after_row['status'] == 'draft'
    assert after_row['source_slug'] == 'example-source-b'
    assert after_row['category_slug'] == 'example-category'
    assert after_row['updated_at'] >= before_row['updated_at']



def test_update_draft_item_rejects_non_draft_item(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(ManualImportValidationError) as exc_info:
            update_draft_item(
                'sample-item-1',
                source_slug='example-source-a',
                category_slug='example-category',
                title='Should Not Update Published Item',
                summary='summary',
                content='content',
                external_url='https://example.com/should-not-update',
            )

    assert exc_info.value.errors == ['仅允许编辑 draft 状态条目']
    assert exc_info.value.status_code == 409



def test_admin_edit_page_shows_existing_draft_values(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with admin_client.application.app_context():
        created_item = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='Draft To Edit',
            summary='existing summary',
            content='existing content',
            external_url='https://example.com/draft-to-edit',
        )

    response = admin_client.get(f'/admin/items/{created_item["slug"]}/edit')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '编辑草稿条目' in html
    assert 'value="Draft To Edit"' in html
    assert 'existing summary' in html
    assert 'existing content' in html
    assert 'value="https://example.com/draft-to-edit"' in html
    assert 'example-source-a' in html
    assert 'example-category' in html
    assert 'href="/admin"' in html



def test_admin_edit_page_rejects_non_draft_items_with_conflict(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin/items/sample-item-1/edit')

    assert response.status_code == 409
    assert '仅允许编辑 draft 状态条目' in response.get_data(as_text=True)



def test_admin_edit_page_returns_not_found_for_missing_slug(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin/items/missing-draft/edit')

    assert response.status_code == 404
    assert '条目不存在，无法编辑' in response.get_data(as_text=True)



def test_admin_edit_post_rejects_missing_csrf_token(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with admin_client.application.app_context():
        created_item = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='Draft Missing Csrf',
            summary='summary before csrf failure',
            content='content before csrf failure',
            external_url='https://example.com/draft-missing-csrf',
        )
        before_row = get_db().execute(
            '''
            SELECT
                items.title,
                items.summary,
                items.content,
                items.external_url,
                sources.slug AS source_slug,
                categories.slug AS category_slug,
                items.status,
                items.updated_at
            FROM items
            JOIN sources ON sources.id = items.source_id
            LEFT JOIN categories ON categories.id = items.category_id
            WHERE items.slug = ?
            ''',
            (created_item['slug'],),
        ).fetchone()

    response = admin_client.post(
        f'/admin/items/{created_item["slug"]}/edit',
        data={
            'source_slug': 'example-source-b',
            'category_slug': 'example-category',
            'title': 'Draft Missing Csrf Updated',
            'summary': 'summary after csrf failure',
            'content': 'content after csrf failure',
            'external_url': 'https://example.com/draft-missing-csrf-updated',
        },
    )

    with admin_client.application.app_context():
        after_row = get_db().execute(
            '''
            SELECT
                items.title,
                items.summary,
                items.content,
                items.external_url,
                sources.slug AS source_slug,
                categories.slug AS category_slug,
                items.status,
                items.updated_at
            FROM items
            JOIN sources ON sources.id = items.source_id
            LEFT JOIN categories ON categories.id = items.category_id
            WHERE items.slug = ?
            ''',
            (created_item['slug'],),
        ).fetchone()

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert '请求已失效，请刷新页面后重试' in html
    assert 'value="Draft Missing Csrf Updated"' in html
    assert 'summary after csrf failure' in html
    assert 'content after csrf failure' in html
    assert 'value="https://example.com/draft-missing-csrf-updated"' in html
    assert before_row is not None
    assert after_row is not None
    assert dict(after_row) == dict(before_row)
    assert dict(after_row) == {
        'title': 'Draft Missing Csrf',
        'summary': 'summary before csrf failure',
        'content': 'content before csrf failure',
        'external_url': 'https://example.com/draft-missing-csrf',
        'source_slug': 'example-source-a',
        'category_slug': 'example-category',
        'status': 'draft',
        'updated_at': dict(before_row)['updated_at'],
    }



def test_admin_edit_post_checks_csrf_before_item_lookup(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.post(
        '/admin/items/missing-draft/edit',
        data={
            'source_slug': 'example-source-b',
            'category_slug': 'example-category',
            'title': 'Missing Draft Csrf First',
            'summary': 'csrf should fail before item lookup',
            'content': 'submitted content should be preserved',
            'external_url': 'https://example.com/missing-draft-csrf-first',
        },
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert '请求已失效，请刷新页面后重试' in html
    assert '条目不存在，无法编辑' not in html
    assert 'value="Missing Draft Csrf First"' in html
    assert 'csrf should fail before item lookup' in html
    assert 'submitted content should be preserved' in html
    assert 'value="https://example.com/missing-draft-csrf-first"' in html



def test_admin_edit_post_returns_not_found_for_missing_slug_with_valid_csrf(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin').get_data(as_text=True))
    response = admin_client.post(
        '/admin/items/missing-draft/edit',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-b',
            'category_slug': 'example-category',
            'title': 'Missing Draft Valid Csrf',
            'summary': 'should report not found',
            'content': 'submitted content should be preserved',
            'external_url': 'https://example.com/missing-draft-valid-csrf',
        },
    )

    assert response.status_code == 404
    html = response.get_data(as_text=True)
    assert '条目不存在，无法编辑' in html
    assert 'value="Missing Draft Valid Csrf"' in html
    assert 'should report not found' in html
    assert 'submitted content should be preserved' in html
    assert 'value="https://example.com/missing-draft-valid-csrf"' in html



def test_admin_edit_post_returns_conflict_for_non_draft_item_with_valid_csrf(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin').get_data(as_text=True))
    response = admin_client.post(
        '/admin/items/sample-item-1/edit',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': 'Published Item Update Attempt',
            'summary': 'should report conflict',
            'content': 'published item cannot be edited here',
            'external_url': 'https://example.com/published-item-update-attempt',
        },
    )

    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert '仅允许编辑 draft 状态条目' in html
    assert 'value="Published Item Update Attempt"' in html
    assert 'should report conflict' in html
    assert 'published item cannot be edited here' in html
    assert 'value="https://example.com/published-item-update-attempt"' in html



def test_admin_edit_post_surfaces_end_to_end_validation_failures(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        created_item = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='Draft With Invalid Edit Payload',
            summary='summary before invalid edit',
            content='content before invalid edit',
            external_url='https://example.com/draft-with-invalid-edit-payload',
        )

    csrf_token = extract_csrf_token(admin_client.get(f'/admin/items/{created_item["slug"]}/edit').get_data(as_text=True))
    response = admin_client.post(
        f'/admin/items/{created_item["slug"]}/edit',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'missing-source',
            'category_slug': 'missing-category',
            'title': 'Draft Invalid Edit Payload',
            'summary': 'invalid selection summary',
            'content': 'invalid selection content',
            'external_url': 'ftp://example.com/not-allowed',
        },
    )

    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert '请选择有效来源' in html
    assert '请选择有效分类' in html
    assert '外链仅支持 http 或 https' in html
    assert 'value="Draft Invalid Edit Payload"' in html
    assert 'invalid selection summary' in html
    assert 'invalid selection content' in html
    assert 'value="ftp://example.com/not-allowed"' in html

    with app.app_context():
        row = get_db().execute(
            'SELECT title, summary, content, external_url FROM items WHERE slug = ?',
            (created_item['slug'],),
        ).fetchone()

    assert row is not None
    assert row['title'] == 'Draft With Invalid Edit Payload'
    assert row['summary'] == 'summary before invalid edit'
    assert row['content'] == 'content before invalid edit'
    assert row['external_url'] == 'https://example.com/draft-with-invalid-edit-payload'



def test_admin_edit_post_redirects_back_to_edit_page_and_shows_success(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        created_item = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='Draft Before Update',
            summary='summary before update',
            content='content before update',
            external_url='https://example.com/draft-before-update',
        )

    form_response = admin_client.get(f'/admin/items/{created_item["slug"]}/edit')
    csrf_token = extract_csrf_token(form_response.get_data(as_text=True))

    response = admin_client.post(
        f'/admin/items/{created_item["slug"]}/edit',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-b',
            'category_slug': 'example-category',
            'title': 'Draft After Update',
            'summary': 'summary after update',
            'content': 'content after update',
            'external_url': 'https://example.com/draft-after-update',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith(f'/admin/items/{created_item["slug"]}/edit')

    landing = admin_client.get(f'/admin/items/{created_item["slug"]}/edit')
    assert landing.status_code == 200
    landing_html = landing.get_data(as_text=True)
    assert '草稿已保存' in landing_html
    assert 'Draft After Update' in landing_html
    assert 'draft' in landing_html
    assert 'value="Draft After Update"' in landing_html
    assert 'summary after update' in landing_html
    assert 'content after update' in landing_html
    assert 'value="https://example.com/draft-after-update"' in landing_html
    assert 'example-source-b' in landing_html

    with app.app_context():
        db = get_db()
        row = db.execute(
            '''
            SELECT
                items.title,
                items.summary,
                items.content,
                items.external_url,
                items.status,
                sources.slug AS source_slug,
                categories.slug AS category_slug
            FROM items
            JOIN sources ON sources.id = items.source_id
            LEFT JOIN categories ON categories.id = items.category_id
            WHERE items.slug = ?
            ''',
            (created_item['slug'],),
        ).fetchone()

    assert row is not None
    assert row['title'] == 'Draft After Update'
    assert row['summary'] == 'summary after update'
    assert row['content'] == 'content after update'
    assert row['external_url'] == 'https://example.com/draft-after-update'
    assert row['status'] == 'draft'
    assert row['source_slug'] == 'example-source-b'
    assert row['category_slug'] == 'example-category'



def test_publish_item_changes_draft_to_published_and_sets_timestamp(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        created = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='待发布草稿',
            summary='draft summary',
            content='draft content',
            external_url='https://example.com/draft-publish',
        )

        published = publish_item(created['slug'])

    assert published['slug'] == created['slug']
    assert published['status'] == 'published'
    assert published['published_at']



def test_publish_item_rejects_missing_slug(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(PublishValidationError) as exc_info:
            publish_item('missing-slug')

    assert exc_info.value.errors == ['条目不存在，无法发布']
    assert exc_info.value.status_code == 404



def test_publish_item_rejects_non_draft_item(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(PublishValidationError) as exc_info:
            publish_item('sample-item-1')

    assert exc_info.value.errors == ['仅允许发布 draft 状态条目']
    assert exc_info.value.status_code == 409



def test_publish_item_is_bootstrap_safe_before_init_db(app):
    with app.app_context():
        with pytest.raises(PublishValidationError) as exc_info:
            publish_item('any-slug')

    assert exc_info.value.errors == ['数据库尚未初始化，暂时无法发布条目']
    assert exc_info.value.status_code == 503



def test_admin_publish_post_returns_not_found_for_missing_slug(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin').get_data(as_text=True))
    response = admin_client.post('/admin/items/missing-slug/publish', data={'csrf_token': csrf_token})

    assert response.status_code == 404
    assert '条目不存在，无法发布' in response.get_data(as_text=True)



def test_admin_publish_post_returns_conflict_for_already_published_item(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin').get_data(as_text=True))
    response = admin_client.post('/admin/items/sample-item-1/publish', data={'csrf_token': csrf_token})

    assert response.status_code == 409
    assert '仅允许发布 draft 状态条目' in response.get_data(as_text=True)



def test_admin_publish_post_is_bootstrap_safe_before_init_db(admin_client):
    csrf_token = extract_csrf_token(admin_client.get('/admin/login').get_data(as_text=True))
    response = admin_client.post('/admin/items/any-slug/publish', data={'csrf_token': csrf_token})

    assert response.status_code == 503
    assert '数据库尚未初始化，暂时无法发布条目' in response.get_data(as_text=True)



def test_admin_publish_post_redirects_after_success(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    import_page = admin_client.get('/admin/import')
    csrf_token = extract_csrf_token(import_page.get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '待 PRG 发布草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/prg-publish',
        },
    )

    admin_page = admin_client.get('/admin')
    publish_token = extract_csrf_token(admin_page.get_data(as_text=True))
    response = admin_client.post(
        '/admin/items/prg-publish-draft/publish',
        data={'csrf_token': publish_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin')

    landing = admin_client.get('/admin')
    html = landing.get_data(as_text=True)
    assert '草稿已发布' in html
    assert 'prg-publish-draft' in html



def test_admin_publish_post_promotes_draft_and_makes_item_public(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    import_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': import_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '后台发布草稿',
            'summary': '发布前摘要',
            'content': '发布后应进入公开详情',
            'external_url': 'https://example.com/admin-publish',
        },
    )

    publish_token = extract_csrf_token(admin_client.get('/admin').get_data(as_text=True))
    publish_response = admin_client.post(
        '/admin/items/backend-publish-draft/publish',
        data={'csrf_token': publish_token},
        follow_redirects=True,
    )
    detail_response = admin_client.get('/items/backend-publish-draft')
    search_response = admin_client.get('/search?q=后台发布草稿')

    assert publish_response.status_code == 200
    publish_html = publish_response.get_data(as_text=True)
    assert '草稿已发布' in publish_html
    assert 'published' in publish_html
    assert detail_response.status_code == 200
    assert search_response.status_code == 200
    assert '后台发布草稿' in search_response.get_data(as_text=True)



def test_get_admin_dashboard_data_returns_sources_and_recent_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        dashboard = get_admin_dashboard_data()

    assert set(dashboard.keys()) == {'stats', 'sources', 'items'}
    assert dashboard['stats'] == {'source_count': 2, 'item_count': 3}

    assert len(dashboard['sources']) == 2
    assert all(set(source.keys()) == {'name', 'slug', 'source_type', 'enabled'} for source in dashboard['sources'])
    assert {source['name'] for source in dashboard['sources']} == {'示例站点 A', '示例站点 B'}
    assert {source['slug'] for source in dashboard['sources']} == {'example-source-a', 'example-source-b'}
    assert all(source['source_type'] == 'manual' for source in dashboard['sources'])
    assert all(source['enabled'] == 1 for source in dashboard['sources'])

    assert len(dashboard['items']) == 3
    assert all(
        set(item.keys())
        == {
            'title',
            'slug',
            'status',
            'source_name',
            'category_name',
            'external_url',
            'updated_at',
        }
        for item in dashboard['items']
    )
    assert all(item['status'] == 'published' for item in dashboard['items'])
    assert {item['title'] for item in dashboard['items']} == {'示例条目 1', '示例条目 2', '示例条目 3'}
    assert {item['slug'] for item in dashboard['items']} == {'sample-item-1', 'sample-item-2', 'sample-item-3'}
    assert {item['source_name'] for item in dashboard['items']} == {'示例站点 A', '示例站点 B'}
    assert {item['category_name'] for item in dashboard['items']} == {'示例分类'}
    assert dashboard['items'][0]['title'] == '示例条目 3'
    assert dashboard['items'][0]['source_name'] == '示例站点 B'


def test_get_admin_dashboard_data_returns_empty_state_before_init_db(app):
    with app.app_context():
        dashboard = get_admin_dashboard_data()

    assert dashboard == {
        'stats': {'source_count': 0, 'item_count': 0},
        'sources': [],
        'items': [],
    }



def test_get_admin_dashboard_data_honors_item_limit(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        dashboard = get_admin_dashboard_data(item_limit=2)

    assert len(dashboard['items']) == 2
    assert [item['title'] for item in dashboard['items']] == ['示例条目 3', '示例条目 2']
    assert all(item['status'] == 'published' for item in dashboard['items'])
    assert dashboard['stats'] == {'source_count': 2, 'item_count': 3}
    assert len(dashboard['sources']) == 2
    assert {item['slug'] for item in dashboard['items']} == {'sample-item-3', 'sample-item-2'}



def test_get_admin_dashboard_data_includes_item_metadata(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        dashboard = get_admin_dashboard_data(item_limit=1)

    first_item = dashboard['items'][0]

    assert set(first_item.keys()) == {
        'title',
        'slug',
        'status',
        'source_name',
        'category_name',
        'external_url',
        'updated_at',
    }
    assert first_item['external_url'] == 'https://example.com/b/3'
    assert first_item['updated_at']


def test_get_admin_dashboard_data_includes_draft_items_in_admin_list(app, runner):
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
                '后台草稿条目',
                'admin-draft-item',
                '后台列表应展示草稿',
                'draft body',
                'https://example.com/admin-draft',
                '编辑部',
                'draft',
            ),
        )
        db.commit()
        dashboard = get_admin_dashboard_data()

    assert dashboard['stats'] == {'source_count': 2, 'item_count': 3}
    assert len(dashboard['items']) == 4
    assert dashboard['items'][0]['slug'] == 'admin-draft-item'
    assert dashboard['items'][0]['title'] == '后台草稿条目'
    assert dashboard['items'][0]['status'] == 'draft'
    assert [item['slug'] for item in dashboard['items'][1:]] == ['sample-item-3', 'sample-item-2', 'sample-item-1']



def test_admin_page_renders_draft_items_in_management_list(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    response = admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '后台页面草稿条目',
            'summary': '用于验证后台页面展示草稿',
            'content': 'draft content for admin page',
            'external_url': 'https://example.com/admin-page-draft',
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    admin_response = admin_client.get('/admin')

    assert admin_response.status_code == 200
    html = admin_response.get_data(as_text=True)
    assert '条目管理（含草稿）' in html
    assert '后台页面草稿条目' in html
    assert 'draft' in html
    assert 'https://example.com/admin-page-draft' in html



def test_get_admin_dashboard_data_clamps_non_positive_item_limit(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        zero_limit_dashboard = get_admin_dashboard_data(item_limit=0)
        negative_limit_dashboard = get_admin_dashboard_data(item_limit=-1)

    assert zero_limit_dashboard['items'] == []
    assert negative_limit_dashboard['items'] == []
    assert zero_limit_dashboard['stats'] == {'source_count': 2, 'item_count': 3}
    assert negative_limit_dashboard['stats'] == {'source_count': 2, 'item_count': 3}
    assert len(zero_limit_dashboard['sources']) == 2
    assert len(negative_limit_dashboard['sources']) == 2


def test_home_and_admin_pages_are_bootstrap_safe_before_init_db(admin_client):
    home_response = admin_client.get('/')
    assert home_response.status_code == 200
    home_html = home_response.get_data(as_text=True)
    assert '已接入 0 个来源' in home_html
    assert '当前包含 0 条示例条目' in home_html

    admin_response = admin_client.get('/admin')
    assert admin_response.status_code == 200
    admin_html = admin_response.get_data(as_text=True)
    assert '数据库状态：已接入 0 个来源' in admin_html
    assert '当前共有 0 条公开条目' in admin_html


def test_init_db_command_creates_and_seeds_database_idempotently(app, runner):
    first_result = runner.invoke(args=['init-db'])
    second_result = runner.invoke(args=['init-db'])

    assert first_result.exit_code == 0
    assert second_result.exit_code == 0
    assert 'Initialized the database.' in first_result.output
    assert 'Initialized the database.' in second_result.output

    with app.app_context():
        db = get_db()
        source_count = db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]
        item_count = db.execute('SELECT COUNT(*) FROM items').fetchone()[0]

    assert source_count >= 2
    assert item_count >= 3
    assert source_count == 2
    assert item_count == 3


def test_homepage_lists_recent_seed_items_after_init_db(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    home_response = client.get('/')
    assert home_response.status_code == 200
    home_html = home_response.get_data(as_text=True)
    assert '已接入 2 个来源' in home_html
    assert '当前包含 3 条示例条目' in home_html
    assert '示例条目 1' in home_html


def test_get_homepage_data_returns_stats_and_recent_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        homepage_data = get_homepage_data()

    assert homepage_data['source_count'] == 2
    assert homepage_data['item_count'] == 3
    assert len(homepage_data['recent_items']) == 3
    assert homepage_data['recent_items'][0]['title'].startswith('示例条目')
    assert any(item['title'] == '示例条目 1' for item in homepage_data['recent_items'])


def test_home_and_admin_pages_show_database_stats(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    home_response = admin_client.get('/')
    assert home_response.status_code == 200
    home_html = home_response.get_data(as_text=True)
    assert '已接入' in home_html
    assert '示例条目' in home_html

    admin_response = admin_client.get('/admin')
    assert admin_response.status_code == 200
    admin_html = admin_response.get_data(as_text=True)
    assert '数据库状态' in admin_html
    assert '当前共有 3 条公开条目' in admin_html
    assert '当前包含 3 条示例条目' in home_html



def test_homepage_stats_count_only_published_items(app, admin_client, runner):
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
                '草稿统计条目',
                'draft-stats-item',
                '不应计入前台公开统计',
                '隐藏统计内容',
                'https://example.com/draft-stats',
                '编辑部',
                'draft',
            ),
        )
        db.commit()
        homepage_data = get_homepage_data()

    home_response = admin_client.get('/')
    admin_response = admin_client.get('/admin')
    home_html = home_response.get_data(as_text=True)
    admin_html = admin_response.get_data(as_text=True)

    assert homepage_data['item_count'] == 3
    assert '当前包含 3 条示例条目' in home_html
    assert '当前共有 3 条公开条目' in admin_html
    assert '4 条示例条目' not in home_html
    assert '4 条公开条目' not in admin_html


def test_admin_page_lists_sources_and_recent_items(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert '数据源管理' in html
    assert '条目管理' in html

    source_section = html.split('数据源管理', 1)[1].split('条目管理', 1)[0]
    item_section = html.split('条目管理', 1)[1]

    # Each admin section should prove multiple seeded records inside its own
    # subsection, not merely somewhere else on the page.
    assert '示例站点 A' in source_section
    assert '示例站点 B' in source_section
    assert 'example-source-a' in source_section
    assert 'example-source-b' in source_section
    assert '示例条目' not in source_section

    assert '示例条目 3' in item_section
    assert '示例条目 2' in item_section
    assert 'sample-item-3' in item_section
    assert 'sample-item-2' in item_section
    assert '来源：示例站点 B' in item_section
    assert '更新时间：' in item_section


def test_admin_page_shows_item_source_update_time_and_external_link(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    item_section = html.split('条目管理', 1)[1]

    assert '来源：示例站点 B' in item_section
    assert '更新时间：' in item_section
    assert 'https://example.com/b/3' in item_section
    assert '查看原文' in item_section



def test_admin_page_omits_external_link_for_unsafe_item_url(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE items SET external_url = ? WHERE slug = ?",
            ('javascript:alert(1)', 'sample-item-3'),
        )
        db.commit()

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    item_section = html.split('条目管理', 1)[1]
    unsafe_item_section = item_section.split('示例条目 3', 1)[1].split('示例条目 2', 1)[0]

    assert '示例条目 3' in item_section
    assert 'href="javascript:alert(1)"' not in unsafe_item_section
    assert 'javascript:alert(1)' not in unsafe_item_section
    assert '查看原文' not in unsafe_item_section



def test_admin_page_shows_empty_state_before_init_db(admin_client):
    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert '数据源管理' in html
    assert '条目管理' in html

    source_section = html.split('数据源管理', 1)[1].split('条目管理', 1)[0]
    item_section = html.split('条目管理', 1)[1]

    assert '暂无数据源，请先初始化数据库。' in source_section
    assert '暂无条目，请先初始化数据库。' in item_section
    assert '示例站点' not in source_section
    assert '示例条目' not in item_section
    assert '数据库状态：已接入 0 个来源' in html
    assert '当前共有 0 条公开条目' in html
