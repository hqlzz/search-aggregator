# Admin Import Validation Implementation Plan

**Goal:** Strengthen the admin import flow so failed submissions are explicit and useful instead of depending on implicit SQLite errors or allowing empty shell drafts.

**Architecture:** Keep the existing admin import route and form shape. Add validation in the data layer so import attempts fail safely before touching missing tables, and require at least one meaningful content carrier (`summary`, `content`, or `external_url`). Reuse the same content rule in draft editing to keep item integrity consistent after creation.

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: Add failing coverage for bootstrap-safe import

**Objective:** Prevent missing-table import attempts from turning into raw SQLite errors.

**Files:**
- Add: `tests/test_admin_import_validation.py`

**Coverage added:**

- `test_create_manual_import_item_is_bootstrap_safe_before_init_db`
- `test_admin_import_post_is_bootstrap_safe_before_init_db`

**Expected initial state:** FAIL — posting to `/admin/import` before `init-db` raises a table-missing error instead of returning a controlled validation result.

---

### Task 2: Add failing coverage for meaningful-content validation

**Objective:** Block empty shell drafts that contain only a title and taxonomy.

**Files:**
- Modify: `tests/test_admin_import_validation.py`

**Coverage added:**

- `test_create_manual_import_item_requires_meaningful_content`
- `test_admin_import_post_shows_meaningful_content_error_and_preserves_values`
- `test_update_draft_item_requires_meaningful_content`

**Expected initial state:** FAIL — imports without summary, content, and external URL are still accepted.

---

### Task 3: Implement shared validation and route status propagation

**Objective:** Centralize item-content validation and preserve accurate HTTP semantics at the route layer.

**Files:**
- Modify: `app/db.py`
- Modify: `app/routes.py`

**Implementation notes:**

- Return a 503 validation error when import runs before database bootstrap
- Require `summary`, `content`, or `external_url` to be present
- Reuse the same content rule in `update_draft_item`
- Let `/admin/import` propagate `ManualImportValidationError.status_code`

---

### Verification

Run:

```bash
python -m pytest tests/test_admin_import_validation.py -q
python -m pytest tests -q
```

Expected: PASS
