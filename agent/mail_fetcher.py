import time
import logging
from datetime import datetime, timedelta

import win32com.client
import pythoncom

from api.db import get_conn

log = logging.getLogger(__name__)

DEFAULT_DAYS = 7
SNIPPET_LEN = 200


def _to_iso(dt) -> str:
    try:
        return dt.strftime("%Y-%m-%dT%H:%M:%S")
    except (AttributeError, ValueError):
        return ""


def _snippet(body: str) -> str:
    if not body:
        return ""
    text = body.replace("\r", " ").replace("\n", " ").strip()
    return text[:SNIPPET_LEN]


def fetch_once(days: int = DEFAULT_DAYS) -> int:
    log.info("fetching emails via Outlook COM, days=%d", days)
    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)
        messages = inbox.Items
        messages.Sort("[ReceivedTime]", True)

        cutoff = datetime.now() - timedelta(days=days)
        cutoff_naive = cutoff.replace(tzinfo=None)

        collected = []
        count = 0
        for msg in messages:
            try:
                rt = msg.ReceivedTime
            except AttributeError:
                continue
            try:
                rt_naive = datetime(rt.year, rt.month, rt.day, rt.hour, rt.minute, rt.second)
            except AttributeError:
                continue
            if rt_naive < cutoff_naive:
                break
            entry_id = ""
            try:
                entry_id = msg.EntryID or ""
            except AttributeError:
                pass
            subject = ""
            sender = ""
            snippet = ""
            try:
                subject = msg.Subject or ""
            except AttributeError:
                pass
            try:
                sender = msg.SenderName or ""
            except AttributeError:
                pass
            try:
                snippet = _snippet(msg.Body or "")
            except AttributeError:
                pass
            collected.append({
                "entry_id": entry_id,
                "subject": subject,
                "sender": sender,
                "snippet": snippet,
                "received_at": _to_iso(rt),
            })
            count += 1
            if count >= 500:
                break

        saved = _save(collected)
        log.info("fetched %d emails, saved %d new", len(collected), saved)
        return saved
    except Exception as e:
        log.error("Outlook COM error: %s", e)
        return 0
    finally:
        pythoncom.CoUninitialize()


def _save(items: list[dict]) -> int:
    if not items:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    try:
        conn.executemany(
            "INSERT OR IGNORE INTO emails(entry_id, subject, sender, snippet, received_at, fetched_at) "
            "VALUES(?,?,?,?,?,?)",
            [
                (
                    it["entry_id"],
                    it["subject"],
                    it["sender"],
                    it["snippet"],
                    it["received_at"],
                    now,
                )
                for it in items
            ],
        )
        conn.commit()
        return conn.total_changes
    finally:
        conn.close()


def run_loop(interval: int = 3600, stop_event=None) -> None:
    log.info("mail_fetcher started, interval=%ds", interval)
    while True:
        if stop_event is not None and stop_event.is_set():
            log.info("mail_fetcher stop signal received")
            break
        try:
            fetch_once()
        except Exception as e:
            log.error("mail_fetcher error: %s", e)
        if stop_event is not None:
            stop_event.wait(interval)
            if stop_event.is_set():
                break
        else:
            time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    n = fetch_once(days=7)
    print(f"saved {n} new emails")
