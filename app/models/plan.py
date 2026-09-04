"""数据模型：plans 表（PRD 5.1 + 设计决策 7/8/9）。

字段契约（对齐 changes/my-plans-page/specs/plan-api/spec.md 计划对象）：
- user_id:       归属用户（用户决策 2026-09-02：计划与登录用户绑定，必填外键语义）
- name:          非空
- destination / depart_date / return_date / people_count:
                 决策 8，草稿关键字段可空（Step1 仅命名即可持久化）
- depart_date / return_date: 决策 9，无时区 Date 字段
- completed:     布尔，false=草稿 / true=非草稿（产品决策 2026-08-28）
- total_budget:  默认 0（草稿为 0）
- created_at / updated_at: 默认当前 UTC 时间；updated_at 在更新时自动刷新
- total_days / generated_days: 决策 9/12，查询层派生，模型层不存储
"""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def _utcnow() -> datetime:
    """返回无时区 UTC 当前时间，跨 SQLite/MySQL 均存储为 naive datetime。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 归属用户：计划与登录用户绑定（2026-09-02），查询一律按 user_id 隔离。
    # 未加真正的 ForeignKeyConstraint，避免对既有 0001 迁移与存量数据做破坏性变更；
    # 级联清理由应用层保证（后续如需可在迁移中补外键）。
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(100), nullable=True)
    depart_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    people_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    total_budget: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<Plan id={self.id} name={self.name!r} completed={self.completed}>"
