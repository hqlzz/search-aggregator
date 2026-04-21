# 搜索聚合站（Search Aggregator）

一个面向个人或小团队的轻量搜索聚合站，使用 Python + Flask + SQLite 构建，强调稳定、低负载、可运行、可验证、可持续迭代。

## 项目目标

本项目要逐步实现一个真正可用的前后端网站，而不是一次性的脚本或玩具页面。目标能力包括：

- 多数据源接入
- 统一搜索入口
- 搜索结果展示
- 来源/标签/分类筛选
- 数据源管理后台
- 条目详情页
- SQLite 存储与全文检索
- 可扩展排序、摘要、聚合规则、导入规则

## 当前技术选型

- Python 3.12
- Flask（轻量 Web 框架）
- SQLite（含 FTS5 全文检索）
- Jinja2 模板
- 原生 CSS（先不引入重型前端框架）

## 目录结构

- `app/`：应用代码
- `app/templates/`：前端模板
- `app/static/`：静态资源
- `docs/`：规划与进展文档
- `tests/`：测试
- `instance/`：SQLite 数据库与运行期文件

## 当前阶段

当前处于 **来源/分类/标签筛选、排序、摘要/片段展示、基础导入校验、后台来源管理闭环、双聚合源搜索通路、RSS 半自动/批量导入、部署配置、上线前自检与最终冒烟检查已交付，已具备第一版试运行条件**。

- 前台 `/search` 已支持来源、分类、标签三类筛选与排序方式选择
- 首页统一搜索入口已同步支持来源、分类、标签三类筛选与排序方式选择
- `/search` 对非法 `source`、`category`、`tag`、`sort` 参数已显式安全降级
- 搜索结果页现在会优先展示条目摘要；当摘要为空时，会回退展示围绕命中词截取的正文片段
- 聚合搜索模式现已支持通过已启用的 `wikipedia`、`hackernews` 类型来源接入真实外部结果；未配置聚合源时，仍会安全回退为占位提示
- 后台已具备登录、手动导入、草稿编辑、草稿发布、来源编辑、状态页
- 后台现已支持直接新增来源，`manual`、`rss`、`wikipedia` 与 `hackernews` 类型可在表单中直接配置，聚合源留空地址时会自动补全默认站点
- `rss` 类型来源现已支持在后台一键抓取最新订阅内容，并自动生成去重后的草稿条目
- 后台现已支持批量抓取所有已启用 RSS 来源，CLI 也可通过 `flask sync-rss` 触发同一套同步流程
- 后台写操作已具备 session 级别基础 CSRF 校验
- 导入、编辑、发布流程已采用 PRG（POST/Redirect/GET）
- 后台导入在数据库未初始化时会以 503 明确失败，不再因缺表直接抛出 500
- 后台导入与草稿编辑现在要求摘要、正文、外链三者至少填写一项，避免生成只有标题的空壳条目
- 后台 `/admin/status` 现已包含上线前检查，可直接提示默认口令、未初始化数据库、无公开内容等阻塞项
- 应用现已支持通过环境变量或 `instance/config.py` 加载部署配置，并提供 `wsgi.py` 入口
- 应用现已支持 `flask check-release` 和 `/health/ready` 两种上线前自检入口
- 应用现已支持 `flask smoke-test` 做最终试运行冒烟检查
- 当前新增搜索摘要/片段、导入校验、来源管理、双聚合源搜索、RSS 导入/批量同步、部署配置、上线前自检与冒烟检查回归测试已通过

## 本地启动

```bash
cd /root/search-aggregator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp instance/config.example.py instance/config.py
python run.py
```

首次启动前建议先初始化数据库：

```bash
flask --app run.py init-db
```

如需同步已启用 RSS 来源：

```bash
flask --app run.py sync-rss
```

如需执行上线前检查：

```bash
flask --app run.py check-release
```

如需执行最终冒烟检查：

```bash
flask --app run.py smoke-test
```

## 部署配置

应用支持两种配置方式：

- `instance/config.py`
- 环境变量（优先级高于默认值）

建议至少配置以下项目：

- `SECRET_KEY`
- `ADMIN_PASSWORD`
- `DATABASE`（如需自定义 SQLite 位置）
- `TRUST_PROXY=True`（部署在 Nginx / Caddy 等反向代理后时）
- `PREFERRED_URL_SCHEME="https"`（生产环境建议开启）

对应环境变量如下：

- `SEARCH_AGGREGATOR_SECRET_KEY`
- `SEARCH_AGGREGATOR_ADMIN_PASSWORD`
- `SEARCH_AGGREGATOR_DATABASE`
- `SEARCH_AGGREGATOR_TRUST_PROXY`
- `SEARCH_AGGREGATOR_PREFERRED_URL_SCHEME`
- `SEARCH_AGGREGATOR_HOST`
- `SEARCH_AGGREGATOR_PORT`
- `SEARCH_AGGREGATOR_DEBUG`

## 生产运行

默认运行入口：

```bash
python run.py
```

WSGI 入口：

```bash
wsgi:app
```

如果使用 Gunicorn，可直接指向：

```bash
gunicorn wsgi:app
```

就绪检查接口：

```bash
GET /health/ready
```

## 推荐上线顺序

```bash
cp instance/config.example.py instance/config.py
flask --app run.py init-db
flask --app run.py check-release
flask --app run.py smoke-test
python run.py
```

## 开发原则

- 稳定性优先
- 小步迭代
- 每轮都落地可验证改动
- 每轮都更新项目状态文件
- 每小时整点推进一轮，直到项目真正完成
