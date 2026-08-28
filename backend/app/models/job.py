"""异步任务与结果表模型（阶段 5）。"""
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Job(Base):
    __tablename__ = "job"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parse_id: Mapped[int] = mapped_column(ForeignKey("parse_history.id"), index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    # aggregate / add_column
    job_type: Mapped[str] = mapped_column(String(16))
    # pending / running / success / failed
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    result_table_id: Mapped[int | None] = mapped_column(Integer, default=None)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ResultTable(Base):
    __tablename__ = "result_table"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("job.id"), index=True)
    # 结果库物理表名：rpt_{job_id}_{时间戳}
    table_name: Mapped[str] = mapped_column(String(128), unique=True)
    # aggregate / add_column
    result_type: Mapped[str] = mapped_column(String(16))
    business_name: Mapped[str] = mapped_column(String(256), default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    # 明细结果是否已通过审批写回原表
    applied_to_source: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
