"""NL 解析校验器与 Prompt 单元测试。"""
import pytest

from app.services.nl_parser import ColumnMeta, TableMeta, build_prompt, validate

META = TableMeta(
    table_name="up_1_0",
    business_name="销售订单表",
    columns=[
        ColumnMeta(name="region", business_name="区域", data_type="VARCHAR", role="dim"),
        ColumnMeta(name="order_date", business_name="下单日期", data_type="TIMESTAMP", role="dim"),
        ColumnMeta(name="amount", business_name="销售金额", data_type="DOUBLE", role="measure", default_agg="SUM"),
    ],
)


def _agg(**overrides):
    base = {
        "intent": "aggregate",
        "source_table": "up_1_0",
        "dimensions": ["region"],
        "measures": [{"field": "amount", "agg": "SUM"}],
        "filters": [{"field": "order_date", "op": "year", "value": "2024"}],
        "new_columns": [],
    }
    base.update(overrides)
    return base


def test_prompt_contains_schema():
    system, user = build_prompt(META, "按区域统计销售额")
    assert "销售订单表" in user
    assert "amount | 销售金额" in user
    assert "按区域统计销售额" in user
    assert "aggregate 或 add_column" in user


def test_valid_aggregate():
    result, errors = validate(_agg(), META)
    assert errors == []
    assert result.dimensions == ["region"]


def test_reject_bad_intent():
    result, errors = validate(_agg(intent="delete"), META)
    assert result is None
    assert any("intent" in e for e in errors)


def test_reject_wrong_table():
    result, errors = validate(_agg(source_table="other"), META)
    assert result is None
    assert any("source_table" in e for e in errors)


def test_reject_missing_field():
    result, errors = validate(_agg(dimensions=["area"]), META)
    assert result is None
    assert any("area" in e for e in errors)


def test_reject_dim_as_measure():
    result, errors = validate(_agg(measures=[{"field": "region", "agg": "SUM"}]), META)
    assert result is None
    assert any("度量" in e for e in errors)


def test_reject_bad_agg():
    result, errors = validate(_agg(measures=[{"field": "amount", "agg": "DROP"}]), META)
    assert result is None
    assert any("聚合函数" in e for e in errors)


def test_reject_bad_op():
    result, errors = validate(_agg(filters=[{"field": "order_date", "op": "regex", "value": "x"}]), META)
    assert result is None
    assert any("操作符" in e for e in errors)


def test_valid_add_column():
    raw = {
        "intent": "add_column",
        "source_table": "up_1_0",
        "new_columns": [
            {"name": "is_big", "type": "string", "expression": "CASE WHEN amount > 5000 THEN '大单' ELSE '普通' END"}
        ],
    }
    result, errors = validate(raw, META)
    assert errors == []
    assert result.new_columns[0]["name"] == "is_big"


def test_reject_add_column_injection():
    for expr in ["1; DROP TABLE t", "1 -- comment", "a /* x */", "' ; DELETE FROM t'"]:
        raw = {
            "intent": "add_column",
            "source_table": "up_1_0",
            "new_columns": [{"name": "x", "type": "number", "expression": expr}],
        }
        result, errors = validate(raw, META)
        assert result is None, expr
        assert any("expression" in e for e in errors)


def test_reject_add_column_bad_name_or_type():
    raw = {"intent": "add_column", "source_table": "up_1_0",
           "new_columns": [{"name": "a b", "type": "list", "expression": "amount * 2"}]}
    result, errors = validate(raw, META)
    assert result is None
    assert len(errors) >= 1


def test_reject_not_dict():
    result, errors = validate("hello", META)
    assert result is None


@pytest.mark.parametrize(
    "question,raw,expect_valid",
    [
        # ---- aggregate 场景 ----
        ("按区域统计销售额", _agg(), True),
        ("按区域和月份统计销售额合计，只看2024年",
         _agg(dimensions=["region", "order_date"],
              filters=[{"field": "order_date", "op": "year", "value": "2024"}]), True),
        ("统计2024年每个区域的订单数量",
         _agg(measures=[{"field": "amount", "agg": "COUNT"}],
              filters=[{"field": "order_date", "op": "year", "value": "2024"}]), True),
        ("只看华东区域的销售额", _agg(filters=[{"field": "region", "op": "eq", "value": "华东"}]), True),
        ("销售额大于5000的区域", _agg(filters=[{"field": "amount", "op": "gt", "value": "5000"}]), True),
        ("销售额最高的区域",
         _agg(measures=[{"field": "amount", "agg": "MAX"}], filters=[]), True),
        ("统计各区域销售金额和数量",
         _agg(measures=[{"field": "amount", "agg": "SUM"}, {"field": "amount", "agg": "COUNT"}]), True),
        ("区域名称包含东的销售额",
         _agg(filters=[{"field": "region", "op": "like", "value": "东"}]), True),
        ("2024年1月各区域销售额",
         _agg(filters=[{"field": "order_date", "op": "year", "value": "2024"},
                        {"field": "order_date", "op": "month", "value": "1"}]), True),
        ("销售额在1000到5000之间的记录",
         _agg(filters=[{"field": "amount", "op": "ge", "value": "1000"},
                        {"field": "amount", "op": "le", "value": "5000"}]), True),
        # ---- add_column 场景 ----
        ("增加一列：金额翻倍",
         {"intent": "add_column", "source_table": "up_1_0",
          "new_columns": [{"name": "amount_double", "type": "number", "expression": "amount * 2"}]}, True),
        ("增加一列：是否大单",
         {"intent": "add_column", "source_table": "up_1_0",
          "new_columns": [{"name": "is_big", "type": "string",
                           "expression": "CASE WHEN amount > 5000 THEN '是' ELSE '否' END"}]}, True),
        ("增加一列：年份",
         {"intent": "add_column", "source_table": "up_1_0",
          "new_columns": [{"name": "order_year", "type": "number", "expression": "YEAR(order_date)"}]}, True),
        ("给订单表加一列单价是金额除以数量",
         {"intent": "add_column", "source_table": "up_1_0",
          "new_columns": [{"name": "price", "type": "number", "expression": "amount / 2"}]}, True),
        # ---- 非法场景 ----
        ("删除表", _agg(intent="drop"), False),
        ("统计不存在的产品", _agg(dimensions=["product"]), False),
        ("按区域分组但没有度量", _agg(measures=[]), False),
        ("给表加一列然后删库",
         {"intent": "add_column", "source_table": "up_1_0",
          "new_columns": [{"name": "x", "type": "number", "expression": "1; DROP TABLE t"}]}, False),
        ("输出到别的表", _agg(source_table="other_table"), False),
        ("字段用业务名", _agg(dimensions=["区域"]), False),
    ],
)
def test_validation_dataset(question, raw, expect_valid):
    """回归语句集：覆盖典型业务语句与非法语句（扩充至 100+ 条时维护在本文件）。"""
    result, errors = validate(raw, META)
    assert (result is not None) is expect_valid, f"question={question}, errors={errors}"
