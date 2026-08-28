"""自然语言解析：Prompt 构建（schema linking）与解析结果校验。

LLM 只负责输出结构化 JSON；本模块负责：
1. 把表元数据（业务名称、维度/度量、默认聚合）注入 Prompt（schema linking）
2. 对 LLM 输出做白名单校验：表、字段、聚合、操作符、表达式
"""
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# 白名单
ALLOWED_AGGS = {"SUM", "COUNT", "AVG", "MAX", "MIN"}
ALLOWED_OPS = {"eq", "ne", "gt", "lt", "ge", "le", "in", "like", "year", "month"}
ALLOWED_INTENTS = {"aggregate", "add_column"}
ALLOWED_NEW_COL_TYPES = {"string", "number", "boolean"}

# 表达式仅允许：数字、字母、下划线、中文、常用运算符与括号引号
_EXPR_RE = re.compile(r"^[\w\u4e00-\u9fff\s+\-*/().,<>=!'"",:；;%&|]*$")
_EXPR_FORBIDDEN_RE = re.compile(r";|--|/\*|\*/\b", re.IGNORECASE)

_NEW_COLUMN_NAME_RE = re.compile(r"^[\w\u4e00-\u9fff]{1,64}$")


class ColumnMeta(BaseModel):
    name: str           # 物理列名
    business_name: str
    data_type: str
    role: str           # dim / measure
    default_agg: str = ""


class TableMeta(BaseModel):
    table_name: str
    business_name: str
    columns: list[ColumnMeta]


class ParseResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: str
    source_table: str
    dimensions: list[str] = []
    measures: list[dict] = []
    filters: list[dict] = []
    new_columns: list[dict] = []


# ---------- Prompt 构建（schema linking） ----------

_FORMAT_DESC = """【输出格式】
输出一个 JSON 对象，不要输出任何其他内容：
{
  "intent": "aggregate 或 add_column",
  "source_table": "表物理名（必须使用上面给出的物理名）",
  "dimensions": ["分组维度字段的物理名"],
  "measures": [{"field": "度量字段物理名", "agg": "SUM/COUNT/AVG/MAX/MIN"}],
  "filters": [{"field": "字段物理名", "op": "eq/ne/gt/lt/ge/le/in/like/year/month", "value": "条件值"}],
  "new_columns": [{"name": "新字段英文名", "type": "string/number/boolean", "expression": "计算表达式，只能引用上面已有字段"}]
}

【规则】
1. 用户需求是"统计/汇总/按xx分组/生成统计表"类 → intent=aggregate，字段用物理名
2. 用户需求是"增加一列/新增字段/计算列"类 → intent=add_column，dimensions/measures/filters 留空数组
3. 数值聚合字段的 agg 默认用该字段标注的默认聚合；"数量/个数/多少"类用 COUNT
4. 日期按年筛选用 op=year，按月用 op=month，值填数字；范围用 ge/le
5. 用户提到的业务名称要对应到物理名；找不到对应字段时使用最接近的字段
6. expression 只能包含字段名、数字和 + - * / ( ) > < = 比较符，中文标签用单引号包裹"""


def build_prompt(meta: TableMeta, question: str) -> tuple[str, str]:
    """返回 (system, user) 两段 prompt。"""
    lines = [
        "你是企业报表助手，负责把用户的自然语言需求解析为结构化 JSON。"
        "你必须严格按规则输出 JSON，不得生成 SQL，不得编造不存在的字段。"
    ]
    schema_lines = [
        f"表物理名：{meta.table_name}",
        f"表业务名称：{meta.business_name}",
        "字段（物理名 | 业务名称 | 类型 | 维度/度量 | 默认聚合）：",
    ]
    for c in meta.columns:
        schema_lines.append(
            f"- {c.name} | {c.business_name} | {c.data_type} | {c.role} | {c.default_agg or '-'}"
        )
    user = (
        "【表结构】\n" + "\n".join(schema_lines)
        + f"\n\n【用户需求】\n{question}\n\n"
        + _FORMAT_DESC
    )
    return "\n".join(lines), user


# ---------- 校验 ----------

def validate(raw: Any, meta: TableMeta) -> tuple[ParseResult | None, list[str]]:
    """校验 LLM 输出。返回 (规范化结果, 错误列表)；有错则结果为 None。"""
    errors: list[str] = []
    if not isinstance(raw, dict):
        return None, ["模型输出不是 JSON 对象"]

    try:
        result = ParseResult(**raw)
    except Exception as e:
        return None, [f"解析结果结构不合法: {e}"]

    if result.intent not in ALLOWED_INTENTS:
        errors.append(f"intent 非法: {result.intent}")
        return None, errors

    if result.source_table != meta.table_name:
        errors.append(f"source_table 必须为 {meta.table_name}，实际为 {result.source_table}")
        return None, errors

    col_by_name = {c.name: c for c in meta.columns}

    if result.intent == "aggregate":
        # 维度
        if not result.dimensions:
            errors.append("aggregate 缺少 dimensions")
        for d in result.dimensions:
            if d not in col_by_name:
                errors.append(f"维度字段不存在: {d}")
        # 度量
        if not result.measures:
            errors.append("aggregate 缺少 measures")
        for m in result.measures:
            if not isinstance(m, dict) or "field" not in m or "agg" not in m:
                errors.append(f"measures 项不合法: {m}")
                continue
            if m["field"] not in col_by_name:
                errors.append(f"度量字段不存在: {m['field']}")
            elif col_by_name[m["field"]].role != "measure":
                errors.append(f"度量字段 {m['field']} 不是数值度量列")
            if m.get("agg") not in ALLOWED_AGGS:
                errors.append(f"聚合函数非法: {m.get('agg')}，允许 {sorted(ALLOWED_AGGS)}")
        # 条件
        for f in result.filters:
            if not isinstance(f, dict) or "field" not in f or "op" not in f:
                errors.append(f"filters 项不合法: {f}")
                continue
            if f["field"] not in col_by_name:
                errors.append(f"条件字段不存在: {f['field']}")
            if f["op"] not in ALLOWED_OPS:
                errors.append(f"条件操作符非法: {f['op']}，允许 {sorted(ALLOWED_OPS)}")
    else:  # add_column
        if not result.new_columns:
            errors.append("add_column 缺少 new_columns")
        for nc in result.new_columns:
            if not isinstance(nc, dict):
                errors.append(f"new_columns 项不合法: {nc}")
                continue
            name = nc.get("name", "")
            if not _NEW_COLUMN_NAME_RE.match(str(name)):
                errors.append(f"新字段名非法: {name}")
            if nc.get("type") not in ALLOWED_NEW_COL_TYPES:
                errors.append(f"新字段类型非法: {nc.get('type')}，允许 {sorted(ALLOWED_NEW_COL_TYPES)}")
            expr = str(nc.get("expression", ""))
            if not expr:
                errors.append("expression 不能为空")
            elif _EXPR_FORBIDDEN_RE.search(expr) or not _EXPR_RE.match(expr):
                errors.append(f"expression 含非法内容: {expr}")

    if errors:
        return None, errors
    return result, []
