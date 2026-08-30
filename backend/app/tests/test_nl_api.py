"""集成测试：NL 解析接口（mock Ollama）、SQL 预览、确认流程。"""

from app.services import ollama_service
from app.services.ollama_service import OllamaError


def _mock_llm(monkeypatch, payload):
    def fake(system, user):
        return payload

    monkeypatch.setattr(ollama_service, "chat_json", fake)


AGG_OK = {
    "intent": "aggregate",
    "source_table": "up_1_0",
    "dimensions": ["区域"],
    "measures": [{"field": "销售金额", "agg": "SUM"}],
    "filters": [{"field": "下单日期", "op": "year", "value": "2024"}],
    "new_columns": [],
}

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


def test_parse_aggregate(client, auth_headers, sales_table_id, monkeypatch):
    _mock_llm(monkeypatch, AGG_OK)
    resp = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "按区域统计销售额，只看2024年"}
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["valid"] is True
    sql = data["sql_preview"]
    assert "SUM(" in sql and "GROUP BY" in sql and "YEAR(" in sql
    # 源表物理名随上传自增，SQL 中应引用正确表名
    assert f'"{data["result"]["source_table"]}"' in sql


def test_parse_add_column(client, auth_headers, sales_table_id, monkeypatch):
    _mock_llm(monkeypatch, ADD_COL_OK)
    resp = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "增加一列是否大单"}
    )
    data = resp.json()
    assert data["valid"] is True
    assert "SELECT *" in data["sql_preview"]
    assert "AS \"is_big\"" in data["sql_preview"]


def test_parse_invalid_returns_errors(client, auth_headers, sales_table_id, monkeypatch):
    _mock_llm(monkeypatch, {**AGG_OK, "dimensions": ["不存在的字段"]})
    resp = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "统计"}
    )
    data = resp.json()
    assert data["valid"] is False
    assert data["errors"]
    assert data["raw"]  # 原始输出保留供排查


def test_parse_llm_down(client, auth_headers, sales_table_id, monkeypatch):
    def fake(system, user):
        raise OllamaError("connection refused")

    monkeypatch.setattr(ollama_service, "chat_json", fake)
    resp = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "统计"}
    )
    assert resp.status_code == 502


def test_parse_table_not_found(client, auth_headers):
    resp = client.post("/api/nl/parse", headers=auth_headers, json={"table_id": 999, "question": "统计"})
    assert resp.status_code == 404


def test_parse_requires_auth(client, sales_table_id):
    resp = client.post("/api/nl/parse", json={"table_id": sales_table_id, "question": "统计"})
    assert resp.status_code == 401


def test_confirm_flow(client, auth_headers, sales_table_id, monkeypatch):
    _mock_llm(monkeypatch, AGG_OK)
    parse_id = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "统计"}
    ).json()["parse_id"]

    resp = client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parse_id})
    assert resp.status_code == 200
    assert resp.json()["confirmed"] is True

    # 重复确认幂等
    assert client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parse_id}).status_code == 200


def test_confirm_invalid_parse_rejected(client, auth_headers, sales_table_id, monkeypatch):
    _mock_llm(monkeypatch, {**AGG_OK, "dimensions": ["bad"]})
    parse_id = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": sales_table_id, "question": "统计"}
    ).json()["parse_id"]
    resp = client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parse_id})
    assert resp.status_code == 400
