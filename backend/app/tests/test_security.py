"""鉴权工具单元测试。"""
import time

import jwt as pyjwt

from app.core.config import get_settings
from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("admin123")
    assert hashed != "admin123"
    assert verify_password("admin123", hashed)
    assert not verify_password("wrong", hashed)


def test_password_hash_unique_salt():
    assert hash_password("pw") != hash_password("pw")


def test_token_roundtrip():
    token = create_access_token(1, "admin")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "1"
    assert payload["username"] == "admin"


def test_expired_token():
    settings = get_settings()
    now = int(time.time())
    token = pyjwt.encode(
        {"sub": "1", "exp": now - 10}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )
    assert decode_token(token) is None


def test_invalid_token():
    assert decode_token("not-a-jwt") is None
