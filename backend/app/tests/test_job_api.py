"""集成测试：统计任务端到端（上传 → 解析 → 确认 → 任务 → 结果 → 导出）。"""
import io

import pandas as pd
import pytest

from app.services import ollama_service
from app.tests.excel_helpers import SAMPLE_TIME, build_xlsx

AGG_OK = {
    "intent": "aggregate",
    "source_table": "up_1_0",
    "dimensions": ["区域"],
    "measures": [{"field": "销售金额", "agg": "SUM"}],
    "filters": [],
    "new_columns": [],
}


def _mock_llm(monkeypatch, payload):
    monkeypatch.setattr(ollama_service, "chat_json", lambda s, u: payload)


def test_job_requires_confirmed_parse(client, auth_headers, sales_table_id, monkeypatch):
    _mock_llm(monkeypatch, AGG_OK)
    parsed = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "统计"}
    ).json()
    resp = client.post("/api/jobs", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    assert resp.status_code == 400


def test_job_add_column_end_to_end(client, auth_headers, sales_table_id, monkeypatch):
    """明细任务：原字段+新字段结果表，条件标签列计算正确。"""
    _mock_llm(monkeypatch, {
        "intent": "add_column", "source_table": "up_1_0", "dimensions": [], "measures": [],
        "filters": [], "new_columns": [{"name": "is_big", "type": "string",
                                        "expression": "CASE WHEN 销售金额 > 5000 THEN '大单' ELSE '普通' END"}],
    })
    parsed = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "加列"}
    ).json()
    client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    resp = client.post("/api/jobs", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    assert resp.status_code == 200
    job = resp.json()
    assert job["status"] == "success"

    results = client.get("/api/results", headers=auth_headers).json()
    assert results[0]["result_type"] == "add_column"
    assert results[0]["row_count"] == 3
    assert results[0]["applied_to_source"] is False

    pv = client.get(f"/api/results/{results[0]['id']}/preview", headers=auth_headers).json()
    cols = [c["name"] for c in pv["columns"]]
    assert cols[-1] == "is_big"
    tag_by_amount = {r[1]: r[3] for r in pv["rows"]}
    assert tag_by_amount[5000.5] == "大单"
    assert tag_by_amount[3000] == "普通"


def test_stats_end_to_end(client, auth_headers, confirmed_parse_id):
    # 提交任务（eager 模式同步执行完成）
    resp = client.post("/api/jobs", headers=auth_headers, json={"parse_id": confirmed_parse_id})
    assert resp.status_code == 200, resp.text
    job = resp.json()
    assert job["status"] == "success"
    assert job["result_table_id"] is not None

    # 任务状态查询
    detail = client.get(f"/api/jobs/{job['job_id']}", headers=auth_headers).json()
    assert detail["status"] == "success"

    # 结果列表
    results = client.get("/api/results", headers=auth_headers).json()
    assert len(results) == 1
    assert results[0]["row_count"] == 2  # 华东/华北 两组

    # 结果预览：聚合正确性
    pv = client.get(f"/api/results/{results[0]['id']}/preview", headers=auth_headers).json()
    rows = {r[0]: r[1] for r in pv["rows"]}
    assert rows["华东"] == 8000
    assert rows["华北"] == 8000


def test_export_xlsx_integrity(client, auth_headers, confirmed_parse_id):
    """导出完整性：行数与表头一致。"""
    job = client.post("/api/jobs", headers=auth_headers, json={"parse_id": confirmed_parse_id}).json()
    results = client.get("/api/results", headers=auth_headers).json()
    rid = results[0]["id"]

    resp = client.get(f"/api/results/{rid}/export?format=xlsx", headers=auth_headers)
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]

    df = pd.read_excel(io.BytesIO(resp.content))
    assert list(df.columns) == ["区域", "sum_销售金额"]
    assert len(df) == 2


def test_export_csv_utf8(client, auth_headers, confirmed_parse_id):
    client.post("/api/jobs", headers=auth_headers, json={"parse_id": confirmed_parse_id})
    rid = client.get("/api/results", headers=auth_headers).json()[0]["id"]
    resp = client.get(f"/api/results/{rid}/export?format=csv", headers=auth_headers)
    assert resp.status_code == 200
    text = resp.content.decode("utf-8-sig")
    assert "区域" in text and "华东" in text


def test_result_access_control(client, auth_headers, test_env, confirmed_parse_id):
    """其他用户看不到别人的结果。"""
    from sqlalchemy.orm import sessionmaker

    from app.core.security import hash_password
    from app.models.user import User

    client.post("/api/jobs", headers=auth_headers, json={"parse_id": confirmed_parse_id})

    factory = sessionmaker(bind=test_env, expire_on_commit=False)
    with factory() as db:
        db.add(User(username="emp9", password_hash=hash_password("p123456"), role="employee"))
        db.commit()
    emp_token = client.post("/api/auth/login", json={"username": "emp9", "password": "p123456"}).json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}

    assert client.get("/api/results", headers=emp_headers).json() == []
    rid = client.get("/api/results", headers=auth_headers).json()[0]["id"]
    assert client.get(f"/api/results/{rid}/preview", headers=emp_headers).status_code == 404


def test_large_dataset_aggregation(client, auth_headers, monkeypatch):
    """大数据量：10000 行聚合正确且可完成。"""
    _mock_llm(monkeypatch, AGG_OK)
    n = 10000
    rows = [["区域", "销售金额", "下单日期"]]
    for i in range(n):
        rows.append(["华东" if i % 2 else "华北", float(i), SAMPLE_TIME])
    content = build_xlsx({"大数据": rows})
    up = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("big.xlsx", content, "application/octet-stream")},
    ).json()
    assert up["tables"][0]["row_count"] == n

    parsed = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": up["tables"][0]["id"], "question": "按区域统计"}
    ).json()
    client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    job = client.post("/api/jobs", headers=auth_headers, json={"parse_id": parsed["parse_id"]}).json()
    assert job["status"] == "success"

    rid = job["result_table_id"]
    pv = client.get(f"/api/results/{rid}/preview", headers=auth_headers).json()
    rows_map = {r[0]: r[1] for r in pv["rows"]}
    # 偶数索引华北 5000 行，奇数索引华东 5000 行
    assert rows_map["华北"] == sum(i for i in range(n) if i % 2 == 0)
    assert rows_map["华东"] == sum(i for i in range(n) if i % 2 == 1)
