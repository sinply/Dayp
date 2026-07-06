from datetime import datetime, timedelta
from fastapi import APIRouter, Query

from api.db import get_conn

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _fmt_duration(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    if m > 0:
        return f"{m}m{s:02d}s"
    return f"{s}s"


@router.get("/today")
def today():
    date_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT process_name, SUM(duration_sec) AS total, COUNT(*) AS samples "
            "FROM app_usage WHERE date = ? GROUP BY process_name ORDER BY total DESC",
            (date_str,),
        ).fetchall()
        total = sum(r["total"] for r in rows) or 1
        return {
            "date": date_str,
            "total_sec": sum(r["total"] for r in rows),
            "total_fmt": _fmt_duration(sum(r["total"] for r in rows)),
            "apps": [
                {
                    "process_name": r["process_name"],
                    "total_sec": r["total"],
                    "total_fmt": _fmt_duration(r["total"]),
                    "pct": round(r["total"] * 100.0 / total, 2),
                    "samples": r["samples"],
                }
                for r in rows
            ],
        }
    finally:
        conn.close()


@router.get("/week")
def week():
    end = datetime.now()
    start = end - timedelta(days=6)
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT date, process_name, total_sec FROM daily_summary "
            "WHERE date >= ? AND date <= ? ORDER BY date, total_sec DESC",
            (dates[0], dates[-1]),
        ).fetchall()
        today_rows = conn.execute(
            "SELECT date, process_name, SUM(duration_sec) AS total_sec "
            "FROM app_usage WHERE date = ? GROUP BY date, process_name",
            (end.strftime("%Y-%m-%d"),),
        ).fetchall()
    finally:
        conn.close()

    by_date: dict[str, dict[str, int]] = {d: {} for d in dates}
    for r in rows:
        if r["date"] in by_date:
            by_date[r["date"]][r["process_name"]] = r["total_sec"]
    for r in today_rows:
        by_date[r["date"]][r["process_name"]] = r["total_sec"]

    all_procs = set()
    for d in dates:
        all_procs.update(by_date[d].keys())
    all_procs = sorted(all_procs)

    return {
        "dates": dates,
        "processes": all_procs,
        "series": [
            {"process_name": p, "data": [by_date[d].get(p, 0) for d in dates]}
            for p in all_procs
        ],
    }


@router.get("/date/{date_str}")
def by_date(date_str: str):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT process_name, SUM(duration_sec) AS total, COUNT(*) AS samples "
            "FROM app_usage WHERE date = ? GROUP BY process_name ORDER BY total DESC",
            (date_str,),
        ).fetchall()
        total = sum(r["total"] for r in rows) or 1
        return {
            "date": date_str,
            "total_sec": sum(r["total"] for r in rows),
            "total_fmt": _fmt_duration(sum(r["total"] for r in rows)),
            "apps": [
                {
                    "process_name": r["process_name"],
                    "total_sec": r["total"],
                    "total_fmt": _fmt_duration(r["total"]),
                    "pct": round(r["total"] * 100.0 / total, 2),
                    "samples": r["samples"],
                }
                for r in rows
            ],
        }
    finally:
        conn.close()
