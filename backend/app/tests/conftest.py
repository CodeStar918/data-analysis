"""测试夹具：每个测试使用独立临时 SQLite 库与 DuckDB 文件。"""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def test_env(monkeypatch, tmp_path):
    """隔离环境：独立 SQLite / DuckDB / 配置缓存。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path}")
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("MAX_UPLOAD_MB", "5")
    # 清除配置缓存，使环境变量生效
    from app.core.config import get_settings

    get_settings.cache_clear()
    # 重置数据库与 DuckDB 引擎缓存
    import app.db.session as session_mod
    from app.services import duckdb_service

    monkeypatch.setattr(session_mod, "_engine", None)
    monkeypatch.setattr(session_mod, "_SessionLocal", None)
    duckdb_service.reset_conn()

    from app.models.base_seed import init_db
    from app.services import db_service

    engine = session_mod.get_engine()
    init_db(engine)
    yield engine

    db_service.close_all()
    duckdb_service.reset_conn()
    engine.dispose()
    os.remove(path)


@pytest.fixture()
def client(test_env) -> TestClient:
    from app.db.session import get_db
    from app.main import app

    factory = sessionmaker(bind=test_env, expire_on_commit=False)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client) -> dict:
    """登录获取 Token。"""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sales_table_id(client, auth_headers) -> int:
    """上传销售样例 Excel（区域/销售金额/下单日期），返回表 ID。"""
    from app.tests.excel_helpers import SAMPLE_TIME, build_xlsx

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
    resp = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("sales.xlsx", content, "application/octet-stream")},
    )
    return resp.json()["tables"][0]["id"]


@pytest.fixture()
def confirmed_parse_id(client, auth_headers, monkeypatch):
    """mock LLM 上传 3 行销售数据并完成解析确认，返回 parse_id。"""
    from app.services import ollama_service
    from app.tests.excel_helpers import SAMPLE_TIME, build_xlsx

    monkeypatch.setattr(
        ollama_service,
        "chat_json",
        lambda s, u: {
            "intent": "aggregate",
            "source_table": "up_1_0",
            "dimensions": ["区域"],
            "measures": [{"field": "销售金额", "agg": "SUM"}],
            "filters": [],
            "new_columns": [],
        },
    )
    content = build_xlsx(
        {
            "销售明细": [
                ["区域", "销售金额", "下单日期"],
                ["华东", 5000, SAMPLE_TIME],
                ["华北", 8000, SAMPLE_TIME],
                ["华东", 3000, SAMPLE_TIME],
            ]
        }
    )
    up = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("sales.xlsx", content, "application/octet-stream")},
    ).json()
    parsed = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": up["tables"][0]["id"], "question": "按区域统计销售额"}
    ).json()
    client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    return parsed["parse_id"]
