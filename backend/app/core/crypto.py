"""敏感信息加密（阶段 7）：数据库连接串等落库前加密存储。

- Fernet 对称加密，密钥由 SECURITY_KEY（缺省用 JWT_SECRET）派生
- 带 enc:v1: 前缀；解密时自动兼容旧明文（渐进迁移）
"""
import base64
import hashlib

from app.core.config import get_settings
from cryptography.fernet import Fernet

_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    settings = get_settings()
    key_src = (settings.SECURITY_KEY or settings.JWT_SECRET).encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(key_src).digest())
    return Fernet(key)


def encrypt(plain: str) -> str:
    return _PREFIX + _fernet().encrypt(plain.encode()).decode()


def decrypt(value: str) -> str:
    if not value or not value.startswith(_PREFIX):
        return value  # 兼容历史明文
    return _fernet().decrypt(value[len(_PREFIX):]).decode()
