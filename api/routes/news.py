from fastapi import APIRouter, Query

from api.db import get_conn

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
def list_news(
    limit: int = Query(30, ge=1, le=100),
    source: str = Query("", description=" Filter by source: hn, 36kr, leiphone, or empty for all"),
):
    conn = get_conn()
    try:
        if source:
            rows = conn.execute(
                "SELECT hn_id, title, url, score, by, time, source, fetched_at "
                "FROM news WHERE source = ? ORDER BY time DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT hn_id, title, url, score, by, time, source, fetched_at "
                "FROM news ORDER BY time DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {
            "count": len(rows),
            "items": [dict(r) for r in rows],
        }
    finally:
        conn.close()
