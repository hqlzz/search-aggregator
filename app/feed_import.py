import re
from html import unescape
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import click
from flask.cli import with_appcontext

from .db import (
    MANUAL_IMPORT_DEFAULT_STATUS,
    ManualImportValidationError,
    build_unique_item_slug,
    get_db,
    has_bootstrapped_tables,
    is_safe_external_url,
)


RSS_SOURCE_TYPE = "rss"
FEED_FETCH_TIMEOUT_SECONDS = 5
TAG_PATTERN = re.compile(r"<[^>]+>")


def fetch_feed_text(url, timeout=FEED_FETCH_TIMEOUT_SECONDS):
    request = Request(
        url,
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            "User-Agent": "search-aggregator/0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except (OSError, URLError, UnicodeDecodeError) as exc:
        raise ManualImportValidationError(["RSS 抓取失败，请稍后再试"], 502) from exc


def normalize_feed_text(value):
    return " ".join((value or "").split())


def strip_markup(value):
    return normalize_feed_text(unescape(TAG_PATTERN.sub(" ", value or "")))


def get_local_name(tag):
    if not isinstance(tag, str):
        return ""
    return tag.split("}", 1)[-1]


def find_first_child(element, names):
    for child in list(element):
        if get_local_name(child.tag) in names:
            return child
    return None


def read_child_text(element, names):
    child = find_first_child(element, names)
    if child is None:
        return ""
    return strip_markup("".join(child.itertext()))


def read_atom_link(entry):
    for child in list(entry):
        if get_local_name(child.tag) != "link":
            continue
        href = normalize_feed_text(child.attrib.get("href", ""))
        rel = normalize_feed_text(child.attrib.get("rel", ""))
        if href and rel in {"", "alternate"}:
            return href
    return ""


def parse_rss_item(item):
    return {
        "title": read_child_text(item, {"title"}),
        "summary": read_child_text(item, {"description"}),
        "content": read_child_text(item, {"encoded", "content"}),
        "external_url": normalize_feed_text(read_child_text(item, {"link"})),
        "author": read_child_text(item, {"author", "creator"}),
    }


def parse_atom_entry(entry):
    author_element = find_first_child(entry, {"author"})
    author_name = read_child_text(author_element, {"name"}) if author_element is not None else ""
    return {
        "title": read_child_text(entry, {"title"}),
        "summary": read_child_text(entry, {"summary"}),
        "content": read_child_text(entry, {"content"}),
        "external_url": read_atom_link(entry),
        "author": author_name,
    }


def parse_feed_entries(feed_text):
    try:
        root = ElementTree.fromstring(feed_text)
    except ElementTree.ParseError as exc:
        raise ManualImportValidationError(["RSS 解析失败，来源内容格式无效"], 502) from exc

    root_name = get_local_name(root.tag)
    if root_name == "feed":
        return [
            parse_atom_entry(entry)
            for entry in list(root)
            if get_local_name(entry.tag) == "entry"
        ]

    channel = root if root_name == "channel" else find_first_child(root, {"channel"})
    if channel is not None:
        return [
            parse_rss_item(item)
            for item in list(channel)
            if get_local_name(item.tag) == "item"
        ]

    raise ManualImportValidationError(["RSS 解析失败，来源内容格式无效"], 502)


def is_duplicate_feed_item(source_id, title, external_url):
    db = get_db()
    if external_url:
        return (
            db.execute(
                """
                SELECT 1
                FROM items
                WHERE source_id = ? AND external_url = ?
                LIMIT 1
                """,
                (source_id, external_url),
            ).fetchone()
            is not None
        )

    return (
        db.execute(
            """
            SELECT 1
            FROM items
            WHERE source_id = ? AND title = ?
            LIMIT 1
            """,
            (source_id, title),
        ).fetchone()
        is not None
    )


def get_rss_source(source_slug):
    if not has_bootstrapped_tables():
        raise ManualImportValidationError(["数据库尚未初始化，暂时无法抓取来源"], 503)

    row = get_db().execute(
        """
        SELECT id, name, slug, source_type, base_url, enabled
        FROM sources
        WHERE slug = ?
        LIMIT 1
        """,
        (source_slug,),
    ).fetchone()
    if row is None:
        raise ManualImportValidationError(["来源不存在，无法抓取"], 404)

    source = dict(row)
    if (source["source_type"] or "").strip().lower() != RSS_SOURCE_TYPE:
        raise ManualImportValidationError(["仅支持抓取 rss 类型来源"], 409)
    if not source["base_url"]:
        raise ManualImportValidationError(["RSS 来源地址不能为空"], 400)
    if not is_safe_external_url(source["base_url"]):
        raise ManualImportValidationError(["来源地址仅支持 http 或 https"], 400)
    return source


def get_enabled_rss_sources():
    if not has_bootstrapped_tables():
        raise ManualImportValidationError(["数据库尚未初始化，暂时无法抓取来源"], 503)

    rows = get_db().execute(
        """
        SELECT id, name, slug, source_type, base_url, enabled
        FROM sources
        WHERE enabled = 1 AND lower(source_type) = ?
        ORDER BY id ASC
        """,
        (RSS_SOURCE_TYPE,),
    ).fetchall()
    return [dict(row) for row in rows]


def sync_rss_source(source_slug):
    source = get_rss_source(source_slug)
    feed_text = fetch_feed_text(source["base_url"])
    entries = parse_feed_entries(feed_text)

    created_items = []
    skipped_count = 0
    db = get_db()

    with db:
        for entry in entries:
            title = normalize_feed_text(entry.get("title"))
            summary = normalize_feed_text(entry.get("summary"))
            content = normalize_feed_text(entry.get("content"))
            external_url = normalize_feed_text(entry.get("external_url"))
            author = normalize_feed_text(entry.get("author")) or None

            if external_url and not is_safe_external_url(external_url):
                external_url = ""
            if not title or (not summary and not content and not external_url):
                skipped_count += 1
                continue
            if is_duplicate_feed_item(source["id"], title, external_url or None):
                skipped_count += 1
                continue

            slug = build_unique_item_slug(title)
            cursor = db.execute(
                """
                INSERT INTO items (
                    source_id, category_id, title, slug, summary, content, external_url, author, status
                )
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source["id"],
                    title,
                    slug,
                    summary or None,
                    content or None,
                    external_url or None,
                    author,
                    MANUAL_IMPORT_DEFAULT_STATUS,
                ),
            )
            created_items.append(
                {
                    "id": cursor.lastrowid,
                    "title": title,
                    "slug": slug,
                    "external_url": external_url or None,
                }
            )

    return {
        "source_name": source["name"],
        "source_slug": source["slug"],
        "created_count": len(created_items),
        "skipped_count": skipped_count,
        "created_items": created_items,
    }


def sync_enabled_rss_sources():
    sources = get_enabled_rss_sources()
    summary = {
        "source_count": len(sources),
        "success_count": 0,
        "failure_count": 0,
        "created_count": 0,
        "skipped_count": 0,
        "results": [],
        "errors": [],
    }

    for source in sources:
        try:
            result = sync_rss_source(source["slug"])
        except ManualImportValidationError as exc:
            summary["failure_count"] += 1
            summary["errors"].append(
                {
                    "source_slug": source["slug"],
                    "source_name": source["name"],
                    "message": exc.errors[0] if exc.errors else "RSS 抓取失败，请稍后再试",
                }
            )
        else:
            summary["success_count"] += 1
            summary["created_count"] += result["created_count"]
            summary["skipped_count"] += result["skipped_count"]
            summary["results"].append(result)

    return summary


@click.command("sync-rss")
@with_appcontext
def sync_rss_command():
    summary = sync_enabled_rss_sources()
    if summary["source_count"] == 0:
        click.echo("没有找到已启用的 RSS 来源。")
        return

    click.echo(
        f"已同步 {summary['source_count']} 个 RSS 来源，"
        f"新增 {summary['created_count']} 条草稿，"
        f"跳过 {summary['skipped_count']} 条内容。"
    )
    for error in summary["errors"]:
        click.echo(f"[failed] {error['source_slug']}: {error['message']}")

    if summary["failure_count"] > 0:
        raise click.ClickException(f"{summary['failure_count']} 个 RSS 来源同步失败")


def init_app(app):
    app.cli.add_command(sync_rss_command)
