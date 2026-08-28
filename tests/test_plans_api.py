"""计划接口 API 测试（任务 1.2 列表 / 任务 1.3 草稿创建、改名、删除）。

运行方式：cd journey-plan-api && python -m pytest tests/test_plans_api.py
契约依据：changes/my-plans-page/specs/plan-api/spec.md「计划列表接口（GET /plans）」
「草稿创建接口（POST /plans）」「计划改名接口（PATCH /plans/{id}）」
「计划删除接口（DELETE /plans/{id}）」、design.md 决策 2（仅 completed 区分
草稿/非草稿）、决策 3（keyword 服务端 LIKE 过滤）、决策 9（total_days 按
「返回−出发+1」日历日派生）、决策 11（开发期 CORS 放行本地来源）、
决策 12（generated_days 恒 0）。

测试通过 TestClient 走真实 HTTP 路由（依赖覆盖为每个测试独立的内存 SQLite）。
"""

import re
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_session
from app.models import Plan
from main import app

# 计划对象 JSON 字段（spec.md 计划对象示例，snake_case，无 status）
EXPECTED_PLAN_FIELDS = {
    "id",
    "user_id",
    "name",
    "destination",
    "depart_date",
    "return_date",
    "people_count",
    "completed",
    "total_budget",
    "total_days",
    "generated_days",
    "created_at",
    "updated_at",
}

ISO_Z_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


@pytest.fixture()
def engine():
    """每个测试独立的内存 SQLite 引擎，避免测试间数据串扰。

    TestClient 在独立线程中处理请求，故用 StaticPool 固定单连接并允许跨线程
    （内存库默认每连接独立且禁跨线程，会抛 ProgrammingError）。
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(engine):
    """TestClient：覆盖 get_session 依赖指向测试引擎，走真实 HTTP 路由。"""

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _add_plan(session, name, *, updated_at=None, **kwargs):
    """插入计划；updated_at 可显式指定以便断言排序，默认按插入先后递增。"""
    plan = Plan(name=name, **kwargs)
    if updated_at is not None:
        plan.updated_at = updated_at
    session.add(plan)
    return plan


def test_list_empty_returns_empty_items_and_total_zero(client):
    resp = client.get("/plans")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_list_orders_by_updated_at_desc(engine, client):
    """默认排序：updated_at 倒序（spec「默认排序」场景）。"""
    with Session(engine) as session:
        _add_plan(session, "最早", completed=True, updated_at=datetime(2026, 8, 1, 9, 0, 0))
        _add_plan(session, "居中", completed=True, updated_at=datetime(2026, 8, 2, 9, 0, 0))
        _add_plan(session, "最新", completed=True, updated_at=datetime(2026, 8, 3, 9, 0, 0))
        session.commit()

    names = [p["name"] for p in client.get("/plans").json()["items"]]
    assert names == ["最新", "居中", "最早"]


def test_list_keyword_case_insensitive_and_chinese_substring(engine, client):
    """keyword 忽略大小写（SQLite/MySQL LIKE）与中文子串模糊匹配。"""
    with Session(engine) as session:
        _add_plan(session, "Kyoto 秋日漫游", completed=True)
        _add_plan(session, "京都冬雪之旅", completed=True)
        _add_plan(session, "大理环海慢游", completed=True)
        session.commit()

    # 英文大小写不敏感：KYOTO 命中 Kyoto…
    items = client.get("/plans", params={"keyword": "KYOTO"}).json()["items"]
    assert [p["name"] for p in items] == ["Kyoto 秋日漫游"]

    # 中文子串：京都 命中「京都冬雪之旅」
    items = client.get("/plans", params={"keyword": "京都"}).json()["items"]
    assert [p["name"] for p in items] == ["京都冬雪之旅"]

    # 无匹配：keyword 不命中任何计划时 total=0
    body = client.get("/plans", params={"keyword": "不存在的名称"}).json()
    assert body["items"] == [] and body["total"] == 0


def test_list_pagination_total_and_pages(engine, client):
    """分页：total 正确，page/page_size 生效，翻页与空页行为符合契约。"""
    with Session(engine) as session:
        for i in range(5):
            _add_plan(
                session,
                f"计划 {i}",
                completed=True,
                updated_at=datetime(2026, 8, 1, 0, i, 0),
            )
        session.commit()

    page1 = client.get("/plans", params={"page": 1, "page_size": 2}).json()
    assert page1["total"] == 5
    assert page1["page"] == 1
    assert page1["page_size"] == 2
    assert len(page1["items"]) == 2
    assert [p["name"] for p in page1["items"]] == ["计划 4", "计划 3"]  # 倒序第一页

    page3 = client.get("/plans", params={"page": 3, "page_size": 2}).json()
    assert len(page3["items"]) == 1  # 5 条恰好 3 页，末页 1 条
    assert [p["name"] for p in page3["items"]] == ["计划 0"]

    page4 = client.get("/plans", params={"page": 4, "page_size": 2}).json()
    assert page4["items"] == []  # 超出范围的空页
    assert page4["total"] == 5  # total 不受页偏移影响

    # 关键字与分页可组合
    filtered = client.get(
        "/plans", params={"keyword": "计划", "page": 2, "page_size": 2}
    ).json()
    assert filtered["total"] == 5 and len(filtered["items"]) == 2


def test_list_invalid_pagination_params_rejected(client):
    """page>=1、1<=page_size<=100；越界返回 422。"""
    assert client.get("/plans", params={"page": 0}).status_code == 422
    assert client.get("/plans", params={"page_size": 0}).status_code == 422
    assert client.get("/plans", params={"page_size": 101}).status_code == 422


def test_list_draft_plan_serialization(engine, client):
    """草稿语义（决策 2/8）：仅名称创建 → completed=false，其余关键字段 null，total_budget 0，
    total_days null（日期缺失，决策 9）、generated_days 0（决策 12）；响应无 status 字段。"""
    with Session(engine) as session:
        _add_plan(session, "成都美食探访")  # 仅名称：草稿
        session.commit()

    body = client.get("/plans").json()
    assert body["total"] == 1
    plan = body["items"][0]

    # 字段集合精确匹配 spec 计划对象，且无四态派生 status
    assert set(plan) == EXPECTED_PLAN_FIELDS
    assert "status" not in plan

    assert plan["id"] == 1
    assert plan["user_id"] == 1
    assert plan["name"] == "成都美食探访"
    assert plan["completed"] is False  # 草稿
    assert plan["destination"] is None
    assert plan["depart_date"] is None
    assert plan["return_date"] is None
    assert plan["people_count"] is None
    assert plan["total_budget"] == 0
    assert plan["total_days"] is None
    assert plan["generated_days"] == 0

    # 时间字段序列化为 UTC ISO8601（spec 示例 ...T12:00:00Z）
    assert ISO_Z_RE.fullmatch(plan["created_at"])
    assert ISO_Z_RE.fullmatch(plan["updated_at"])


def test_list_completed_plan_fields_and_total_days(engine, client):
    """非草稿（completed=true）：完整字段序列化 + total_days 含首尾日历日（10-02~10-09 → 8）。"""
    with Session(engine) as session:
        _add_plan(
            session,
            "京都秋日漫游",
            completed=True,
            destination="日本 · 京都",
            depart_date=date(2026, 10, 2),
            return_date=date(2026, 10, 9),
            people_count=2,
            total_budget=17400,
        )
        session.commit()

    plan = client.get("/plans").json()["items"][0]
    assert plan["completed"] is True
    assert plan["destination"] == "日本 · 京都"
    assert plan["depart_date"] == "2026-10-02"
    assert plan["return_date"] == "2026-10-09"
    assert plan["people_count"] == 2
    assert plan["total_budget"] == 17400
    assert plan["total_days"] == 8  # 返回-出发+1，含首尾
    assert plan["generated_days"] == 0  # 决策 12：恒 0


def test_list_total_days_same_day_return_is_one(engine, client):
    """total_days 边界：同日往返 = 1 天（执行契约「必需的边界情况」）。"""
    with Session(engine) as session:
        _add_plan(
            session,
            "厦门文艺周末",
            completed=True,
            destination="福建 · 厦门",
            depart_date=date(2026, 5, 10),
            return_date=date(2026, 5, 10),
            people_count=2,
            total_budget=6800,
        )
        session.commit()

    plan = client.get("/plans").json()["items"][0]
    assert plan["total_days"] == 1


def test_list_total_days_null_when_dates_missing(engine, client):
    """total_days 边界：仅缺一个日期同样为 null（决策 9「日期缺失（草稿）时 total_days 为空」）。"""
    with Session(engine) as session:
        _add_plan(
            session,
            "日期不全的计划",
            completed=True,
            destination="某地",
            depart_date=date(2026, 10, 2),  # 缺 return_date
            people_count=2,
            total_budget=3000,
        )
        session.commit()

    plan = client.get("/plans").json()["items"][0]
    assert plan["depart_date"] == "2026-10-02"
    assert plan["return_date"] is None
    assert plan["total_days"] is None


def test_list_generated_days_always_zero(engine, client):
    """决策 12：generated_days 恒 0，无论草稿/非草稿。"""
    with Session(engine) as session:
        _add_plan(session, "草稿 A", completed=False)
        _add_plan(
            session,
            "非草稿 B",
            completed=True,
            destination="日本 · 京都",
            depart_date=date(2026, 10, 2),
            return_date=date(2026, 10, 9),
            people_count=2,
            total_budget=17400,
        )
        session.commit()

    items = client.get("/plans").json()["items"]
    assert all(p["generated_days"] == 0 for p in items)


# ---------------------------------------------------------------- 任务 1.3：草稿创建


def test_post_creates_draft_plan(client):
    """POST /plans 合法创建（spec「合法创建」）：201 + 完整计划对象；
    名称已去首尾空格，completed=false 草稿，关键字段 null、total_budget 0、
    total_days null、generated_days 0，且列表立即可见。"""
    resp = client.post("/plans", json={"name": "  成都美食探访  "})
    assert resp.status_code == 201
    plan = resp.json()

    assert set(plan) == EXPECTED_PLAN_FIELDS
    assert plan["name"] == "成都美食探访"  # 首尾空格已去除
    assert plan["completed"] is False  # 草稿
    assert plan["destination"] is None
    assert plan["depart_date"] is None
    assert plan["return_date"] is None
    assert plan["people_count"] is None
    assert plan["total_budget"] == 0
    assert plan["total_days"] is None
    assert plan["generated_days"] == 0
    assert plan["user_id"] == 1
    assert ISO_Z_RE.fullmatch(plan["created_at"])
    assert ISO_Z_RE.fullmatch(plan["updated_at"])

    # 列表立即可见（GET /plans 与创建结果同源）
    items = client.get("/plans").json()["items"]
    assert len(items) == 1 and items[0]["id"] == plan["id"]


@pytest.mark.parametrize(
    "bad_name",
    [
        "",  # 空名称
        "   ",  # 仅空格
        "甲",  # 去空格后 1 字符
        "a" * 21,  # 去空格后 21 字符
        "  " + "a" * 21 + " ",  # 首尾空格不影响长度判定（去除后仍 21）
    ],
)
def test_post_rejects_invalid_names_and_creates_nothing(client, bad_name):
    """POST /plans 非法名称（spec「非法名称拒绝」）：422 且不创建任何数据。"""
    resp = client.post("/plans", json={"name": bad_name})
    assert resp.status_code == 422
    assert client.get("/plans").json()["total"] == 0


def test_post_accepts_name_length_boundaries(client):
    """名称校验边界：去空格后恰好 2 字符与 20 字符均为合法（含首尾空格）。"""
    resp2 = client.post("/plans", json={"name": "旅游"})
    resp20 = client.post("/plans", json={"name": "  " + "a" * 20 + "  "})
    assert resp2.status_code == 201
    assert resp20.status_code == 201
    assert resp2.json()["name"] == "旅游"
    assert resp20.json()["name"] == "a" * 20


# ---------------------------------------------------------------- 任务 1.3：改名


def test_patch_renames_plan_and_bumps_updated_at(engine, client):
    """PATCH /plans/{id} 合法改名（spec「合法改名」）：200、新名称生效、
    updated_at 随之更新，列表查询立即可见新名称。"""
    with Session(engine) as session:
        plan = _add_plan(session, "旧名称", updated_at=datetime(2026, 8, 1, 9, 0, 0))
        session.commit()
        plan_id = plan.id

    resp = client.patch(f"/plans/{plan_id}", json={"name": "新名称"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == plan_id
    assert body["name"] == "新名称"
    assert body["updated_at"] != "2026-08-01T09:00:00Z"  # updated_at 应随之变化
    assert body["completed"] is False  # 其余字段不受改名影响

    names = [p["name"] for p in client.get("/plans").json()["items"]]
    assert names == ["新名称"]


@pytest.mark.parametrize("bad_name", ["", "   ", "甲", "a" * 21])
def test_patch_rejects_invalid_name_and_keeps_original(engine, client, bad_name):
    """PATCH 非法名称（spec「非法名称拒绝」）：422 且原名称不变。"""
    with Session(engine) as session:
        _add_plan(session, "原名")
        session.commit()

    resp = client.patch("/plans/1", json={"name": bad_name})
    assert resp.status_code == 422

    items = client.get("/plans").json()["items"]
    assert len(items) == 1 and items[0]["name"] == "原名"


def test_patch_not_found_returns_404(client):
    """PATCH 不存在的计划（spec「计划不存在」）：404。"""
    resp = client.patch("/plans/999", json={"name": "新名称"})
    assert resp.status_code == 404


# ---------------------------------------------------------------- 任务 1.3：删除


def test_delete_removes_plan_physically(engine, client):
    """DELETE /plans/{id} 删除成功（spec「删除成功」）：204，物理删除，
    随后 GET /plans 不再返回该计划且数据库中行已不存在。"""
    with Session(engine) as session:
        _add_plan(session, "待删除")
        session.commit()

    resp = client.delete("/plans/1")
    assert resp.status_code == 204

    body = client.get("/plans").json()
    assert body["items"] == [] and body["total"] == 0

    with Session(engine) as session:
        assert session.get(Plan, 1) is None  # 物理删除（MVP 无回收站）


def test_delete_not_found_returns_404(client):
    """DELETE 不存在的计划（spec「计划不存在」）：404。"""
    resp = client.delete("/plans/999")
    assert resp.status_code == 404


# ---------------------------------------------------------------- 任务 1.3：开发 CORS（决策 11）


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:8080"])
def test_cors_preflight_allows_local_dev_origins(client, origin):
    """设计决策 11：开发期 CORS 放行 http://localhost:* 与 http://127.0.0.1:* 预检。"""
    resp = client.options(
        "/plans",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


def test_cors_simple_request_carries_allow_origin(client):
    """非预检请求（带 Origin）同样返回 Access-Control-Allow-Origin。"""
    resp = client.get("/plans", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_non_local_origin(client):
    """非本地来源不放行：预检响应不带 Access-Control-Allow-Origin。"""
    resp = client.options(
        "/plans",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers.get("access-control-allow-origin") is None
