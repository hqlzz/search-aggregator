# Admin Publish Failure Semantics Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make admin draft publishing fail safely and predictably for missing items, already-published items, and uninitialized databases.

**Architecture:** Keep the current lightweight Flask + SQLite admin flow, but tighten the publish contract around explicit failure cases. Put state validation in `app/db.py`, surface predictable HTTP statuses from `app/routes.py`, and keep the admin page feedback lightweight in `app/templates/admin.html`. Cover each failure mode with focused pytest cases before implementation, then run regression checks and document the new behavior.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing tests for publish failure cases

**Objective:** Define the contract for missing slug, repeated publish, and bootstrap-safe admin publish behavior before changing production code.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_publish_item_rejects_missing_slug(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        try:
            publish_item('missing-slug')
        except ManualImportValidationError as exc:
            errors = exc.errors
        else:
            errors = []

    assert errors == ['条目不存在，无法发布']
```

```python
def test_publish_item_rejects_non_draft_item(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        try:
            publish_item('sample-item-1')
        except ManualImportValidationError as exc:
            errors = exc.errors
        else:
            errors = []

    assert errors == ['仅允许发布 draft 状态条目']
```

```python
def test_admin_publish_post_returns_not_found_for_missing_slug(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.post('/admin/items/missing-slug/publish')

    assert response.status_code == 404
    assert '条目不存在，无法发布' in response.get_data(as_text=True)
```

```python
def test_admin_publish_post_returns_conflict_for_already_published_item(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.post('/admin/items/sample-item-1/publish')

    assert response.status_code == 409
    assert '仅允许发布 draft 状态条目' in response.get_data(as_text=True)
```

```python
def test_admin_publish_post_is_bootstrap_safe_before_init_db(client):
    response = client.post('/admin/items/any-slug/publish')

    assert response.status_code == 503
    assert '数据库尚未初始化，暂时无法发布条目' in response.get_data(as_text=True)
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_publish_item_rejects_missing_slug tests/test_db.py::test_publish_item_rejects_non_draft_item tests/test_db.py::test_admin_publish_post_returns_not_found_for_missing_slug tests/test_db.py::test_admin_publish_post_returns_conflict_for_already_published_item tests/test_db.py::test_admin_publish_post_is_bootstrap_safe_before_init_db -v`
Expected: FAIL — current helper/route collapse failure cases into one generic validation path.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the tests are written and verified failing.

**Step 4: Run test to verify failure**

Run the same command again and confirm FAIL.

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 2: Implement explicit publish failure semantics

**Objective:** Return specific validation messages and HTTP statuses for each publish failure mode without expanding scope.

**Files:**
- Modify: `app/db.py`
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

Reuse the tests from Task 1.

**Step 2: Run test to verify failure**

Run the Task 1 pytest command and confirm FAIL.

**Step 3: Write minimal implementation**

```python
class PublishValidationError(ValueError):
    def __init__(self, errors, status_code):
        super().__init__('publish validation failed')
        self.errors = errors
        self.status_code = status_code
```

```python
def publish_item(slug):
    if not has_bootstrapped_tables():
        raise PublishValidationError(['数据库尚未初始化，暂时无法发布条目'], 503)

    db = get_db()
    row = db.execute(
        'SELECT id, slug, status FROM items WHERE slug = ? LIMIT 1',
        (slug,),
    ).fetchone()
    if row is None:
        raise PublishValidationError(['条目不存在，无法发布'], 404)
    if row['status'] != 'draft':
        raise PublishValidationError(['仅允许发布 draft 状态条目'], 409)

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

    published_row = db.execute(
        'SELECT slug, status, published_at FROM items WHERE id = ?',
        (row['id'],),
    ).fetchone()
    return dict(published_row)
```

```python
@bp.post('/admin/items/<slug>/publish')
def admin_publish_item(slug):
    status_code = 200
    try:
        published_item = publish_item(slug)
        message = '草稿已发布'
        errors = []
    except PublishValidationError as exc:
        published_item = None
        message = None
        errors = exc.errors
        status_code = exc.status_code

    dashboard = get_admin_dashboard_data()
    return (
        render_template(...),
        status_code,
    )
```

**Step 4: Run test to verify pass**

Run the Task 1 pytest command.
Expected: PASS.

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 3: Run regression checks and update project state

**Objective:** Verify the publish flow still works and document the new failure semantics for the next iteration.

**Files:**
- Modify: `README.md`
- Modify: `docs/project-status.md`
- Modify: `docs/todo.md`
- Modify: `docs/progress-log.md`
- Test: `tests/test_db.py`
- Test: `tests/test_search.py`

**Step 1: Write failing test**

No new test required. Reuse the publish success/failure tests and public visibility tests.

**Step 2: Run test to verify current state**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_publish_item_changes_draft_to_published_and_sets_timestamp tests/test_db.py::test_admin_publish_post_promotes_draft_and_makes_item_public tests/test_db.py::test_publish_item_rejects_missing_slug tests/test_db.py::test_publish_item_rejects_non_draft_item tests/test_db.py::test_admin_publish_post_returns_not_found_for_missing_slug tests/test_db.py::test_admin_publish_post_returns_conflict_for_already_published_item tests/test_db.py::test_admin_publish_post_is_bootstrap_safe_before_init_db tests/test_search.py -q`
Expected: PASS after Task 2.

**Step 3: Write minimal implementation**

Update docs so they explicitly say:
- admin publish now distinguishes missing item / non-draft / uninitialized database cases
- successful publish still makes the item visible to detail page and search results
- next focus moves to PRG and lightweight admin auth/CSRF protection

**Step 4: Run verification**

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

Run: `hermes cron list`
Expected: `search-aggregator-hourly-dev` remains `active` with the next hourly run scheduled.

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```