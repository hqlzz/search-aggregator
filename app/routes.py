import secrets
from functools import wraps
from urllib.parse import urlencode, urlparse

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    get_flashed_messages,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .aggregate import (
    SUPPORTED_AGGREGATE_SOURCE_TYPES,
    search_aggregate_items,
)
from .db import (
    ManualImportValidationError,
    PublishValidationError,
    create_source,
    create_manual_import_item,
    get_admin_dashboard_data,
    get_admin_edit_item,
    get_admin_edit_source,
    get_enabled_aggregate_sources,
    get_admin_import_options,
    get_source_type_options,
    get_admin_status_snapshot,
    get_homepage_data,
    get_item_detail,
    get_search_category_options,
    get_search_source_options,
    get_search_tag_options,
    normalize_search_query,
    normalize_search_sort,
    publish_item,
    search_items,
    update_draft_item,
    update_source,
)
from .feed_import import sync_enabled_rss_sources, sync_rss_source
from .release_checks import get_release_readiness_snapshot

bp = Blueprint("main", __name__)

CSRF_ERROR_MESSAGE = "请求已失效，请刷新页面后重试"


def is_admin_authenticated():
    return session.get("is_admin_authenticated") is True


def build_login_redirect_response():
    next_value = request.full_path if request.query_string else request.path
    if next_value.endswith("?"):
        next_value = next_value[:-1]
    return redirect(f"{url_for('main.admin_login')}?{urlencode({'next': next_value})}")


def require_admin(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not is_admin_authenticated():
            return build_login_redirect_response()
        return view(*args, **kwargs)

    return wrapped_view


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf():
    token = request.form.get("csrf_token", "")
    return bool(token) and token == session.get("csrf_token")


def sanitize_next_url(next_value):
    if not next_value:
        return url_for("main.admin")

    parsed = urlparse(next_value)
    if parsed.scheme or parsed.netloc or not next_value.startswith("/"):
        return url_for("main.admin")
    return next_value


def build_empty_source_form_data():
    return {
        "name": "",
        "slug": "",
        "source_type": "manual",
        "base_url": "",
        "enabled": False,
        "notes": "",
    }


def build_source_form_data(source):
    if not source:
        return build_empty_source_form_data()
    return {
        "name": source["name"] or "",
        "slug": source["slug"] or "",
        "source_type": source["source_type"] or "",
        "base_url": source["base_url"] or "",
        "enabled": bool(source["enabled"]),
        "notes": source["notes"] or "",
    }


@bp.get("/")
def index():
    q = request.args.get("q", "").strip()
    mode = request.args.get("mode", "local").strip()
    if mode not in {"local", "aggregate"}:
        mode = "local"
    sort = normalize_search_sort(request.args.get("sort", ""))
    homepage_data = get_homepage_data()
    source_options = get_search_source_options()
    category_options = get_search_category_options()
    tag_options = get_search_tag_options()
    return render_template(
        "index.html",
        query=q,
        homepage=homepage_data,
        source_options=source_options,
        category_options=category_options,
        tag_options=tag_options,
        selected_source_slug="",
        selected_category_slug="",
        selected_tag_slug="",
        selected_sort=sort,
        search_mode=mode,
    )


@bp.get("/search")
def search():
    q = request.args.get("q", "")
    source_slug = request.args.get("source", "").strip()
    category_slug = request.args.get("category", "").strip()
    tag_slug = request.args.get("tag", "").strip()
    mode = request.args.get("mode", "local").strip()
    sort = normalize_search_sort(request.args.get("sort", ""))
    if mode not in {"local", "aggregate"}:
        mode = "local"
    normalized_query = normalize_search_query(q)
    source_options = get_search_source_options()
    source_lookup = {option["slug"]: option for option in source_options}
    selected_source = source_lookup.get(source_slug)
    effective_source_slug = selected_source["slug"] if selected_source else ""
    category_options = get_search_category_options()
    category_lookup = {option["slug"]: option for option in category_options}
    selected_category = category_lookup.get(category_slug)
    effective_category_slug = selected_category["slug"] if selected_category else ""
    tag_options = get_search_tag_options()
    tag_lookup = {option["slug"]: option for option in tag_options}
    selected_tag = tag_lookup.get(tag_slug)
    effective_tag_slug = selected_tag["slug"] if selected_tag else ""
    if mode == "aggregate":
        aggregate_sources = get_enabled_aggregate_sources(SUPPORTED_AGGREGATE_SOURCE_TYPES)
        if not aggregate_sources:
            results = []
            aggregate_notice = "聚合搜索功能开发中，后续将支持外部搜索源接入。当前尚未配置可用聚合源。"
        elif not normalized_query:
            results = []
            aggregate_notice = None
        else:
            results, aggregate_errors = search_aggregate_items(normalized_query, aggregate_sources)
            if results and aggregate_errors:
                aggregate_notice = f"部分聚合源暂时不可用，已展示其余 {len(results)} 条结果。"
            elif aggregate_errors:
                results = []
                aggregate_notice = "聚合搜索暂时不可用，请稍后再试。"
            elif not results:
                aggregate_notice = f"已检索 {len(aggregate_sources)} 个聚合源，暂无匹配结果。"
            else:
                aggregate_notice = f"已检索 {len(aggregate_sources)} 个聚合源。"
    else:
        results = search_items(
            normalized_query,
            source_slug=effective_source_slug,
            category_slug=effective_category_slug,
            tag_slug=effective_tag_slug,
            sort=sort,
        )
        aggregate_notice = None
    return render_template(
        "search_results.html",
        query=normalized_query,
        results=results,
        result_count=len(results),
        source_options=source_options,
        selected_source_slug=effective_source_slug,
        selected_source=selected_source,
        category_options=category_options,
        selected_category_slug=effective_category_slug,
        selected_category=selected_category,
        tag_options=tag_options,
        selected_tag_slug=effective_tag_slug,
        selected_tag=selected_tag,
        selected_sort=sort,
        search_mode=mode,
        aggregate_notice=aggregate_notice,
    )


@bp.get("/items/<slug>")
def item_detail(slug):
    item = get_item_detail(slug)
    if item is None:
        abort(404)
    return render_template("item_detail.html", item=item)


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    next_value = request.args.get("next", "")

    if request.method == "POST":
        password = request.form.get("password", "")
        next_value = request.form.get("next", next_value)
        if password == current_app.config["ADMIN_PASSWORD"]:
            session["is_admin_authenticated"] = True
            get_csrf_token()
            return redirect(sanitize_next_url(next_value))
        error = "口令错误"
        return (
            render_template(
                "admin_login.html",
                error=error,
                next_url=sanitize_next_url(next_value),
                csrf_token=get_csrf_token(),
            ),
            401,
        )

    return render_template(
        "admin_login.html",
        error=error,
        next_url=sanitize_next_url(next_value),
        csrf_token=get_csrf_token(),
    )


@bp.post("/admin/logout")
@require_admin
def admin_logout():
    if not validate_csrf():
        return (
            render_template(
                "admin_login.html",
                error=CSRF_ERROR_MESSAGE,
                next_url=url_for("main.admin"),
                csrf_token=get_csrf_token(),
            ),
            400,
        )

    session.clear()
    return redirect(url_for("main.admin_login"))


@bp.get("/admin")
@require_admin
def admin():
    dashboard = get_admin_dashboard_data()
    publish_messages = get_flashed_messages(category_filter=["admin_publish_success"])
    publish_payload = publish_messages[-1] if publish_messages else None
    batch_sync_messages = get_flashed_messages(category_filter=["admin_source_sync_batch_result"])
    batch_sync_payload = batch_sync_messages[-1] if batch_sync_messages else None
    return render_template(
        "admin.html",
        dashboard=dashboard,
        stats=dashboard["stats"],
        published_item=publish_payload["item"] if publish_payload else None,
        publish_message=publish_payload["message"] if publish_payload else None,
        source_sync_batch_message=batch_sync_payload["message"] if batch_sync_payload else None,
        source_sync_batch_summary=batch_sync_payload["summary"] if batch_sync_payload else None,
        source_sync_batch_errors=batch_sync_payload["errors"] if batch_sync_payload else [],
        csrf_token=get_csrf_token(),
    )


@bp.get("/admin/status")
@require_admin
def admin_status():
    return render_template(
        "admin_status.html",
        status_snapshot=get_admin_status_snapshot(),
        release_snapshot=get_release_readiness_snapshot(),
    )


@bp.post("/admin/sources/sync")
@require_admin
def admin_sync_enabled_sources():
    dashboard = get_admin_dashboard_data()
    if not validate_csrf():
        return (
            render_template(
                "admin.html",
                dashboard=dashboard,
                stats=dashboard["stats"],
                published_item=None,
                publish_message=None,
                source_sync_batch_message=None,
                source_sync_batch_summary=None,
                source_sync_batch_errors=[CSRF_ERROR_MESSAGE],
                csrf_token=get_csrf_token(),
            ),
            400,
        )

    try:
        summary = sync_enabled_rss_sources()
    except ManualImportValidationError as exc:
        return (
            render_template(
                "admin.html",
                dashboard=dashboard,
                stats=dashboard["stats"],
                published_item=None,
                publish_message=None,
                source_sync_batch_message=None,
                source_sync_batch_summary=None,
                source_sync_batch_errors=exc.errors,
                csrf_token=get_csrf_token(),
            ),
            exc.status_code,
        )

    if summary["source_count"] == 0:
        message = "没有找到已启用的 RSS 来源。"
    else:
        message = (
            f"RSS 批量抓取完成：同步 {summary['source_count']} 个来源，"
            f"新增 {summary['created_count']} 条草稿，"
            f"跳过 {summary['skipped_count']} 条内容。"
        )
        if summary["failure_count"] > 0:
            message = f"{message} 其中 {summary['failure_count']} 个来源抓取失败。"

    flash(
        {
            "message": message,
            "summary": summary,
            "errors": summary["errors"],
        },
        "admin_source_sync_batch_result",
    )
    return redirect(url_for("main.admin"))


@bp.route("/admin/sources/new", methods=["GET", "POST"])
@require_admin
def admin_create_source():
    form_data = build_empty_source_form_data()
    errors = []
    status_code = 200

    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data.keys()}
        form_data["enabled"] = request.form.get("enabled") == "1"
        if not validate_csrf():
            errors = [CSRF_ERROR_MESSAGE]
            status_code = 400
        else:
            try:
                created_source = create_source(**form_data)
            except ManualImportValidationError as exc:
                errors = exc.errors
                status_code = exc.status_code
            else:
                flash({"message": "来源已创建", "source": created_source}, "admin_source_edit_success")
                return redirect(url_for("main.admin_edit_source", slug=created_source["slug"]))

    return (
        render_template(
            "admin_edit_source.html",
            source=None,
            form_data=form_data,
            errors=errors,
            save_message=None,
            saved_source=None,
            source_type_options=get_source_type_options(),
            form_mode="create",
            csrf_token=get_csrf_token(),
        ),
        status_code,
    )


@bp.route("/admin/sources/<slug>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit_source(slug):
    form_data = build_empty_source_form_data()
    errors = []
    sync_errors = []
    status_code = 200
    source = None

    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data.keys()}
        form_data["enabled"] = request.form.get("enabled") == "1"
        if not validate_csrf():
            errors = [CSRF_ERROR_MESSAGE]
            status_code = 400
        else:
            try:
                updated_source = update_source(
                    slug,
                    **form_data,
                )
            except ManualImportValidationError as exc:
                errors = exc.errors
                status_code = exc.status_code
            else:
                flash({"message": "来源已保存", "source": updated_source}, "admin_source_edit_success")
                return redirect(url_for("main.admin_edit_source", slug=updated_source["slug"]))
    else:
        try:
            source = get_admin_edit_source(slug)
        except ManualImportValidationError as exc:
            return (
                render_template(
                    "admin_edit_source.html",
                    source=None,
                    form_data={**build_empty_source_form_data(), "slug": slug},
                    errors=exc.errors,
                    save_message=None,
                    saved_source=None,
                    sync_message=None,
                    sync_summary=None,
                    sync_errors=[],
                    source_type_options=get_source_type_options(),
                    form_mode="edit",
                    csrf_token=get_csrf_token(),
                ),
                exc.status_code,
            )

        form_data = build_source_form_data(source)

    edit_messages = get_flashed_messages(category_filter=["admin_source_edit_success"])
    edit_payload = edit_messages[-1] if edit_messages else None
    sync_messages = get_flashed_messages(category_filter=["admin_source_sync_success"])
    sync_payload = sync_messages[-1] if sync_messages else None
    return (
        render_template(
            "admin_edit_source.html",
            source=source,
            form_data=form_data,
            errors=errors,
            save_message=edit_payload["message"] if edit_payload else None,
            saved_source=edit_payload["source"] if edit_payload else None,
            sync_message=sync_payload["message"] if sync_payload else None,
            sync_summary=sync_payload["summary"] if sync_payload else None,
            sync_errors=sync_errors,
            source_type_options=get_source_type_options(),
            form_mode="edit",
            csrf_token=get_csrf_token(),
        ),
        status_code,
    )


@bp.post("/admin/sources/<slug>/sync")
@require_admin
def admin_sync_source(slug):
    source = None
    form_data = {**build_empty_source_form_data(), "slug": slug}
    status_code = 200
    sync_errors = []

    try:
        source = get_admin_edit_source(slug)
    except ManualImportValidationError as exc:
        sync_errors = exc.errors
        status_code = exc.status_code
    else:
        form_data = build_source_form_data(source)

    if not sync_errors and not validate_csrf():
        sync_errors = [CSRF_ERROR_MESSAGE]
        status_code = 400
    elif not sync_errors:
        try:
            sync_summary = sync_rss_source(slug)
        except ManualImportValidationError as exc:
            sync_errors = exc.errors
            status_code = exc.status_code
        else:
            flash(
                {
                    "message": (
                        f"RSS 抓取完成：新增 {sync_summary['created_count']} 条草稿，"
                        f"跳过 {sync_summary['skipped_count']} 条重复内容。"
                    ),
                    "summary": sync_summary,
                },
                "admin_source_sync_success",
            )
            return redirect(url_for("main.admin_edit_source", slug=slug))

    return (
        render_template(
            "admin_edit_source.html",
            source=source,
            form_data=form_data,
            errors=[],
            save_message=None,
            saved_source=None,
            sync_message=None,
            sync_summary=None,
            sync_errors=sync_errors,
            source_type_options=get_source_type_options(),
            form_mode="edit",
            csrf_token=get_csrf_token(),
        ),
        status_code,
    )


@bp.post("/admin/items/<slug>/publish")
@require_admin
def admin_publish_item(slug):
    if not validate_csrf():
        dashboard = get_admin_dashboard_data()
        return (
            render_template(
                "admin.html",
                dashboard=dashboard,
                stats=dashboard["stats"],
                publish_errors=[CSRF_ERROR_MESSAGE],
                csrf_token=get_csrf_token(),
            ),
            400,
        )

    try:
        published_item = publish_item(slug)
    except PublishValidationError as exc:
        dashboard = get_admin_dashboard_data()
        return (
            render_template(
                "admin.html",
                dashboard=dashboard,
                stats=dashboard["stats"],
                publish_errors=exc.errors,
                csrf_token=get_csrf_token(),
            ),
            exc.status_code,
        )

    flash({"message": "草稿已发布", "item": published_item}, "admin_publish_success")
    return redirect(url_for("main.admin"))


@bp.route("/admin/items/<slug>/edit", methods=["GET", "POST"])
@require_admin
def admin_edit_item(slug):
    form_data = {
        "source_slug": "",
        "category_slug": "",
        "title": "",
        "summary": "",
        "content": "",
        "external_url": "",
    }
    errors = []
    status_code = 200
    item = None

    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data.keys()}
        if not validate_csrf():
            errors = [CSRF_ERROR_MESSAGE]
            status_code = 400
        else:
            try:
                updated_item = update_draft_item(slug, **form_data)
            except ManualImportValidationError as exc:
                errors = exc.errors
                status_code = exc.status_code
            else:
                flash({"message": "草稿已保存", "item": updated_item}, "admin_edit_success")
                return redirect(url_for("main.admin_edit_item", slug=slug))
    else:
        try:
            item = get_admin_edit_item(slug)
        except ManualImportValidationError as exc:
            import_options = get_admin_import_options()
            return (
                render_template(
                    "admin_edit_item.html",
                    item=None,
                    form_data=form_data,
                    import_options=import_options,
                    errors=exc.errors,
                    save_message=None,
                    saved_item=None,
                    csrf_token=get_csrf_token(),
                ),
                exc.status_code,
            )

        form_data = {
            "source_slug": item["source_slug"] or "",
            "category_slug": item["category_slug"] or "",
            "title": item["title"] or "",
            "summary": item["summary"] or "",
            "content": item["content"] or "",
            "external_url": item["external_url"] or "",
        }

    import_options = get_admin_import_options()
    success_messages = get_flashed_messages(category_filter=["admin_edit_success"])
    success_payload = success_messages[-1] if success_messages else None
    return (
        render_template(
            "admin_edit_item.html",
            item=item,
            form_data=form_data,
            import_options=import_options,
            errors=errors,
            save_message=success_payload["message"] if success_payload else None,
            saved_item=success_payload["item"] if success_payload else None,
            csrf_token=get_csrf_token(),
        ),
        status_code,
    )


@bp.route("/admin/import", methods=["GET", "POST"])
@require_admin
def admin_import():
    form_data = {
        "source_slug": "",
        "category_slug": "",
        "title": "",
        "summary": "",
        "content": "",
        "external_url": "",
    }
    errors = []
    status_code = 200

    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data.keys()}
        if not validate_csrf():
            errors = [CSRF_ERROR_MESSAGE]
            status_code = 400
        else:
            try:
                created_item = create_manual_import_item(**form_data)
            except ManualImportValidationError as exc:
                errors = exc.errors
                status_code = exc.status_code
            else:
                flash({"message": "已创建草稿条目", "item": created_item}, "admin_import_success")
                return redirect(url_for("main.admin_import"))

    import_options = get_admin_import_options()
    success_messages = get_flashed_messages(category_filter=["admin_import_success"])
    success_payload = success_messages[-1] if success_messages else None
    return (
        render_template(
            "admin_import.html",
            form_data=form_data,
            import_options=import_options,
            errors=errors,
            created_item=success_payload["item"] if success_payload else None,
            import_message=success_payload["message"] if success_payload else None,
            csrf_token=get_csrf_token(),
        ),
        status_code,
    )
