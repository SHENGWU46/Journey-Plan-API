"""每日计划相关模型（agent 接口契约 + 单日计划持久化）。

依据 docs/journey-plan-prototype.html 的 STEP4「单日详情」（FR-DY-02~06）与需求约定。

agent 接口（POST /plans/{plan_id}/days）契约：
  入参：
    1) 第一步填写的计划信息（目的地/往返时间/同行人数/总预算）——由服务端按 plan_id
       从计划本体读取后注入 agent，不在请求体中重复传递，避免客户端篡改计划级事实。
    2) 每日计划参数（请求体 DailyPlanGenReq）：
       - date        当日日期（必须）
       - tour_time   当日游玩时间段（可选）
       - daily_budget 当日预算（可选）
  返回（DailyPlanGenOut）：
    1) weather        当日天气
    2) attractions[]  景点列表，每项含：
       景点名称 name / 景点类型 type / 建议游玩时间 suggested_duration /
       人均预算 budget_per_person / 景点描述 description

字段口径与原型 RECOS_POOL 对齐：{name, tag→type, dur→suggested_duration(小时),
cost→budget_per_person(元), desc→description}。
"""

import datetime as dt
import json

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Attraction(BaseModel):
    """单个景点。

    suggested_duration 单位为小时（原型 dur，可为 1.5 这类小数）；
    budget_per_person 单位为元（原型 cost，免费景点为 0）。
    """

    name: str = Field(description="景点名称")
    type: str = Field(default="", description="景点类型，如 古刹 / 老街 / 博物馆 / 美食 / 自然")
    suggested_duration: float = Field(default=0, ge=0, description="建议游玩时间（小时）")
    budget_per_person: int = Field(default=0, ge=0, description="人均预算（元）")
    description: str = Field(default="", description="景点描述")


class DailyPlanGenReq(BaseModel):
    """生成某日计划的请求体（agent 入参中的「每日计划」部分）。"""

    date: dt.date = Field(description="当日日期，必填")
    tour_time: str | None = Field(default=None, description="当日游玩时间段，如 09:00-18:00")
    daily_budget: int | None = Field(default=None, ge=0, description="当日预算（元）")

    @field_validator("tour_time")
    @classmethod
    def _strip_blank_to_none(cls, value: str | None) -> str | None:
        """去首尾空格，空串归一为 None（前端可能传未填的空字符串）。"""
        if value is None:
            return None
        value = value.strip()
        return value or None


class DailyPlanGenOut(BaseModel):
    """agent 输出：当日天气 + 景点推荐列表。"""

    date: dt.date
    weather: str = Field(default="", description="当日天气，如 晴 26°C")
    attractions: list[Attraction] = Field(default_factory=list, description="景点推荐列表")


class DayPlanUpsertIn(BaseModel):
    """新增或更新某日计划（PUT /plans/{plan_id}/days/{day_index}）。

    date 必填（用于新建时落库与日期变更）；其余字段未提供（None）时保持原值；
    attractions 传空数组表示清空已选路线。
    """

    date: dt.date = Field(description="当日日期，必填")
    weather: str | None = None
    tour_time: str | None = None
    daily_budget: int | None = Field(default=None, ge=0)
    attractions: list[Attraction] | None = None


class DayPlanOut(BaseModel):
    """单日计划（持久化对象）。

    attractions 在库中以 JSON 文本存储，读取时反序列化为景点对象数组；
    解析失败降级为空数组，避免脏数据导致整个计划详情接口 500。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    day_index: int
    day_date: dt.date
    weather: str | None
    tour_time: str | None
    daily_budget: int | None
    attractions: list[Attraction]
    ai_generated: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    @field_validator("attractions", mode="before")
    @classmethod
    def _parse_attractions(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return []
        return value


class DayPlanListOut(BaseModel):
    """单计划下的每日计划列表响应。"""

    items: list[DayPlanOut]
    total: int
