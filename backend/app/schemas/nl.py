"""Pydantic 模型：NL 解析接口。"""
from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    table_id: int = Field(description="目标表 ID")
    question: str = Field(min_length=1, max_length=500, description="自然语言需求")


class ConfirmRequest(BaseModel):
    parse_id: int
