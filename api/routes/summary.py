from datetime import datetime, timedelta
from fastapi import APIRouter

from api.db import get_conn

router = APIRouter(prefix="/api/summary", tags=["summary"])


def _fmt(sec: int) -> str:
    h, rem = divmod(sec, 3600)
    m, _ = divmod(rem, 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


@router.get("/week")
def week_summary():
    end = datetime.now()
    start = end - timedelta(days=6)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    conn = get_conn()
    try:
        usage_rows = conn.execute(
            "SELECT process_name, SUM(total_sec) AS total "
            "FROM daily_summary WHERE date >= ? AND date <= ? "
            "GROUP BY process_name ORDER BY total DESC",
            (start_str, end_str),
        ).fetchall()

        today_rows = conn.execute(
            "SELECT process_name, SUM(duration_sec) AS total "
            "FROM app_usage WHERE date = ? GROUP BY process_name",
            (end_str,),
        ).fetchall()

        today_map = {r["process_name"]: r["total"] for r in today_rows}
        merged: dict[str, int] = {}
        for r in usage_rows:
            merged[r["process_name"]] = merged.get(r["process_name"], 0) + r["total"]
        for proc, total in today_map.items():
            merged[proc] = merged.get(proc, 0) + total

        top = sorted(merged.items(), key=lambda x: x[1], reverse=True)
        grand_total = sum(v for _, v in top) or 1

        email_rows = conn.execute(
            "SELECT COUNT(*) AS cnt, "
            "GROUP_CONCAT(subject, '||') AS subjects "
            "FROM emails WHERE received_at >= ? OR received_at = ''",
            (start_str,),
        ).fetchone()
        email_count = email_rows["cnt"] if email_rows else 0

        news_rows = conn.execute(
            "SELECT COUNT(*) AS cnt FROM news WHERE fetched_at >= ?",
            (start_str,),
        ).fetchone()
        news_count = news_rows["cnt"] if news_rows else 0
    finally:
        conn.close()

    lines = []
    lines.append(f"周报（{start_str} ~ {end_str}）")
    lines.append("=" * 40)
    lines.append("")
    lines.append(f"本周总活跃时长：{_fmt(grand_total)}")
    lines.append("")
    lines.append("Top 5 使用软件：")
    for i, (proc, sec) in enumerate(top[:5], 1):
        pct = round(sec * 100.0 / grand_total, 1)
        lines.append(f"  {i}. {proc} - {_fmt(sec)}（{pct}%）")
    lines.append("")
    lines.append(f"本周收到邮件：{email_count} 封")
    if email_rows and email_rows["subjects"]:
        subjects = [s for s in email_rows["subjects"].split("||") if s][:5]
        if subjects:
            lines.append("近期邮件主题示例：")
            for s in subjects:
                lines.append(f"  - {s[:60]}")
    lines.append("")
    lines.append(f"本周抓取 AI 新闻：{news_count} 条")
    lines.append("")
    lines.append("-" * 40)
    text = "\n".join(lines)

    return {
        "range": {"start": start_str, "end": end_str},
        "total_sec": grand_total,
        "total_fmt": _fmt(grand_total),
        "top_apps": [
            {"process_name": p, "total_sec": s, "pct": round(s * 100.0 / grand_total, 2)}
            for p, s in top[:10]
        ],
        "email_count": email_count,
        "news_count": news_count,
        "text": text,
    }
