"""数据库连接封装（SQLAlchemy 2.0，设计决策 1）。

- engine：按 app.config.get_database_url() 创建，SQLite 开发 / MySQL 生产。
- Base：所有 ORM 模型的声明基类。
- SessionLocal：应用会话工厂（供后续 API 任务使用）。
- get_session()：FastAPI 依赖注入用的会话生成器（任务 1.2/1.3 挂载路由时接入）。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_database_url

# 仅创建 engine 对象，惰性连接；首次使用时才真正建立数据库连接。
engine = create_engine(get_database_url())

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """ORM 声明基类：所有模型的元数据（Base.metadata）集中于此。"""


def get_session():
    """会话上下文管理器：FastAPI 依赖注入使用，请求结束自动关闭。"""
    with SessionLocal() as session:
        yield session
