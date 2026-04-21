# Release Readiness Checks Implementation Plan

**Goal:** Add a practical pre-launch verification layer so the first release can be checked from the admin UI, CLI, and health endpoints before going live.

**Architecture:** Keep release checks read-only and centralize them in a dedicated module. Reuse the existing database/status information, then layer on deployment-specific checks such as default credentials, database initialization, FTS readiness, enabled source presence, public-content presence, and RSS source validity. Expose the same readiness snapshot through the admin status page, `flask check-release`, and `/health/ready`.

**Tech Stack:** Python 3.12, Flask, SQLite, pytest, Click

---

### Task 1: Add reusable release-readiness service

**Objective:** Build one source of truth for launch gating.

**Files:**
- Add: `app/release_checks.py`
- Add: `app/runtime_config.py`
- Modify: `app/__init__.py`
- Modify: `run.py`

**Delivered:**

- shared readiness snapshot builder
- CLI command `check-release`
- `/health/ready` endpoint
- config constants extracted for reuse

---

### Task 2: Integrate readiness checks into admin status

**Objective:** Surface launch blockers directly inside the existing admin workflow.

**Files:**
- Modify: `app/routes.py`
- Modify: `app/templates/admin_status.html`
- Modify: `app/static/style.css`

**Delivered:**

- status page section for launch readiness
- blocking and warning issue lists
- per-check status badges

---

### Task 3: Add regression coverage

**Objective:** Lock down readiness behavior before the final release pass.

**Files:**
- Add: `tests/test_release_readiness.py`

**Coverage added:**

- `/health/ready` before and after secure bootstrap
- `check-release` CLI failure and success cases
- admin status readiness rendering

---

### Verification

Run:

```bash
python -m pytest tests/test_release_readiness.py tests/test_app_config.py -q
python -m pytest tests -q
```

Expected: PASS
