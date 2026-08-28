"""写回原表审批服务（阶段 6）。

安全约定：
- 仅 Excel（DuckDB）数据源允许写回；业务库为只读账号，物理上禁止写回
- 写回必须经管理员审批，系统不提供任何绕过审批的写回途径（原表保护）
"""
import re

from app.core.logging import setup_logging
from app.services import duckdb_service

logger = setup_logging()

_TYPE_MAP = {"string": "VARCHAR", "number": "DOUBLE", "boolean": "BOOLEAN"}
_IDENT_RE = re.compile(r"^[\w\u4e00-\u9fff]+$")
_EXPR_FORBIDDEN_RE = re.compile(r";|--|/\*|\*/\b", re.IGNORECASE)


def apply_writeback(source_table: str, new_columns: list[dict]) -> None:
    """把新字段写回 DuckDB 原表：ALTER TABLE ADD COLUMN + UPDATE。

    调用前提：审批已通过；source_table 为 DuckDB 物理表；表达式已通过解析校验。
    """
    if not _IDENT_RE.match(source_table):
        raise ValueError(f"非法表名: {source_table}")

    for nc in new_columns:
        name = str(nc.get("name", ""))
        expr = str(nc.get("expression", ""))
        col_type = _TYPE_MAP.get(nc.get("type"), "VARCHAR")
        if not _IDENT_RE.match(name):
            raise ValueError(f"非法字段名: {name}")
        if not expr or _EXPR_FORBIDDEN_RE.search(expr):
            raise ValueError(f"非法表达式: {expr}")

        duckdb_service.execute_ddl(
            f'ALTER TABLE "{source_table}" ADD COLUMN IF NOT EXISTS "{name}" {col_type}'
        )
        duckdb_service.execute_ddl(f'UPDATE "{source_table}" SET "{name}" = ({expr})')
        logger.info("写回字段 %s.%s (%s) 完成", source_table, name, col_type)
