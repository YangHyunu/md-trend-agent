"""RSS 수집 — SPEC_V3 §5.1: WWD 태그피드 + 글로시 all.xml 키워드 필터."""

import hashlib
import re
import time
from datetime import datetime, timezone

import feedparser


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
