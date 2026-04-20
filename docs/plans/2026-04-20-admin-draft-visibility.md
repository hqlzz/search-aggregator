# Admin Draft Visibility Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make newly imported draft items visible in the admin dashboard so operators get immediate management feedback after manual import.

**Architecture:** Keep public behavior unchanged and only expand the admin dashboard query path. Update the admin item query in `app/db.py` so `/admin` can list both `published` and `draft` items with newest-first ordering, keep route logic unchanged, and use targeted template copy to explain that the list now includes drafts. Cover the behavior with TDD in `tests/test_db.py`, especially that drafts are visible in admin while homepage/search/detail remain public-only.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing tests for admin draft visibility

**Objective:** Define the expected admin dashboard behavior before changing production code.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_get_admin_dashboard_data_includes_draft_items_for_management_feedback(app, runner):
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
    assert dashboard['items'][0]['status'] == 'draft'
```

```python
def test_admin_page_shows_draft_item_and_management_hint(client, runner):
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
                '后台页面草稿条目',
                'admin-page-draft-item',
                '后台页面应展示草稿',
                'draft body',
                'https://example.com/admin-page-draft',
                '编辑部',
                'draft',
            ),
        )
        db.commit()

    response = client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '条目管理（含草稿）' in html
    assert '后台页面草稿条目' in html
    assert 'draft' in html
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_draft_items_for_management_feedback tests/test_db.py::test_admin_page_shows_draft_item_and_management_hint -v`
Expected: FAIL — admin dashboard currently filters items to `published` only and the template does not mention drafts.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the tests are written and verified failing.

**Step 4: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_draft_items_for_management_feedback tests/test_db.py::test_admin_page_shows_draft_item_and_management_hint -v`
Expected: FAIL

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 2: Implement admin draft visibility in data and template layers

**Objective:** Make `/admin` list draft and published items without affecting public pages.

**Files:**
- Modify: `app/db.py`
- Modify: `app/templates/admin.html`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

Use the tests from Task 1.

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_draft_items_for_management_feedback tests/test_db.py::test_admin_page_shows_draft_item_and_management_hint -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
rows = db.execute(
    """
    SELECT
        items.title,
        items.slug,
        items.status,
        sources.name AS source_name,
        categories.name AS category_name,
        items.external_url,
        items.updated_at
    FROM items
    JOIN sources ON sources.id = items.source_id
    LEFT JOIN categories ON categories.id = items.category_id
    WHERE items.status IN ('published', 'draft')
    ORDER BY items.id DESC
    LIMIT ?
    """,
    (limit,),
).fetchall()
```

```html
<h3>条目管理（含草稿）</h3>
<p class="admin-help">展示最近条目，包含已发布与草稿状态，便于核对手动导入结果。</p>
```

Keep `get_stats()`, homepage, search, and detail-page visibility rules unchanged.

**Step 4: Run test to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_draft_items_for_management_feedback tests/test_db.py::test_admin_page_shows_draft_item_and_management_hint -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_db.py app/db.py app/templates/admin.html
git commit -m "feat: show draft items on admin dashboard"
```

---

### Task 3: Run regression checks and document the behavior

**Objective:** Prove the change does not break public visibility rules and update project docs.

**Files:**
- Modify: `README.md`
- Modify: `docs/project-status.md`
- Modify: `docs/todo.md`
- Modify: `docs/progress-log.md`
- Test: `tests/test_db.py`
- Test: `tests/test_search.py`

**Step 1: Write failing test**

No new test required. Reuse the admin draft visibility tests plus existing public visibility tests.

**Step 2: Run test to verify current state**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_get_admin_dashboard_data_includes_draft_items_for_management_feedback tests/test_db.py::test_admin_page_shows_draft_item_and_management_hint tests/test_search.py::test_unpublished_items_are_excluded_from_recent_items_search_and_detail tests/ -q`
Expected: PASS after Task 2; public visibility tests remain green.

**Step 3: Write minimal implementation**

Update docs so they explicitly say:
- admin dashboard now shows draft items for management feedback
- public pages still only expose `published` items
- next focus moves to draft actions / publish flow or stricter manual import validation

**Step 4: Run verification**

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

Run: `hermes cron list`
Expected: `search-aggregator-hourly-dev` remains `active` with the next hourly run scheduled.

**Step 5: Commit**

```bash
git add README.md docs/project-status.md docs/todo.md docs/progress-log.md
git commit -m "docs: record admin draft visibility progress"
```