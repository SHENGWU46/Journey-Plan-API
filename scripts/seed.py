"""开发演示数据脚本（异步版）。

运行方式（journey-plan-api 目录）：
    python scripts/seed.py

幂等性：每次执行先清空 plans 表再重建，重复运行结果一致。
数据风格参照 docs/journey-plan-prototype.html 的演示计划（京都秋日漫游 / 大理环海慢游 /
厦门文艺周末等），按任务 1.2 要求调整为：
- 3 条非草稿（completed=true，含 destination/往返日期/人数/总预算，日期覆盖过去与未来）；
- 1 条草稿（仅名称，completed=false，destination/日期/人数为 null、total_budget 0）。

注意：因引擎已改为异步（aiosqlite / aiomysql），本脚本用 asyncio 驱动。
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

# 允许直接 `python scripts/seed.py` 运行（scripts 目录不在 sys.path 时也能导入 app 包）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 控制台统一 UTF-8 输出（避免 Windows GBK 控制台对部分字符报 UnicodeEncodeError）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import delete, select  # noqa: E402

from app.models import AsyncSessionLocal, Base, Plan, engine  # noqa: E402

DEMO_PLANS = [
    # 非草稿：未来行程
    dict(
        name="京都秋日漫游",
        destination="日本 · 京都",
        depart_date=date(2026, 10, 2),
        return_date=date(2026, 10, 9),
        people_count=2,
        completed=True,
        total_budget=17400,
    ),
    # 非草稿：过去行程
    dict(
        name="大理环海慢游",
        destination="云南 · 大理",
        depart_date=date(2026, 8, 15),
        return_date=date(2026, 8, 19),
        people_count=4,
        completed=True,
        total_budget=18400,
    ),
    # 非草稿：未来行程
    dict(
        name="北海道雪国之约",
        destination="日本 · 北海道",
        depart_date=date(2026, 12, 20),
        return_date=date(2026, 12, 25),
        people_count=2,
        completed=True,
        total_budget=26000,
    ),
    # 草稿：仅名称，其余字段留空（completed=false 即草稿）
    dict(name="成都美食探访", completed=False),
]


async def main() -> None:
    # 全新环境自动建表（正式环境由 Alembic 迁移管理）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # 清空重建，保证幂等
        deleted = (await session.execute(delete(Plan))).rowcount or 0
        session.add_all(Plan(**data) for data in DEMO_PLANS)
        await session.commit()
        rows = (await session.scalars(select(Plan).order_by(Plan.id))).all()

    print(f"已清空旧数据 {deleted} 条，写入 {len(rows)} 条演示计划：")
    for plan in rows:
        draft = "" if plan.completed else "（草稿，仅名称）"
        dates = (
            f"{plan.depart_date} ~ {plan.return_date}"
            if plan.depart_date and plan.return_date
            else "无日期"
        )
        print(
            f"  [{plan.id}] {plan.name} | {dates} | {plan.people_count}人 | "
            f"预算 {plan.total_budget} | completed={plan.completed} {draft}"
        )


if __name__ == "__main__":
    asyncio.run(main())
