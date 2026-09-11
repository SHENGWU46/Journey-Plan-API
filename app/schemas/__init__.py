"""Pydantic 模型包（对齐 fastapi学习/AN-API/schemas）：按模块拆分。

- plan.py：计划相关（PlanOut / PlanListOut / PlanIn / PlanPatch）
- user.py：认证相关（UserOut / LoginIn / RegisterIn / LoginOut）
- daily_plan.py：每日计划相关（Attraction / DailyPlanGenReq / DailyPlanGenOut /
  DayPlanUpsertIn / DayPlanOut / DayPlanListOut）

统一在此再导出，路由层仍可 `from app.schemas import PlanOut`。
"""

from app.schemas.daily_plan import (
    Attraction,
    DailyPlanGenOut,
    DailyPlanGenReq,
    DayPlanListOut,
    DayPlanOut,
    DayPlanUpsertIn,
)
from app.schemas.plan import PlanIn, PlanListOut, PlanOut, PlanPatch
from app.schemas.user import (
    LoginIn,
    LoginOut,
    RefreshIn,
    RefreshOut,
    RegisterIn,
    UserOut,
)

__all__ = [
    "Attraction",
    "DailyPlanGenOut",
    "DailyPlanGenReq",
    "DayPlanListOut",
    "DayPlanOut",
    "DayPlanUpsertIn",
    "LoginIn",
    "LoginOut",
    "PlanIn",
    "PlanListOut",
    "PlanOut",
    "PlanPatch",
    "RefreshIn",
    "RefreshOut",
    "RegisterIn",
    "UserOut",
]
