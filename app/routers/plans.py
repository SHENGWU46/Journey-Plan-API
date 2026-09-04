"""计划接口路由（异步版 + Repository 分层 + 登录鉴权）。

本层只做：请求参数解析（Query / Pydantic）、调用 PlanRepository、把结果交给
Pydantic 响应模型、以及 404 等业务判定；不直接编写 SQL。

鉴权（用户决策 2026-09-02）：本模块全部接口要求登录，
且只返回当前登录用户（user_id = token 中的用户 id）自己的计划。

契约依据：changes/my-plans-page/specs/plan-api/spec.md「计划列表接口（GET /plans）」
「草稿创建接口（POST /plans）」「计划改名接口（PATCH /plans/{id}）」
「计划删除接口（DELETE /plans/{id}）」：
- 无 status 参数（产品决策 2026-08-28：状态系统取消，仅 completed 区分草稿/非草稿）。
- keyword：name 忽略大小写模糊匹配（ilike），服务端执行（设计决策 3）。
- 排序：updated_at 倒序（spec「默认排序」场景）。
- 分页：page>=1、1<=page_size<=100；响应 items/total/page/page_size。
- 名称：去首尾空格后 2-20 字符（Pydantic 校验，非法 422）；POST 返回 201，
  PATCH 仅更新 name 与 updated_at；不存在返回 404；DELETE 物理删除返回 204。
- 越权访问他人计划：同样返回 404（不暴露资源存在性）。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthHandler
from app.models import get_session
from app.repository.plan_repo import PlanRepository
from app.schemas import PlanIn, PlanListOut, PlanOut, PlanPatch

router = APIRouter(prefix="/plans", tags=["plans"])

auth_handler = AuthHandler()


@router.get("", response_model=PlanListOut)
async def list_plans(
    keyword: str | None = Query(default=None, description="名称关键字，忽略大小写模糊匹配"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数（1-100）"),
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(auth_handler.auth_access_dependency),
) -> PlanListOut:
    """当前登录用户的计划列表：关键字搜索 + 分页，按 updated_at 倒序。"""
    repo = PlanRepository(session)
    rows, total = await repo.list_plans(
        owner_id=user_id, keyword=keyword, page=page, page_size=page_size
    )
    return PlanListOut(items=rows, total=total, page=page, page_size=page_size)


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanIn,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(auth_handler.auth_access_dependency),
) -> PlanOut:
    """为当前登录用户创建草稿计划（spec「草稿创建接口」）：仅名称（已去空格），
    completed=false，destination/depart_date/return_date/people_count 为 null，
    total_budget 0（均由模型默认值落地），返回 201 与完整计划对象。"""
    repo = PlanRepository(session)
    return await repo.create(owner_id=user_id, name=payload.name)


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan(
    plan_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(auth_handler.auth_access_dependency),
) -> PlanOut:
    """计划详情（spec「计划详情接口」补充）：返回单个完整计划对象；
    计划不存在或不属于当前用户，均返回 404。"""
    repo = PlanRepository(session)
    plan = await repo.get_by_id(plan_id, owner_id=user_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="计划不存在")
    return plan


@router.patch("/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: int,
    payload: PlanPatch,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(auth_handler.auth_access_dependency),
) -> PlanOut:
    """编辑计划（spec「计划编辑接口」补充）：支持多字段部分更新
    （name/destination/depart_date/return_date/people_count/completed/total_budget）。
    未提供字段保持原值；updated_at 由模型 onupdate 自动刷新。
    计划不存在或不属于当前用户，均返回 404。"""
    repo = PlanRepository(session)
    plan = await repo.get_by_id(plan_id, owner_id=user_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="计划不存在")
    fields = payload.model_dump(exclude_unset=True)
    return await repo.update(plan, fields)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: int,
    session: AsyncSession = Depends(get_session),
    user_id: int = Depends(auth_handler.auth_access_dependency),
) -> Response:
    """物理删除计划（spec「计划删除接口」，MVP 无回收站）：删除后列表不再返回；
    计划不存在或不属于当前用户，均返回 404。"""
    repo = PlanRepository(session)
    plan = await repo.get_by_id(plan_id, owner_id=user_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="计划不存在")
    await repo.delete(plan)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
