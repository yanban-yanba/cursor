from __future__ import annotations

import html
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import feedparser
import httpx

from us_culture.config import CATEGORIES, FetchConfig
from us_culture.models import Topic, TopicBundle

logger = logging.getLogger("us_culture.fetch")

# 美区主流 RSS：按栏目覆盖社会 / 科技 / 影视 / 音乐 / 八卦
FEEDS: dict[str, tuple[str, ...]] = {
    "社会": (
        "https://news.google.com/rss/headlines/section/topic/NATION?hl=en-US&gl=US&ceid=US:en",
        "https://feeds.npr.org/1001/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/US.xml",
    ),
    "科技": (
        "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
    ),
    "影视": (
        "https://variety.com/feed/",
        "https://deadline.com/feed/",
        "https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml",
    ),
    "音乐": (
        "https://www.billboard.com/feed/",
        "https://www.rollingstone.com/music/music-news/feed/",
        "https://rss.nytimes.com/services/xml/rss/nyt/Music.xml",
    ),
    "八卦": (
        "https://pagesix.com/feed/",
        "https://www.tmz.com/rss.xml",
        "https://www.usmagazine.com/feed/",
    ),
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _plain(text: str) -> str:
    text = html.unescape(_TAG_RE.sub(" ", text or ""))
    return _SPACE_RE.sub(" ", text).strip()


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


def _parse_published(entry) -> datetime | None:
    raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass
    parsed_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed_struct:
        return None
    try:
        return datetime(*parsed_struct[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _download_feed(url: str, timeout: int) -> bytes:
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"},
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content


def _entries_from_feed(category: str, url: str, content: bytes) -> list[Topic]:
    parsed = feedparser.parse(content)
    source = _plain(getattr(parsed.feed, "title", "") or "") or _host(url)
    items: list[Topic] = []
    for entry in parsed.entries:
        title = _plain(getattr(entry, "title", "") or "")
        link = (getattr(entry, "link", "") or "").strip()
        if not title or not link:
            continue
        summary = _plain(getattr(entry, "summary", "") or getattr(entry, "description", "") or "")
        if summary.startswith(title):
            summary = summary[len(title) :].strip(" -–—|")
        published = _parse_published(entry)
        items.append(
            Topic(
                category=category,
                title=title,
                summary=summary[:400],
                source=source,
                url=link,
                published_at=published.isoformat() if published else None,
            )
        )
    return items


def _still_fresh(topic: Topic, cutoff: datetime) -> bool:
    if not topic.published_at:
        return True
    published = datetime.fromisoformat(topic.published_at)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published >= cutoff


def _dedupe(items: list[Topic], limit: int) -> list[Topic]:
    seen: set[str] = set()
    unique: list[Topic] = []
    for item in items:
        key = re.sub(r"\W+", " ", item.title.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
        if len(unique) >= limit:
            break
    return unique


def fetch_topics(fetch: FetchConfig, run_date: str, us_date: str) -> TopicBundle:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=fetch.lookback_hours)
    jobs = [(category, url) for category in CATEGORIES for url in FEEDS[category]]
    collected: dict[str, list[Topic]] = {category: [] for category in CATEGORIES}

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_download_feed, url, fetch.timeout_seconds): (category, url)
            for category, url in jobs
        }
        for future in as_completed(futures):
            category, url = futures[future]
            try:
                content = future.result()
                entries = _entries_from_feed(category, url, content)
                fresh = [item for item in entries if _still_fresh(item, cutoff)]
                collected[category].extend(fresh)
                logger.info("抓取成功 %s %s：%s 条", category, url, len(fresh))
            except Exception as exc:
                logger.warning("抓取失败 %s %s：%s", category, url, exc)

    items: list[Topic] = []
    empty: list[str] = []
    for category in CATEGORIES:
        picked = _dedupe(collected[category], fetch.per_category)
        if not picked:
            empty.append(category)
        items.extend(picked)

    if empty:
        raise RuntimeError(f"以下栏目没有抓到热点，停止生成：{', '.join(empty)}")
    if len(items) < len(CATEGORIES) * 3:
        raise RuntimeError(f"热点数量过少（{len(items)}），停止生成")

    logger.info("抓取完成，共 %s 条", len(items))
    return TopicBundle(run_date=run_date, us_date=us_date, items=items)


def render_topic_prompt(bundle: TopicBundle) -> str:
    lines = [f"推送日：{bundle.run_date}", f"美东日期：{bundle.us_date}", ""]
    for category, topics in bundle.by_category().items():
        lines.append(f"## {category}")
        for topic in topics:
            published = topic.published_at or "时间未知"
            summary = topic.summary or "无摘要"
            lines.append(f"- {topic.title} | {summary} | {topic.source} | {published} | {topic.url}")
        lines.append("")
    return "\n".join(lines)
