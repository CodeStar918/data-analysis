"""Excel 解析：多 sheet、表头识别、类型推断。

解析结果为 ParsedSheet 列表，每个 sheet 对应一张 DuckDB 表。
- 表头默认取第一行；空表头列自动命名为 col_N
- 列名清洗：去首尾空白、空白转下划线、去重
- 类型推断：pandas 常规读取推断类型；另用 header=None 读取保留原始表头
  （避免 pandas 对重复/空表头的自动改名，如 名称.1 / Unnamed: 2）
"""
import io
import re
from typing import Any

import pandas as pd
from pydantic import BaseModel


class ParsedColumn(BaseModel):
    name: str           # 清洗后的物理列名
    business_name: str  # 原始表头（业务名称）
    data_type: str      # DuckDB 类型
    role: str = "dim"   # dim / measure
    default_agg: str = ""


class ParsedSheet(BaseModel):
    sheet_name: str
    df: Any = None      # pd.DataFrame
    columns: list[ParsedColumn] = []


_DTYPE_MAP = {
    "int64": "BIGINT",
    "int32": "INTEGER",
    "float64": "DOUBLE",
    "float32": "FLOAT",
    "bool": "BOOLEAN",
    "datetime64[ns]": "TIMESTAMP",
}


def map_dtype(dtype) -> str:
    name = str(dtype)
    if name in _DTYPE_MAP:
        return _DTYPE_MAP[name]
    if name.startswith("datetime64"):
        return "TIMESTAMP"
    return "VARCHAR"


def _clean_column_name(raw: str | None, used: set[str]) -> str:
    if raw is None or raw == "":
        base = "col"
    else:
        base = re.sub(r"\s+", "_", str(raw).strip())
        if not base:
            base = "col"
        if base[0].isdigit():
            base = "c_" + base
    candidate, i = base, 0
    while candidate.lower() in used:
        i += 1
        candidate = f"{base}_{i}"
    used.add(candidate.lower())
    return candidate


def _original_headers(book_raw: dict[str, pd.DataFrame], sheet_name: str) -> list:
    if sheet_name not in book_raw or len(book_raw[sheet_name]) == 0:
        return []
    return list(book_raw[sheet_name].iloc[0])


def parse_excel(content: bytes) -> list[ParsedSheet]:
    """解析 Excel 字节流。完全无数据的文件抛 ValueError。"""
    if not content:
        raise ValueError("文件为空")
    try:
        book = pd.read_excel(io.BytesIO(content), sheet_name=None, engine="openpyxl")
        book_raw = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"无法解析的 Excel 文件: {e}") from e

    sheets: list[ParsedSheet] = []
    for sheet_name, df in book.items():
        if len(df.columns) == 0:
            continue  # 完全空 sheet 跳过
        headers = _original_headers(book_raw, sheet_name)
        used: set[str] = set()
        cols: list[ParsedColumn] = []
        for i, pandas_name in enumerate(df.columns):
            orig = headers[i] if i < len(headers) else None
            if orig is None or (isinstance(orig, float) and pd.isna(orig)):
                business = ""
            else:
                business = str(orig).strip()
            phys = _clean_column_name(business or None, used)

            series = df[pandas_name]
            if series.isna().all():
                dt, role, agg = "VARCHAR", "dim", ""      # 全空列
            else:
                dt = map_dtype(series.dtype)
                role = "measure" if dt in ("BIGINT", "INTEGER", "DOUBLE", "FLOAT") else "dim"
                agg = "SUM" if role == "measure" else ""
            cols.append(ParsedColumn(name=phys, business_name=business, data_type=dt, role=role, default_agg=agg))

        df = df.copy()
        df.columns = [c.name for c in cols]
        sheets.append(ParsedSheet(sheet_name=str(sheet_name), df=df, columns=cols))
    return sheets
