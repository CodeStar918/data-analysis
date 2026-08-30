"""NL 解析历史模型。"""
from datetime import UTC, datetime

from app.models.user import Base
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column


class ParseHistory(Base):
    __tablename__ = "parse_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    datasource_id: Mapped[int] = mapped_column(ForeignKey("datasource.id"), index=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("meta_table.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    parse_json: Mapped[str] = mapped_column(Text, default="")
    sql_preview: Mapped[str] = mapped_column(Text, default="")
    # 校验是否通过
    valid: Mapped[bool] = mapped_column(Boolean, default=False)
    error_msg: Mapped[str] = mapped_column(Text, default="")
    # 用户是否已确认（确认后阶段 5 才允许执行）
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
