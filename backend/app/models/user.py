"""SQLAlchemy 模型：阶段 1 仅用户表（RBAC 基础）。"""
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    # 角色：employee 普通员工 / dept_admin 部门管理员 / admin 系统管理员
    role: Mapped[str] = mapped_column(String(32), default="employee")
    dept: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
