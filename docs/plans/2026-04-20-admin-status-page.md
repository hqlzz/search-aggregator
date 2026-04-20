# 后台状态展示页 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为已登录管理员新增 `/admin/status` 状态展示页，集中展示数据库初始化状态、来源数量、公开条目数、草稿条目数与最近更新时间，并从后台首页提供明确入口。

**Architecture:** 继续沿用现有 Flask + SQLite + Jinja2 轻量结构，在数据层新增只读状态快照 helper，由路由层负责鉴权和模板渲染。状态页不引入新依赖、不改 schema，只复用现有表并保持 bootstrap-safe；数据库未初始化时返回零值与“未初始化”提示。

**Tech Stack:** Python 3.12, Flask, SQLite, pytest, Jinja2

---

### Task 1: 为后台状态页写失败测试

**Objective:** 先定义管理员状态页的目标行为，覆盖已初始化和未初始化两种场景。

**Files:**
- Modify: `tests/test_db.py`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_admin_page_links_to_status_page(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '系统状态' in html
    assert 'href="/admin/status"' in html


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
    assert '数据库已初始化' in html
    assert '公开条目数' in html
    assert '草稿条目数' in html
    assert 'FTS 索引表' in html
    assert '最近更新时间' in html
    assert '>1<' in html


def test_admin_status_page_is_bootstrap_safe_before_init_db(admin_client):
    response = admin_client.get('/admin/status')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '后台系统状态' in html
    assert '数据库未初始化' in html
    assert '公开条目数' in html
    assert '草稿条目数' in html
    assert '>0<' in html
```

**Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_status_page tests/test_db.py::test_admin_status_page_shows_database_and_content_summary tests/test_db.py::test_admin_status_page_is_bootstrap_safe_before_init_db -q`
Expected: FAIL — `/admin/status` 尚未实现，后台首页也还没有状态页入口。

**Step 3: Write minimal implementation**

先不要写生产代码；确认测试准确失败后再进入 Task 2。

**Step 4: Run test to verify pass**

本任务不要求通过；目标是稳定得到预期 RED。

**Step 5: Commit**

当前项目不是 git 仓库，跳过 commit；在 `docs/progress-log.md` 记录此约束。

### Task 2: 实现后台状态快照 helper、路由与模板

**Objective:** 提供可复用的后台状态数据，并新增受保护的状态页模板。

**Files:**
- Modify: `app/db.py`
- Modify: `app/routes.py`
- Create: `app/templates/admin_status.html`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

复用 Task 1 中的三个失败测试，不新增额外测试。

**Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_status_page tests/test_db.py::test_admin_status_page_shows_database_and_content_summary tests/test_db.py::test_admin_status_page_is_bootstrap_safe_before_init_db -q`
Expected: FAIL

**Step 3: Write minimal implementation**

在 `app/db.py` 新增 helper：

```python
def get_admin_status_snapshot():
    snapshot = {
        'database_ready': has_bootstrapped_tables(),
        'fts_ready': table_exists('item_search'),
        'source_count': 0,
        'enabled_source_count': 0,
        'published_item_count': 0,
        'draft_item_count': 0,
        'latest_item_updated_at': None,
    }
    if not snapshot['database_ready']:
        return snapshot

    db = get_db()
    counts = db.execute(
        """
        SELECT
            COUNT(*) AS total_items,
            SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published_item_count,
            SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft_item_count,
            MAX(updated_at) AS latest_item_updated_at
        FROM items
        """
    ).fetchone()
    snapshot.update(
        source_count=db.execute('SELECT COUNT(*) FROM sources').fetchone()[0],
        enabled_source_count=db.execute('SELECT COUNT(*) FROM sources WHERE enabled = 1').fetchone()[0],
        published_item_count=counts['published_item_count'] or 0,
        draft_item_count=counts['draft_item_count'] or 0,
        latest_item_updated_at=counts['latest_item_updated_at'],
    )
    return snapshot
```

在 `app/routes.py` 导入 helper 并新增受保护路由：

```python
@bp.get('/admin/status')
@require_admin
def admin_status():
    return render_template(
        'admin_status.html',
        status_snapshot=get_admin_status_snapshot(),
        csrf_token=get_csrf_token(),
    )
```

创建 `app/templates/admin_status.html`：

```html
{% extends 'base.html' %}
{% block title %}后台系统状态 - 搜索聚合站{% endblock %}
{% block content %}
<section>
  <h2>后台系统状态</h2>
  <p>
    {% if status_snapshot.database_ready %}
    数据库已初始化，可继续执行导入、发布与搜索管理。
    {% else %}
    数据库未初始化，当前仅展示安全零值状态。
    {% endif %}
  </p>

  <div class="admin-actions">
    <a class="button-link button-link-secondary" href="{{ url_for('main.admin') }}">返回后台</a>
  </div>

  <div class="admin-dashboard">
    <section class="admin-panel">
      <h3>系统概览</h3>
      <ul class="admin-list">
        <li class="admin-list-item"><strong>数据库状态</strong><div class="admin-meta"><span>{{ '数据库已初始化' if status_snapshot.database_ready else '数据库未初始化' }}</span></div></li>
        <li class="admin-list-item"><strong>FTS 索引表</strong><div class="admin-meta"><span>{{ 'item_search 已就绪' if status_snapshot.fts_ready else 'item_search 未就绪' }}</span></div></li>
        <li class="admin-list-item"><strong>来源总数</strong><div class="admin-meta"><span>{{ status_snapshot.source_count }}</span><span>启用中：{{ status_snapshot.enabled_source_count }}</span></div></li>
        <li class="admin-list-item"><strong>公开条目数</strong><div class="admin-meta"><span>{{ status_snapshot.published_item_count }}</span></div></li>
        <li class="admin-list-item"><strong>草稿条目数</strong><div class="admin-meta"><span>{{ status_snapshot.draft_item_count }}</span></div></li>
        <li class="admin-list-item"><strong>最近更新时间</strong><div class="admin-meta"><span>{{ status_snapshot.latest_item_updated_at or '暂无条目更新时间' }}</span></div></li>
      </ul>
    </section>
  </div>
</section>
{% endblock %}
```

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_status_page tests/test_db.py::test_admin_status_page_shows_database_and_content_summary tests/test_db.py::test_admin_status_page_is_bootstrap_safe_before_init_db -q`
Expected: PASS

Then run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -q`
Expected: PASS

**Step 5: Commit**

当前项目不是 git 仓库，跳过 commit；在 `docs/progress-log.md` 记录此约束。

### Task 3: 将状态页入口接入后台首页文案并完成回归

**Objective:** 让管理员能从 `/admin` 明确发现状态页，并澄清公开统计与草稿列表的关系。

**Files:**
- Modify: `app/templates/admin.html`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

复用 `test_admin_page_links_to_status_page`；如链接或文案缺失则继续保持失败。

**Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_status_page -q`
Expected: FAIL（若入口或文案尚未接通）

**Step 3: Write minimal implementation**

将后台首页顶部说明改为公开统计口径，并新增状态页入口：

```html
<p>数据库状态：已接入 {{ stats.source_count }} 个来源，当前共有 {{ stats.item_count }} 条公开条目。</p>
<div class="admin-actions">
  <a class="button-link" href="{{ url_for('main.admin_import') }}">手动导入</a>
  <a class="button-link button-link-secondary" href="{{ url_for('main.admin_status') }}">系统状态</a>
  ...
</div>
```

同时将条目列表说明保持为“含草稿”，避免顶部统计与列表范围混淆。

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_status_page -q`
Expected: PASS

Then run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

**Step 5: Commit**

当前项目不是 git 仓库，跳过 commit；在 `docs/progress-log.md` 记录此约束。

---

Plan save path: `docs/plans/2026-04-20-admin-status-page.md`
