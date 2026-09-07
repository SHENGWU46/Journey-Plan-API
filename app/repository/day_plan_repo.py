"""每日计划数据访问层（DayPlanRepository）。

职责边界与 PlanRepository 一致：
- 本层只做 day_plans 表的查询与持久化，不抛 HTTPException、不决定响应格式；
  计划归属校验由路由层先用 PlanRepository.get_by_id 完成，越权在路由层转 404。
- 读方法只执行查询；写方法内部完成 add/commit/refresh，一次请求调用一个写方法。

与 PlanRepository.update 的差异：update 会跳过 None 值（None 表示「不改」），
而 upsert 由调用方用 exclude_unset 先筛掉未提供的字段，故全部照设，
以支持把 weather/attractions 显式清空（用户删掉路线里最后一个景点）。
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DayPlan


class DayPlanRepository:
    """day_plans 表的数据访问对象，持有调用方注入的会话。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_days(self, plan_id: int) -> Sequence[DayPlan]:
        """按天序号升序返回某计划下的全部每日计划。"""
        stmt = (
            select(DayPlan)
            .where(DayPlan.plan_id == plan_id)
            .order_by(DayPlan.day_index)
        )
        return (await self.session.scalars(stmt)).all()

    async def count_by_plan(self, plan_id: int) -> int:
        """返回某计划下已保存每日计划的数量（驱动计划卡片「已生成 X/N」）。"""
        stmt = (
            select(func.count())
            .select_from(DayPlan)
            .where(DayPlan.plan_id == plan_id)
        )
        return await self.session.scalar(stmt) or 0

    async def get_by_index(self, plan_id: int, day_index: int) -> DayPlan | None:
        """按 (plan_id, day_index) 取单日计划；不存在返回 None。"""
        stmt = select(DayPlan).where(
            DayPlan.plan_id == plan_id, DayPlan.day_index == day_index
        )
        return (await self.session.scalars(stmt)).one_or_none()

    async def upsert(
        self, plan_id: int, day_index: int, day_date, fields: dict
    ) -> DayPlan:
        """按 (plan_id, day_index) 新增或更新，返回已刷新（含 id 与默认字段）的实例。

        fields 应为「调用方已用 exclude_unset 过滤后的字段」，故此处不再跳过 None。
        """
        day = await self.get_by_index(plan_id, day_index)
        if day is None:
            day = DayPlan(plan_id=plan_id, day_index=day_index, day_date=day_date)
            self.session.add(day)
        else:
            # 行程日期可能被用户在 STEP1 改动，以当次提交为准
            day.day_date = day_date
        for key, value in fields.items():
            setattr(day, key, value)
        await self.session.commit()
        await self.session.refresh(day)
        return day

    async def delete_by_plan(self, plan_id: int) -> None:
        """删除某计划下的全部每日计划。

        计划删除时调用，避免 day_plans 留下指向已不存在计划的孤儿数据
        （模型层未建数据库级外键级联，清理由应用层保证）。
        """
        rows = (
            await self.session.scalars(
                select(DayPlan).where(DayPlan.plan_id == plan_id)
            )
        ).all()
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()
