"""计划数据访问层（PlanRepository，对齐 fastapi学习/AN-API/repository/user_repo.py）。

职责边界：
- 本层只做 plans 表的查询与持久化，不抛 HTTPException、不决定响应格式；
  路由层（app/routers/plans.py）负责编排与 404 等业务判定。
- 读方法只执行查询；写方法内部完成 add/commit/refresh，一次请求调用一个写方法。

数据隔离（用户决策 2026-09-02）：所有方法都带 owner_id，只读写该用户的计划，
越权访问表现为「查不到」（路由层转 404），不暴露资源存在性。

与 AN-API 的差异（重要）：AN-API 的 repo 方法内部使用
`async with self.session.begin()`，同一请求内连续调用两个 repo 方法会因
「事务已开始」而报错；本实现避免该嵌套事务问题，把提交收敛到单个写方法内。
"""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Plan


class PlanRepository:
    """plans 表的数据访问对象，持有调用方注入的会话。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_plans(
        self, owner_id: int, keyword: str | None, page: int, page_size: int
    ) -> tuple[Sequence[Plan], int]:
        """分页查询当前用户的计划：keyword 忽略大小写模糊匹配，按 updated_at/id 倒序。

        返回 (当前页计划列表, 满足条件的总条数)。
        """
        stmt = select(Plan).where(Plan.user_id == owner_id)
        if keyword:
            stmt = stmt.where(Plan.name.ilike(f"%{keyword}%"))

        total = await self.session.scalar(
            select(func.count()).select_from(stmt.subquery())
        )
        rows = (
            await self.session.scalars(
                stmt.order_by(Plan.updated_at.desc(), Plan.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
        return rows, total or 0

    async def get_by_id(self, plan_id: int, owner_id: int) -> Plan | None:
        """按主键取计划，并限定归属用户；不存在或不属于该用户均返回 None。"""
        plan = await self.session.get(Plan, plan_id)
        if plan is None or plan.user_id != owner_id:
            return None
        return plan

    async def create(self, owner_id: int, name: str) -> Plan:
        """创建计划并返回已刷新（含 id 与默认字段）的实例。"""
        plan = Plan(user_id=owner_id, name=name)
        self.session.add(plan)
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def rename(self, plan: Plan, name: str) -> Plan:
        """改名：仅更新 name，updated_at 由模型 onupdate 自动刷新。"""
        plan.name = name
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def update(self, plan: Plan, fields: dict) -> Plan:
        """部分字段更新：fields 为「非 None 字段名 -> 新值」，updated_at 自动刷新。"""
        for key, value in fields.items():
            if value is not None:
                setattr(plan, key, value)
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def delete(self, plan: Plan) -> None:
        """物理删除（MVP 无回收站）。"""
        await self.session.delete(plan)
        await self.session.commit()
