"""集成测试：上传 → 解析 → 导入 DuckDB → 元数据 → 预览。"""
from app.tests.excel_helpers import SAMPLE_TIME, build_xlsx


def _upload(client, headers, content: bytes, filename="test.xlsx"):
    return client.post(
        "/api/upload",
        headers=headers,
        files={"file": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_upload_requires_auth(client):
    resp = client.post(
        "/api/upload", files={"file": ("a.xlsx", b"xlsx-bytes")}
    )
    assert resp.status_code == 401


def test_upload_and_preview_flow(client, auth_headers):
    content = build_xlsx(
        {
            "销售明细": [
                ["区域", "销售金额", "下单日期"],
                ["华东", 5000.5, SAMPLE_TIME],
                ["华北", 8000, SAMPLE_TIME],
                ["华东", 3000, SAMPLE_TIME],
            ]
        }
    )
    resp = _upload(client, auth_headers, content)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "test.xlsx"
    assert len(data["tables"]) == 1
    table = data["tables"][0]
    assert table["sheet_name"] == "销售明细"
    assert table["row_count"] == 3
    assert [c["business_name"] for c in table["columns"]] == ["区域", "销售金额", "下单日期"]

    # 数据源列表
    resp = client.get("/api/datasources", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["id"] == data["datasource_id"]

    # 表列表
    resp = client.get(f"/api/datasources/{data['datasource_id']}/tables", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()[0]["table_name"] == table["table_name"]

    # 预览
    resp = client.get(f"/api/tables/{table['id']}/preview?limit=2", headers=auth_headers)
    assert resp.status_code == 200
    preview = resp.json()
    assert len(preview["rows"]) == 2
    assert preview["rows"][0][0] == "华东"
    assert [c["business_name"] for c in preview["columns"]] == ["区域", "销售金额", "下单日期"]


def test_upload_wrong_ext(client, auth_headers):
    resp = _upload(client, auth_headers, b"not excel", filename="a.txt")
    assert resp.status_code == 400


def test_upload_empty_xlsx(client, auth_headers):
    content = build_xlsx({"Sheet1": []})
    resp = _upload(client, auth_headers, content)
    assert resp.status_code == 400


def test_upload_oversized(client, auth_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_MB", 1)
    big = b"\x00" * (2 * 1024 * 1024)
    resp = _upload(client, auth_headers, big)
    assert resp.status_code == 400
    assert "大小限制" in resp.json()["detail"]


def test_null_values_in_preview(client, auth_headers):
    content = build_xlsx(
        {"t": [["a", "b"], [1, None], [2, "x"]]}
    )
    resp = _upload(client, auth_headers, content)
    table_id = resp.json()["tables"][0]["id"]
    resp = client.get(f"/api/tables/{table_id}/preview", headers=auth_headers)
    rows = resp.json()["rows"]
    assert rows[0][1] is None  # 空单元格 → null


def test_table_not_found(client, auth_headers):
    resp = client.get("/api/tables/999/preview", headers=auth_headers)
    assert resp.status_code == 404
