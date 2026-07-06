import re
import time
import logging
import ssl
from datetime import datetime

import feedparser
import urllib.request

from api.db import get_conn

log = logging.getLogger(__name__)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE
_HTTPS_HANDLER = urllib.request.HTTPSHandler(context=_SSL_CTX)

CN_SOURCES = [
    {
        "source": "36kr",
        "name": "36氪",
        "url": "https://36kr.com/feed",
    },
    {
        "source": "leiphone",
        "name": "雷锋网",
        "url": "https://www.leiphone.com/feed/",
    },
    {
        "source": "ifanr",
        "name": "爱范儿",
        "url": "https://www.ifanr.com/feed",
    },
    {
        "source": "aibase",
        "name": "AIbase",
        "url": "https://rsshub.rssforever.com/aibase/news",
    },
    {
        "source": "huxiu",
        "name": "虎嗅",
        "url": "https://rsshub.rssforever.com/huxiu/article",
    },
]

AI_RE = re.compile(
    r"(AI|人工智能|大模型|LLM|GPT|ChatGPT|Claude|Gemini|OpenAI|Anthropic|"
    r"通义|文心|千问|豆包|DeepSeek|Kimi|智谱|百川|零一万物|月之暗面|"
    r"芯片|GPU|算力|训练|推理|微调|RAG|Agent|智能体|具身|"
    r"neural|deep[\s-]?learning|machine[\s-]?learning|\bML\b|"
    r"diffusion|transformer|foundation[\s-]?model|"
    r"generative|AGI|alignment|fine[\s-]?tuning|RLHF|"
    r"Mistral|Llama|Stable[\s-]?Diffusion|Midjourney|Sora)",
    re.IGNORECASE,
)

KEEP_PER_SOURCE = 20


def _is_ai_related(title: str, summary: str = "") -> bool:
    return bool(AI_RE.search(title or "") or AI_RE.search(summary or ""))


def _parse_time(entry) -> str:
    for key in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, key, None)
        if tp:
            try:
                dt = datetime(*tp[:6])
                return dt.strftime("%Y-%m-%dT%H:%M:%S")
            except (TypeError, ValueError):
                pass
    for key in ("published", "updated"):
        val = getattr(entry, key, None)
        if val:
            return val
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _save(items: list[dict]) -> int:
    if not items:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO news(hn_id, title, url, score, by, time, source, fetched_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            [
                (
                    it["id"],
                    it.get("title", ""),
                    it.get("url", ""),
                    it.get("score", 0),
                    it.get("by", ""),
                    it.get("time", ""),
                    it.get("source", "cn"),
                    now,
                )
                for it in items
            ],
        )
        conn.commit()
        return conn.total_changes
    finally:
        conn.close()


def fetch_once() -> list[dict]:
    all_items: list[dict] = []
    for src in CN_SOURCES:
        log.info("fetching CN feed: %s", src["url"])
        try:
            d = feedparser.parse(
                src["url"],
                request_headers={"User-Agent": "Dayp/0.2"},
                handlers=[_HTTPS_HANDLER],
            )
            if d.bozo:
                log.warning("feed %s bozo: %s", src["url"], d.bozo_exception)
            count = 0
            for entry in d.entries:
                title = getattr(entry, "title", "") or ""
                link = getattr(entry, "link", "") or ""
                summary = getattr(entry, "summary", "") or ""
                if not _is_ai_related(title, summary):
                    continue
                all_items.append({
                    "id": f"{src['source']}-{link}",
                    "title": title,
                    "url": link,
                    "score": 0,
                    "by": src["name"],
                    "time": _parse_time(entry),
                    "source": src["source"],
                })
                count += 1
                if count >= KEEP_PER_SOURCE:
                    break
        except Exception as e:
            log.error("fetch %s failed: %s", src["url"], e)

    saved = _save(all_items)
    log.info("fetched %d CN AI stories, saved %d new", len(all_items), saved)
    return all_items


def run_loop(interval: int = 3600, stop_event=None) -> None:
    log.info("cn_news_fetcher started, interval=%ds", interval)
    while True:
        if stop_event is not None and stop_event.is_set():
            log.info("cn_news_fetcher stop signal received")
            break
        try:
            fetch_once()
        except Exception as e:
            log.error("cn_news_fetcher error: %s", e)
        if stop_event is not None:
            stop_event.wait(interval)
            if stop_event.is_set():
                break
        else:
            time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    items = fetch_once()
    for it in items[:10]:
        print(f"  [{it['source']}] {it['title'][:50]}")
