# Admin Manual Import Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a minimal admin-side manual import form so operators can create new draft items from the browser without touching SQLite directly.

**Architecture:** Keep the current lightweight Flask + SQLite admin flow and introduce a dedicated `/admin/import` page with a small POST form. Put validation and insert logic in `app/db.py`, keep the route thin in `app/routes.py`, render the form in a new Jinja template, and link to it from `/admin`. New items default to `draft` so the feature is safe-by-default and does not change public search behavior.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing tests for the manual import entry page

**Objective:** Define the admin import page and form behavior before changing production code.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_admin_page_links_to_manual_import_entry(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/admin')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '手动导入' in html
    assert 'href="/admin/import"' in html
```

```python
def test_admin_import_page_shows_manual_import_form(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/admin/import')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '手动导入条目' in html
    assert 'name="title"' in html
    assert 'name="source_slug"' in html
    assert 'example-source-a' in html
    assert 'example-category' in html
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_manual_import_entry tests/test_db.py::test_admin_import_page_shows_manual_import_form -v`
Expected: FAIL — `/admin` does not link to the import page and `/admin/import` does not exist yet.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the tests are written and verified failing.

**Step 4: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_manual_import_entry tests/test_db.py::test_admin_import_page_shows_manual_import_form -v`
Expected: FAIL

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 2: Add failing tests for successful manual import creation

**Objective:** Define the POST flow and persistence behavior for a minimal draft import.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_admin_import_post_creates_draft_item_and_shows_success(app, client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.post(
        '/admin/import',
        data={
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '后台手动导入条目',
            'summary': '来自后台表单的摘要',
            'content': '这是后台手动导入的正文。',
            'external_url': 'https://example.com/manual-import',
        },
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
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_creates_draft_item_and_shows_success -v`
Expected: FAIL — POST handling and insert helper do not exist yet.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the test is written and verified failing.

**Step 4: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_creates_draft_item_and_shows_success -v`
Expected: FAIL

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 3: Add failing validation test for manual import errors

**Objective:** Lock down the minimal validation contract so invalid submissions do not write rows.

**Files:**
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_admin_import_post_requires_title_and_source(app, client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.post(
        '/admin/import',
        data={
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
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_requires_title_and_source -v`
Expected: FAIL — validation branch does not exist yet.

**Step 3: Write minimal implementation**

Do not implement in this task. Stop after the test is written and verified failing.

**Step 4: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_requires_title_and_source -v`
Expected: FAIL

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```

---

### Task 4: Implement the admin manual import route, template, and SQLite insert helper

**Objective:** Make the tested import page work end-to-end with safe defaults and simple validation.

**Files:**
- Modify: `app/db.py`
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Create: `app/templates/admin_import.html`
- Modify: `app/static/style.css`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

Use the tests from Tasks 1-3.

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_manual_import_entry tests/test_db.py::test_admin_import_page_shows_manual_import_form tests/test_db.py::test_admin_import_post_creates_draft_item_and_shows_success tests/test_db.py::test_admin_import_post_requires_title_and_source -v`
Expected: FAIL

**Step 3: Write minimal implementation**

```python
def get_admin_import_options():
    return {
        'sources': get_admin_sources(),
        'categories': get_admin_categories(),
    }
```

```python
def create_manual_import_item(*, source_slug, category_slug, title, summary, content, external_url):
    # Validate required fields.
    # Resolve source/category IDs.
    # Generate a unique slug from title.
    # Insert a new draft row into items.
    # Return a dict describing the new item.
```

```python
@bp.route('/admin/import', methods=['GET', 'POST'])
def admin_import():
    if request.method == 'POST':
        ...
    return render_template('admin_import.html', ...)
```

```html
<a class="button-link" href="{{ url_for('main.admin_import') }}">手动导入</a>
```

```html
<form method="post" class="admin-form">
  <!-- source, category, title, summary, content, external_url -->
</form>
```

**Step 4: Run test to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_db.py::test_admin_page_links_to_manual_import_entry tests/test_db.py::test_admin_import_page_shows_manual_import_form tests/test_db.py::test_admin_import_post_creates_draft_item_and_shows_success tests/test_db.py::test_admin_import_post_requires_title_and_source -v`
Expected: PASS

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

**Step 5: Commit**

```bash
# Skip commit if git repo is absent.
```
