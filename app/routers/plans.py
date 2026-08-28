"""计划接口路由。

任务 1.2 仅实现 GET /plans 列表查询（keyword/page/page_size）。
契约依据：changes/my-plans-page/specs/plan-api/spec.md「计划列表接口（GET /plans）」：
- 无 status 参数（产品决策 2026-08-28：状态系统取消，仅 completed 区分草稿/非草稿）。
- keyword：name 忽略大小写模糊匹配（ilike），服务端执行（设计决策 3）。
- 排序：updated_at 倒序（spec「默认排序」场景）。
- 分页：page>=1、1<=page_size<=100；响应 items/total/page/page_size。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Plan
from app.schemas import PlanListOut

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
