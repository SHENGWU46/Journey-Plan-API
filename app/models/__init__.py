"""模型包：异步引擎 / 会话工厂 / 声明基类集中于此（对齐 fastapi学习/AN-API）。

参考 AN-API 的 models/__init__.py：engine、AsyncSessionFactory、Base 集中定义在
本文件，各模型模块（如 plan.py）从本包导入 Base，保证 ORM 元数据只有一份权威
来源，Alembic 的 target_metadata 也直接取 Base.metadata。

- engine：按 app.settings.DB_URI 创建异步引擎（aiosqlite 开发 / aiomysql 生产）。
- AsyncSessionFactory：异步会话工厂；AsyncSessionLocal 为兼容旧名的别名。
- Base：声明基类，带与 0001 迁移一致的约束命名约定（避免 autogenerate 漂移）。
- get_session()：FastAPI 依赖注入入口，请求结束自动关闭会话。
"""

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app import settings

# 仅创建 engine 对象，惰性连接；首次使用时才真正建立数据库连接。
engine = create_async_engine(settings.DB_URI, echo=settings.DB_ECHO)

AsyncSessionFactory = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# 兼容旧引用（原 app.database.AsyncSessionLocal）
AsyncSessionLocal = AsyncSessionFactory


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类，元数据集中在 Base.metadata。

    naming_convention 与 alembic/versions/0001_create_plans.py 的约束命名保持
    一致（主键即 pk_plans），使后续 autogenerate 不会因约束无名而产生假差异。
    """

    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


async def get_session():
    """异步会话生成器：FastAPI 依赖注入使用，请求结束自动关闭。"""
    async with AsyncSessionFactory() as session:
        yield session


from .plan import Plan  # noqa: E402  模型模块必须在 Base 定义之后再导入
from .user import User  # noqa: E402

__all__ = [
    "AsyncSession",
    "AsyncSessionFactory",
    "AsyncSessionLocal",
    "Base",
    "Plan",
    "User",
    "engine",
    "get_session",
]
