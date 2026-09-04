"""数据模型：users 表（PRD 5 数据需求 · User 实体）。

字段说明：
- username：登录账号，唯一（MVP 账号体系：账号 + 密码，无第三方登录）
- password_hash：bcrypt 哈希，绝不存明文（PRD 4 安全 / AC-NF-02）
- created_at：注册时间，无时区 UTC

密码校验由 User 模型自身承担（hash/verify），路由层与 repository 层不接触哈希细节。
当前 Python 环境的 bcrypt 5.0 对明文有 72 字节上限，故校验前做 UTF-8 截断。
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

# bcrypt 只取明文前 72 字节；超长密码静默截断会导致"能注册但登录不上"，
# 故在哈希与校验两端统一截断，保证行为一致。
_BCRYPT_MAX_BYTES = 72


def _utcnow() -> datetime:
    """返回无时区 UTC 当前时间，跨 SQLite/MySQL 均存储为 naive datetime。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _truncate(raw: str) -> bytes:
    """按 UTF-8 字节截断，避免多字节字符被切半。"""
    encoded = raw.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return encoded
    return encoded[:_BCRYPT_MAX_BYTES]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    def set_password(self, raw_password: str) -> None:
        """写入 bcrypt 哈希（注册 / 改密时调用）。"""
        import bcrypt

        self.password_hash = bcrypt.hashpw(
            _truncate(raw_password), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        """校验明文密码；哈希损坏时返回 False 而非抛异常（避免 500）。"""
        import bcrypt

        try:
            return bcrypt.checkpw(
                _truncate(raw_password), self.password_hash.encode("utf-8")
            )
        except (ValueError, TypeError):
            return False

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
