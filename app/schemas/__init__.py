"""Pydantic 模型包（对齐 fastapi学习/AN-API/schemas）：按模块拆分。

- plan.py：计划相关（PlanOut / PlanListOut / PlanIn / PlanPatch）
- user.py：认证相关（UserOut / LoginIn / RegisterIn / LoginOut）

统一在此再导出，路由层仍可 `from app.schemas import PlanOut`。
"""

from app.schemas.plan import PlanIn, PlanListOut, PlanOut, PlanPatch
from app.schemas.user import LoginIn, LoginOut, RegisterIn, UserOut

__all__ = [
    "LoginIn",
    "LoginOut",
    "PlanIn",
    "PlanListOut",
    "PlanOut",
    "PlanPatch",
    "RegisterIn",
    "UserOut",
]
