"""数据源与元数据模型（阶段 2：Excel 数据源登记；阶段 3 扩展管理功能）。"""
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Datasource(Base):
    __tablename__ = "datasource"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    # 类型：excel / db
    type: Mapped[str] = mapped_column(String(16))
    # excel 存原始文件名；db 存加密连接串（阶段 3）
    conn_info: Mapped[str] = mapped_column(Text, default="")
    # 状态：ready / failed
    status: Mapped[str] = mapped_column(String(16), default="ready")
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MetaTable(Base):
    __tablename__ = "meta_table"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    datasource_id: Mapped[int] = mapped_column(ForeignKey("datasource.id"), index=True)
    # 物理表名（DuckDB 中）
    table_name: Mapped[str] = mapped_column(String(128), unique=True)
    sheet_name: Mapped[str] = mapped_column(String(128), default="")
    business_name: Mapped[str] = mapped_column(String(128), default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class MetaColumn(Base):
    __tablename__ = "meta_column"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    table_id: Mapped[int] = mapped_column(ForeignKey("meta_table.id"), index=True)
    # 物理列名
    column_name: Mapped[str] = mapped_column(String(128))
    # 业务名称（Excel 原表头），阶段 3 可维护
    business_name: Mapped[str] = mapped_column(String(128), default="")
    # DuckDB 类型
    data_type: Mapped[str] = mapped_column(String(32), default="VARCHAR")
    # 维度/度量：dim / measure（阶段 3 维护，Excel 先按类型预判）
    role: Mapped[str] = mapped_column(String(16), default="dim")
    default_agg: Mapped[str] = mapped_column(String(16), default="")
    column_order: Mapped[int] = mapped_column(Integer, default=0)
