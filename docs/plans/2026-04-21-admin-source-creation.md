# Admin Source Creation Implementation Plan

**Goal:** Close the admin-side source-management loop so aggregate providers can be configured through the UI instead of requiring manual database inserts.

**Architecture:** Reuse the existing source-edit page structure, but add a dedicated `/admin/sources/new` route and shared source-payload validation in `app/db.py`. Keep source creation conservative for now by supporting only `manual` and the already implemented `wikipedia` provider type. Apply provider-aware defaults at save time so `wikipedia` can work without forcing the admin to type the default base URL each time.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Unify source validation and creation logic

**Objective:** Move source validation into shared helpers so create and edit behave consistently.

**Files:**
- Modify: `app/db.py`

**Delivered:**

- shared source-type normalization and validation
- duplicate `name` and `slug` protection
- supported source-type whitelist for current UI
- default `https://en.wikipedia.org` base URL when saving `wikipedia` sources without a custom address
- new `create_source(...)` helper for admin use

---

### Task 2: Add admin create-source route and UI affordances

**Objective:** Make source creation available from the existing admin dashboard.

**Files:**
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Modify: `app/templates/admin_edit_source.html`
- Modify: `app/static/style.css`

**Delivered:**

- `/admin/sources/new` GET/POST flow
- dashboard entry point for creating new sources
- shared create/edit source form
- source-type selector and inline guidance for admins

---

### Task 3: Add regression coverage

**Objective:** Lock down the new source-management workflow and provider-aware defaults.

**Files:**
- Add: `tests/test_admin_source_management.py`

**Coverage added:**

- creating a `wikipedia` source with default base URL
- rejecting unsupported source types
- updating an existing source into a `wikipedia` provider with default base URL
- end-to-end admin create-source flow
- validation error rendering and field preservation

---

### Verification

Run:

```bash
python -m pytest tests/test_admin_source_management.py -q
python -m pytest tests -q
```

Expected: PASS
