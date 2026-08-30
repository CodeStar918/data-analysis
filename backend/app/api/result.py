"""结果接口：列表、预览、导出 Excel/CSV。"""
import io
from urllib.parse import quote

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.job import ResultTable
from app.schemas.auth import CurrentUser
from app.services import duckdb_service
from app.services.audit_service import audit
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/results", tags=["result"])


def _get_result(db: Session, result_id: int, user: CurrentUser) -> ResultTable:
    rt = db.get(ResultTable, result_id)
    if rt is None or (rt.created_by != user.id and user.role != "admin"):
        raise HTTPException(404, "结果不存在")
    return rt


@router.get("")
def list_results(
    db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    q = db.query(ResultTable).order_by(ResultTable.id.desc())
    if user.role != "admin":
        q = q.filter(ResultTable.created_by == user.id)
    return [
        {
            "id": r.id,
            "job_id": r.job_id,
            "table_name": r.table_name,
            "result_type": r.result_type,
            "business_name": r.business_name,
            "row_count": r.row_count,
            "applied_to_source": r.applied_to_source,
            "created_at": r.created_at,
        }
        for r in q.all()
    ]


@router.get("/{result_id}/preview")
def preview_result(
    result_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    rt = _get_result(db, result_id, user)
    if not duckdb_service.table_exists(rt.table_name):
        raise HTTPException(404, "结果表不存在，可能已被清理")
    cols, rows = duckdb_service.preview(rt.table_name, limit)
    return {
        "result_id": rt.id,
        "table_name": rt.table_name,
        "columns": [{"name": c} for c in cols],
        "rows": rows,
    }


@router.get("/{result_id}/export")
def export_result(
    result_id: int,
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """导出完整结果（不受预览行数限制）。"""
    rt = _get_result(db, result_id, user)
    if not duckdb_service.table_exists(rt.table_name):
        raise HTTPException(404, "结果表不存在，可能已被清理")

    df = duckdb_service.fetch_df(rt.table_name)
    audit(db, user.id, user.username, "export", f"导出 {rt.table_name} ({format})", commit=True)
    filename = f"{rt.table_name}.{format}"

    if format == "csv":
        buf = io.StringIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        media = "text/csv; charset=utf-8"
        payload = buf.getvalue().encode("utf-8-sig")
    else:
        buf = io.BytesIO()
        df.to_excel(buf, index=False, engine="openpyxl")
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        payload = buf.getvalue()

    return StreamingResponse(
        io.BytesIO(payload),
        media_type=media,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
