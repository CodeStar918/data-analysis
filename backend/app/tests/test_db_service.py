"""业务库只读服务单元测试。"""
import pytest
from sqlalchemy import create_engine, text

from app.services import db_service


@pytest.fixture()
def biz_db(tmp_path):
    """模拟业务库：SQLite 文件，含一张表和数据。"""
    path = tmp_path / "biz.db"
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE sales_order (id INTEGER PRIMARY KEY, region VARCHAR, amount FLOAT)"))
        conn.execute(text("INSERT INTO sales_order VALUES (1, '华东', 100.5), (2, '华北', 200)"))
    eng.dispose()
    yield f"sqlite:///{path}"
    db_service.close_all()
    path.unlink(missing_ok=True)


def test_assert_readonly_sql():
    assert db_service.assert_readonly_sql("SELECT * FROM t")
    assert db_service.assert_readonly_sql("  with x as (select 1) select * from x  ")
    assert db_service.assert_readonly_sql("select 1;") == "select 1"


def test_assert_readonly_rejects_writes():
    for bad in [
        "INSERT INTO t VALUES (1)",
        "UPDATE t SET a = 1",
        "DELETE FROM t",
        "DROP TABLE t",
        "CREATE TABLE t (a INT)",
        "SELECT 1; DROP TABLE t",
        "",
        "   ",
    ]:
        with pytest.raises(ValueError):
            db_service.assert_readonly_sql(bad)


def test_list_tables_and_columns(biz_db):
    tables = db_service.list_tables(biz_db)
    assert tables == ["sales_order"]
    cols = db_service.get_columns(biz_db, "sales_order")
    assert [c["name"] for c in cols] == ["id", "region", "amount"]


def test_read_table_preview(biz_db):
    cols, rows = db_service.read_table_preview(1, biz_db, "sales_order", limit=1)
    assert cols == ["id", "region", "amount"]
    assert len(rows) == 1


def test_read_table_preview_rejects_bad_identifier(biz_db):
    with pytest.raises(ValueError):
        db_service.read_table_preview(1, biz_db, "sales; DROP TABLE x")
