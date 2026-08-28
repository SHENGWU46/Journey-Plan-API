"""模型层测试：plans 表结构、默认值语义与 updated_at 自动刷新（任务 1.1）。

运行方式：cd journey-plan-api && python -m pytest tests/test_models.py
契约依据：changes/my-plans-page/design.md 决策 7/8/9、specs/plan-api/spec.md 计划对象字段。
"""

import time
from datetime import date

import pytest
from sqlalchemy import Boolean, Date, DateTime, Integer, String, create_engine, inspect
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Plan

EXPECTED_COLUMNS = {
    "id",
    "user_id",
    "name",
    "destination",
    "depart_date",
    "return_date",
    "people_count",
    "completed",
    "total_budget",
    "created_at",
    "updated_at",
}


@pytest.fixture()
def engine():
    """每个测试独立的内存 SQLite 引擎，避免测试间数据串扰。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_plans_table_exists_with_all_columns(engine):
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "plans" in tables

    columns = {col["name"]: col for col in inspector.get_columns("plans")}
    assert set(columns) == EXPECTED_COLUMNS


def test_column_nullability_and_types(engine):
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("plans")}

    # 主键与必填字段（SQLite 反射的 primary_key 为 1，按真值断言）
    assert columns["id"]["primary_key"]
    assert columns["name"]["nullable"] is False
    assert columns["user_id"]["nullable"] is False
    assert columns["completed"]["nullable"] is False
    assert columns["total_budget"]["nullable"] is False
    assert columns["created_at"]["nullable"] is False
    assert columns["updated_at"]["nullable"] is False

    # 草稿关键字段可空（决策 8：Step1 仅命名即可持久化）
    for field in ("destination", "depart_date", "return_date", "people_count"):
        assert columns[field]["nullable"] is True, f"{field} 应允许 NULL"

    # 类型（决策 9：日期为无时区 date 字段）
    assert isinstance(columns["depart_date"]["type"], Date)
    assert isinstance(columns["return_date"]["type"], Date)
    assert isinstance(columns["completed"]["type"], Boolean)
    assert isinstance(columns["user_id"]["type"], Integer)
    assert isinstance(columns["people_count"]["type"], Integer)
    assert isinstance(columns["total_budget"]["type"], Integer)
    assert isinstance(columns["name"]["type"], String)
    assert isinstance(columns["created_at"]["type"], DateTime)
    assert isinstance(columns["updated_at"]["type"], DateTime)


def test_draft_plan_defaults(engine):
    """仅命名创建的草稿：全部默认值符合契约（决策 7/8）。"""
    with Session(engine) as session:
        plan = Plan(name="京都秋日漫游")
        session.add(plan)
        session.commit()
        session.refresh(plan)

        assert plan.id is not None
        assert plan.user_id == 1  # 决策 7：MVP 单用户默认 1
        assert plan.name == "京都秋日漫游"
        assert plan.destination is None
        assert plan.depart_date is None
        assert plan.return_date is None
        assert plan.people_count is None
        assert plan.completed is False  # 草稿
        assert plan.total_budget == 0
        assert plan.created_at is not None
        assert plan.updated_at is not None


def test_full_plan_fields_persist(engine):
    """完整计划字段往返持久化（对齐 spec.md 计划对象示例）。"""
    with Session(engine) as session:
        plan = Plan(
            user_id=1,
            name="京都秋日漫游",
            destination="日本 · 京都",
            depart_date=date(2026, 10, 2),
            return_date=date(2026, 10, 9),
            people_count=2,
            completed=True,
            total_budget=17400,
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)

        assert plan.destination == "日本 · 京都"
        assert plan.depart_date == date(2026, 10, 2)
        assert plan.return_date == date(2026, 10, 9)
        assert plan.people_count == 2
        assert plan.completed is True
        assert plan.total_budget == 17400


def test_updated_at_refreshes_on_update(engine):
    """更新行时 updated_at 自动刷新，created_at 保持不变。"""
    with Session(engine) as session:
        plan = Plan(name="旧名称")
        session.add(plan)
        session.commit()
        session.refresh(plan)
        original_created_at = plan.created_at
        original_updated_at = plan.updated_at

        time.sleep(0.02)  # 保证时间戳有可观测间隔
        plan.name = "新名称"
        session.commit()
        session.refresh(plan)

        assert plan.name == "新名称"
        assert plan.created_at == original_created_at
        assert plan.updated_at > original_updated_at
