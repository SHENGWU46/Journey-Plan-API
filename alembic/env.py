"""Alembic 环境（异步 SQLAlchemy 版，对齐 fastapi学习/AN-API/alembic/env.py）。

连接串由 app.settings.DB_URI 全局变量注入——
该项目通过 DATABASE_URL 环境变量在 SQLite（开发）与 MySQL（生产）之间切换。
异步引擎需通过 run_async_migrations() 在事件循环中驱动迁移。
"""

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app import settings
from app.models import Base

# Alembic Config 对象（提供 .ini 文件中的值访问）
config = context.config

# 注入数据库连接串（取自 app.settings.DB_URI 全局变量，未设置则回退 SQLite 默认）
database_url = settings.DB_URI
if database_url is None:
    raise ValueError("DB_URI not resolvable from app.settings")
config.set_main_option("sqlalchemy.url", database_url)

# 配置 Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 用于 autogenerate 的模型元数据
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只配置 URL，不创建 Engine。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：创建异步 Engine 并运行迁移。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """入口：在事件循环中驱动异步迁移。"""
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
