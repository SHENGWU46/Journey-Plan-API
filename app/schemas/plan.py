"""计划接口的 Pydantic v2 序列化模型（任务 1.2）。

契约依据：changes/my-plans-page/specs/plan-api/spec.md 计划对象示例（snake_case，
无 status 字段）、design.md 决策 9/12（total_days 按日历日派生含首尾，日期缺失为 null；
generated_days 恒 0）。
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer, field_validator


class PlanOut(BaseModel):
    """计划对象（列表项与后续单对象响应共用，任务 1.3 复用）。

    派生字段（决策 9/12）不在 DB 存储，由响应层计算：
    - total_days：返回 − 出发 + 1（含首尾，决策 9；同日往返 = 1）；
      任一日缺失为 null（草稿）。具体口径见属性注释。
    - generated_days：本次恒 0（DayPlan 数据在后续 FR-DY 变更才引入）。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    destination: str | None
    depart_date: date | None
    return_date: date | None
    people_count: int | None
    completed: bool
    total_budget: int
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_days(self) -> int | None:
        if self.depart_date is None or self.return_date is None:
            return None
        # 口径：design.md 决策 9「返回−出发+1」含首尾日历日（spec.md 示例
        # 京都 2026-10-02~10-09 → 8）；同日往返 0+1=1；任一日缺失为 null。
        return (self.return_date - self.depart_date).days + 1

    @computed_field  # type: ignore[prop-decorator]
    @property
    def generated_days(self) -> int:
        return 0

    @field_serializer("created_at", "updated_at")
    def _serialize_datetime_utc(self, value: datetime) -> str:
        """无时区 UTC → 带 Z 后缀的 ISO8601，与 spec 示例 ...T12:00:00Z 一致。"""
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class PlanListOut(BaseModel):
    """GET /plans 列表响应：{"items": [...], "total": N, "page": P, "page_size": S}。"""

    items: list[PlanOut]
    total: int
    page: int
    page_size: int


class _PlanNameValidated(BaseModel):
    """POST /plans 与 PATCH /plans/{id} 共用的名称请求体与校验（任务 1.3）。

    契约（spec「草稿创建接口」/「计划改名接口」）：去除首尾空格后 2-20 字符；
    非法名称由 Pydantic 在请求层拒绝（FastAPI 422），且校验通过后存储的是
    已去空格名称（「名称已去空格」）。
    """

    name: str

    @field_validator("name")
    @classmethod
    def _strip_and_validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2 or len(value) > 20:
            raise ValueError("计划名称去除首尾空格后需为 2-20 个字符")
        return value


class PlanIn(_PlanNameValidated):
    """POST /plans 请求体：仅计划名称。"""


class PlanPatch(BaseModel):
    """PATCH /plans/{id} 请求体：支持多字段部分更新。

    仅下列字段可改（其余字段由服务器派生或本期未开放）：name、destination、
    depart_date、return_date、people_count、completed、total_budget。
    未提供的字段保持原值；name 若提供需满足 2-20 字符校验。
    """

    name: str | None = None
    destination: str | None = None
    depart_date: date | None = None
    return_date: date | None = None
    people_count: int | None = Field(default=None, ge=1, le=99)
    completed: bool | None = None
    total_budget: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def _strip_and_validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2 or len(value) > 20:
            raise ValueError("计划名称去除首尾空格后需为 2-20 个字符")
        return value
