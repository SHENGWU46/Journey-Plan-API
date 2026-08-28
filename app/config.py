"""应用配置。

设计决策 1：数据库通过 DATABASE_URL 环境变量切换——
开发默认 SQLite（sqlite:///./journey_plan.db），生产通过
DATABASE_URL 指向 MySQL 8.x（如 mysql+pymysql://user:pass@host/db）。
"""

import os

DEFAULT_DATABASE_URL = "sqlite:///./journey_plan.db"


def get_database_url() -> str:
    """返回数据库连接串，未设置环境变量时回退到开发默认 SQLite。"""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
