"""RSS 수집 — SPEC_V3 §5.1: WWD 태그피드 + 글로시 all.xml 키워드 필터."""

import hashlib
import re
import time
from datetime import datetime, timezone

import feedparser
import httpx

from poc import config


def _article_id(url: str) -> str:
    return "a" + hashlib.sha1(url.encode()).hexdigest()[:10]


def _iso(struct: time.struct_time | None) -> str | None:
    if struct is None:
        return None
    return datetime(*struct[:6], tzinfo=timezone.utc).isoformat()


def _excerpt(entry: dict) -> str:
    raw = entry.get("summary", "") or ""
    return re.sub(r"<[^>]+>", "", raw).strip()[:300]


def parse_feed(xml_text: str, source: str) -> list[dict]:
    parsed = feedparser.parse(xml_text)
    now = datetime.now(timezone.utc).isoformat()
    articles = []
    for entry in parsed.entries:
        url = entry.get("link", "")
        if not url:
            continue
        articles.append(
            {
                "id": _article_id(url),
                "source": source,
                "url": url,
                "title": entry.get("title", ""),
                "published_at": _iso(entry.get("published_parsed")),
                "fetched_at": now,
                "matched_terms": [],
                "excerpt": _excerpt(entry),
            }
        )
    return articles


def filter_by_terms(articles: list[dict], terms: list[str]) -> list[dict]:
    kept = []
    for a in articles:
        text = f"{a['title']} {a['excerpt']}".lower()
        matched = [t for t in terms if t in text]
        if matched:
            kept.append({**a, "matched_terms": matched})
    return kept


DEFAULT_TIMEOUT = 20.0
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) md-trend-agent/0.1"


def fetch_feed(client: httpx.Client, url: str) -> str | None:
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError:
        return None


def fetch_all_feeds(client: httpx.Client | None = None) -> dict:
    own = client is None
    if own:
        client = httpx.Client(
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _UA},
        )
    articles: list[dict] = []
    failures: list[str] = []
    try:
        for term, url in config.WWD_TAG_FEEDS.items():
            xml = fetch_feed(client, url)
            if xml is None:
                failures.append(f"wwd:{term}")
                continue
            found = parse_feed(xml, source=f"wwd:{term}")
            articles.extend({**a, "matched_terms": [term]} for a in found)
        for name, url in config.GLOSSY_FEEDS.items():
            xml = fetch_feed(client, url)
            if xml is None:
                failures.append(f"glossy:{name}")
                continue
            found = parse_feed(xml, source=f"glossy:{name}")
            articles.extend(filter_by_terms(found, config.KNIT_FILTER_TERMS))
    finally:
        if own:
            client.close()
    return {"articles": articles, "failures": failures}
