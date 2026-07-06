import time
import logging
from datetime import datetime

import win32gui
import win32process
import psutil

from api.db import get_conn

log = logging.getLogger(__name__)

SAMPLE_INTERVAL = 1.0


def _get_foreground_info() -> tuple[str, str]:
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return ("Idle", "")
    title = win32gui.GetWindowText(hwnd) or ""
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        proc = "Unknown"
    return (proc, title)


_IGNORED = {"Idle", "Unknown", "", None, "explorer.exe"}


def _is_valid(proc: str, title: str) -> bool:
    if proc in _IGNORED:
        return False
    return True


def track_once() -> dict | None:
    proc, title = _get_foreground_info()
    if not _is_valid(proc, title):
        return None
    now = datetime.now()
    return {
        "ts": now.isoformat(timespec="seconds"),
        "date": now.strftime("%Y-%m-%d"),
        "process_name": proc,
        "window_title": title,
        "duration_sec": 1,
    }


def _insert(record: dict) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO app_usage(ts, date, process_name, window_title, duration_sec) "
            "VALUES(?,?,?,?,?)",
            (
                record["ts"],
                record["date"],
                record["process_name"],
                record["window_title"],
                record["duration_sec"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def run_loop(stop_event=None) -> None:
    log.info("window_tracker started, interval=%.1fs", SAMPLE_INTERVAL)
    last_proc: str | None = None
    last_title: str | None = None
    accum_sec = 0
    last_ts: datetime | None = None

    while True:
        if stop_event is not None and stop_event.is_set():
            log.info("window_tracker stop signal received")
            break
        proc, title = _get_foreground_info()
        now = datetime.now()

        if proc == last_proc and title == last_title:
            accum_sec += 1
        else:
            if last_proc is not None and _is_valid(last_proc, last_title or "") and accum_sec > 0:
                _insert({
                    "ts": (last_ts or now).isoformat(timespec="seconds"),
                    "date": (last_ts or now).strftime("%Y-%m-%d"),
                    "process_name": last_proc,
                    "window_title": last_title or "",
                    "duration_sec": accum_sec,
                })
            last_proc = proc
            last_title = title
            last_ts = now
            accum_sec = 1 if _is_valid(proc, title) else 0

        time.sleep(SAMPLE_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    run_loop()
