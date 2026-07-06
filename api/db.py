import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "dayp.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS app_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT NOT NULL,
    date          TEXT NOT NULL,
    process_name  TEXT NOT NULL,
    window_title  TEXT,
    duration_sec  INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_app_usage_date ON app_usage(date);
CREATE INDEX IF NOT EXISTS idx_app_usage_proc ON app_usage(process_name);

CREATE TABLE IF NOT EXISTS daily_summary (
    date          TEXT NOT NULL,
    process_name  TEXT NOT NULL,
    total_sec     INTEGER NOT NULL DEFAULT 0,
    pct           REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (date, process_name)
);

CREATE TABLE IF NOT EXISTS emails (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id      TEXT UNIQUE,
    subject       TEXT,
    sender        TEXT,
    snippet       TEXT,
    received_at   TEXT,
    fetched_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at);

CREATE TABLE IF NOT EXISTS news (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    hn_id         TEXT UNIQUE,
    title         TEXT,
    url           TEXT,
    score         INTEGER DEFAULT 0,
    by            TEXT,
    time          TEXT,
    source        TEXT NOT NULL DEFAULT 'hn',
    fetched_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_news_time ON news(time);
"""

_MIGRATIONS = [
    ("ALTER TABLE news ADD COLUMN source TEXT NOT NULL DEFAULT 'hn'", False),
    ("CREATE INDEX IF NOT EXISTS idx_news_source ON news(source)", True),
]


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        for stmt, _ in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        conn.commit()
    finally:
        conn.close()


def aggregate_daily(date_str: str | None = None) -> int:
    from datetime import datetime, timedelta
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT process_name, SUM(duration_sec) AS total "
            "FROM app_usage WHERE date = ? GROUP BY process_name",
            (date_str,),
        ).fetchall()
        if not rows:
            return 0
        grand = sum(r["total"] for r in rows) or 1
        conn.execute("DELETE FROM daily_summary WHERE date = ?", (date_str,))
        conn.executemany(
            "INSERT INTO daily_summary(date, process_name, total_sec, pct) "
            "VALUES(?,?,?,?)",
            [
                (date_str, r["process_name"], r["total"], round(r["total"] * 100.0 / grand, 2))
                for r in rows
            ],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"[db] initialized at {DB_PATH}")
