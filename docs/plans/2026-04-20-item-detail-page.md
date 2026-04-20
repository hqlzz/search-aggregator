# Item Detail Page Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a first-pass item detail page so users can open a search result or homepage item and read full in-site metadata before optionally visiting the external source.

**Architecture:** Add one SQLite read helper that joins `items`, `sources`, and `categories` for a single published item, expose it through a new `/items/<slug>` Flask route, and render a dedicated Jinja detail template. Keep the feature lightweight: no new dependencies, no edit forms, and no search enhancements beyond simple internal navigation links.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add item detail data access, route, template, and navigation links

**Objective:** Deliver a working detail page with graceful 404 handling and internal links from homepage recent items and search results.

**Files:**
- Modify: `tests/test_search.py`
- Modify: `app/db.py`
- Modify: `app/routes.py`
- Modify: `app/templates/index.html`
- Modify: `app/templates/search_results.html`
- Modify: `app/static/style.css`
- Create: `app/templates/item_detail.html`

**Step 1: Write failing tests**

```python
def test_get_item_detail_returns_joined_item_data(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        item = get_item_detail('sample-item-2')

    assert item['title'] == '示例条目 2'
    assert item['source_name'] == '示例站点 A'
    assert item['category_name'] == '示例分类'


def test_item_detail_page_renders_full_item_information(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/items/sample-item-2')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '示例条目 2' in html
    assert '来源：示例站点 A' in html
    assert '分类：示例分类' in html
    assert '用于初始化数据库的示例条目 2' in html
    assert '示例内容 2' in html
    assert '查看原文' in html


def test_item_detail_page_returns_404_for_missing_slug(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/items/not-found-item')

    assert response.status_code == 404


def test_homepage_and_search_results_link_to_item_detail_pages(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    home_html = client.get('/').get_data(as_text=True)
    search_html = client.get('/search?q=示例内容 2').get_data(as_text=True)

    assert '/items/sample-item-1' in home_html or '/items/sample-item-3' in home_html
    assert '/items/sample-item-2' in search_html
```

**Step 2: Run test to verify failure**

Run: `./.venv/bin/python -m pytest tests/test_search.py -v`
Expected: FAIL — `get_item_detail` missing and `/items/<slug>` returns 404.

**Step 3: Write minimal implementation**

```python
def get_item_detail(slug):
    if not slug or not has_bootstrapped_tables():
        return None

    db = get_db()
    row = db.execute(
        """
        SELECT
            items.id,
            items.title,
            items.slug,
            items.summary,
            items.content,
            items.external_url,
            items.author,
            sources.name AS source_name,
            categories.name AS category_name
        FROM items
        JOIN sources ON sources.id = items.source_id
        LEFT JOIN categories ON categories.id = items.category_id
        WHERE items.slug = ? AND items.status = 'published'
        LIMIT 1
        """,
        (slug,),
    ).fetchone()
    return dict(row) if row else None
```

```python
@bp.get('/items/<slug>')
def item_detail(slug):
    item = get_item_detail(slug)
    if item is None:
        abort(404)
    return render_template('item_detail.html', item=item)
```

```html
<h3><a href="{{ url_for('main.item_detail', slug=item.slug) }}">{{ item.title }}</a></h3>
```

**Step 4: Run test to verify pass**

Run: `./.venv/bin/python -m pytest tests/test_search.py -v`
Expected: PASS

Run: `./.venv/bin/python -m pytest tests/ -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_search.py app/db.py app/routes.py app/templates/index.html app/templates/search_results.html app/templates/item_detail.html app/static/style.css
git commit -m "feat: add item detail page"
```

Note: if the directory is not a git repository, skip commit and record that limitation in the status update instead of forcing git commands.
