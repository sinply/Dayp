import re
import time
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from api.db import get_conn

log = logging.getLogger(__name__)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
FETCH_LIMIT = 100
KEEP_TOP = 30

AI_RE = re.compile(
    r"\b(AI|LLM|GPT|ChatGPT|Claude|Gemini|OpenAI|Anthropic|"
    r"neural|deep[\s-]?learning|machine[\s-]?learning|\bML\b|"
    r"diffusion|transformer|foundation[\s-]?model|"
    r"reinforcement[\s-]?learning|NLP|computer[\s-]?vision|"
    r"generative|AGI|alignment|fine[\s-]?tuning|RLHF|"
    r"Mistral|Llama|Stable[\s-]?Diffusion|Midjourney|Sora|"
    r"embedding|vector[\s-]?database|RAG|agent)\b",
    re.IGNORECASE,
)


def _is_ai_related(title: str) -> bool:
    return bool(AI_RE.search(title or ""))


def _fetch_item(item_id: int) -> dict | None:
    try:
        r = requests.get(HN_ITEM.format(id=item_id), timeout=10)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        log.warning("fetch item %s failed: %s", item_id, e)
        return None


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
                    str(it["id"]),
                    it.get("title", ""),
                    it.get("url", ""),
                    it.get("score", 0),
                    it.get("by", ""),
                    datetime.fromtimestamp(it.get("time", 0), tz=timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "hn",
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
    log.info("fetching HN top %d stories", FETCH_LIMIT)
    try:
        r = requests.get(HN_TOP, timeout=15)
        r.raise_for_status()
        ids = r.json()[:FETCH_LIMIT]
    except (requests.RequestException, ValueError) as e:
        log.error("fetch topstories failed: %s", e)
        return []

    ai_items: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch_item, i): i for i in ids}
        for fut in as_completed(futures):
            item = fut.result()
            if item and item.get("type") == "story" and _is_ai_related(item.get("title", "")):
                ai_items.append(item)

    ai_items.sort(key=lambda x: x.get("score", 0), reverse=True)
    ai_items = ai_items[:KEEP_TOP]
    saved = _save(ai_items)
    log.info("fetched %d AI stories, saved %d new", len(ai_items), saved)
    return ai_items


def run_loop(interval: int = 3600, stop_event=None) -> None:
    log.info("news_fetcher started, interval=%ds", interval)
    while True:
        if stop_event is not None and stop_event.is_set():
            log.info("news_fetcher stop signal received")
            break
        try:
            fetch_once()
        except Exception as e:
            log.error("news_fetcher error: %s", e)
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
        print(f"  [{it.get('score',0):>4}] {it.get('title','')}")
