"""审计日志查询接口（仅管理员）。"""
from app.api.auth import require_admin
from app.db.session import get_db
from app.models.audit import AuditLog
from app.schemas.auth import CurrentUser
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit(
    action: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    q = db.query(AuditLog).order_by(AuditLog.id.desc())
    if action:
        q = q.filter(AuditLog.action == action)
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "username": a.username,
            "action": a.action,
            "detail": a.detail,
            "ip": a.ip,
            "created_at": a.created_at,
        }
        for a in q.limit(limit).all()
    ]
