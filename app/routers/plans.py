"""计划接口路由。

任务 1.2 实现 GET /plans 列表查询（keyword/page/page_size）；
任务 1.3 新增 POST /plans（草稿创建）、PATCH /plans/{id}（改名）、
DELETE /plans/{id}（物理删除）。
契约依据：changes/my-plans-page/specs/plan-api/spec.md「计划列表接口（GET /plans）」
「草稿创建接口（POST /plans）」「计划改名接口（PATCH /plans/{id}）」
「计划删除接口（DELETE /plans/{id}）」：
- 无 status 参数（产品决策 2026-08-28：状态系统取消，仅 completed 区分草稿/非草稿）。
- keyword：name 忽略大小写模糊匹配（ilike），服务端执行（设计决策 3）。
- 排序：updated_at 倒序（spec「默认排序」场景）。
- 分页：page>=1、1<=page_size<=100；响应 items/total/page/page_size。
- 名称：去首尾空格后 2-20 字符（Pydantic 校验，非法 422）；POST 返回 201，
  PATCH 仅更新 name 与 updated_at；不存在返回 404；DELETE 物理删除返回 204。
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Plan
from app.schemas import PlanIn, PlanListOut, PlanOut, PlanPatch

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=PlanListOut)
def list_plans(
    keyword: str | None = Query(default=None, description="名称关键字，忽略大小写模糊匹配"),
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数（1-100）"),
    session: Session = Depends(get_session),
) -> PlanListOut:
    """计划列表：关键字搜索 + 分页，按 updated_at 倒序。"""
    stmt = select(Plan)
    if keyword:
        stmt = stmt.where(Plan.name.ilike(f"%{keyword}%"))

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(
        stmt.order_by(Plan.updated_at.desc(), Plan.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PlanListOut(items=rows, total=total, page=page, page_size=page_size)


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanIn, session: Session = Depends(get_session)
) -> PlanOut:
    """创建草稿计划（spec「草稿创建接口」）：仅名称（已去空格），
    completed=false，destination/depart_date/return_date/people_count 为 null，
    total_budget 0（均由模型默认值落地），返回 201 与完整计划对象。"""
    plan = Plan(name=payload.name)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


@router.patch("/{plan_id}", response_model=PlanOut)
def rename_plan(
    plan_id: int, payload: PlanPatch, session: Session = Depends(get_session)
) -> PlanOut:
    """改名（spec「计划改名接口」）：仅更新名称；updated_at 由模型 onupdate
    自动刷新；其余字段不变；计划不存在返回 404。"""
    plan = session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="计划不存在")
    plan.name = payload.name
    session.commit()
    session.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, session: Session = Depends(get_session)) -> Response:
    """物理删除计划（spec「计划删除接口」，MVP 无回收站）：删除后列表不再返回；
    计划不存在返回 404。"""
    plan = session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="计划不存在")
    session.delete(plan)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
