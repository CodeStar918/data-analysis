"""FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.approval import router as approval_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.datasource import router as datasource_router
from app.api.metadata import router as metadata_router
from app.api.jobs import router as jobs_router
from app.api.nl_parse import router as nl_parse_router
from app.api.result import router as result_router
from app.api.upload import router as upload_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import get_engine
from app.models.base_seed import init_db

logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表并初始化管理员账号
    init_db(get_engine())
    logger.info("应用启动: %s (%s)", get_settings().APP_NAME, get_settings().ENV)
    yield
    logger.info("应用停止")


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().APP_NAME, lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(upload_router)
    app.include_router(datasource_router)
    app.include_router(metadata_router)
    app.include_router(nl_parse_router)
    app.include_router(jobs_router)
    app.include_router(result_router)
    app.include_router(approval_router)
    app.include_router(audit_router)

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
