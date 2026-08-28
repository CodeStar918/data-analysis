"""日志配置：统一格式，控制台输出。"""
import logging
import sys

from app.core.config import get_settings


def setup_logging() -> logging.Logger:
    settings = get_settings()
    logger = logging.getLogger("app")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(settings.LOG_LEVEL.upper())
    return logger
