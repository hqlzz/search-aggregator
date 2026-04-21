# Search Result Snippets Implementation Plan

**Goal:** Complete the next search UX slice by showing a useful excerpt on result cards even when an item does not have a dedicated summary.

**Architecture:** Keep the existing Flask + SQLite + FTS5 search flow intact. Extend the search data-layer helper to return a normalized `excerpt` field for every result. Prefer the stored `summary` when present; otherwise, derive a short content snippet centered around the matched query. Keep the template simple by rendering the unified `excerpt` field instead of branching on raw data.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing coverage for summary-first and content-fallback excerpts

**Objective:** Define the expected result-card behavior before implementation.

**Files:**
- Add: `tests/test_search_snippets.py`

**Coverage added:**

- `test_search_items_prefers_summary_as_excerpt`
- `test_search_items_falls_back_to_content_excerpt_when_summary_missing`
- `test_search_page_renders_content_excerpt_when_summary_missing`

**Expected initial state:** FAIL — search results only render `summary`, and data-layer results do not yet expose unified excerpt fields.

---

### Task 2: Build unified excerpt output in the search helper

**Objective:** Make result shaping responsible for summary/snippet fallback so the template receives one consistent field.

**Files:**
- Modify: `app/db.py`

**Implementation notes:**

- Add normalized excerpt helpers
- Prefer `summary` when available
- Fallback to a trimmed content snippet near the matched query
- Return `excerpt` and `excerpt_source` from `search_items()`

---

### Task 3: Render the unified excerpt in the results template

**Objective:** Keep the UI layer minimal and display the new excerpt output without duplicating fallback logic in Jinja.

**Files:**
- Modify: `app/templates/search_results.html`
- Modify: `app/static/style.css`

**Expected final state:** PASS — result cards show summaries when present and query-adjacent content snippets when summaries are missing.

---

### Verification

Run:

```bash
python -m pytest tests/test_search_snippets.py -q
```

Expected: PASS
