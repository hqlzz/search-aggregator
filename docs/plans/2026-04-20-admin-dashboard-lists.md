# Admin Dashboard Lists Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a first useful admin dashboard that lists configured data sources and recent items so the backend is no longer just a placeholder page.

**Architecture:** Extend the existing lightweight SQLite data layer with two read helpers dedicated to admin display: one for source records and one for recent item records including source/category/status metadata. Keep the single `/admin` route and enrich its template with two read-only tables. No forms, mutations, pagination, or auth are added in this round.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing admin dashboard tests for source and item lists

**Objective:** Define the expected backend page behavior before implementation.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_admin_page_lists_sources_and_recent_items(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '数据源管理' in html
    assert '示例站点 A' in html
    assert 'manual' in html
    assert '已启用' in html
    assert '条目管理' in html
    assert '示例条目 3' in html
    assert 'published' in html
```

```python
def test_admin_page_shows_empty_state_before_init_db(client):
    response = client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '暂无数据源，请先初始化数据库。' in html
    assert '暂无条目，请先初始化数据库。' in html
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_lists_sources_and_recent_items tests/test_db.py::test_admin_page_shows_empty_state_before_init_db -v`
Expected: FAIL — admin template does not yet render source or item list sections.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the tests are written and verified failing.

**Step 4: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_lists_sources_and_recent_items tests/test_db.py::test_admin_page_shows_empty_state_before_init_db -v`
Expected: FAIL

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 2: Add admin dashboard data helpers and render read-only lists

**Objective:** Make `/admin` show source and item tables backed by SQLite queries.

**Files:**
- Modify: `app/db.py`
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Modify: `app/static/style.css`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

Use the tests created in Task 1:

```python
def test_admin_page_lists_sources_and_recent_items(client, runner):
    ...
```

```python
def test_admin_page_shows_empty_state_before_init_db(client):
    ...
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_lists_sources_and_recent_items tests/test_db.py::test_admin_page_shows_empty_state_before_init_db -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def get_admin_sources():
    if not has_bootstrapped_tables():
        return []

    db = get_db()
    rows = db.execute(
        '''
        SELECT id, name, slug, source_type, base_url, enabled
        FROM sources
        ORDER BY name COLLATE NOCASE ASC, id ASC
        '''
    ).fetchall()
    return [dict(row) for row in rows]


def get_admin_items(limit=10):
    if not has_bootstrapped_tables():
        return []

    db = get_db()
    rows = db.execute(
        '''
        SELECT
            items.id,
            items.title,
            items.slug,
            items.status,
            sources.name AS source_name,
            categories.name AS category_name
        FROM items
        JOIN sources ON sources.id = items.source_id
        LEFT JOIN categories ON categories.id = items.category_id
        ORDER BY items.id DESC
        LIMIT ?
        ''',
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_admin_dashboard_data():
    return {
        'stats': get_stats(),
        'sources': get_admin_sources(),
        'items': get_admin_items(),
    }
```

```python
@bp.get('/admin')
def admin():
    dashboard = get_admin_dashboard_data()
    return render_template('admin.html', dashboard=dashboard)
```

```html
<section>
  <h3>数据源管理</h3>
  {% if dashboard.sources %}
    <table>
      <thead><tr><th>名称</th><th>类型</th><th>状态</th></tr></thead>
      <tbody>
        {% for source in dashboard.sources %}
          <tr>
            <td>{{ source.name }}</td>
            <td>{{ source.source_type }}</td>
            <td>{{ '已启用' if source.enabled else '已禁用' }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p>暂无数据源，请先初始化数据库。</p>
  {% endif %}
</section>
```

```html
<section>
  <h3>条目管理</h3>
  {% if dashboard.items %}
    <table>
      <thead><tr><th>标题</th><th>来源</th><th>状态</th></tr></thead>
      <tbody>
        {% for item in dashboard.items %}
          <tr>
            <td>{{ item.title }}</td>
            <td>{{ item.source_name }}</td>
            <td>{{ item.status }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% else %}
    <p>暂无条目，请先初始化数据库。</p>
  {% endif %}
</section>
```

**Step 4: Run test to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_lists_sources_and_recent_items tests/test_db.py::test_admin_page_shows_empty_state_before_init_db -v`
Expected: PASS

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 3: Add direct data-layer coverage for admin dashboard queries

**Objective:** Lock down helper output shape so future admin work can build on stable query functions.

**Files:**
- Modify: `tests/test_db.py`
- Modify: `app/db.py`

**Step 1: Write failing test**

```python
def test_get_admin_dashboard_data_returns_sources_and_recent_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        dashboard = get_admin_dashboard_data()

    assert dashboard['stats']['source_count'] == 2
    assert len(dashboard['sources']) == 2
    assert dashboard['sources'][0]['name'].startswith('示例站点')
    assert dashboard['items'][0]['title'].startswith('示例条目')
    assert dashboard['items'][0]['status'] == 'published'
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_returns_sources_and_recent_items -v`
Expected: FAIL — helper missing or output shape incomplete.

**Step 3: Write minimal implementation**

Use `get_admin_dashboard_data()` from Task 2 and ensure it returns a dict with `stats`, `sources`, and `items` keys.

**Step 4: Run test to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_returns_sources_and_recent_items -v`
Expected: PASS

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```
