"""元数据登记：数据源 → 表 → 字段。"""
from app.core.crypto import encrypt
from app.models.datasource import Datasource, MetaColumn, MetaTable
from app.services.excel_service import ParsedSheet
from sqlalchemy.orm import Session


def register_excel_datasource(
    db: Session, user_id: int, filename: str, sheets: list[ParsedSheet]
) -> Datasource:
    """登记 Excel 数据源及其表、字段元数据。"""
    ds = Datasource(name=filename, type="excel", conn_info=filename, status="ready", created_by=user_id)
    db.add(ds)
    db.flush()

    for idx, sheet in enumerate(sheets):
        table_name = f"up_{ds.id}_{idx}"
        mt = MetaTable(
            datasource_id=ds.id,
            table_name=table_name,
            sheet_name=sheet.sheet_name,
            business_name=sheet.sheet_name,
            row_count=len(sheet.df),
        )
        db.add(mt)
        db.flush()
        for order, col in enumerate(sheet.columns):
            db.add(
                MetaColumn(
                    table_id=mt.id,
                    column_name=col.name,
                    business_name=col.business_name or col.name,
                    data_type=col.data_type,
                    role=col.role,
                    default_agg=col.default_agg,
                    column_order=order,
                )
            )
    db.commit()
    db.refresh(ds)
    return ds


def register_db_tables(
    db: Session, user_id: int, name: str, url: str, tables_info: list[dict]
) -> Datasource:
    """登记数据库数据源及其表、字段元数据。

    tables_info: [{"table_name": str, "columns": [{"name", "data_type"}]}]
    """
    ds = Datasource(name=name, type="db", conn_info=encrypt(url), status="ready", created_by=user_id)
    db.add(ds)
    db.flush()

    numeric_prefixes = ("BIGINT", "INT", "INTEGER", "SMALLINT", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL", "NUMBER")
    for tinfo in tables_info:
        mt = MetaTable(
            datasource_id=ds.id,
            table_name=tinfo["table_name"],
            sheet_name=tinfo["table_name"],
            business_name=tinfo["table_name"],
            row_count=0,  # 数据库表行数不预统计
        )
        db.add(mt)
        db.flush()
        for order, col in enumerate(tinfo["columns"]):
            upper = col["data_type"].upper()
            is_measure = any(upper.startswith(p) for p in numeric_prefixes)
            db.add(
                MetaColumn(
                    table_id=mt.id,
                    column_name=col["name"],
                    business_name=col["name"],
                    data_type=col["data_type"][:32],
                    role="measure" if is_measure else "dim",
                    default_agg="SUM" if is_measure else "",
                    column_order=order,
                )
            )
    db.commit()
    db.refresh(ds)
    return ds
