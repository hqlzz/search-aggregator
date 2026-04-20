# 后台草稿编辑流转 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为后台管理页补上草稿条目的最小编辑闭环，让管理员可以进入编辑页、修改草稿字段并保存，且不影响既有发布与公开可见性规则。

**Architecture:** 继续沿用当前 Flask + SQLite + Jinja2 的轻量模式，在现有后台鉴权、session、CSRF 和 draft/published 状态约束上扩展一个仅面向草稿条目的编辑流。数据层增加“读取草稿编辑表单数据”和“更新草稿”函数；路由层增加 GET/POST 编辑页；模板层新增后台编辑表单并复用当前后台导航与反馈风格。

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: 为后台编辑流补失败测试与入口断言

**Objective:** 先用测试定义后台草稿编辑流的最小行为：后台列表出现编辑入口、草稿编辑页可打开、发布条目不可编辑、保存后走 PRG 并落库。

**Files:**
- Modify: `tests/test_db.py`
- Verify: `app/routes.py`, `app/db.py`, `app/templates/admin.html`

**Step 1: Write failing test**

```python
def test_admin_page_renders_edit_link_for_draft_item(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '待编辑草稿',
            'summary': 'draft summary',
            'content': 'draft content',
            'external_url': 'https://example.com/edit-me',
        },
    )

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '编辑' in html
    assert 'href="/admin/items/' in html
    assert '/edit"' in html
```

```python
def test_admin_edit_page_shows_existing_draft_values(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '可编辑草稿',
            'summary': '原摘要',
            'content': '原正文',
            'external_url': 'https://example.com/original',
        },
    )

    response = admin_client.get('/admin/items/editable-draft/edit')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '编辑草稿条目' in html
    assert 'value="可编辑草稿"' in html
    assert '原摘要' in html
    assert '原正文' in html
    assert 'https://example.com/original' in html
```

```python
def test_admin_edit_page_rejects_non_draft_item(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin/items/sample-item-1/edit')

    assert response.status_code == 409
    assert '仅允许编辑 draft 状态条目' in response.get_data(as_text=True)
```

```python
def test_admin_edit_post_redirects_after_success(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '编辑前草稿',
            'summary': '旧摘要',
            'content': '旧正文',
            'external_url': 'https://example.com/before-edit',
        },
    )

    edit_page = admin_client.get('/admin/items/bian-ji-qian-cao-gao/edit')
    edit_csrf = extract_csrf_token(edit_page.get_data(as_text=True))

    response = admin_client.post(
        '/admin/items/bian-ji-qian-cao-gao/edit',
        data={
            'csrf_token': edit_csrf,
            'source_slug': 'example-source-b',
            'category_slug': '',
            'title': '编辑后草稿',
            'summary': '新摘要',
            'content': '新正文',
            'external_url': 'https://example.com/after-edit',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/items/bian-ji-qian-cao-gao/edit')

    landing = admin_client.get('/admin/items/bian-ji-qian-cao-gao/edit')
    html = landing.get_data(as_text=True)
    assert '草稿已保存' in html
    assert '编辑后草稿' in html

    with app.app_context():
        db = get_db()
        row = db.execute(
            '''
            SELECT title, summary, content, external_url, status
            FROM items WHERE slug = ?
            ''',
            ('bian-ji-qian-cao-gao',),
        ).fetchone()

    assert row['title'] == '编辑后草稿'
    assert row['summary'] == '新摘要'
    assert row['content'] == '新正文'
    assert row['external_url'] == 'https://example.com/after-edit'
    assert row['status'] == 'draft'
```

**Step 2: Run test to verify failure**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_renders_edit_link_for_draft_item tests/test_db.py::test_admin_edit_page_shows_existing_draft_values tests/test_db.py::test_admin_edit_page_rejects_non_draft_item tests/test_db.py::test_admin_edit_post_redirects_after_success -q`
Expected: FAIL — 缺少 `/admin/items/<slug>/edit` 路由、编辑入口或更新逻辑。

**Step 3: Write minimal implementation**

在 `app/routes.py` 增加编辑页 GET/POST 路由骨架；在 `app/templates/admin.html` 为 `draft` 条目渲染编辑链接；先只把请求接通到最小占位实现。

**Step 4: Run test to verify pass**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_renders_edit_link_for_draft_item tests/test_db.py::test_admin_edit_page_shows_existing_draft_values tests/test_db.py::test_admin_edit_page_rejects_non_draft_item tests/test_db.py::test_admin_edit_post_redirects_after_success -q`
Expected: PASS

**Step 5: Commit**

```bash
git -C /root/search-aggregator add tests/test_db.py app/routes.py app/templates/admin.html
git -C /root/search-aggregator commit -m "feat: add admin draft edit flow tests"
```

### Task 2: 实现草稿读取与更新的数据层

**Objective:** 在数据层提供“读取指定 draft 条目供编辑”和“更新 draft 条目”的最小能力，并重用现有手动导入校验口径。

**Files:**
- Modify: `app/db.py`
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_update_draft_item_updates_existing_draft_fields(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        created = create_manual_import_item(
            source_slug='example-source-a',
            category_slug='example-category',
            title='可更新草稿',
            summary='旧摘要',
            content='旧正文',
            external_url='https://example.com/old-draft',
        )

        updated = update_draft_item(
            created['slug'],
            source_slug='example-source-b',
            category_slug='',
            title='更新后的草稿',
            summary='新摘要',
            content='新正文',
            external_url='https://example.com/new-draft',
        )

    assert updated['slug'] == created['slug']
    assert updated['title'] == '更新后的草稿'
    assert updated['status'] == 'draft'
```

```python
def test_update_draft_item_rejects_non_draft_item(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        with pytest.raises(PublishValidationError) as exc_info:
            update_draft_item(
                'sample-item-1',
                source_slug='example-source-a',
                category_slug='example-category',
                title='should fail',
                summary='summary',
                content='content',
                external_url='https://example.com/fail',
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.errors == ['仅允许编辑 draft 状态条目']
```

**Step 2: Run test to verify failure**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_update_draft_item_updates_existing_draft_fields tests/test_db.py::test_update_draft_item_rejects_non_draft_item -q`
Expected: FAIL — `update_draft_item` / `get_admin_edit_item` 尚不存在。

**Step 3: Write minimal implementation**

```python
def get_admin_edit_item(slug):
    ...

def update_draft_item(slug, *, source_slug, category_slug, title, summary, content, external_url):
    ...
```

实现要求：
- 仅允许编辑 `draft` 条目；缺失返回 404，非 `draft` 返回 409，数据库未初始化返回 503
- 校验规则与 `create_manual_import_item()` 对齐：标题必填、来源有效、分类有效、外链仅支持 http/https
- 更新后保持原 slug 与 `draft` 状态不变，只更新可编辑字段与 `updated_at`
- 返回可供 flash/页面展示的最小字典（`slug`、`title`、`status`、`external_url`）

**Step 4: Run test to verify pass**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_update_draft_item_updates_existing_draft_fields tests/test_db.py::test_update_draft_item_rejects_non_draft_item -q`
Expected: PASS

**Step 5: Commit**

```bash
git -C /root/search-aggregator add app/db.py tests/test_db.py
git -C /root/search-aggregator commit -m "feat: add admin draft update data layer"
```

### Task 3: 落地后台草稿编辑页面与保存 PRG

**Objective:** 把数据层接到路由和模板，形成真正可用的后台草稿编辑页面。

**Files:**
- Create: `app/templates/admin_edit_item.html`
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_admin_edit_post_rejects_missing_csrf_token(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    csrf_token = extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '缺 token 编辑草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/edit-csrf',
        },
    )

    response = admin_client.post(
        '/admin/items/item/edit',
        data={
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '不会成功',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/blocked',
        },
    )

    assert response.status_code == 400
    assert '请求已失效，请刷新页面后重试' in response.get_data(as_text=True)
```

**Step 2: Run test to verify failure**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_edit_post_rejects_missing_csrf_token -q`
Expected: FAIL — 编辑 POST 尚未复用后台 CSRF/反馈流程。

**Step 3: Write minimal implementation**

在 `app/routes.py` 中实现：
- `GET /admin/items/<slug>/edit`：读取条目、来源选项、分类选项、csrf token，渲染编辑页
- `POST /admin/items/<slug>/edit`：先验 csrf，再调用 `update_draft_item()`；成功后 `flash({'message': '草稿已保存', 'item': ...}, 'admin_edit_success')` 并 redirect 回编辑页；失败时保留用户表单输入并返回对应状态码

在 `app/templates/admin_edit_item.html` 中实现：
- 返回后台链接
- 成功 feedback banner
- 错误 banner
- 来源、分类、标题、摘要、正文、外链表单
- 保存按钮

在 `app/templates/admin.html` 中实现：
- 仅对 `draft` 条目显示“编辑”按钮/链接，与发布按钮并列

**Step 4: Run test to verify pass**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_renders_edit_link_for_draft_item tests/test_db.py::test_admin_edit_page_shows_existing_draft_values tests/test_db.py::test_admin_edit_page_rejects_non_draft_item tests/test_db.py::test_admin_edit_post_rejects_missing_csrf_token tests/test_db.py::test_admin_edit_post_redirects_after_success -q`
Expected: PASS

**Step 5: Commit**

```bash
git -C /root/search-aggregator add app/routes.py app/templates/admin.html app/templates/admin_edit_item.html tests/test_db.py
git -C /root/search-aggregator commit -m "feat: add admin draft edit page"
```

### Task 4: 全量回归、文档同步与收尾验证

**Objective:** 确认新编辑流与现有后台导入/发布/前台搜索没有回归，并把项目状态写回文档。

**Files:**
- Modify: `README.md`
- Modify: `docs/project-status.md`
- Modify: `docs/todo.md`
- Modify: `docs/progress-log.md`

**Step 1: Run focused tests**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_renders_edit_link_for_draft_item tests/test_db.py::test_admin_edit_page_shows_existing_draft_values tests/test_db.py::test_admin_edit_page_rejects_non_draft_item tests/test_db.py::test_admin_edit_post_rejects_missing_csrf_token tests/test_db.py::test_admin_edit_post_redirects_after_success tests/test_db.py::test_update_draft_item_updates_existing_draft_fields tests/test_db.py::test_update_draft_item_rejects_non_draft_item -q`
Expected: PASS

**Step 2: Run full regression**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

**Step 3: Verify recurring job still exists**

Run: `hermes cron list`
Expected: `search-aggregator-hourly-dev` 仍为 `active`，计划 `0 * * * *`

**Step 4: Update docs**

把以下内容写入状态文档：
- 后台已支持草稿编辑页与保存闭环
- 仍未完成来源编辑、分类管理、搜索增强、导入聚合
- 下一轮优先继续推进来源/条目编辑的剩余缺口，或转向导入校验补强

**Step 5: Commit**

```bash
git -C /root/search-aggregator add README.md docs/project-status.md docs/todo.md docs/progress-log.md
git -C /root/search-aggregator commit -m "docs: update status after admin draft edit flow"
```