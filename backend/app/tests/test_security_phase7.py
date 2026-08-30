"""阶段 7 安全加固测试：连接信息加密、审计日志完整性、越权访问。"""

from app.core.crypto import decrypt, encrypt
from app.services import ollama_service
from app.tests.excel_helpers import SAMPLE_TIME, build_xlsx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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


# ---------- 加密 ----------

def test_crypto_roundtrip():
    cipher = encrypt("postgresql://user:secret@host:5432/db")
    assert cipher.startswith("enc:v1:")
    assert "secret" not in cipher
    assert decrypt(cipher) == "postgresql://user:secret@host:5432/db"


def test_crypto_plain_passthrough():
    assert decrypt("sqlite:///./old.db") == "sqlite:///./old.db"
    assert decrypt("") == ""


def test_db_conn_info_encrypted_at_rest(client, auth_headers, tmp_path):
    """数据源连接串落库必须是密文，且预览仍能正常工作（自动解密）。"""
    path = tmp_path / "biz7.db"
    eng = create_engine(f"sqlite:///{path}")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE t7 (id INTEGER, region VARCHAR)"))
        conn.execute(text("INSERT INTO t7 VALUES (1, '华东')"))
    eng.dispose()

    url = f"sqlite:///{path.as_posix()}"
    reg = client.post(
        "/api/datasources/db", headers=auth_headers, json={"name": "加密测试库", "url": url}
    ).json()
    assert reg["datasource_id"] > 0

    # 数据库中是密文
    from app.db.session import get_engine

    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        from app.models.datasource import Datasource

        ds = db.get(Datasource, reg["datasource_id"])
        assert ds.conn_info.startswith("enc:v1:")
        assert url not in ds.conn_info
        assert decrypt(ds.conn_info) == url

    # 预览走解密后的连接串
    tables = client.get(f"/api/datasources/{reg['datasource_id']}/tables", headers=auth_headers).json()
    pv = client.get(f"/api/tables/{tables[0]['id']}/preview", headers=auth_headers).json()
    assert pv["rows"][0][1] == "华东"

    from app.services import db_service

    db_service.close_all()
    path.unlink(missing_ok=True)


# ---------- 审计完整性 ----------

def test_audit_flow_completeness(client, auth_headers, monkeypatch):
    """登录 → 上传 → 解析确认 → 建任务 → 导出，各环节均有审计记录。"""
    _mock_llm(monkeypatch, AGG_OK)
    content = build_xlsx(
        {
            "销售明细": [
                ["区域", "销售金额"],
                ["华东", 5000],
                ["华北", 8000],
            ]
        }
    )
    up = client.post(
        "/api/upload",
        headers=auth_headers,
        files={"file": ("a.xlsx", content, "application/octet-stream")},
    ).json()
    parsed = client.post(
        "/api/nl/parse", headers=auth_headers, json={"table_id": up["tables"][0]["id"], "question": "按区域统计"}
    ).json()
    client.post("/api/nl/confirm", headers=auth_headers, json={"parse_id": parsed["parse_id"]})
    job = client.post("/api/jobs", headers=auth_headers, json={"parse_id": parsed["parse_id"]}).json()
    assert job["status"] == "success"
    rid = job["result_table_id"]
    client.get(f"/api/results/{rid}/export?format=csv", headers=auth_headers)

    actions = {a["action"] for a in client.get("/api/audit", headers=auth_headers).json()}
    assert {"login", "upload", "parse", "parse_confirm", "job_create", "export"} <= actions


def test_audit_login_failure_recorded(client, auth_headers):
    client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
    entries = client.get("/api/audit?action=login_failed", headers=auth_headers).json()
    assert len(entries) >= 1


def test_audit_requires_admin(client, auth_headers, test_env):
    from sqlalchemy.orm import sessionmaker as sm

    from app.core.security import hash_password
    from app.models.user import User

    factory = sm(bind=test_env, expire_on_commit=False)
    with factory() as db:
        db.add(User(username="emp7", password_hash=hash_password("p123456"), role="employee"))
        db.commit()
    token = client.post("/api/auth/login", json={"username": "emp7", "password": "p123456"}).json()["access_token"]
    resp = client.get("/api/audit", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
