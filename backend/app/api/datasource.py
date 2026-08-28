"""数据源与表预览接口。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.datasource import Datasource, MetaColumn, MetaTable
from app.schemas.auth import CurrentUser
from app.services import db_service, duckdb_service

router = APIRouter(prefix="/api", tags=["datasource"])


@router.get("/datasources")
def list_datasources(
    db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    ds_list = db.query(Datasource).order_by(Datasource.id.desc()).all()
    return [
        {
            "id": d.id,
            "name": d.name,
            "type": d.type,
            "status": d.status,
            "created_by": d.created_by,
            "created_at": d.created_at,
        }
        for d in ds_list
    ]


@router.get("/datasources/{ds_id}/tables")
def list_tables(
    ds_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    ds = db.get(Datasource, ds_id)
    if ds is None:
        raise HTTPException(404, "数据源不存在")
    tables = db.query(MetaTable).filter(MetaTable.datasource_id == ds_id).order_by(MetaTable.id).all()
    result = []
    for t in tables:
        cols = (
            db.query(MetaColumn)
            .filter(MetaColumn.table_id == t.id)
            .order_by(MetaColumn.column_order)
            .all()
        )
        result.append(
            {
                "id": t.id,
                "table_name": t.table_name,
                "sheet_name": t.sheet_name,
                "business_name": t.business_name,
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
    return result


@router.get("/tables/{table_id}/preview")
def preview_table(
    table_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    t = db.get(MetaTable, table_id)
    if t is None:
        raise HTTPException(404, "表不存在")

    ds = db.get(Datasource, t.datasource_id)
    if ds.type == "excel":
        if not duckdb_service.table_exists(t.table_name):
            raise HTTPException(404, "物理表不存在，可能已被清理")
        phys_cols, rows = duckdb_service.preview(t.table_name, limit)
    else:
        # 业务库表：只读预览
        try:
            phys_cols, rows = db_service.read_table_preview(ds.id, ds.conn_info, t.table_name, limit)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:
            raise HTTPException(400, f"业务库查询失败: {e}") from e

    cols_meta = (
        db.query(MetaColumn)
        .filter(MetaColumn.table_id == t.id)
        .order_by(MetaColumn.column_order)
        .all()
    )
    col_by_name = {c.column_name: c for c in cols_meta}
    columns = [
        {
            "name": name,
            "business_name": col_by_name[name].business_name if name in col_by_name else name,
            "data_type": col_by_name[name].data_type if name in col_by_name else "VARCHAR",
        }
        for name in phys_cols
    ]
    return {"table_id": t.id, "table_name": t.table_name, "columns": columns, "rows": rows}
