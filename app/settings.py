"""全局配置（设计决策：密钥/连接串走环境变量）。

对齐 fastapi学习/AN-API 的 settings 用法——全项目只从本模块 import 配置常量，
不再在各处散落 os.environ 调用。

数据库 URL 规则：
- 优先读取环境变量 DATABASE_URL（本地 MySQL 示例：
  mysql+aiomysql://user:pwd@127.0.0.1:3306/journey_plan?charset=utf8mb4）
- 未设置时回退到本地 SQLite（journey_plan.db），便于无依赖开发。

JWT 规则（对齐 AN-API：settings 直接暴露常量，AuthHandler 里
`secret = settings.JWT_SECRET_KEY`）：
- 优先读取环境变量 JWT_SECRET_KEY（生产必须注入）；
- 未注入时用固定开发默认值（不是每次随机——随机会导致服务重启后
  已签发的 token 全部失效）。
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv  # noqa: E402

# 加载项目根目录的 .env（journey-plan-api/.env），使其中填写的 DATABASE_URL 生效。
# 显式指定路径而非依赖调用方的工作目录；.env 已被 .gitignore 忽略，不入库。
# python-dotenv 默认按 UTF-8 读取，文件内的中文注释不会导致解码错误。
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ---------------------------------------------------------------- 数据库

# 开发默认：SQLite（异步驱动 aiosqlite）；生产/本地 MySQL 通过 DATABASE_URL 覆盖。
_DEFAULT_SQLITE = "sqlite+aiosqlite:///./journey_plan.db"

DB_URI = os.environ.get("DATABASE_URL") or _DEFAULT_SQLITE

# SQL 日志：开发期可设 DB_ECHO=1 打印所有执行 SQL，默认关闭。
DB_ECHO = os.environ.get("DB_ECHO", "").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------- JWT

# 与 AN-API 的差异：AN-API 把真实密钥硬编码在源码里（JWT_SECRET_KEY="zgrnfzgrnf"），
# 本项目按 AGENTS.md「禁止硬编码密钥」改为环境变量优先；默认值是公开的占位串，
# 仅用于本地开发，生产环境务必通过环境变量注入真实密钥。
_DEFAULT_JWT_SECRET = "dev-only-journey-plan-secret-change-me"

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or _DEFAULT_JWT_SECRET

JWT_ALGORITHM = "HS256"

JWT_ACCESS_TOKEN_EXPIRES = timedelta(
    days=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_DAYS", "15"))
)
JWT_REFRESH_TOKEN_EXPIRES = timedelta(
    days=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES_DAYS", "30"))
)
