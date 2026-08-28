"""DuckDB 操作：连接管理、建表、预览。

DuckDB 单进程单写连接，这里用模块级单连接 + 全局锁串行化访问。
"""
import os
import threading

import duckdb
import pandas as pd

from app.core.config import get_settings

_lock = threading.Lock()
_conn: duckdb.DuckDBPyConnection | None = None


def get_conn() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        path = get_settings().DUCKDB_PATH
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        _conn = duckdb.connect(path)
    return _conn


def reset_conn() -> None:
    """测试用：关闭并重置连接。"""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def create_table(table_name: str, df: pd.DataFrame) -> None:
    with _lock:
        conn = get_conn()
        conn.register("df_import", df)
        try:
            conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            conn.execute(f'CREATE TABLE "{table_name}" AS SELECT * FROM df_import')
        finally:
            conn.unregister("df_import")


def preview(table_name: str, limit: int = 100) -> tuple[list[str], list[list]]:
    """返回 (列名列表, 行数据)。NaN/NaT 统一转为 None。"""
    with _lock:
        cur = get_conn().execute(f'SELECT * FROM "{table_name}" LIMIT {int(limit)}')
        cols = [d[0] for d in cur.description]
        raw_rows = cur.fetchall()
    rows = [[_to_json_safe(v) for v in row] for row in raw_rows]
    return cols, rows


def _to_json_safe(v):
    if v is None:
        return None
    if isinstance(v, float) and v != v:  # NaN
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def table_exists(table_name: str) -> bool:
    with _lock:
        row = get_conn().execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table_name]
        ).fetchone()
    return row[0] > 0


def drop_table(table_name: str) -> None:
    with _lock:
        get_conn().execute(f'DROP TABLE IF EXISTS "{table_name}"')


def execute_ddl(ddl: str) -> None:
    """执行 DDL（建结果表等）。仅限内部调用，SQL 由 sql_builder 生成。"""
    with _lock:
        get_conn().execute(ddl)


def count_rows(table_name: str) -> int:
    _validate_table(table_name)
    with _lock:
        row = get_conn().execute(f'SELECT COUNT(1) FROM "{table_name}"').fetchone()
    return int(row[0])


def fetch_df(table_name: str):
    """读取整表为 DataFrame（导出用）。"""
    _validate_table(table_name)
    with _lock:
        return get_conn().execute(f'SELECT * FROM "{table_name}"').df()


def _validate_table(table_name: str) -> None:
    import re

    if not re.match(r"^[\w\u4e00-\u9fff]+$", table_name):
        raise ValueError(f"非法表名: {table_name}")
