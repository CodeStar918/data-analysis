"""数据库初始化与种子数据。"""
import logging

from app.core.security import hash_password
from app.models.user import Base, User
from sqlalchemy import Engine
from sqlalchemy.orm import Session

logger = logging.getLogger("app")


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        if db.query(User).count() == 0:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
                dept="信息部",
            )
            db.add(admin)
            db.commit()
            logger.info("已初始化默认管理员: admin/admin123（上线前请修改密码）")
