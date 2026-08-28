"""写回审批接口：申请 → 管理员审批 → 执行写回。"""
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import get_current_user, require_admin
from app.db.session import get_db
from app.models.approval import Approval
from app.models.datasource import Datasource, MetaColumn, MetaTable
from app.models.job import Job, ResultTable
from app.models.parse_history import ParseHistory
from app.schemas.auth import CurrentUser
from app.services.approval_service import apply_writeback

router = APIRouter(prefix="/api/approvals", tags=["approval"])


class ApprovalCreate(BaseModel):
    job_id: int = Field(description="已完成的明细任务 ID")
    reason: str = Field(min_length=1, max_length=500, description="写回理由")


class ApprovalDecide(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    comment: str = Field(default="", max_length=500)


def _job_source_info(db: Session, job: Job):
    """返回 (meta_table, datasource, result_table)。"""
    rt = db.get(ResultTable, job.result_table_id)
    history = db.get(ParseHistory, job.parse_id)
    mt = db.get(MetaTable, history.table_id)
    ds = db.get(Datasource, mt.datasource_id)
    return mt, ds, rt


@router.post("")
def create_approval(
    body: ApprovalCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    job = db.get(Job, body.job_id)
    if job is None:
        raise HTTPException(404, "任务不存在")
    if job.user_id != user.id:
        raise HTTPException(403, "只能对自己的任务申请写回")
    if job.status != "success" or job.job_type != "add_column" or job.result_table_id is None:
        raise HTTPException(400, "仅成功完成的明细任务可申请写回")

    mt, ds, _rt = _job_source_info(db, job)
    if ds.type != "excel":
        raise HTTPException(400, "业务库数据源为只读，不支持写回原表")

    exists = (
        db.query(Approval)
        .filter(
            Approval.job_id == job.id,
            Approval.status.in_(["pending", "approved"]),
        )
        .first()
    )
    if exists:
        raise HTTPException(400, "该任务已有待审批或已通过的写回申请")

    approval = Approval(job_id=job.id, applicant=user.id, reason=body.reason)
    db.add(approval)
    db.commit()
    return {"approval_id": approval.id, "status": approval.status}


@router.get("")
def list_approvals(
    db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    q = db.query(Approval).order_by(Approval.id.desc())
    if user.role != "admin":
        q = q.filter(Approval.applicant == user.id)
    approvals = q.all()
    result = []
    for a in approvals:
        job = db.get(Job, a.job_id)
        rt = db.get(ResultTable, job.result_table_id) if job and job.result_table_id else None
        result.append(
            {
                "id": a.id,
                "job_id": a.job_id,
                "applicant": a.applicant,
                "approver": a.approver,
                "status": a.status,
                "reason": a.reason,
                "comment": a.comment,
                "error_msg": a.error_msg,
                "question": rt.business_name if rt else "",
                "created_at": a.created_at,
                "decided_at": a.decided_at,
            }
        )
    return result


@router.post("/{approval_id}/decide")
def decide(
    approval_id: int,
    body: ApprovalDecide,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    approval = db.get(Approval, approval_id)
    if approval is None:
        raise HTTPException(404, "审批记录不存在")
    if approval.status != "pending":
        raise HTTPException(400, "该审批已处理")

    approval.approver = user.id
    approval.comment = body.comment
    approval.decided_at = datetime.now(UTC)

    if body.action == "reject":
        approval.status = "rejected"
        db.commit()
        return {"approval_id": approval.id, "status": approval.status}

    # 审批通过 → 执行写回原表
    job = db.get(Job, approval.job_id)
    mt, ds, rt = _job_source_info(db, job)
    new_columns = json.loads(db.get(ParseHistory, job.parse_id).parse_json).get("new_columns", [])
    try:
        apply_writeback(mt.table_name, new_columns)
    except Exception as e:
        approval.status = "pending"  # 保持待审批，记录错误供排查
        approval.error_msg = f"写回失败: {e}"[:1000]
        db.commit()
        raise HTTPException(500, f"写回执行失败: {e}") from e

    # 登记新字段元数据
    for nc in new_columns:
        exists = (
            db.query(MetaColumn)
            .filter(MetaColumn.table_id == mt.id, MetaColumn.column_name == nc["name"])
            .first()
        )
        if exists is None:
            max_order = (
                db.query(func.max(MetaColumn.column_order))
                .filter(MetaColumn.table_id == mt.id)
                .scalar()
                or -1
            )
            db.add(
                MetaColumn(
                    table_id=mt.id,
                    column_name=nc["name"],
                    business_name=nc["name"],
                    data_type={"string": "VARCHAR", "number": "DOUBLE", "boolean": "BOOLEAN"}.get(
                        nc.get("type"), "VARCHAR"
                    ),
                    role="dim",
                    column_order=max_order + 1,
                )
            )
    rt.applied_to_source = True
    approval.status = "approved"
    db.commit()
    return {"approval_id": approval.id, "status": approval.status}
