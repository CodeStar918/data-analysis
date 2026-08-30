"""Celery 应用：异步任务（阶段 5 统计结果生成）。

开发/测试默认 CELERY_EAGER=true 同步执行，无需 Redis；
生产部署设 CELERY_EAGER=false，启动 worker：
  celery -A app.core.celery_app worker -l info
"""
from app.core.config import get_settings
from celery import Celery

_settings = get_settings()

celery_app = Celery(
    "report_platform",
    broker=_settings.REDIS_URL,
    backend=_settings.REDIS_URL,
    include=["app.services.job_service"],
)
celery_app.conf.task_always_eager = _settings.CELERY_EAGER
celery_app.conf.task_store_eager_result = True
celery_app.conf.timezone = "Asia/Shanghai"
