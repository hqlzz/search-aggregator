# 后台 PRG + 轻量鉴权 + 基础 CSRF 实现计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 让后台导入与草稿发布具备最小可上线安全边界：未登录无法访问后台，POST 操作具备基础 CSRF 校验，并把导入/发布流程收敛为 PRG，减少刷新重复提交。

**Architecture:** 采用 Flask 内建 session 做轻量登录态，不引入重型鉴权依赖；新增一个简单后台登录页，使用配置中的管理口令完成登录。CSRF 采用 session 中持久 token + 隐藏表单字段校验。导入与发布 POST 成功后 redirect 回 GET 页，通过 flash 消息显示结果，失败仍保留明确状态码与错误语义。

**Tech Stack:** Python 3.12, Flask, SQLite, Jinja2, pytest

---

## 范围与约束
- 仅修改 `/root/search-aggregator` 内文件
- 不引入 Flask-Login / WTForms 之类额外依赖
- 保持现有失败语义：缺失条目 404、非 draft 409、数据库未初始化 503
- 优先完成最短上线链路，不扩展角色系统或用户模型
- 该项目当前不是 git 仓库，跳过 commit 步骤

---

### Task 1: 搭后台 session 鉴权基础设施

**Objective:** 为后台页面建立统一的登录态检查与最小登录/登出入口。

**Files:**
- Modify: `app/__init__.py`
- Modify: `app/routes.py`
- Create: `app/templates/admin_login.html`
- Test: `tests/test_db.py`

**Step 1: Write failing tests**

在 `tests/test_db.py` 增加以下测试：

```python
def test_admin_requires_login_redirects_to_login_page(client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = client.get('/admin')

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/login?next=%2Fadmin')


def test_admin_login_page_renders_form(client):
    response = client.get('/admin/login')

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert '后台登录' in html
    assert '管理口令' in html
```

**Step 2: Run tests to verify failure**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_requires_login_redirects_to_login_page tests/test_db.py::test_admin_login_page_renders_form -q
```
Expected: FAIL — 当前 `/admin` 仍返回 200，且没有 `/admin/login`。

**Step 3: Write minimal implementation**

- 在 `app/__init__.py` 中新增配置项：
  - `ADMIN_PASSWORD='change-me'`
- 在 `app/routes.py` 中新增：
  - `is_admin_authenticated()`
  - `require_admin()` 或等价 helper
  - `GET/POST /admin/login`
  - `POST /admin/logout`
- `GET /admin` 与 `GET/POST /admin/import`、`POST /admin/items/<slug>/publish` 改为先检查登录态
- 创建 `app/templates/admin_login.html`，包含口令输入框与登录按钮

实现约束：
- 未登录访问后台页或后台 POST 路由，统一重定向到 `/admin/login?next=原路径`
- 登录成功后跳转到 `next` 或 `/admin`
- 登录失败返回 401，并在页面展示 “口令错误”
- session 内使用例如 `session['is_admin_authenticated'] = True`

**Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_requires_login_redirects_to_login_page tests/test_db.py::test_admin_login_page_renders_form -q
```
Expected: PASS

---

### Task 2: 为后台操作补登录成功流与会话测试

**Objective:** 覆盖登录成功、失败和登出行为，确保后续受保护路由可在测试里访问。

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_db.py`

**Step 1: Write failing tests**

新增测试与 fixture：

```python
@pytest.fixture
def admin_client(app, client):
    app.config['ADMIN_PASSWORD'] = 'test-admin-password'
    response = client.post('/admin/login', data={'password': 'test-admin-password'})
    assert response.status_code == 302
    return client


def test_admin_login_rejects_invalid_password(app, client):
    app.config['ADMIN_PASSWORD'] = 'test-admin-password'

    response = client.post('/admin/login', data={'password': 'wrong-password'})

    assert response.status_code == 401
    assert '口令错误' in response.get_data(as_text=True)


def test_admin_logout_clears_session(app, admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.post('/admin/logout')
    assert response.status_code == 302

    protected_response = admin_client.get('/admin')
    assert protected_response.status_code == 302
    assert '/admin/login' in protected_response.headers['Location']
```

**Step 2: Run tests to verify failure**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_login_rejects_invalid_password tests/test_db.py::test_admin_logout_clears_session -q
```
Expected: FAIL

**Step 3: Write minimal implementation**

- 在 `tests/conftest.py` 增加 `admin_client` fixture
- 完成登录失败与登出逻辑
- 确保测试可通过设置 `app.config['ADMIN_PASSWORD']`

**Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_login_rejects_invalid_password tests/test_db.py::test_admin_logout_clears_session -q
```
Expected: PASS

---

### Task 3: 为后台表单加入基础 CSRF token

**Objective:** 为登录后的后台 POST 表单建立 session token 校验，阻断跨站伪造请求。

**Files:**
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Modify: `app/templates/admin_import.html`
- Modify: `app/templates/admin_login.html`
- Test: `tests/test_db.py`

**Step 1: Write failing tests**

新增测试：

```python
def test_admin_import_post_rejects_missing_csrf_token(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    response = admin_client.post(
        '/admin/import',
        data={
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '无 csrf 草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/no-csrf',
        },
    )

    assert response.status_code == 400
    assert '请求已失效，请刷新页面后重试' in response.get_data(as_text=True)


def test_admin_page_renders_csrf_token_in_publish_form(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': extract_csrf_token(admin_client.get('/admin/import').get_data(as_text=True)),
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '带 token 的草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/with-csrf',
        },
    )

    response = admin_client.get('/admin')
    html = response.get_data(as_text=True)
    assert 'name="csrf_token"' in html
```

必要时增加测试辅助函数 `extract_csrf_token(html)`，用正则从隐藏字段中提取 token。

**Step 2: Run tests to verify failure**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_rejects_missing_csrf_token tests/test_db.py::test_admin_page_renders_csrf_token_in_publish_form -q
```
Expected: FAIL

**Step 3: Write minimal implementation**

- 在 `app/routes.py` 新增：
  - `get_csrf_token()`：若 session 无 token 则生成并保存
  - `validate_csrf()`：校验 `request.form['csrf_token']`
- 受保护 POST 路由在业务前先校验 CSRF：
  - `/admin/import`
  - `/admin/items/<slug>/publish`
  - `/admin/logout`
- 模板中所有后台 POST 表单加入：

```html
<input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

- 登录表单先不强制 CSRF（避免首次会话卡住），但可以渲染 token 以便后续一致

失败语义：
- token 缺失或错误返回 400
- 页面展示统一错误文案：`请求已失效，请刷新页面后重试`

**Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_rejects_missing_csrf_token tests/test_db.py::test_admin_page_renders_csrf_token_in_publish_form -q
```
Expected: PASS

---

### Task 4: 把导入与发布改成 PRG

**Objective:** 消除后台成功 POST 刷新重复提交风险，成功后统一 redirect 到 GET 页面并展示 flash 消息。

**Files:**
- Modify: `app/routes.py`
- Modify: `app/templates/admin.html`
- Modify: `app/templates/admin_import.html`
- Test: `tests/test_db.py`

**Step 1: Write failing tests**

新增测试：

```python
def test_admin_import_post_redirects_after_success(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    form_page = admin_client.get('/admin/import')
    csrf_token = extract_csrf_token(form_page.get_data(as_text=True))

    response = admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': 'PRG 草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/prg-draft',
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin/import')

    landing = admin_client.get('/admin/import')
    assert '已创建草稿条目' in landing.get_data(as_text=True)
    assert 'PRG 草稿' in landing.get_data(as_text=True)


def test_admin_publish_post_redirects_after_success(admin_client, runner):
    init_result = runner.invoke(args=['init-db'])
    assert init_result.exit_code == 0

    import_page = admin_client.get('/admin/import')
    csrf_token = extract_csrf_token(import_page.get_data(as_text=True))
    admin_client.post(
        '/admin/import',
        data={
            'csrf_token': csrf_token,
            'source_slug': 'example-source-a',
            'category_slug': 'example-category',
            'title': '待 PRG 发布草稿',
            'summary': 'summary',
            'content': 'content',
            'external_url': 'https://example.com/prg-publish',
        },
    )

    admin_page = admin_client.get('/admin')
    publish_token = extract_csrf_token(admin_page.get_data(as_text=True))
    response = admin_client.post(
        '/admin/items/prg-publish-draft/publish',
        data={'csrf_token': publish_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin')

    landing = admin_client.get('/admin')
    html = landing.get_data(as_text=True)
    assert '草稿已发布' in html
    assert 'prg-publish-draft' in html
```

**Step 2: Run tests to verify failure**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_redirects_after_success tests/test_db.py::test_admin_publish_post_redirects_after_success -q
```
Expected: FAIL — 当前成功 POST 仍直接渲染 200。

**Step 3: Write minimal implementation**

- 成功创建草稿后：
  - `flash({...}, 'admin_import_success')` 或等价简单 flash 结构
  - `redirect(url_for('main.admin_import'))`
- 成功发布后：
  - `flash({...}, 'admin_publish_success')`
  - `redirect(url_for('main.admin'))`
- GET 页从 flash 中读取并展示成功信息
- 保留失败分支现有状态码与错误展示；失败时不 redirect

**Step 4: Run tests to verify pass**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py::test_admin_import_post_redirects_after_success tests/test_db.py::test_admin_publish_post_redirects_after_success -q
```
Expected: PASS

---

### Task 5: 回归现有后台行为并更新文档

**Objective:** 确保新安全边界和 PRG 没破坏已有功能，并同步项目状态。

**Files:**
- Modify: `README.md`
- Modify: `docs/project-status.md`
- Modify: `docs/todo.md`
- Modify: `docs/progress-log.md`

**Step 1: Run targeted regression**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_db.py -q
```
Expected: 所有后台相关测试通过。

**Step 2: Run full regression**

Run:
```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/ -q
```
Expected: 全量通过。

**Step 3: Update docs**

文档需反映：
- 后台已新增轻量登录保护
- 后台 POST 已加基础 CSRF
- 导入/发布成功流已改为 PRG
- 下一轮优先级转向：状态展示、来源/条目编辑、搜索增强、导入聚合

**Step 4: Verify cron continuity**

Run:
```bash
hermes cron list
```
Expected: `search-aggregator-hourly-dev` 仍处于 active / scheduled。

---

## 完成标准
- `/admin`、`/admin/import`、`/admin/items/<slug>/publish` 默认不再裸露给未登录用户
- 后台 POST 路由具备基础 CSRF 校验
- 成功导入与成功发布改为 PRG
- 现有失败语义与公开可见性不回退
- 测试通过，状态文档更新完成
