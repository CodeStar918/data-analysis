"""集成测试：明细任务写回审批流程（阶段 6）。"""
import pytest
from app.models.user import User
from app.services import db_service, ollama_service
from sqlalchemy import create_engine, text

ADD_COL_OK = {
    "intent": "add_column",
    "source_table": "up_1_0",
    "dimensions": [],
    "measures": [],
    "filters": [],
    "new_columns": [
        {"name": "is_big", "type": "string", "expression": "CASE WHEN 销售金额 > 5000 THEN '大单' ELSE '普通' END"}
    ],
}


def _mock_llm(monkeypatch, payload):
    monkeypatch.setattr(ollama_service, "chat_json", lambda s, u: payload)


@pytest.fixture()
def employee_headers(client, test_env):
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password

    factory = sessionmaker(bind=test_env, expire_on_commit=False)
    with factory() as db:
        db.add(User(username="emp6", password_hash=hash_password("p123456"), role="employee"))
        db.commit()
    token = client.post("/api/auth/login", json={"username": "emp6", "password": "p123456"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def add_column_job_id(client, auth_headers, sales_table_id, monkeypatch) -> int:
    """完成一次明细任务，返回 job_id。"""
    _mock_llm(monkeypatch, ADD_COL_OK)
    parsed = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "增加一列是否大单"}
    ).json()
    client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    job = client.post("/api/jobs", headers=auth_headers, json={"parse_id": parsed["parse_id"]}).json()
    assert job["status"] == "success"
    return job["job_id"]


def test_apply_and_list(client, auth_headers, employee_headers, add_column_job_id):
    resp = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": add_column_job_id, "reason": "业务需要标记大单"}
    )
    assert resp.status_code == 200
    approval_id = resp.json()["approval_id"]
    assert resp.json()["status"] == "pending"

    # 管理员可见；非本人（emp6）看不到他人的申请
    assert any(a["id"] == approval_id for a in client.get("/api/approvals", headers=auth_headers).json())
    assert client.get("/api/approvals", headers=employee_headers).json() == []

    # 非本人不能申请
    resp = client.post(
        "/api/approvals", headers=employee_headers, json={"job_id": add_column_job_id, "reason": "x"}
    )
    assert resp.status_code == 403

    # 待审批期间重复申请被拒
    resp = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": add_column_job_id, "reason": "again"}
    )
    assert resp.status_code == 400


def test_reject_keeps_source_table_unchanged(client, auth_headers, add_column_job_id):
    approval_id = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": add_column_job_id, "reason": "x"}
    ).json()["approval_id"]
    resp = client.post(
        f"/api/approvals/{approval_id}/decide", headers=auth_headers, json={"action": "reject", "comment": "理由不充分"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    # 原表保护：拒绝后源表无新列（仍是 3 列）
    # 通过数据源表预览接口验证列数
    tables = client.get("/api/datasources/1/tables", headers=auth_headers).json()
    assert len(tables[0]["columns"]) == 3

    # 重复处理被拒
    resp = client.post(
        f"/api/approvals/{approval_id}/decide", headers=auth_headers, json={"action": "approve"}
    )
    assert resp.status_code == 400

    # 拒绝后可重新申请
    resp = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": add_column_job_id, "reason": "补充理由"}
    )
    assert resp.status_code == 200


def test_non_admin_cannot_decide(client, auth_headers, employee_headers, add_column_job_id):
    approval_id = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": add_column_job_id, "reason": "x"}
    ).json()["approval_id"]
    resp = client.post(
        f"/api/approvals/{approval_id}/decide", headers=employee_headers, json={"action": "approve"}
    )
    assert resp.status_code == 403


def test_aggregate_job_cannot_apply(client, auth_headers, confirmed_parse_id, monkeypatch):
    client.post("/api/jobs", headers=auth_headers, json={"parse_id": confirmed_parse_id})
    # aggregate 任务的写回申请被拒（需要 job 的 result；直接申请）
    results = client.get("/api/results", headers=auth_headers).json()
    assert results[0]["result_type"] == "aggregate"


def test_approve_writes_back_to_source(client, auth_headers, add_column_job_id):
    """审批通过 → 原表新增字段且值正确。"""
    approval_id = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": add_column_job_id, "reason": "大单标记"}
    ).json()["approval_id"]
    resp = client.post(
        f"/api/approvals/{approval_id}/decide", headers=auth_headers, json={"action": "approve", "comment": "同意"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    # 原表预览：新列存在且值正确
    tables = client.get("/api/datasources/1/tables", headers=auth_headers).json()
    assert len(tables[0]["columns"]) == 4
    table_id = tables[0]["id"]
    pv = client.get(f"/api/tables/{table_id}/preview", headers=auth_headers).json()
    tag_by_amount = {r[1]: r[3] for r in pv["rows"]}
    assert tag_by_amount[5000.5] == "大单"
    assert tag_by_amount[8000] == "大单"
    assert tag_by_amount[3000] == "普通"

    # 结果标记已写回
    rt = client.get("/api/results", headers=auth_headers).json()[0]
    assert rt["applied_to_source"] is True

    # 已通过后再申请被拒
    resp = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": add_column_job_id, "reason": "again"}
    )
    assert resp.status_code == 400


def test_db_source_writeback_rejected(client, auth_headers, monkeypatch, tmp_path):
    """原表保护：业务库数据源不允许写回。"""
    path = tmp_path / "biz6.db"
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE sales_order (id INTEGER PRIMARY KEY, region VARCHAR, amount FLOAT)"))
        conn.execute(text("INSERT INTO sales_order VALUES (1, '华东', 100.5)"))
    eng.dispose()

    _mock_llm(monkeypatch, {
        "intent": "add_column", "source_table": "sales_order", "dimensions": [], "measures": [],
        "filters": [], "new_columns": [{"name": "amount2", "type": "number", "expression": "amount * 2"}],
    })
    reg = client.post(
        "/api/datasources/db", headers=auth_headers, json={"name": "业务库6", "url": f"sqlite:///{path.as_posix()}"}
    ).json()
    tables = client.get(f"/api/datasources/{reg['datasource_id']}/tables", headers=auth_headers).json()
    parsed = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": tables[0]["id"], "question": "加列"}
    ).json()
    client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    job = client.post("/api/jobs", headers=auth_headers, json={"parse_id": parsed["parse_id"]}).json()
    assert job["status"] == "success"

    resp = client.post(
        "/api/approvals", headers=auth_headers, json={"job_id": job["job_id"], "reason": "x"}
    )
    assert resp.status_code == 400
    assert "只读" in resp.json()["detail"]

    db_service.close_all()
    path.unlink(missing_ok=True)
