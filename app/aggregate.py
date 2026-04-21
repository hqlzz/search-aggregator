import json
import time
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_AGGREGATE_LIMIT = 8
DEFAULT_PER_SOURCE_LIMIT = 5
AGGREGATE_CACHE_TTL_SECONDS = 300
DEFAULT_WIKIPEDIA_BASE_URL = "https://en.wikipedia.org"
DEFAULT_HACKER_NEWS_BASE_URL = "https://hn.algolia.com"
SUPPORTED_AGGREGATE_SOURCE_TYPES = {"wikipedia", "hackernews"}

_aggregate_cache = {}


class AggregateSearchError(RuntimeError):
    pass


def clear_aggregate_cache():
    _aggregate_cache.clear()


def normalize_aggregate_text(value):
    return " ".join((value or "").split())


def fetch_json(url, timeout=4):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "search-aggregator/0.1",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError) as exc:
        raise AggregateSearchError("外部聚合源请求失败") from exc


def build_cache_key(source, query, limit):
    return (
        source.get("slug", ""),
        source.get("source_type", ""),
        source.get("base_url", "") or "",
        query,
        int(limit),
    )


def get_cached_aggregate_results(cache_key):
    cached_entry = _aggregate_cache.get(cache_key)
    if not cached_entry:
        return None

    expires_at, results = cached_entry
    if expires_at <= time.time():
        _aggregate_cache.pop(cache_key, None)
        return None
    return results


def set_cached_aggregate_results(cache_key, results):
    _aggregate_cache[cache_key] = (
        time.time() + AGGREGATE_CACHE_TTL_SECONDS,
        results,
    )


def build_wikipedia_api_url(source, query, limit):
    base_url = (source.get("base_url") or DEFAULT_WIKIPEDIA_BASE_URL).rstrip("/")
    params = urlencode(
        {
            "action": "opensearch",
            "search": query,
            "limit": int(limit),
            "namespace": 0,
            "format": "json",
        }
    )
    return f"{base_url}/w/api.php?{params}"


def parse_wikipedia_results(source, payload):
    if not isinstance(payload, list) or len(payload) < 4:
        raise AggregateSearchError("外部聚合源返回格式无效")

    titles = payload[1] if isinstance(payload[1], list) else []
    descriptions = payload[2] if isinstance(payload[2], list) else []
    urls = payload[3] if isinstance(payload[3], list) else []
    max_length = min(len(titles), len(urls))

    results = []
    for index in range(max_length):
        title = normalize_aggregate_text(titles[index])
        url = normalize_aggregate_text(urls[index])
        description = normalize_aggregate_text(descriptions[index] if index < len(descriptions) else "")
        if not title or not url:
            continue
        results.append(
            {
                "title": title,
                "url": url,
                "excerpt": description or "Wikipedia 条目搜索结果",
                "source_name": source.get("name") or "Wikipedia",
                "source_slug": source.get("slug") or "wikipedia",
                "provider": "wikipedia",
            }
        )
    return results


def search_wikipedia_source(source, query, limit):
    cache_key = build_cache_key(source, query, limit)
    cached_results = get_cached_aggregate_results(cache_key)
    if cached_results is not None:
        return cached_results

    api_url = build_wikipedia_api_url(source, query, limit)
    payload = fetch_json(api_url)
    results = parse_wikipedia_results(source, payload)
    set_cached_aggregate_results(cache_key, results)
    return results


def build_hackernews_api_url(source, query, limit):
    base_url = (source.get("base_url") or DEFAULT_HACKER_NEWS_BASE_URL).rstrip("/")
    params = urlencode(
        {
            "query": query,
            "hitsPerPage": int(limit),
            "tags": "story",
        }
    )
    return f"{base_url}/api/v1/search?{params}"


def build_hackernews_fallback_url(hit):
    object_id = normalize_aggregate_text(hit.get("objectID"))
    if not object_id:
        return ""
    return f"https://news.ycombinator.com/item?id={object_id}"


def build_hackernews_excerpt(hit):
    story_text = normalize_aggregate_text(hit.get("story_text"))
    if story_text:
        return story_text

    author = normalize_aggregate_text(hit.get("author"))
    points = hit.get("points")
    parts = []
    if author:
        parts.append(f"作者：{author}")
    if isinstance(points, int):
        parts.append(f"分数：{points}")
    return " · ".join(parts) or "Hacker News 搜索结果"


def parse_hackernews_results(source, payload):
    hits = payload.get("hits") if isinstance(payload, dict) else None
    if not isinstance(hits, list):
        raise AggregateSearchError("外部聚合源返回格式无效")

    results = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        title = normalize_aggregate_text(hit.get("title") or hit.get("story_title"))
        url = normalize_aggregate_text(hit.get("url") or hit.get("story_url")) or build_hackernews_fallback_url(hit)
        if not title or not url:
            continue
        results.append(
            {
                "title": title,
                "url": url,
                "excerpt": build_hackernews_excerpt(hit),
                "source_name": source.get("name") or "Hacker News",
                "source_slug": source.get("slug") or "hackernews",
                "provider": "hackernews",
            }
        )
    return results


def search_hackernews_source(source, query, limit):
    cache_key = build_cache_key(source, query, limit)
    cached_results = get_cached_aggregate_results(cache_key)
    if cached_results is not None:
        return cached_results

    api_url = build_hackernews_api_url(source, query, limit)
    payload = fetch_json(api_url)
    results = parse_hackernews_results(source, payload)
    set_cached_aggregate_results(cache_key, results)
    return results


AGGREGATE_SOURCE_HANDLERS = {
    "hackernews": search_hackernews_source,
    "wikipedia": search_wikipedia_source,
}


def search_aggregate_items(query, aggregate_sources, limit=DEFAULT_AGGREGATE_LIMIT):
    normalized_query = normalize_aggregate_text(query)
    if not normalized_query:
        return [], []

    combined_results = []
    errors = []
    per_source_limit = max(1, min(int(limit), DEFAULT_PER_SOURCE_LIMIT))

    for source in aggregate_sources:
        source_type = (source.get("source_type") or "").strip().lower()
        handler = AGGREGATE_SOURCE_HANDLERS.get(source_type)
        if handler is None:
            continue
        try:
            combined_results.extend(handler(source, normalized_query, per_source_limit))
        except Exception as exc:
            message = str(exc) if isinstance(exc, AggregateSearchError) else "外部聚合源请求失败"
            errors.append(
                {
                    "source_name": source.get("name") or source.get("slug") or source_type,
                    "message": message,
                }
            )

    return combined_results[: int(limit)], errors
