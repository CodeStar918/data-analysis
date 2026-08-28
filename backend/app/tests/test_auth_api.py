"""接口测试：健康检查、登录、当前用户。"""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_login_success(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"]
    assert data["username"] == "admin"
    assert data["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
    assert resp.status_code == 401


def test_login_unknown_user(client):
    resp = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_token(client):
    token = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()[
        "access_token"
    ]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"


def test_me_with_bad_token(client):
    resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
    assert resp.status_code == 401


def test_change_password_flow(client):
    headers = {"Authorization": "Bearer " + client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    ).json()["access_token"]}

    # 旧密码错误
    resp = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "wrong-old", "new_password": "newpass123"},
    )
    assert resp.status_code == 400

    # 新密码过短（pydantic 校验 422）
    resp = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "admin123", "new_password": "short"},
    )
    assert resp.status_code == 422

    # 与旧密码相同
    resp = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "admin123", "new_password": "admin123"},
    )
    assert resp.status_code == 400

    # 成功修改 → 旧密码失效、新密码可登录
    resp = client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"old_password": "admin123", "new_password": "newpass123"},
    )
    assert resp.status_code == 200
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"username": "admin", "password": "newpass123"}
    ).status_code == 200

    # 审计已记录
    actions = {a["action"] for a in client.get(
        "/api/audit?action=password_change",
        headers={"Authorization": "Bearer " + client.post(
            "/api/auth/login", json={"username": "admin", "password": "newpass123"}
        ).json()["access_token"]},
    ).json()}
    assert "password_change" in actions


def test_change_password_requires_auth(client):
    resp = client.post(
        "/api/auth/change-password",
        json={"old_password": "a", "new_password": "bbbbbbbb"},
    )
    assert resp.status_code == 401
