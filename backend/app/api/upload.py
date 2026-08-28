"""文件上传接口：Excel → 解析 → DuckDB 导入 → 元数据登记。"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.datasource import Datasource, MetaColumn, MetaTable
from app.schemas.auth import CurrentUser
from app.services import duckdb_service
from app.services.audit_service import audit
from app.services.excel_service import parse_excel
from app.services.metadata_service import register_excel_datasource

router = APIRouter(prefix="/api/upload", tags=["upload"])

_ALLOWED_EXT = {".xlsx"}


@router.post("")
def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    settings = get_settings()

    filename = file.filename or ""
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in _ALLOWED_EXT:
        raise HTTPException(400, "仅支持 .xlsx 文件")

    content = file.file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(400, f"文件超过大小限制 {settings.MAX_UPLOAD_MB}MB")

    try:
        sheets = parse_excel(content)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not sheets:
        raise HTTPException(400, "Excel 中没有可解析的数据表")

    ds = register_excel_datasource(db, user.id, filename, sheets)
    audit(db, user.id, user.username, "upload", f"上传 {filename}，{len(sheets)} 个 sheet", commit=True)

    # 导入 DuckDB；失败则标记数据源失败
    try:
        for idx, sheet in enumerate(sheets):
            duckdb_service.create_table(f"up_{ds.id}_{idx}", sheet.df)
    except Exception:
        ds.status = "failed"
        db.commit()
        raise HTTPException(500, "数据导入失败")

    tables = (
        db.query(MetaTable)
        .filter(MetaTable.datasource_id == ds.id)
        .order_by(MetaTable.id)
        .all()
    )
    result_tables = []
    for t in tables:
        cols = (
            db.query(MetaColumn)
            .filter(MetaColumn.table_id == t.id)
            .order_by(MetaColumn.column_order)
            .all()
        )
        result_tables.append(
            {
                "id": t.id,
                "table_name": t.table_name,
                "sheet_name": t.sheet_name,
                "row_count": t.row_count,
                "columns": [
                    {
                        "name": c.column_name,
                        "business_name": c.business_name,
                        "data_type": c.data_type,
                        "role": c.role,
                        "default_agg": c.default_agg,
                    }
                    for c in cols
                ],
            }
        )
    return {"datasource_id": ds.id, "name": ds.name, "tables": result_tables}
