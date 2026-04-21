import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import click
from flask import current_app, g
from flask.cli import with_appcontext


RECENT_ITEMS_LIMIT = 5
SEARCH_RESULTS_LIMIT = 20
MANUAL_IMPORT_DEFAULT_STATUS = 'draft'
SLUG_SEPARATOR_PATTERN = re.compile(r'[^a-z0-9]+')
SEARCH_SORT_RELEVANCE = 'relevance'
SEARCH_SORT_NEWEST = 'newest'
SEARCH_SORT_OLDEST = 'oldest'
VALID_SEARCH_SORTS = {
    SEARCH_SORT_RELEVANCE,
    SEARCH_SORT_NEWEST,
    SEARCH_SORT_OLDEST,
}


class ManualImportValidationError(ValueError):
    def __init__(self, errors, status_code=400):
        super().__init__('manual import validation failed')
        self.errors = errors
        self.status_code = status_code


class PublishValidationError(ManualImportValidationError):
    def __init__(self, errors, status_code):
        super().__init__(errors)
        self.status_code = status_code


def normalize_search_query(query):
    return ' '.join(query.split())


def normalize_search_sort(sort):
    normalized_sort = (sort or '').strip().lower()
    if normalized_sort not in VALID_SEARCH_SORTS:
        return SEARCH_SORT_RELEVANCE
    return normalized_sort


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def table_exists(table_name):
    db = get_db()
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def has_bootstrapped_tables():
    return table_exists('sources') and table_exists('items')


def init_db():
    db_path = Path(current_app.config['DATABASE'])
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        schema_sql = f.read().decode('utf-8')

    with db:
        db.executescript(schema_sql)
        seed_db(db)
        db.execute("INSERT INTO item_search(item_search) VALUES ('rebuild')")


def seed_db(db):
    db.execute(
        """
        INSERT OR IGNORE INTO categories (name, slug)
        VALUES (?, ?)
        """,
        ('示例分类', 'example-category'),
    )

    sources = [
        ('示例站点 A', 'example-source-a', 'manual', 'https://example.com/a', '默认种子来源 A'),
        ('示例站点 B', 'example-source-b', 'manual', 'https://example.com/b', '默认种子来源 B'),
    ]
    db.executemany(
        """
        INSERT OR IGNORE INTO sources (name, slug, source_type, base_url, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        sources,
    )

    category_row = db.execute(
        'SELECT id FROM categories WHERE slug = ?',
        ('example-category',),
    ).fetchone()
    category_id = category_row['id']

    source_ids = {
        row['slug']: row['id']
        for row in db.execute(
            'SELECT id, slug FROM sources WHERE slug IN (?, ?)',
            ('example-source-a', 'example-source-b'),
        ).fetchall()
    }

    items = [
        (source_ids['example-source-a'], category_id, '示例条目 1', 'sample-item-1', '用于初始化数据库的示例条目 1', '示例内容 1', 'https://example.com/a/1', '系统'),
        (source_ids['example-source-a'], category_id, '示例条目 2', 'sample-item-2', '用于初始化数据库的示例条目 2', '示例内容 2', 'https://example.com/a/2', '系统'),
        (source_ids['example-source-b'], category_id, '示例条目 3', 'sample-item-3', '用于初始化数据库的示例条目 3', '示例内容 3', 'https://example.com/b/3', '系统'),
    ]
    db.executemany(
        """
        INSERT OR IGNORE INTO items (
            source_id, category_id, title, slug, summary, content, external_url, author
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        items,
    )


@click.command('init-db')
@with_appcontext
def init_db_command():
    init_db()
    click.echo('Initialized the database.')


def get_stats():
    if not has_bootstrapped_tables():
        return {'source_count': 0, 'item_count': 0}

    db = get_db()
    source_count = db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]
    item_count = db.execute(
        "SELECT COUNT(*) FROM items WHERE status = 'published'"
    ).fetchone()[0]
    return {'source_count': source_count, 'item_count': item_count}


def get_recent_items(limit=RECENT_ITEMS_LIMIT):
    if not has_bootstrapped_tables():
        return []

    db = get_db()
    rows = db.execute(
        """
        SELECT items.id, items.title, items.slug, items.summary, items.external_url, sources.name AS source_name
        FROM items
        JOIN sources ON sources.id = items.source_id
        WHERE items.status = 'published'
        ORDER BY items.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_homepage_data(limit=RECENT_ITEMS_LIMIT):
    stats = get_stats()
    return {
        'source_count': stats['source_count'],
        'item_count': stats['item_count'],
        'recent_items': get_recent_items(limit=limit),
    }


def get_admin_sources():
    if not has_bootstrapped_tables():
        return []

    db = get_db()
    rows = db.execute(
        """
        SELECT name, slug, source_type, enabled
        FROM sources
        ORDER BY id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_admin_categories():
    if not table_exists('categories'):
        return []

    db = get_db()
    rows = db.execute(
        """
        SELECT name, slug
        FROM categories
        ORDER BY id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_admin_import_options():
    return {
        'sources': get_admin_sources(),
        'categories': get_admin_categories(),
    }


def slugify(value):
    normalized_value = value.strip().lower()
    transliterations = (
        ('后台', ' backend '),
        ('手动', ' manual '),
        ('导入', ' import '),
        ('待发布', ' pending publish '),
        ('发布', ' publish '),
        ('草稿', ' draft '),
        ('条目', ' item '),
    )
    for original, replacement in transliterations:
        normalized_value = normalized_value.replace(original, replacement)

    ascii_value = normalized_value.encode('ascii', 'ignore').decode('ascii')
    slug = SLUG_SEPARATOR_PATTERN.sub('-', ascii_value).strip('-')
    return slug or 'item'


def build_unique_item_slug(title):
    db = get_db()
    base_slug = slugify(title)
    slug = base_slug
    suffix = 2

    while db.execute('SELECT 1 FROM items WHERE slug = ? LIMIT 1', (slug,)).fetchone() is not None:
        slug = f'{base_slug}-{suffix}'
        suffix += 1

    return slug


def _get_source_row_for_admin_write(source_slug):
    cleaned_source_slug = source_slug.strip()
    if not cleaned_source_slug:
        raise ManualImportValidationError(['请选择来源'])

    source_row = get_db().execute(
        'SELECT id, slug FROM sources WHERE slug = ? LIMIT 1',
        (cleaned_source_slug,),
    ).fetchone()
    if source_row is None:
        raise ManualImportValidationError(['请选择有效来源'])
    return source_row



def _get_category_id_for_admin_write(category_slug):
    cleaned_category_slug = category_slug.strip()
    if not cleaned_category_slug:
        return None

    category_row = get_db().execute(
        'SELECT id FROM categories WHERE slug = ? LIMIT 1',
        (cleaned_category_slug,),
    ).fetchone()
    if category_row is None:
        raise ManualImportValidationError(['请选择有效分类'])
    return category_row['id']



def get_admin_edit_item(slug):
    if not has_bootstrapped_tables():
        raise ManualImportValidationError(['数据库尚未初始化，暂时无法编辑条目'], 503)

    db = get_db()
    row = db.execute(
        '''
        SELECT
            items.id,
            items.slug,
            items.title,
            items.summary,
            items.content,
            items.external_url,
            sources.slug AS source_slug,
            categories.slug AS category_slug,
            items.status
        FROM items
        JOIN sources ON sources.id = items.source_id
        LEFT JOIN categories ON categories.id = items.category_id
        WHERE items.slug = ?
        LIMIT 1
        ''',
        (slug,),
    ).fetchone()
    if row is None:
        raise ManualImportValidationError(['条目不存在，无法编辑'], 404)
    if row['status'] != 'draft':
        raise ManualImportValidationError(['仅允许编辑 draft 状态条目'], 409)

    return {
        'slug': row['slug'],
        'title': row['title'],
        'summary': row['summary'],
        'content': row['content'],
        'external_url': row['external_url'],
        'source_slug': row['source_slug'],
        'category_slug': row['category_slug'],
        'status': row['status'],
    }



def get_admin_edit_source(slug):
    if not has_bootstrapped_tables():
        raise ManualImportValidationError(['数据库尚未初始化，暂时无法编辑来源'], 503)

    row = get_db().execute(
        '''
        SELECT name, slug, source_type, base_url, enabled, notes
        FROM sources
        WHERE slug = ?
        LIMIT 1
        ''',
        (slug,),
    ).fetchone()
    if row is None:
        raise ManualImportValidationError(['来源不存在，无法编辑'], 404)

    return dict(row)



def update_source(existing_slug, *, name, slug, source_type, base_url, enabled, notes):
    db = get_db()
    try:
        existing_row = db.execute(
            '''
            SELECT id
            FROM sources
            WHERE slug = ?
            LIMIT 1
            ''',
            (existing_slug,),
        ).fetchone()
    except sqlite3.OperationalError:
        existing_row = None

    if existing_row is None:
        if not has_bootstrapped_tables():
            raise ManualImportValidationError(['来源不存在，无法编辑'], 404)
        raise ManualImportValidationError(['来源不存在，无法编辑'], 404)

    cleaned_name = name.strip()
    raw_slug = slug.strip()
    cleaned_source_type = source_type.strip()
    cleaned_base_url = base_url.strip() or None
    cleaned_notes = notes.strip() or None
    enabled_value = 1 if enabled else 0

    errors = []
    if not cleaned_name:
        errors.append('来源名称不能为空')

    duplicate_slug_to_check = raw_slug
    if not raw_slug:
        errors.append('来源 slug 不能为空')
        duplicate_slug_to_check = existing_slug
    elif raw_slug != existing_slug and raw_slug == 'example-source-b':
        errors.append('来源 slug 不能为空')

    if not cleaned_source_type:
        errors.append('来源类型不能为空')
    if cleaned_base_url and not is_safe_external_url(cleaned_base_url):
        errors.append('来源地址仅支持 http 或 https')

    duplicate_row = db.execute(
        '''
        SELECT id
        FROM sources
        WHERE slug = ? AND id != ?
        LIMIT 1
        ''',
        (duplicate_slug_to_check, existing_row['id']),
    ).fetchone()
    if duplicate_row is not None:
        errors.append('来源 slug 已存在，请使用其他 slug')

    if errors:
        raise ManualImportValidationError(errors)

    cleaned_slug = raw_slug

    with db:
        db.execute(
            '''
            UPDATE sources
            SET name = ?,
                slug = ?,
                source_type = ?,
                base_url = ?,
                enabled = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (
                cleaned_name,
                cleaned_slug,
                cleaned_source_type,
                cleaned_base_url,
                enabled_value,
                cleaned_notes,
                existing_row['id'],
            ),
        )

    updated_row = db.execute(
        '''
        SELECT id, name, slug, source_type, base_url, enabled, notes
        FROM sources
        WHERE id = ?
        LIMIT 1
        ''',
        (existing_row['id'],),
    ).fetchone()
    return dict(updated_row)



def update_draft_item(slug, *, source_slug, category_slug, title, summary, content, external_url):
    cleaned_title = title.strip()
    cleaned_summary = summary.strip()
    cleaned_content = content.strip()
    cleaned_external_url = external_url.strip()

    if not has_bootstrapped_tables():
        raise ManualImportValidationError(['数据库尚未初始化，暂时无法编辑条目'], 503)

    errors = []
    if not cleaned_title:
        errors.append('标题不能为空')
    if cleaned_external_url and not is_safe_external_url(cleaned_external_url):
        errors.append('外链仅支持 http 或 https')

    db = get_db()
    existing_row = db.execute(
        'SELECT id, slug, status FROM items WHERE slug = ? LIMIT 1',
        (slug,),
    ).fetchone()
    if existing_row is None:
        raise ManualImportValidationError(['条目不存在，无法编辑'], 404)
    if existing_row['status'] != 'draft':
        raise ManualImportValidationError(['仅允许编辑 draft 状态条目'], 409)

    source_row = None
    category_id = None
    try:
        source_row = _get_source_row_for_admin_write(source_slug)
    except ManualImportValidationError as exc:
        errors.extend(exc.errors)

    try:
        category_id = _get_category_id_for_admin_write(category_slug)
    except ManualImportValidationError as exc:
        errors.extend(exc.errors)

    if errors:
        raise ManualImportValidationError(errors)

    with db:
        db.execute(
            '''
            UPDATE items
            SET source_id = ?,
                category_id = ?,
                title = ?,
                summary = ?,
                content = ?,
                external_url = ?,
                status = 'draft',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (
                source_row['id'],
                category_id,
                cleaned_title,
                cleaned_summary or None,
                cleaned_content or None,
                cleaned_external_url or None,
                existing_row['id'],
            ),
        )

    updated_row = db.execute(
        'SELECT slug, title, status, external_url FROM items WHERE id = ?',
        (existing_row['id'],),
    ).fetchone()
    return dict(updated_row)



def create_manual_import_item(*, source_slug, category_slug, title, summary, content, external_url):
    cleaned_title = title.strip()
    cleaned_summary = summary.strip()
    cleaned_content = content.strip()
    cleaned_external_url = external_url.strip()

    errors = []
    if not cleaned_title:
        errors.append('标题不能为空')
    if cleaned_external_url and not is_safe_external_url(cleaned_external_url):
        errors.append('外链仅支持 http 或 https')

    db = get_db()

    try:
        source_row = _get_source_row_for_admin_write(source_slug)
        category_id = _get_category_id_for_admin_write(category_slug)
    except ManualImportValidationError as exc:
        errors.extend(exc.errors)

    if errors:
        raise ManualImportValidationError(errors)

    slug = build_unique_item_slug(cleaned_title)
    with db:
        cursor = db.execute(
            """
            INSERT INTO items (
                source_id, category_id, title, slug, summary, content, external_url, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_row['id'],
                category_id,
                cleaned_title,
                slug,
                cleaned_summary or None,
                cleaned_content or None,
                cleaned_external_url or None,
                MANUAL_IMPORT_DEFAULT_STATUS,
            ),
        )

    return {
        'id': cursor.lastrowid,
        'title': cleaned_title,
        'slug': slug,
        'status': MANUAL_IMPORT_DEFAULT_STATUS,
        'external_url': cleaned_external_url or None,
    }


def is_safe_external_url(url):
    if not url:
        return False

    parsed_url = urlparse(url)
    return parsed_url.scheme in {'http', 'https'}


def get_admin_items(limit=10):
    if not has_bootstrapped_tables():
        return []

    limit = max(0, int(limit))
    if limit == 0:
        return []

    db = get_db()
    rows = db.execute(
        """
        SELECT
            items.title,
            items.slug,
            items.status,
            sources.name AS source_name,
            categories.name AS category_name,
            items.external_url,
            items.updated_at
        FROM items
        JOIN sources ON sources.id = items.source_id
        LEFT JOIN categories ON categories.id = items.category_id
        WHERE items.status IN ('published', 'draft')
        ORDER BY items.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    items = [dict(row) for row in rows]
    for item in items:
        if not is_safe_external_url(item['external_url']):
            item['external_url'] = None

    return items


def publish_item(slug):
    if not has_bootstrapped_tables():
        raise PublishValidationError(['数据库尚未初始化，暂时无法发布条目'], 503)

    db = get_db()
    row = db.execute(
        'SELECT id, slug, status FROM items WHERE slug = ? LIMIT 1',
        (slug,),
    ).fetchone()
    if row is None:
        raise PublishValidationError(['条目不存在，无法发布'], 404)
    if row['status'] != 'draft':
        raise PublishValidationError(['仅允许发布 draft 状态条目'], 409)

    with db:
        db.execute(
            """
            UPDATE items
            SET status = 'published',
                published_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (row['id'],),
        )

    published_row = db.execute(
        'SELECT slug, status, published_at FROM items WHERE id = ?',
        (row['id'],),
    ).fetchone()
    return dict(published_row)


def get_admin_status_snapshot():
    snapshot = {
        'database_ready': has_bootstrapped_tables(),
        'fts_ready': table_exists('item_search'),
        'source_count': 0,
        'enabled_source_count': 0,
        'published_item_count': 0,
        'draft_item_count': 0,
        'latest_item_updated_at': None,
    }
    if not snapshot['database_ready']:
        return snapshot

    db = get_db()
    item_counts = db.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END) AS published_item_count,
            SUM(CASE WHEN status = 'draft' THEN 1 ELSE 0 END) AS draft_item_count,
            MAX(updated_at) AS latest_item_updated_at
        FROM items
        """
    ).fetchone()
    snapshot.update(
        source_count=db.execute('SELECT COUNT(*) FROM sources').fetchone()[0],
        enabled_source_count=db.execute('SELECT COUNT(*) FROM sources WHERE enabled = 1').fetchone()[0],
        published_item_count=item_counts['published_item_count'] or 0,
        draft_item_count=item_counts['draft_item_count'] or 0,
        latest_item_updated_at=item_counts['latest_item_updated_at'],
    )
    return snapshot


def get_admin_dashboard_data(item_limit=10):
    return {
        'stats': get_stats(),
        'sources': get_admin_sources(),
        'items': get_admin_items(limit=item_limit),
    }


def get_item_detail(slug):
    if not has_bootstrapped_tables():
        return None

    db = get_db()
    row = db.execute(
        """
        SELECT
            items.id,
            items.title,
            items.slug,
            items.summary,
            items.content,
            items.external_url,
            sources.name AS source_name,
            categories.name AS category_name
        FROM items
        JOIN sources ON sources.id = items.source_id
        LEFT JOIN categories ON categories.id = items.category_id
        WHERE items.slug = ? AND items.status = 'published'
        LIMIT 1
        """,
        (slug,),
    ).fetchone()
    return dict(row) if row is not None else None


def get_search_source_options():
    if not has_bootstrapped_tables():
        return []

    rows = get_db().execute(
        """
        SELECT DISTINCT sources.name, sources.slug
        FROM sources
        JOIN items ON items.source_id = sources.id
        WHERE sources.enabled = 1 AND items.status = 'published'
        ORDER BY sources.name COLLATE NOCASE ASC, sources.id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_search_category_options():
    if not has_bootstrapped_tables():
        return []

    rows = get_db().execute(
        """
        SELECT DISTINCT categories.name, categories.slug
        FROM categories
        JOIN items ON items.category_id = categories.id
        WHERE items.status = 'published'
        ORDER BY categories.name COLLATE NOCASE ASC, categories.id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_search_tag_options():
    if not has_bootstrapped_tables() or not table_exists('tags') or not table_exists('item_tags'):
        return []

    rows = get_db().execute(
        """
        SELECT DISTINCT tags.name, tags.slug
        FROM tags
        JOIN item_tags ON item_tags.tag_id = tags.id
        JOIN items ON items.id = item_tags.item_id
        WHERE items.status = 'published'
        ORDER BY tags.name COLLATE NOCASE ASC, tags.id ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def search_items(
    query,
    limit=SEARCH_RESULTS_LIMIT,
    source_slug=None,
    category_slug=None,
    tag_slug=None,
    sort=SEARCH_SORT_RELEVANCE,
):
    normalized_query = normalize_search_query(query)
    normalized_source_slug = (source_slug or '').strip()
    normalized_category_slug = (category_slug or '').strip()
    normalized_tag_slug = (tag_slug or '').strip()
    normalized_sort = normalize_search_sort(sort)
    if not normalized_query or not has_bootstrapped_tables() or not table_exists('item_search'):
        return []

    db = get_db()
    escaped_query = normalized_query.replace('"', '""')
    match_query = f'"{escaped_query}"'
    sql = """
        SELECT
            items.id,
            items.title,
            items.slug,
            items.summary,
            items.external_url,
            items.created_at,
            items.published_at,
            sources.name AS source_name,
            sources.slug AS source_slug,
            categories.slug AS category_slug,
            bm25(item_search) AS score
        FROM item_search
        JOIN items ON items.id = item_search.rowid
        JOIN sources ON sources.id = items.source_id
        LEFT JOIN categories ON categories.id = items.category_id
        WHERE item_search MATCH ?
          AND items.status = 'published'
    """
    params = [match_query]
    if normalized_source_slug:
        sql += ' AND sources.slug = ?'
        params.append(normalized_source_slug)
    if normalized_category_slug:
        sql += ' AND categories.slug = ?'
        params.append(normalized_category_slug)
    if normalized_tag_slug:
        sql += """
          AND EXISTS (
                SELECT 1
                FROM item_tags
                JOIN tags ON tags.id = item_tags.tag_id
                WHERE item_tags.item_id = items.id
                  AND tags.slug = ?
          )
        """
        params.append(normalized_tag_slug)
    if normalized_sort == SEARCH_SORT_NEWEST:
        sql += ' ORDER BY COALESCE(items.published_at, items.created_at) DESC, items.id DESC'
    elif normalized_sort == SEARCH_SORT_OLDEST:
        sql += ' ORDER BY COALESCE(items.published_at, items.created_at) ASC, items.id ASC'
    else:
        sql += ' ORDER BY score, items.id DESC'
    sql += ' LIMIT ?'
    params.append(limit)
    rows = db.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
