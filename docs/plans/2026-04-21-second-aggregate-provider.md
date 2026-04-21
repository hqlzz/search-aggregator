# Second Aggregate Provider Implementation Plan

**Goal:** Expand aggregate search from a single-source proof of concept into a more credible first-release experience by adding a second real external provider.

**Architecture:** Keep the existing provider-registry structure in `app/aggregate.py`, and add a new `hackernews` provider backed by the public Algolia Hacker News search API. Reuse the same admin source-management workflow introduced in the previous round so the new provider remains data-driven and can be enabled or disabled from the dashboard.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest, urllib

---

### Task 1: Add Hacker News aggregate provider

**Objective:** Support a second real aggregate source without changing route-level architecture.

**Files:**
- Modify: `app/aggregate.py`

**Delivered:**

- `hackernews` provider registration
- Algolia Hacker News query URL builder
- normalized result parsing
- reuse of existing aggregate cache path

---

### Task 2: Extend admin source typing and defaults

**Objective:** Make the new provider configurable from the same admin flow as current providers.

**Files:**
- Modify: `app/db.py`
- Modify: `app/templates/admin_edit_source.html`

**Delivered:**

- `hackernews` added to supported source type whitelist
- default `https://hn.algolia.com` base URL when the provider is saved without a custom address
- updated admin form guidance

---

### Task 3: Add regression coverage

**Objective:** Lock down provider parsing, page rendering, and admin validation changes.

**Files:**
- Modify: `tests/test_aggregate_search.py`
- Modify: `tests/test_admin_source_management.py`

**Coverage added:**

- creating a `hackernews` source with default base URL
- unsupported source-type error message update
- provider result parsing for Hacker News
- aggregate search page rendering with configured Hacker News source

---

### Verification

Run:

```bash
python -m pytest tests/test_admin_source_management.py tests/test_aggregate_search.py -q
python -m pytest tests -q
```

Expected: PASS
