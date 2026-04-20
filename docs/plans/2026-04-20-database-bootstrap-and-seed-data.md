# Database Bootstrap and Seed Data Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为搜索聚合站接入可重复执行的 SQLite 初始化与种子数据装载流程，并把数据库状态展示到页面中。

**Architecture:** 新增 `app/db.py` 负责连接、schema 初始化、种子数据写入和简单统计查询；在 app factory 中注册数据库生命周期与 CLI 初始化命令。首页和后台页只消费轻量查询结果，不直接拼 SQL，保持后续搜索页与管理页可继续复用同一数据层。

**Tech Stack:** Python 3.12, Flask, SQLite, pytest

---

### Task 1: 建立数据库初始化测试骨架

**Objective:** 先用测试定义数据库初始化、种子写入与页面显示的目标行为。

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_db.py`
- Modify: `requirements.txt`

**Step 1: Write failing test**

```python
from app import create_app
from app.db import get_db


def test_init_db_command_creates_seeded_content(runner, app):
    result = runner.invoke(args=["init-db"])

    assert result.exit_code == 0
    assert "Initialized the database." in result.output

    with app.app_context():
        db = get_db()
        source_count = db.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        item_count = db.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    assert source_count >= 2
    assert item_count >= 3
```

```python
def test_home_and_admin_pages_show_database_stats(client):
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "已接入" in html
    assert "示例条目" in html

    admin_response = client.get("/admin")
    admin_html = admin_response.get_data(as_text=True)

    assert admin_response.status_code == 200
    assert "数据库状态" in admin_html
```

**Step 2: Run test to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_db.py -v`
Expected: FAIL — 缺少 `app.db` 模块、`init-db` 命令或页面文案。

**Step 3: Write minimal implementation**

先只实现能让测试通过所需的最小数据库模块、fixture 和模板动态区块。

**Step 4: Run test to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_db.py -v`
Expected: PASS

**Step 5: Commit**

当前目录尚未初始化 git 仓库；若后续补齐 git，再执行提交。

---

### Task 2: 接入 SQLite 初始化、种子数据与统计查询

**Objective:** 让应用真实创建 SQLite 文件、执行 schema、填充示例数据，并提供复用查询函数。

**Files:**
- Create: `app/db.py`
- Modify: `app/__init__.py`
- Modify: `app/routes.py`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_get_homepage_stats_returns_counts(app):
    from app.db import get_homepage_stats

    with app.app_context():
        stats = get_homepage_stats()

    assert stats["source_count"] >= 2
    assert stats["item_count"] >= 3
    assert len(stats["recent_items"]) >= 1
```

**Step 2: Run test to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_db.py::test_get_homepage_stats_returns_counts -v`
Expected: FAIL — 查询函数不存在或未返回预期结构。

**Step 3: Write minimal implementation**

```python
def get_homepage_stats() -> dict:
    db = get_db()
    return {
        "source_count": db.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
        "item_count": db.execute("SELECT COUNT(*) FROM items").fetchone()[0],
        "recent_items": db.execute(
            "SELECT title, slug FROM items ORDER BY COALESCE(published_at, created_at) DESC LIMIT 5"
        ).fetchall(),
    }
```

**Step 4: Run test to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_db.py::test_get_homepage_stats_returns_counts -v`
Expected: PASS

**Step 5: Commit**

当前目录尚未初始化 git 仓库；若后续补齐 git，再执行提交。

---

### Task 3: 页面展示数据库状态并完成回归验证

**Objective:** 把数据库接入结果显示到首页和后台页，便于后续继续做搜索结果页与管理页。

**Files:**
- Modify: `app/templates/index.html`
- Modify: `app/templates/admin.html`
- Modify: `app/static/style.css`
- Test: `tests/test_db.py`

**Step 1: Write failing test**

```python
def test_homepage_lists_recent_seed_items(client):
    response = client.get("/")
    html = response.get_data(as_text=True)

    assert "Flask 官方文档" in html
    assert "SQLite FTS5 指南" in html
```

**Step 2: Run test to verify failure**

Run: `source .venv/bin/activate && pytest tests/test_db.py::test_homepage_lists_recent_seed_items -v`
Expected: FAIL — 页面尚未渲染种子条目。

**Step 3: Write minimal implementation**

在模板中渲染统计卡片与最近条目列表，并保持结构轻量。

**Step 4: Run test to verify pass**

Run: `source .venv/bin/activate && pytest tests/test_db.py -v && pytest tests/ -q`
Expected: PASS

**Step 5: Commit**

当前目录尚未初始化 git 仓库；若后续补齐 git，再执行提交。
