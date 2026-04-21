# Final Launch Smoke Test Implementation Plan

**Goal:** Close the first-release loop by turning the final trial-run checklist into an executable smoke test instead of leaving it as a manual process.

**Architecture:** Reuse the existing app factory, admin login flow, and readiness endpoint. The smoke test runs against a Flask test client inside the configured app and checks the real request path for health, homepage, admin login, admin dashboard, readiness endpoint, local search, and item detail pages. Unlike basic route checks, this command uses launch-oriented success criteria, so `/health/ready` must actually report ready.

**Tech Stack:** Python 3.12, Flask, pytest, Click

---

### Task 1: Add smoke-test service and CLI command

**Objective:** Make final trial-run validation executable from the command line.

**Files:**
- Modify: `app/release_checks.py`

**Delivered:**

- reusable smoke snapshot builder
- `flask smoke-test` CLI command
- route-level checks for health, homepage, admin login, admin dashboard, readiness, search, and detail pages

---

### Task 2: Update operator-facing docs

**Objective:** Make the release flow explicit and repeatable.

**Files:**
- Modify: `README.md`

**Delivered:**

- smoke-test command added to docs
- recommended launch sequence added to README

---

### Task 3: Add regression coverage

**Objective:** Lock down the final release command before handoff.

**Files:**
- Add: `tests/test_smoke_test.py`

**Coverage added:**

- smoke test fails before the app is launch-ready
- smoke test passes after secure bootstrap and database initialization

---

### Verification

Run:

```bash
python -m pytest tests/test_smoke_test.py tests/test_release_readiness.py -q
python -m pytest tests -q
```

Expected: PASS
