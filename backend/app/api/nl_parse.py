"""自然语言解析接口：解析 → 校验 → SQL 预览 → 用户确认。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.datasource import MetaColumn, MetaTable
from app.models.parse_history import ParseHistory
from app.schemas.auth import CurrentUser
from app.schemas.nl import ConfirmRequest, ParseRequest
from app.services import ollama_service
from app.services.audit_service import audit
from app.services.nl_parser import TableMeta, build_prompt, validate
from app.services.ollama_service import OllamaError
from app.services.sql_builder import build_select_sql

router = APIRouter(prefix="/api/nl", tags=["nl"])


def _load_table_meta(db: Session, table_id: int) -> tuple[MetaTable, TableMeta]:
    t = db.get(MetaTable, table_id)
    if t is None:
        raise HTTPException(404, "表不存在")
    cols = (
        db.query(MetaColumn)
        .filter(MetaColumn.table_id == t.id)
        .order_by(MetaColumn.column_order)
        .all()
    )
    meta = TableMeta(
        table_name=t.table_name,
        business_name=t.business_name,
        columns=[
            {
                "name": c.column_name,
                "business_name": c.business_name,
                "data_type": c.data_type,
                "role": c.role,
                "default_agg": c.default_agg,
            }
            for c in cols
        ],
    )
    return t, meta


@router.post("/parse")
def parse_question(
    body: ParseRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """自然语言 → 结构化解析结果（LLM 输出经白名单校验）。"""
    t, meta = _load_table_meta(db, body.table_id)

    system, prompt = build_prompt(meta, body.question)
    try:
        raw = ollama_service.chat_json(system, prompt)
    except OllamaError as e:
        raise HTTPException(502, str(e)) from e

    result, errors = validate(raw, meta)
    sql_preview = ""
    if result is not None:
        try:
            sql_preview = build_select_sql(meta, result)
        except ValueError as e:
            errors.append(f"SQL 构建失败: {e}")
            result = None

    history = ParseHistory(
        user_id=user.id,
        datasource_id=t.datasource_id,
        table_id=t.id,
        question=body.question,
        parse_json=json.dumps(raw, ensure_ascii=False) if isinstance(raw, dict) else str(raw),
        sql_preview=sql_preview,
        valid=result is not None,
        error_msg="；".join(errors),
    )
    db.add(history)
    db.commit()
    audit(db, user.id, user.username, "parse", f"{body.question}（校验{'通过' if result is not None else '未通过'}）", commit=True)

    if result is None:
        return {"parse_id": history.id, "valid": False, "errors": errors, "raw": raw}
    return {
        "parse_id": history.id,
        "valid": True,
        "result": result.model_dump(),
        "sql_preview": sql_preview,
    }


@router.post("/confirm")
def confirm_parse(
    body: ConfirmRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """用户确认解析结果（阶段 5 执行任务的前置条件）。"""
    history = db.get(ParseHistory, body.parse_id)
    if history is None:
        raise HTTPException(404, "解析记录不存在")
    if history.user_id != user.id:
        raise HTTPException(403, "只能确认自己的解析记录")
    if not history.valid:
        raise HTTPException(400, "解析结果未通过校验，无法确认")
    history.confirmed = True
    db.commit()
    audit(db, user.id, user.username, "parse_confirm", f"确认解析 #{history.id}", commit=True)
    return {"parse_id": history.id, "confirmed": True}
