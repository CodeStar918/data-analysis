"""配置与日志模块单元测试。"""
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.APP_NAME
    assert s.JWT_ALGORITHM == "HS256"
    assert s.JWT_EXPIRE_MINUTES > 0


def test_settings_cache():
    assert get_settings() is get_settings()


def test_setup_logging():
    logger = setup_logging()
    assert logger.handlers
    assert logger.level == 20  # INFO
