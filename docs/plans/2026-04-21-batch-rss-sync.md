# Batch RSS Sync Implementation Plan

**Goal:** Turn RSS import from a single-source admin action into an operational workflow that can be triggered in bulk from either the admin dashboard or the command line.

**Architecture:** Reuse the existing single-source RSS sync path in `app/feed_import.py`, and add a bulk-sync coordinator that iterates over every enabled RSS source. Keep per-source errors isolated so one broken feed does not block the rest. Expose that same coordinator through both a dashboard action and a Flask CLI command.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest, Click

---

### Task 1: Add bulk RSS sync coordinator and CLI command

**Objective:** Make the RSS ingestion path reusable for manual operations and future scheduled jobs.

**Files:**
- Modify: `app/feed_import.py`
- Modify: `app/__init__.py`

**Delivered:**

- enabled RSS source enumeration
- bulk sync summary with success/failure aggregation
- `flask sync-rss` CLI command
- command registration during app bootstrap

---

### Task 2: Add admin bulk-sync action

**Objective:** Let admins sync all enabled RSS feeds from the main dashboard without visiting each source.

**Files:**
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`

**Delivered:**

- `POST /admin/sources/sync` route
- dashboard action button for bulk RSS sync
- summarized sync feedback plus per-source error reporting

---

### Task 3: Add regression coverage

**Objective:** Lock down the new operational entry points before moving on to deployment and release hardening.

**Files:**
- Modify: `tests/test_rss_import.py`

**Coverage added:**

- bulk sync success/error aggregation
- admin bulk-sync flow
- CLI bulk-sync reporting

---

### Verification

Run:

```bash
python -m pytest tests/test_rss_import.py -q
python -m pytest tests -q
```

Expected: PASS
