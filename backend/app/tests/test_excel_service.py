"""Excel 解析单元测试：类型推断、表头清洗、多 sheet、边界。"""
import pytest

from app.services.excel_service import parse_excel
from app.tests.excel_helpers import SAMPLE_TIME, build_xlsx


def test_type_inference():
    data = build_xlsx(
        {
            "Sheet1": [
                ["区域", "金额", "数量", "是否VIP", "下单日期", "备注"],
                ["华东", 100.5, 3, True, SAMPLE_TIME, "x"],
                ["华北", 200, 5, False, SAMPLE_TIME, None],
            ]
        }
    )
    sheets = parse_excel(data)
    assert len(sheets) == 1
    dtypes = {c.business_name: c.data_type for c in sheets[0].columns}
    assert dtypes["区域"] == "VARCHAR"
    assert dtypes["金额"] == "DOUBLE"
    assert dtypes["数量"] == "BIGINT"
    assert dtypes["是否VIP"] == "BOOLEAN"
    assert dtypes["下单日期"] == "TIMESTAMP"
    assert dtypes["备注"] == "VARCHAR"
    roles = {c.business_name: c.role for c in sheets[0].columns}
    assert roles["金额"] == "measure"
    assert roles["区域"] == "dim"
    agg = {c.business_name: c.default_agg for c in sheets[0].columns}
    assert agg["金额"] == "SUM"


def test_header_cleanup():
    data = build_xlsx(
        {
            "s": [
                [" 名称 ", "名称", None, "2列", "名称"],
                [1, 2, 3, 4, 5],
            ]
        }
    )
    cols = parse_excel(data)[0].columns
    names = [c.name for c in cols]
    # 空白清洗、去重、空表头命名、数字开头处理
    assert names == ["名称", "名称_1", "col", "c_2列", "名称_2"]
    biz = [c.business_name for c in cols]
    assert biz[0] == "名称"


def test_multi_sheet():
    data = build_xlsx({"订单": [["a", "b"], [1, 2]], "库存": [["x", "y"], [3, 4]]})
    sheets = parse_excel(data)
    assert [s.sheet_name for s in sheets] == ["订单", "库存"]


def test_empty_file():
    with pytest.raises(ValueError):
        parse_excel(b"")


def test_invalid_file():
    with pytest.raises(ValueError):
        parse_excel(b"this is not excel")


def test_blank_sheet_skipped():
    # 仅有一个空 sheet 的合法 xlsx
    data = build_xlsx({"Sheet1": []})
    assert parse_excel(data) == []


def test_merged_cells_no_crash():
    data = build_xlsx(
        {"m": [["标题", None], ["a", "b"], [1, 2]]},
        merges={"m": ["A1:B1"]},
    )
    sheets = parse_excel(data)
    assert len(sheets) == 1
    assert sheets[0].columns[0].business_name == "标题"
    assert len(sheets[0].df) == 2


def test_all_null_column():
    # 中间列为全空（openpyxl 不写尾部空单元格，故不放在末列）
    data = build_xlsx({"s": [["a", None, "b"], [1, None, 2], [3, None, 4]]})
    sheets = parse_excel(data)
    dtypes = [c.data_type for c in sheets[0].columns]
    names = [c.name for c in sheets[0].columns]
    assert names == ["a", "col", "b"]
    assert dtypes == ["BIGINT", "VARCHAR", "BIGINT"]
