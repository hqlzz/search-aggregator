# 后台来源编辑入口 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 为后台管理页补上来源编辑最小闭环，让管理员可以打开来源编辑页，修改名称、类型、基础 URL、备注与启用状态，并安全保存。

**Architecture:** 延续现有 Flask + SQLite + Jinja2 轻量结构，复用后台 session 鉴权、CSRF 与 PRG 模式。数据层新增“读取来源编辑数据”和“更新来源”函数；路由层新增 `/admin/sources/<slug>/edit` GET/POST；模板层新增来源编辑页，并在后台来源列表中加入编辑入口。

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

### Task 1: 先用测试定义后台来源编辑最小行为

**Objective:** 通过失败测试锁定来源编辑入口、编辑页回填、保存 PRG、缺失来源 404、缺失 CSRF 400 等关键行为。

**Files:**
- Modify: `tests/test_db.py`
- Verify: `app/routes.py`, `app/db.py`, `app/templates/admin.html`

**Step 1: Write failing test**

覆盖以下行为：
- `/admin` 的来源列表为每个来源渲染“编辑”入口
- `/admin/sources/example-source-a/edit` 可以打开并回填当前来源字段
- POST 保存后走 PRG，并刷新展示“来源已保存”
- 不存在的来源 slug 返回 404
- 缺失 CSRF token 返回 400 且不改库

**Step 2: Run test to verify failure**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -k admin_source_edit -q`
Expected: FAIL — 当前没有来源编辑路由、模板与更新逻辑。

**Step 3: Write minimal implementation**

先接通后台来源列表中的编辑链接，并加上来源编辑页 GET/POST 骨架。

**Step 4: Run test to verify pass**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -k admin_source_edit -q`
Expected: PASS

### Task 2: 实现来源读取与更新数据层

**Objective:** 在数据层增加来源编辑读取与更新能力，并对名称、类型、基础 URL 做最小校验。

**Files:**
- Modify: `app/db.py`
- Modify: `tests/test_db.py`

**Step 1: Write failing test**

覆盖以下行为：
- `get_admin_edit_source(slug)` 返回可供表单回填的字段
- `update_admin_source(...)` 能更新 name/source_type/base_url/notes/enabled
- 缺失来源返回 404
- 空名称 / 空类型 / 非法 URL 返回 400

**Step 2: Run test to verify failure**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -k "edit_source or update_admin_source" -q`
Expected: FAIL — 相关 helper 尚不存在。

**Step 3: Write minimal implementation**

在 `app/db.py` 增加来源读取、来源更新和最小校验逻辑，更新时间戳写入 `updated_at`。

**Step 4: Run test to verify pass**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -k "edit_source or update_admin_source" -q`
Expected: PASS

### Task 3: 完成来源编辑页面与回归验证

**Objective:** 补齐后台来源编辑页模板、错误回填与全量回归，形成闭环。

**Files:**
- Create: `app/templates/admin_edit_source.html`
- Modify: `app/templates/admin.html`
- Modify: `app/routes.py`
- Modify: `tests/test_db.py`
- Modify: `docs/project-status.md`
- Modify: `docs/todo.md`
- Modify: `docs/progress-log.md`

**Step 1: Write failing test**

补以下行为：
- 校验失败时保留提交值
- 编辑页显示来源 slug、启用状态、备注等字段
- `/admin` 页面显示来源编辑入口

**Step 2: Run test to verify failure**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -k admin_source_edit -q`
Expected: FAIL

**Step 3: Write minimal implementation**

完成模板、错误展示、PRG 成功消息与后台页来源编辑链接。

**Step 4: Run test to verify pass**

Run: `cd /root/search-aggregator && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -k admin_source_edit -q && PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -q && PYTHONPATH=. ./.venv/bin/python -m pytest tests/ -q`
Expected: PASS
