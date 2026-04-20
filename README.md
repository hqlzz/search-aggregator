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

当前处于 **来源筛选已交付，下一步继续推进标签/分类筛选、排序与摘要/片段展示，并补强导入校验**。

- 前台 `/search` 已支持来源筛选：搜索结果页会渲染“按来源筛选”下拉框、保留已选来源，并在筛选生效时展示“当前筛选来源”摘要
- 首页统一搜索入口现已同步支持来源筛选，下拉选项来自当前启用且存在公开条目的来源
- `/search` 对非法 `source` 参数已显式安全降级：未知来源 slug 会退回“全部来源”，不会错误收窄结果
- 后台现已新增轻量登录：`/admin`、`/admin/import`、`/admin/status`、`/admin/items/<slug>/edit`、`/admin/items/<slug>/publish`、`/admin/sources/<slug>/edit`、`/admin/logout` 默认要求管理员会话
- 登录使用 `app.config['ADMIN_PASSWORD']`，并提供 `/admin/login` 与 `/admin/logout`
- 后台导入、编辑、发布、登出 POST 表单已增加基于 session 的基础 CSRF token 校验
- 后台导入、草稿编辑、草稿发布与来源编辑成功流已改为 PRG（POST/Redirect/GET）并通过 flash 消息展示结果
- 后台 `/admin/status` 可展示数据库初始化状态、FTS 就绪情况、来源总数、启用来源数、公开/草稿条目数与最近更新时间，并在数据库未初始化时安全降级为 0 值快照
- 后台现已支持来源编辑最小闭环，管理员可以修改来源名称、slug、类型、地址、启用状态与备注，并在失败时保留提交值、保持明确 400/404/503 语义
- 当前来源筛选相关回归、数据库测试与全量测试均已通过
- 当前每小时整点任务 `search-aggregator-hourly-dev` 仍为 active，下一次运行时间为 `2026-04-20T17:00:00+08:00`
- 下一轮重点转向：继续搜索增强（标签/分类筛选优先，其后补排序与摘要/片段），并继续补强后台导入校验

## 启动方式（计划）

```bash
cd /root/search-aggregator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## 开发原则

- 稳定性优先
- 小步迭代
- 每轮都落地可验证改动
- 每轮都更新项目状态文件
- 每小时整点推进一轮，直到项目真正完成
