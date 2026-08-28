"""集成测试：数据库数据源接入、元数据维护、权限控制。"""
import pytest
from sqlalchemy import create_engine, text

from app.models.user import User
from app.services import db_service


@pytest.fixture()
def biz_db_url(tmp_path):
    """模拟业务库：SQLite 文件 + 销售订单表。"""
    path = tmp_path / "biz.db"
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE sales_order (id INTEGER PRIMARY KEY, region VARCHAR, amount FLOAT, order_date DATE)"))
        conn.execute(text("INSERT INTO sales_order VALUES (1, '华东', 100.5, '2024-01-05'), (2, '华北', 200, '2024-02-01')"))
    eng.dispose()
    yield f"sqlite:///{path}"
    db_service.close_all()
    path.unlink(missing_ok=True)


@pytest.fixture()
def employee_headers(client, test_env):
    """创建普通员工并登录。"""
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password

    factory = sessionmaker(bind=test_env, expire_on_commit=False)
    with factory() as db:
        db.add(User(username="emp1", password_hash=hash_password("emp123"), role="employee", dept="业务部"))
        db.commit()
    resp = client.post("/api/auth/login", json={"username": "emp1", "password": "emp123"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_register_db_datasource(client, auth_headers, biz_db_url):
    resp = client.post(
        "/api/datasources/db",
        headers=auth_headers,
        json={"name": "业务库", "url": biz_db_url},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["table_count"] == 1

    # 元数据登记：字段角色预判
    resp = client.get("/api/metadata/tables", headers=auth_headers)
    tables = resp.json()
    assert len(tables) == 1
    t = tables[0]
    cols = {c["name"]: c for c in t["columns"]}
    assert cols["region"]["role"] == "dim"
    assert cols["amount"]["role"] == "measure"
    assert cols["amount"]["default_agg"] == "SUM"

    # 业务库表预览（走只读查询）
    resp = client.get(f"/api/tables/{t['id']}/preview?limit=1", headers=auth_headers)
    assert resp.status_code == 200
    pv = resp.json()
    assert pv["rows"][0][1] == "华东"


def test_register_db_requires_admin(client, employee_headers, biz_db_url):
    resp = client.post(
        "/api/datasources/db",
        headers=employee_headers,
        json={"name": "x", "url": biz_db_url},
    )
    assert resp.status_code == 403


def test_metadata_update_requires_admin(client, employee_headers):
    assert client.get("/api/metadata/tables", headers=employee_headers).status_code == 403
    assert client.patch("/api/metadata/columns/1", headers=employee_headers, json={"role": "dim"}).status_code == 403


def test_metadata_crud(client, auth_headers, biz_db_url):
    client.post("/api/datasources/db", headers=auth_headers, json={"name": "业务库", "url": biz_db_url})
    tables = client.get("/api/metadata/tables", headers=auth_headers).json()
    t = tables[0]
    col_id = t["columns"][0]["id"]

    # 更新表业务名
    resp = client.patch(f"/api/metadata/tables/{t['id']}", headers=auth_headers, json={"business_name": "销售订单表"})
    assert resp.status_code == 200
    assert resp.json()["business_name"] == "销售订单表"

    # 更新字段业务名 / 角色
    resp = client.patch(
        f"/api/metadata/columns/{col_id}",
        headers=auth_headers,
        json={"business_name": "区域", "role": "dim", "default_agg": ""},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["business_name"] == "区域" and body["role"] == "dim"

    # 非法角色被拒绝
    resp = client.patch(f"/api/metadata/columns/{col_id}", headers=auth_headers, json={"role": "hacker"})
    assert resp.status_code == 422

    # 更新结果回读
    tables = client.get("/api/metadata/tables", headers=auth_headers).json()
    assert tables[0]["business_name"] == "销售订单表"


def test_register_db_bad_url(client, auth_headers):
    resp = client.post(
        "/api/datasources/db",
        headers=auth_headers,
        json={"name": "x", "url": "postgresql+psycopg://u:p@10.255.255.1:5432/nope"},
    )
    assert resp.status_code == 400
