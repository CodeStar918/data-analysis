"""任务接口：提交统计任务、查询状态。"""
import json

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.job import Job
from app.models.parse_history import ParseHistory
from app.schemas.auth import CurrentUser
from app.services import job_service
from app.services.audit_service import audit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/jobs", tags=["job"])


class JobCreate(BaseModel):
    parse_id: int = Field(description="已确认的解析记录 ID")


@router.post("")
def create_job(
    body: JobCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """提交已确认的解析结果为异步统计任务。"""
    history = db.get(ParseHistory, body.parse_id)
    if history is None:
        raise HTTPException(404, "解析记录不存在")
    if history.user_id != user.id:
        raise HTTPException(403, "只能执行自己的解析记录")
    if not history.valid or not history.confirmed:
        raise HTTPException(400, "解析结果未确认或未通过校验")

    intent = json.loads(history.parse_json).get("intent", "aggregate")
    job = Job(
        parse_id=history.id,
        user_id=user.id,
        job_type=intent,
        status="pending",
    )
    db.add(job)
    db.commit()
    audit(db, user.id, user.username, "job_create", f"{intent} 任务（解析 #{history.id}）", commit=True)

    job_service.execute_job_task(job.id)

    db.refresh(job)
    return {"job_id": job.id, "status": job.status, "result_table_id": job.result_table_id}


@router.get("/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    job = db.get(Job, job_id)
    if job is None or (job.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "任务不存在")
    return {
        "job_id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "result_table_id": job.result_table_id,
        "error_msg": job.error_msg,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
    }
