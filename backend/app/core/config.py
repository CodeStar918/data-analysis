"""全局配置：通过环境变量/.env 覆盖默认值。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "报表生成平台"
    ENV: str = "dev"

    # 元数据库连接：开发默认 SQLite，生产可切换 PostgreSQL/MySQL
    DATABASE_URL: str = "sqlite:///./backend_dev.db"

    # JWT 鉴权
    JWT_SECRET: str = "change-me-in-production-please-use-32-bytes-min"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 8 * 60

    LOG_LEVEL: str = "INFO"

    # 阶段 2：Excel 上传与 DuckDB
    DUCKDB_PATH: str = "./data/report.duckdb"
    MAX_UPLOAD_MB: int = 20

    # 阶段 4：Ollama 本地模型
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_TIMEOUT_SECONDS: int = 120

    # 阶段 5：异步任务（开发默认 eager 同步执行，无需 Redis；部署时设为 false 并启动 worker）
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_EAGER: bool = True

    # 阶段 7：安全加固。SECURITY_KEY 为空时派生自 JWT_SECRET
    SECURITY_KEY: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
