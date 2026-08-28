"""审计服务：关键动作统一落审计日志。"""
from sqlalchemy.orm import Session

from app.core.logging import setup_logging
from app.models.audit import AuditLog

logger = setup_logging()


def audit(
    db: Session,
    user_id: int,
    username: str,
    action: str,
    detail: str = "",
    ip: str = "",
    commit: bool = False,
) -> None:
    """记录审计日志。默认随端点自身事务提交；无事务的端点传 commit=True。"""
    try:
        db.add(
            AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                detail=detail[:2000],
                ip=ip,
            )
        )
        if commit:
            db.commit()
    except Exception:  # 审计失败不阻断业务
        logger.exception("审计日志写入失败: %s", action)
