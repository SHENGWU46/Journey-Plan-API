"""数据模型：day_plans 表（每日计划，对应原型 STEP4 单日详情 FR-DY-02~06）。

字段契约：
- plan_id:     所属计划（外键 plans.id），查询一律经计划归属校验后访问
- day_index:   第几天，从 1 开始（与「第 1 天 / 第 2 天」展示口径一致）
- day_date:    当日日期，必填（agent 入参的 date）
- weather:     当日天气，AI 生成后可由用户手改
- tour_time:   当日游玩时间段，用户自填（可选）
- daily_budget: 当日预算，用户自填（可选）
- attractions: 已选入「我的路线」的景点，JSON 数组文本，保持用户选择顺序。
               用文本而非关联表：景点为 agent 输出的一次性快照，MVP 不需要按景点检索。
- ai_generated: 是否经 AI 推荐生成过（驱动列表页「待推荐 / 已推荐」角标）
- created_at / updated_at: 默认当前 UTC 时间；updated_at 更新时自动刷新

唯一性：同一计划的同一天只应有一条记录（plan_id + day_index）。
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


def _utcnow() -> datetime:
    """返回无时区 UTC 当前时间，跨 SQLite/MySQL 均存储为 naive datetime。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DayPlan(Base):
    __tablename__ = "day_plans"
    __table_args__ = (
        UniqueConstraint("plan_id", "day_index", name="uq_day_plans_plan_id_day_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id"), nullable=False, index=True
    )
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    day_date: Mapped[date] = mapped_column(Date, nullable=False)
    weather: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tour_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    daily_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attractions: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_cards: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<DayPlan id={self.id} plan_id={self.plan_id} "
            f"day_index={self.day_index} date={self.day_date}>"
        )
