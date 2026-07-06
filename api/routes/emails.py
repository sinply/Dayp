import subprocess
from datetime import datetime, timedelta
from fastapi import APIRouter, Query, HTTPException

from api.db import get_conn

router = APIRouter(prefix="/api/emails", tags=["emails"])


@router.get("")
def list_emails(days: int = Query(7, ge=1, le=90)):
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT entry_id, subject, sender, snippet, received_at, fetched_at "
            "FROM emails WHERE received_at >= ? OR received_at = '' "
            "ORDER BY received_at DESC LIMIT 200",
            (cutoff,),
        ).fetchall()
        return {
            "count": len(rows),
            "days": days,
            "emails": [dict(r) for r in rows],
        }
    finally:
        conn.close()


@router.get("/{entry_id}/open")
def open_email(entry_id: str):
    """Open an email in Outlook by EntryID via COM automation."""
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
            namespace = outlook.GetNamespace("MAPI")
            try:
                msg = namespace.GetItemFromID(entry_id)
            except Exception as e:
                raise HTTPException(status_code=404, detail=f"邮件未找到: {e}")
            msg.Display()
            return {"status": "ok", "subject": msg.Subject}
        finally:
            pythoncom.CoUninitialize()
    except ImportError:
        raise HTTPException(status_code=500, detail="pywin32 未安装，无法打开邮件")
