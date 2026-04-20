# Admin Draft Publish Flow Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a minimal admin-side publish action so draft items can be promoted to published from the browser.

**Architecture:** Keep the current lightweight Flask + SQLite admin flow and add one narrow state transition: `draft -> published`. Put transition validation and persistence in `app/db.py`, expose a POST route in `app/routes.py`, and add a small publish form beside draft items in `app/templates/admin.html`. Cover the behavior with TDD in `tests/test_db.py`, ensuring public pages remain `published`-only until the publish action succeeds.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing tests for draft publish behavior

**Objective:** Define the draft publish contract before changing production code.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
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
```

```python
def test_admin_publish_post_promotes_draft_and_makes_item_public(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    client.post(
        '/admin/import',
        data={
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '后台发布草稿',
            'summary': '发布前摘要',
            'content': '发布后应进入公开详情',
            'external_url': 'https://example.com/admin-publish',
        },
    )

    publish_response = client.post('/admin/items/backend-publish-draft/publish')
    detail_response = client.get('/items/backend-publish-draft')
    search_response = client.get('/search?q=后台发布草稿')

    assert publish_response.status_code == 200
    publish_html = publish_response.get_data(as_text=True)
    assert '草稿已发布' in publish_html
    assert 'published' in publish_html
    assert detail_response.status_code == 200
    assert search_response.status_code == 200
    assert '后台发布草稿' in search_response.get_data(as_text=True)
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_publish_item_changes_draft_to_published_and_sets_timestamp tests/test_db.py::test_admin_publish_post_promotes_draft_and_makes_item_public -v`
Expected: FAIL — publish helper and route do not exist yet.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the tests are written and verified failing.

**Step 4: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_publish_item_changes_draft_to_published_and_sets_timestamp tests/test_db.py::test_admin_publish_post_promotes_draft_and_makes_item_public -v`
Expected: FAIL

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 2: Implement the draft publish helper, route, and admin action

**Objective:** Make draft items publishable from `/admin` without changing unrelated flows.

**Files:**
- Modify: `app/db.py`
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Modify: `app/static/style.css`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

Use the tests from Task 1.

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_publish_item_changes_draft_to_published_and_sets_timestamp tests/test_db.py::test_admin_publish_post_promotes_draft_and_makes_item_public -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def publish_item(slug):
    db = get_db()
    row = db.execute(
        'SELECT id, slug, status FROM items WHERE slug = ? LIMIT 1',
        (slug,),
    ).fetchone()
    if row is None or row['status'] != 'draft':
        raise ManualImportValidationError(['仅允许发布草稿条目'])

    with db:
        db.execute(
            """
            UPDATE items
            SET status = 'published',
                published_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row['id'],),
        )

    return db.execute(
        'SELECT slug, status, published_at FROM items WHERE id = ?',
        (row['id'],),
    ).fetchone()
```

```python
@bp.post('/admin/items/<slug>/publish')
def admin_publish_item(slug):
    try:
        published_item = publish_item(slug)
        message = '草稿已发布'
        errors = []
    except ManualImportValidationError as exc:
        published_item = None
        message = None
        errors = exc.errors

    dashboard = get_admin_dashboard_data()
    return render_template(
        'admin.html',
        dashboard=dashboard,
        stats=dashboard['stats'],
        publish_message=message,
        publish_errors=errors,
        published_item=published_item,
    )
```

```html
{% if item.status == 'draft' %}
<form method="post" action="{{ url_for('main.admin_publish_item', slug=item.slug) }}">
  <button type="submit">发布</button>
</form>
{% endif %}
```

**Step 4: Run test to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_publish_item_changes_draft_to_published_and_sets_timestamp tests/test_db.py::test_admin_publish_post_promotes_draft_and_makes_item_public -v`
Expected: PASS

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 3: Run regression checks and record the new workflow

**Objective:** Verify the new publish flow does not break current behavior and update project state.

**Files:**
- Modify: `README.md`
- Modify: `docs/project-status.md`
- Modify: `docs/todo.md`
- Modify: `docs/progress-log.md`
- Test: `tests/test_db.py`
- Test: `tests/test_search.py`

**Step 1: Write failing test**

No new test required. Reuse publish-flow tests plus existing public visibility tests.

**Step 2: Run test to verify current state**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_publish_item_changes_draft_to_published_and_sets_timestamp tests/test_db.py::test_admin_publish_post_promotes_draft_and_makes_item_public tests/test_search.py -q`
Expected: PASS after Task 2.

**Step 3: Write minimal implementation**

Update docs so they explicitly say:
- admin now supports publishing draft items from the dashboard
- published items immediately become visible to detail page and search results
- next focus moves to stricter validation and lightweight admin protection

**Step 4: Run verification**

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

Run: `hermes cron list`
Expected: `search-aggregator-hourly-dev` remains `active` with the next hourly run scheduled.

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```
