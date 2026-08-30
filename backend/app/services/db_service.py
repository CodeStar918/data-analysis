"""业务数据库只读接入：基于 SQLAlchemy 连接串。

- 仅做只读操作：表结构拉取、SELECT 预览
- execute_read 强制仅允许单条 SELECT/WITH 语句（防注入兜底；账号本身也应为只读账号）
- 支持 PostgreSQL / MySQL / SQL Server 等（需安装对应驱动），测试用 SQLite 方言
"""
import re

import sqlalchemy as sa
from app.core.logging import setup_logging

logger = setup_logging()

# 标识符白名单：字母/数字/下划线
_IDENT_RE = re.compile(r"^\w+$")

_engines: dict[int, sa.Engine] = {}


def _validate_identifier(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"非法标识符: {name}")
    return name


def get_engine(ds_id: int, url: str) -> sa.Engine:
    """按数据源缓存引擎。"""
    eng = _engines.get(ds_id)
    if eng is None:
        eng = sa.create_engine(url, pool_pre_ping=True)
        _engines[ds_id] = eng
    return eng


def close_engine(ds_id: int) -> None:
    eng = _engines.pop(ds_id, None)
    if eng is not None:
        eng.dispose()


def close_all() -> None:
    for ds_id in list(_engines):
        close_engine(ds_id)


def test_connection(url: str) -> None:
    """连接测试，失败抛异常。"""
    eng = sa.create_engine(url, pool_pre_ping=True)
    try:
        with eng.connect():
            pass
    finally:
        eng.dispose()


def list_tables(url: str) -> list[str]:
    """拉取默认 schema 的表清单。"""
    eng = sa.create_engine(url, pool_pre_ping=True)
    try:
        return sorted(sa.inspect(eng).get_table_names())
    finally:
        eng.dispose()


def get_columns(url: str, table: str) -> list[dict]:
    """拉取字段：name/type/nullable。"""
    _validate_identifier(table)
    eng = sa.create_engine(url, pool_pre_ping=True)
    try:
        cols = sa.inspect(eng).get_columns(table)
        return [
            {
                "name": c["name"],
                "data_type": str(c["type"]),
                "nullable": bool(c.get("nullable", True)),
            }
            for c in cols
        ]
    finally:
        eng.dispose()


def assert_readonly_sql(sql: str) -> str:
    """仅允许单条 SELECT/WITH 语句（只读兜底校验）。"""
    stripped = sql.strip().rstrip(";").strip()
    if not stripped:
        raise ValueError("空查询")
    if ";" in stripped:
        raise ValueError("不允许多条语句")
    if not re.match(r"^(SELECT|WITH)\b", stripped, re.IGNORECASE):
        raise ValueError("仅允许 SELECT 查询")
    return stripped


def read_query(url: str, sql: str, limit: int = 100) -> tuple[list[str], list[list]]:
    """执行只读查询，返回 (列名, 行数据)。"""
    sql = assert_readonly_sql(sql)
    eng = sa.create_engine(url, pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            result = conn.execute(sa.text(f"SELECT * FROM ({sql}) AS _q LIMIT {int(limit)}"))
            cols = list(result.keys())
            rows = [list(r) for r in result.fetchall()]
    finally:
        eng.dispose()
    return cols, rows


def read_table_preview(ds_id: int, url: str, table: str, limit: int = 100) -> tuple[list[str], list[list]]:
    """业务表预览：SELECT * LIMIT。"""
    _validate_identifier(table)
    eng = get_engine(ds_id, url)
    with eng.connect() as conn:
        result = conn.execute(sa.text(f'SELECT * FROM "{table}" LIMIT {int(limit)}'))
        cols = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    return cols, rows
