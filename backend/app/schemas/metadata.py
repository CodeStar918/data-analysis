"""元数据与数据源管理的 Pydantic 模型。"""
from pydantic import BaseModel, Field


class DbDatasourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, description="数据源名称")
    url: str = Field(min_length=1, description="SQLAlchemy 连接串，如 postgresql+psycopg://user:pwd@host:5432/db")


class MetaTableUpdate(BaseModel):
    business_name: str = Field(min_length=1, max_length=128)


class MetaColumnUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: str | None = Field(default=None, pattern="^(dim|measure)$")
    default_agg: str | None = Field(default=None, pattern="^(SUM|COUNT|AVG|MAX|MIN|)$")
