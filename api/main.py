import os
import time
import threading
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.db import init_db, aggregate_daily
from agent.window_tracker import run_loop as run_window
from agent.news_fetcher import run_loop as run_news
from agent.cn_news_fetcher import run_loop as run_cn_news
from agent.mail_fetcher import run_loop as run_mail
from api.routes import usage, emails, news, summary

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

log = logging.getLogger("dayp")

app = FastAPI(title="Dayp", version="0.1.0")

app.include_router(usage.router)
app.include_router(emails.router)
app.include_router(news.router)
app.include_router(summary.router)

_agent_stop: threading.Event | None = None
_agent_threads: list[threading.Thread] = []

_last_heartbeat: float = 0.0
_heartbeat_lock = threading.Lock()
_HEARTBEAT_TIMEOUT = 15.0
_autostop_thread: threading.Thread | None = None
_autostop_stop: threading.Event | None = None


def _now_ts() -> float:
    return time.monotonic()


def _touch_heartbeat() -> None:
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = _now_ts()


def _autostop_loop(stop_event: threading.Event) -> None:
    log.info("autostop monitor started, timeout=%.0fs", _HEARTBEAT_TIMEOUT)
    while not stop_event.is_set():
        stop_event.wait(3)
        if stop_event.is_set():
            break
        with _heartbeat_lock:
            elapsed = _now_ts() - _last_heartbeat
        if elapsed >= _HEARTBEAT_TIMEOUT:
            log.warning("no heartbeat for %.1fs, shutting down", elapsed)
            _shutdown_and_exit()
            return
    log.info("autostop monitor stopped")


def _shutdown_and_exit() -> None:
    _stop_agent()
    os._exit(0)


def _daily_aggregator(stop_event: threading.Event) -> None:
    import time
    from datetime import datetime, timedelta
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


def _start_agent() -> None:
    global _agent_stop, _agent_threads, _autostop_thread, _autostop_stop
    _agent_stop = threading.Event()
    _agent_threads = [
        threading.Thread(target=run_window, kwargs={"stop_event": _agent_stop}, name="window", daemon=True),
        threading.Thread(target=run_news, kwargs={"stop_event": _agent_stop, "interval": 3600}, name="news", daemon=True),
        threading.Thread(target=run_cn_news, kwargs={"stop_event": _agent_stop, "interval": 3600}, name="cn_news", daemon=True),
        threading.Thread(target=run_mail, kwargs={"stop_event": _agent_stop, "interval": 3600}, name="mail", daemon=True),
        threading.Thread(target=_daily_aggregator, args=(_agent_stop,), name="agg", daemon=True),
    ]
    for t in _agent_threads:
        t.start()
    log.info("agent started: %d threads", len(_agent_threads))

    _touch_heartbeat()
    _autostop_stop = threading.Event()
    _autostop_thread = threading.Thread(
        target=_autostop_loop, args=(_autostop_stop,), name="autostop", daemon=True
    )
    _autostop_thread.start()


def _stop_agent() -> None:
    global _agent_stop, _agent_threads, _autostop_stop
    if _autostop_stop is not None:
        _autostop_stop.set()
    if _agent_stop is not None:
        _agent_stop.set()
        for t in _agent_threads:
            t.join(timeout=5)
        log.info("agent stopped")
    _agent_threads = []
    _agent_stop = None


@app.on_event("startup")
def _startup():
    init_db()
    log.info("database initialized")
    _start_agent()
    try:
        import webbrowser
        webbrowser.open("http://127.0.0.1:8000")
    except Exception as e:
        log.warning("open browser failed: %s", e)


@app.on_event("shutdown")
def _shutdown():
    _stop_agent()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/heartbeat")
def heartbeat():
    _touch_heartbeat()
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(WEB_DIR / "index.html"))
