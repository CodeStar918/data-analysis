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
