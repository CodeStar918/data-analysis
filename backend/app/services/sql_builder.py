"""SQL 构建：由校验后的解析结果确定性生成 SQL（阶段 4 仅预览，阶段 5 扩展执行）。

安全约定：输入已通过 nl_parser 白名单校验；标识符再校验一次；
值一律转义或参数化，绝不拼接未经校验的内容。
"""
import re

from app.services.nl_parser import ParseResult, TableMeta

_IDENT_RE = re.compile(r"^\w+$")
_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")

_OP_SQL = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "lt": "<",
    "ge": ">=",
    "le": "<=",
}


def _quote_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"非法标识符: {name}")
    return f'"{name}"'


def _quote_value(value) -> str:
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) or (isinstance(value, str) and _NUM_RE.match(value)):
        return str(value)
    if value is None:
        return "NULL"
    if isinstance(value, list):
        return "(" + ", ".join(_quote_value(v) for v in value) + ")"
    return "'" + str(value).replace("'", "''") + "'"


def build_select_sql(meta: TableMeta, parse: ParseResult) -> str:
    """构建 SELECT 语句（预览用）。"""
    table = _quote_ident(parse.source_table)

    if parse.intent == "aggregate":
        select_parts = []
        group_parts = []
        for d in parse.dimensions:
            ident = _quote_ident(d)
            select_parts.append(ident)
            group_parts.append(ident)
        for m in parse.measures:
            agg = m["agg"].upper()
            if agg == "COUNT":
                expr = "COUNT(1)" if m["field"] == "*" else f"COUNT({_quote_ident(m['field'])})"
            else:
                expr = f"{agg}({_quote_ident(m['field'])})"
            alias = _quote_ident(f"{m['agg'].lower()}_{m['field']}")
            select_parts.append(f"{expr} AS {alias}")
        where_parts = [_build_condition(f, col_names={c.name for c in meta.columns}) for f in parse.filters]
        sql = f"SELECT {', '.join(select_parts)} FROM {table}"
        if where_parts:
            sql += " WHERE " + " AND ".join(where_parts)
        if group_parts:
            sql += " GROUP BY " + ", ".join(group_parts)
        return sql

    # add_column：原字段 + 新字段
    if parse.new_columns:
        new_parts = ", " + ", ".join(
            f'({_nc["expression"]}) AS {_quote_ident(_nc["name"])}' for _nc in parse.new_columns
        )
    else:
        new_parts = ""
    return f"SELECT *{new_parts}\nFROM {table}"


def _build_condition(f: dict, col_names: set) -> str:
    field = _quote_ident(f["field"])
    op = f["op"]
    value = f.get("value")
    if op in _OP_SQL:
        return f"{field} {_OP_SQL[op]} {_quote_value(value)}"
    if op == "in":
        if not isinstance(value, list):
            value = [value]
        return f"{field} IN {_quote_value(value)}"
    if op == "like":
        return f"{field} LIKE {_quote_value(f'%{value}%')}"
    if op == "year":
        return f"YEAR({field}) = {_quote_value(value)}"
    if op == "month":
        return f"MONTH({field}) = {_quote_value(value)}"
    raise ValueError(f"不支持的操作符: {op}")
