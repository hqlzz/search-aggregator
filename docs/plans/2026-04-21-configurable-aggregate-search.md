# Configurable Aggregate Search Implementation Plan

**Goal:** Turn aggregate search from a static placeholder into a real, testable integration path without breaking the default local-search-only installation.

**Architecture:** Keep `mode=aggregate` in the existing `/search` route, but make it consult enabled `sources` rows whose `source_type` maps to a supported aggregate provider. This keeps aggregate-search enablement data-driven. When no supported aggregate source is configured, preserve the current placeholder-style fallback. When a supported source exists, fetch and render real external results. Add a lightweight in-process TTL cache so repeated identical searches do not call the provider every time.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest, urllib

---

### Task 1: Add aggregate provider service and cache

**Objective:** Create a pluggable external-search layer that stays independent from route rendering.

**Files:**
- Add: `app/aggregate.py`

**Delivered:**

- provider registry keyed by `source_type`
- first provider: `wikipedia`
- result normalization to a shared shape
- in-process TTL cache for identical source/query pairs
- graceful provider-level error collection

---

### Task 2: Add DB helper for enabled aggregate sources

**Objective:** Make aggregate search opt-in through existing source records instead of hard-coding enabled providers in the route.

**Files:**
- Modify: `app/db.py`

**Delivered:**

- `get_enabled_aggregate_sources(supported_source_types)`

---

### Task 3: Wire aggregate mode to real results with safe fallback

**Objective:** Let `/search?mode=aggregate` render external results when supported sources exist, while keeping old behavior safe when they do not.

**Files:**
- Modify: `app/routes.py`
- Modify: `app/templates/search_results.html`

**Delivered:**

- aggregate mode now queries configured providers
- default installations still show a clear fallback notice
- provider failures degrade to user-friendly messages instead of server errors

---

### Task 4: Add regression coverage

**Objective:** Lock down both the default fallback path and the configured-provider success path.

**Files:**
- Add: `tests/test_aggregate_search.py`

**Coverage added:**

- supported aggregate source filtering
- provider result parsing
- cache reuse
- default placeholder fallback
- configured Wikipedia results
- graceful provider failure handling

---

### Verification

Run:

```bash
python -m pytest tests/test_aggregate_search.py -q
python -m pytest tests -q
```

Expected: PASS
