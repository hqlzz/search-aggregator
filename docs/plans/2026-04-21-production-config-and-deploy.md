# Production Config And Deploy Readiness Plan

**Goal:** Close the remaining deployment gaps for the first release by making configuration, startup, and server integration explicit and repeatable.

**Architecture:** Keep the app lightweight and SQLite-based, but formalize runtime configuration through `instance/config.py` and environment variables. Avoid adding new heavy runtime dependencies in this round; instead, provide a stable WSGI entry point and deployment-ready configuration hooks so the app can be run behind an external process manager or reverse proxy.

**Tech Stack:** Python 3.12, Flask, SQLite, pytest, Werkzeug

---

### Task 1: Improve runtime configuration loading

**Objective:** Make the app configurable in production without editing source code.

**Files:**
- Modify: `app/__init__.py`
- Modify: `run.py`

**Delivered:**

- environment-variable config loading
- instance directory auto-creation
- optional reverse-proxy trust via `ProxyFix`
- runtime host/port/debug loading from environment

---

### Task 2: Add deployment artifacts

**Objective:** Give operators a clear configuration template and server entry point.

**Files:**
- Add: `instance/.gitignore`
- Add: `instance/config.example.py`
- Add: `wsgi.py`

**Delivered:**

- tracked config example without committing live instance files
- explicit WSGI entry point for production servers

---

### Task 3: Document deployment path

**Objective:** Make first-release setup reproducible for local trial deploys.

**Files:**
- Modify: `README.md`

**Delivered:**

- local startup instructions
- config explanation
- environment variable reference
- production entry point notes

---

### Task 4: Add regression coverage

**Objective:** Lock down config precedence and startup behavior before final release hardening.

**Files:**
- Add: `tests/test_app_config.py`

**Coverage added:**

- loading config from instance file plus environment variables
- test config overriding environment values
- run settings parsing from environment variables

---

### Verification

Run:

```bash
python -m pytest tests/test_app_config.py -q
python -m pytest tests -q
```

Expected: PASS
