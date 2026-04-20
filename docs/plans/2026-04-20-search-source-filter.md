# Search Source Filter Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a minimal but useful source filter to the public search flow so users can narrow results to a selected source without affecting existing full-text search behavior.

**Architecture:** Keep the feature lightweight by extending the existing `/search` GET flow and SQLite query layer rather than adding new pages or JS. The backend will expose the available published-result sources, accept an optional `source` query parameter, constrain `search_items()` when valid, and render the filter in both the homepage and search results form.

**Tech Stack:** Python 3.12, Flask, SQLite/FTS5, Jinja2, pytest

---

### Task 1: Add failing tests for source-filtered search query behavior

**Objective:** Define the database-layer contract for listing filterable sources and applying an optional source slug filter to search results.

**Files:**
- Modify: `tests/test_search.py`
- Modify: `app/db.py`
- Test: `tests/test_search.py`

**Step 1: Write failing test**

```python
def test_search_items_can_filter_by_source_slug(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        results = search_items('示例内容', source_slug='example-source-b')

    assert len(results) == 1
    assert results[0]['slug'] == 'sample-item-3'
    assert all(item['source_slug'] == 'example-source-b' for item in results)


def test_get_search_source_options_returns_enabled_sources_with_published_items(app, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    with app.app_context():
        options = get_search_source_options()

    assert options == [
        {'name': '示例站点 A', 'slug': 'example-source-a'},
        {'name': '示例站点 B', 'slug': 'example-source-b'},
    ]
```

**Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_search.py::test_search_items_can_filter_by_source_slug tests/test_search.py::test_get_search_source_options_returns_enabled_sources_with_published_items -q`
Expected: FAIL — `search_items()` does not accept `source_slug` and `get_search_source_options()` does not exist.

**Step 3: Write minimal implementation**

```python
def get_search_source_options():
    if not has_bootstrapped_tables():
        return []

    rows = get_db().execute(
        '''
        SELECT DISTINCT sources.name, sources.slug
        FROM sources
        JOIN items ON items.source_id = sources.id
        WHERE sources.enabled = 1 AND items.status = 'published'
        ORDER BY sources.name COLLATE NOCASE ASC, sources.id ASC
        '''
    ).fetchall()
    return [dict(row) for row in rows]


def search_items(query, limit=SEARCH_RESULTS_LIMIT, source_slug=None):
    normalized_query = normalize_search_query(query)
    normalized_source_slug = (source_slug or '').strip()
    if not normalized_query or not has_bootstrapped_tables() or not table_exists('item_search'):
        return []

    escaped_query = normalized_query.replace('"', '""')
    match_query = f'"{escaped_query}"'

    sql = '''
        SELECT
            items.id,
            items.title,
            items.slug,
            items.summary,
            items.external_url,
            sources.name AS source_name,
            sources.slug AS source_slug,
            bm25(item_search) AS score
        FROM item_search
        JOIN items ON items.id = item_search.rowid
        JOIN sources ON sources.id = items.source_id
        WHERE item_search MATCH ?
          AND items.status = 'published'
    '''
    params = [match_query]
    if normalized_source_slug:
        sql += ' AND sources.slug = ?'
        params.append(normalized_source_slug)
    sql += ' ORDER BY score, items.id DESC LIMIT ?'
    params.append(limit)

    rows = get_db().execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]
```

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_search.py::test_search_items_can_filter_by_source_slug tests/test_search.py::test_get_search_source_options_returns_enabled_sources_with_published_items -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_search.py app/db.py
git commit -m "feat: add source-filtered search query support"
```

### Task 2: Add failing tests for search page source filter UX

**Objective:** Lock in the HTTP and template behavior for source filter options, selected state, and result count updates.

**Files:**
- Modify: `tests/test_search.py`
- Modify: `app/routes.py`
- Modify: `app/templates/index.html`
- Modify: `app/templates/search_results.html`
- Test: `tests/test_search.py`

**Step 1: Write failing test**

```python
def test_search_page_renders_source_filter_options(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容')

    html = response.get_data(as_text=True)
    assert '按来源筛选' in html
    assert '<option value="example-source-a">示例站点 A</option>' in html
    assert '<option value="example-source-b">示例站点 B</option>' in html


def test_search_page_filters_results_and_preserves_selected_source(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容&source=example-source-b')

    html = response.get_data(as_text=True)
    assert '共找到 1 条结果' in html
    assert '示例条目 3' in html
    assert '示例条目 1' not in html
    assert 'option value="example-source-b" selected' in html
    assert '当前筛选来源：示例站点 B' in html
```

**Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_search.py::test_search_page_renders_source_filter_options tests/test_search.py::test_search_page_filters_results_and_preserves_selected_source -q`
Expected: FAIL — page has no source filter UI or selected-source summary.

**Step 3: Write minimal implementation**

```python
@bp.get('/search')
def search():
    q = request.args.get('q', '')
    source_slug = request.args.get('source', '').strip()
    normalized_query = normalize_search_query(q)
    source_options = get_search_source_options()
    source_lookup = {option['slug']: option for option in source_options}
    selected_source = source_lookup.get(source_slug)
    effective_source_slug = selected_source['slug'] if selected_source else ''
    results = search_items(normalized_query, source_slug=effective_source_slug)
    return render_template(
        'search_results.html',
        query=normalized_query,
        results=results,
        result_count=len(results),
        source_options=source_options,
        selected_source_slug=effective_source_slug,
        selected_source=selected_source,
    )
```

```html
<label for="results-source">按来源筛选</label>
<select id="results-source" name="source">
  <option value="">全部来源</option>
  {% for source in source_options %}
    <option value="{{ source.slug }}" {% if selected_source_slug == source.slug %}selected{% endif %}>{{ source.name }}</option>
  {% endfor %}
</select>
```

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_search.py::test_search_page_renders_source_filter_options tests/test_search.py::test_search_page_filters_results_and_preserves_selected_source -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_search.py app/routes.py app/templates/index.html app/templates/search_results.html
git commit -m "feat: add search source filter ui"
```

### Task 3: Add homepage entry-point support and invalid-filter regression tests

**Objective:** Make the homepage search form capable of submitting the same source filter and ensure invalid source slugs degrade safely.

**Files:**
- Modify: `tests/test_search.py`
- Modify: `app/routes.py`
- Modify: `app/templates/index.html`
- Test: `tests/test_search.py`

**Step 1: Write failing test**

```python
def test_homepage_renders_source_filter_options(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/')

    html = response.get_data(as_text=True)
    assert '按来源筛选' in html
    assert 'name="source"' in html
    assert 'value="example-source-a"' in html


def test_search_page_ignores_unknown_source_filter(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/search?q=示例内容&source=missing-source')

    html = response.get_data(as_text=True)
    assert '共找到 3 条结果' in html
    assert '当前筛选来源：' not in html
    assert 'option value="" selected' in html
```

**Step 2: Run test to verify failure**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_search.py::test_homepage_renders_source_filter_options tests/test_search.py::test_search_page_ignores_unknown_source_filter -q`
Expected: FAIL — homepage lacks filter UI and invalid filter handling is not explicit.

**Step 3: Write minimal implementation**

```python
@bp.get('/')
def index():
    q = request.args.get('q', '').strip()
    homepage_data = get_homepage_data()
    return render_template(
        'index.html',
        query=q,
        homepage=homepage_data,
        source_options=get_search_source_options(),
        selected_source_slug='',
    )
```

```html
<label for="homepage-source">按来源筛选</label>
<select id="homepage-source" name="source">
  <option value="" selected>全部来源</option>
  {% for source in source_options %}
    <option value="{{ source.slug }}">{{ source.name }}</option>
  {% endfor %}
</select>
```

**Step 4: Run test to verify pass**

Run: `PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_search.py::test_homepage_renders_source_filter_options tests/test_search.py::test_search_page_ignores_unknown_source_filter -q`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_search.py app/routes.py app/templates/index.html
git commit -m "feat: add source filter to homepage search entry"
```

### Task 4: Verify, document, and hand off

**Objective:** Confirm the new source filter works end-to-end and update project tracking docs.

**Files:**
- Modify: `README.md`
- Modify: `docs/project-status.md`
- Modify: `docs/todo.md`
- Modify: `docs/progress-log.md`
- Test: `tests/test_search.py`

**Step 1: Run focused regression tests**

```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_search.py -q
```

Expected: PASS

**Step 2: Run broader regression tests**

```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -q
PYTHONPATH=. ./.venv/bin/python -m pytest tests/ -q
```

Expected: PASS

**Step 3: Update project docs**

```markdown
- README.md: move current stage from “search enhancement planned” to “source filter delivered, next up tags/categories/sorting/snippets”
- docs/project-status.md: record latest test counts, current stage, remaining search-enhancement work, and next cron time
- docs/todo.md: mark “来源筛选” as done
- docs/progress-log.md: append this round’s actions, verification commands, and next steps
```

**Step 4: Verify cron continuity**

Run: `date -Iseconds && hermes cron list`
Expected: hourly job `search-aggregator-hourly-dev` remains active/scheduled for the next top-of-hour run.

**Step 5: Commit**

```bash
git add README.md docs/project-status.md docs/todo.md docs/progress-log.md
git commit -m "docs: record source filter search progress"
```
