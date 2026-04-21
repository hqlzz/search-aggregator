# RSS Source Sync Implementation Plan

**Goal:** Move the project closer to a usable first release by adding a semi-automated content-ingestion path for RSS/Atom sources.

**Architecture:** Treat RSS as a new admin-manageable source type, but keep ingestion separate from aggregate search. A dedicated feed-import module fetches and parses RSS/Atom data, then stores new entries as drafts using the existing content-review flow. Duplicate detection is handled at import time by source plus external URL, with a title fallback when no link is available.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest, urllib, xml.etree.ElementTree

---

### Task 1: Add feed import service

**Objective:** Create a reusable import layer that can later support manual sync, scheduled jobs, or batch sync.

**Files:**
- Add: `app/feed_import.py`

**Delivered:**

- RSS/Atom fetching via `urllib`
- lightweight feed parsing with the Python standard library
- HTML stripping and text normalization for imported summaries/content
- duplicate detection and draft creation
- clear error mapping for fetch and parse failures

---

### Task 2: Extend admin source model and sync workflow

**Objective:** Let admins configure RSS sources and trigger imports without touching the database.

**Files:**
- Modify: `app/db.py`
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Modify: `app/templates/admin_edit_source.html`
- Modify: `app/static/style.css`

**Delivered:**

- new `rss` source type in admin source configuration
- validation requiring a real feed URL for RSS sources
- `POST /admin/sources/<slug>/sync` admin action
- one-click RSS sync buttons in dashboard and source detail pages
- success/error feedback after sync

---

### Task 3: Add regression coverage

**Objective:** Lock down the new import path before building more automation on top of it.

**Files:**
- Add: `tests/test_rss_import.py`
- Modify: `tests/test_admin_source_management.py`

**Coverage added:**

- RSS source validation
- RSS sync draft creation
- duplicate skipping on repeated sync
- invalid feed error handling
- admin sync success flow

---

### Verification

Run:

```bash
python -m pytest tests/test_admin_source_management.py tests/test_rss_import.py -q
python -m pytest tests -q
```

Expected: PASS
