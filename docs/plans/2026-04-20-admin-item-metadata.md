# Admin Item Metadata Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Enrich the admin dashboard item list so operators can see each published item's source, last update time, and external link without leaving `/admin`.

**Architecture:** Keep the current single `/admin` route and extend the existing admin dashboard query helper rather than introducing mutations or new pages. Add test-first coverage for both the data helper and rendered HTML, then update the SQLite query and Jinja template to expose extra read-only metadata for each published item.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing tests for admin item metadata

**Objective:** Define the expected admin dashboard behavior before changing production code.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_get_admin_dashboard_data_includes_item_metadata(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        dashboard = get_admin_dashboard_data(item_limit=1)

    item = dashboard['items'][0]
    assert set(item.keys()) == {
        'title',
        'slug',
        'status',
        'source_name',
        'category_name',
        'external_url',
        'updated_at',
    }
    assert item['external_url'] == 'https://example.com/b/3'
    assert item['updated_at']
```

```python
def test_admin_page_shows_item_source_update_time_and_external_link(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    item_section = html.split('条目管理', 1)[1]
    assert '来源：示例站点 B' in item_section
    assert '更新时间：' in item_section
    assert 'https://example.com/b/3' in item_section
    assert '查看原文' in item_section
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_item_metadata tests/test_db.py::test_admin_page_shows_item_source_update_time_and_external_link -v`
Expected: FAIL — admin item query and template do not yet expose `external_url` or `updated_at`.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the tests are written and verified failing.

**Step 4: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_item_metadata tests/test_db.py::test_admin_page_shows_item_source_update_time_and_external_link -v`
Expected: FAIL

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 2: Render admin item metadata from the data layer

**Objective:** Show extra item metadata in the admin dashboard using the tested helper output.

**Files:**
- Modify: `app/db.py`
- Modify: `app/templates/admin.html`
- Modify: `app/static/style.css`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

Use the tests added in Task 1:

```python
def test_get_admin_dashboard_data_includes_item_metadata(app, runner):
    ...
```

```python
def test_admin_page_shows_item_source_update_time_and_external_link(client, runner):
    ...
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_item_metadata tests/test_db.py::test_admin_page_shows_item_source_update_time_and_external_link -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def get_admin_items(limit=10):
    if not has_bootstrapped_tables():
        return []

    limit = max(0, int(limit))
    if limit == 0:
        return []

    db = get_db()
    rows = db.execute(
        """
        SELECT
            items.title,
            items.slug,
            items.status,
            items.external_url,
            items.updated_at,
            sources.name AS source_name,
            categories.name AS category_name
        FROM items
        JOIN sources ON sources.id = items.source_id
        LEFT JOIN categories ON categories.id = items.category_id
        WHERE items.status = 'published'
        ORDER BY items.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
```

```html
<li class="admin-list-item">
  <strong>{{ item.title }}</strong>
  <div class="admin-meta">
    <span>{{ item.slug }}</span>
    <span>{{ item.status }}</span>
    <span>{{ item.category_name or '未分类' }}</span>
  </div>
  <div class="admin-meta admin-meta-secondary">
    <span>来源：{{ item.source_name }}</span>
    <span>更新时间：{{ item.updated_at }}</span>
    {% if item.external_url %}
    <a href="{{ item.external_url }}" target="_blank" rel="noopener noreferrer">查看原文</a>
    {% endif %}
  </div>
</li>
```

```css
.admin-meta-secondary {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #dbe4f0;
}
```

**Step 4: Run test to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_item_metadata tests/test_db.py::test_admin_page_shows_item_source_update_time_and_external_link -v`
Expected: PASS

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```
