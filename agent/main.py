import sys
import threading
import logging
import time
from datetime import datetime, timedelta

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from api.db import init_db, aggregate_daily
from agent.window_tracker import run_loop as run_window
from agent.news_fetcher import run_loop as run_news
from agent.cn_news_fetcher import run_loop as run_cn_news
from agent.mail_fetcher import run_loop as run_mail

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("agent")


def _daily_aggregator(stop_event: threading.Event) -> None:
    last_run_date = None
    log.info("daily aggregator started")
    while not stop_event.is_set():
        now = datetime.now()
        if now.hour == 0 and now.minute < 5:
            today = now.strftime("%Y-%m-%d")
            if last_run_date != today:
                target = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                try:
                    n = aggregate_daily(target)
                    log.info("aggregated %s -> %d processes", target, n)
                    last_run_date = today
                except Exception as e:
                    log.error("aggregate %s failed: %s", target, e)
        stop_event.wait(60)
    log.info("daily aggregator stopped")


def main() -> None:
    init_db()
    log.info("database initialized")

    stop = threading.Event()

    threads = [
        threading.Thread(target=run_window, kwargs={"stop_event": stop}, name="window", daemon=True),
        threading.Thread(target=run_news, kwargs={"stop_event": stop, "interval": 3600}, name="news", daemon=True),
        threading.Thread(target=run_cn_news, kwargs={"stop_event": stop, "interval": 3600}, name="cn_news", daemon=True),
        threading.Thread(target=run_mail, kwargs={"stop_event": stop, "interval": 3600}, name="mail", daemon=True),
        threading.Thread(target=_daily_aggregator, args=(stop,), name="agg", daemon=True),
    ]

    for t in threads:
        t.start()
    log.info("all %d threads started", len(threads))

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("received Ctrl+C, stopping...")
        stop.set()
        for t in threads:
            t.join(timeout=5)
        log.info("agent stopped")


if __name__ == "__main__":
    main()
