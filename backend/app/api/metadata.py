"""元数据管理与数据库数据源接入接口（管理员）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.session import get_db
from app.models.datasource import Datasource, MetaColumn, MetaTable
from app.schemas.auth import CurrentUser
from app.schemas.metadata import DbDatasourceCreate, MetaColumnUpdate, MetaTableUpdate
from app.services import db_service
from app.services.metadata_service import register_db_tables

router = APIRouter(prefix="/api", tags=["metadata"])


@router.post("/datasources/db")
def register_db_datasource(
    body: DbDatasourceCreate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    """接入业务数据库：测试连接 → 拉取表结构 → 登记元数据（只读）。"""
    try:
        db_service.test_connection(body.url)
        table_names = db_service.list_tables(body.url)
        tables_info = []
        for name in table_names:
            cols = db_service.get_columns(body.url, name)
            tables_info.append({"table_name": name, "columns": cols})
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(400, f"数据库连接失败: {e}") from e

    ds = register_db_tables(db, user.id, body.name, body.url, tables_info)
    table_count = db.query(MetaTable).filter(MetaTable.datasource_id == ds.id).count()
    return {
        "datasource_id": ds.id,
        "name": ds.name,
        "table_count": table_count,
        "tables": tables_info,
    }


@router.get("/metadata/tables")
def metadata_tables(
    datasource_id: int | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    """数据字典：表与字段全量（可按数据源过滤）。"""
    q = db.query(MetaTable)
    if datasource_id is not None:
        q = q.filter(MetaTable.datasource_id == datasource_id)
    tables = q.order_by(MetaTable.datasource_id, MetaTable.id).all()
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
                "datasource_id": t.datasource_id,
                "table_name": t.table_name,
                "sheet_name": t.sheet_name,
                "business_name": t.business_name,
                "row_count": t.row_count,
                "columns": [
                    {
                        "id": c.id,
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


@router.patch("/metadata/tables/{table_id}")
def update_table(
    table_id: int,
    body: MetaTableUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    t = db.get(MetaTable, table_id)
    if t is None:
        raise HTTPException(404, "表不存在")
    t.business_name = body.business_name
    db.commit()
    return {"id": t.id, "business_name": t.business_name}


@router.patch("/metadata/columns/{column_id}")
def update_column(
    column_id: int,
    body: MetaColumnUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_admin),
):
    c = db.get(MetaColumn, column_id)
    if c is None:
        raise HTTPException(404, "字段不存在")
    if body.business_name is not None:
        c.business_name = body.business_name
    if body.role is not None:
        c.role = body.role
        if body.role == "dim":
            c.default_agg = ""
    if body.default_agg is not None:
        c.default_agg = body.default_agg
    db.commit()
    return {
        "id": c.id,
        "business_name": c.business_name,
        "role": c.role,
        "default_agg": c.default_agg,
    }
