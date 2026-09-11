"""认证及用户中心相关 Pydantic 模型（注册 / 登录 / 资料 / 改密）。

校验规则（用户确认 2026-09-02「最简规则」）：
- username：去首尾空格后 2-20 字符；
- password：≥6 位，不强制字母+数字组合；
- 注册需二次确认密码（confirm_password 须与 password 一致）。

注：这里是「最简规则」，与 PRD 3.8 业务约束的「密码 ≥8 位含字母数字」不同，
已按用户本次决策放宽；后续如需收紧，只改本文件两处 Field 即可。
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UserOut(BaseModel):
    """对外返回的用户信息（不含密码哈希）。

    统计字段（plan_count / completed_count / travel_days）当前后端未落地，
    前端资料页需要展示，先以可选默认值 0 返回，后续接真实统计时改为聚合查询。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    plan_count: int = 0
    completed_count: int = 0
    travel_days: int = 0


class _Credentials(BaseModel):
    """登录与注册共用的账号密码校验。"""

    username: str
    password: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2 or len(value) > 20:
            raise ValueError("账号去除首尾空格后需为 2-20 个字符")
        return value

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        if len(value) < 6:
            raise ValueError("密码至少 6 位")
        return value


class LoginIn(_Credentials):
    """POST /auth/login 请求体。"""


class RegisterIn(_Credentials):
    """POST /auth/register 请求体：额外要求两次密码一致。"""

    confirm_password: str

    @model_validator(mode="after")
    def _passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("两次输入的密码不一致")
        return self


class LoginOut(BaseModel):
    """登录响应：access_token 供前端 Bearer 鉴权，refresh_token 供后续无感续期，user 供前端展示。"""

    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer")
    user: UserOut


class RefreshIn(BaseModel):
    """POST /auth/refresh 请求体：携带未过期的 refresh_token。"""

    refresh_token: str


class RefreshOut(BaseModel):
    """POST /auth/refresh 响应：返回新的 access_token（refresh_token 长期有效，无需回传）。"""

    access_token: str
    token_type: str = Field(default="bearer")


class UserProfileUpdate(BaseModel):
    """PATCH /user/profile 请求体：修改昵称（username）。

    约束与注册一致：去空格后 2-20 字符。其余资料字段（头像等）本期未实现。
    """

    username: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2 or len(value) > 20:
            raise ValueError("昵称去除首尾空格后需为 2-20 个字符")
        return value


class UserPasswordUpdate(BaseModel):
    """PATCH /user/password 请求体：校验原密码并设新密码。

    约束：旧密码必填；新密码 ≥6 位；新旧密码可相同（允许重设）。
    原密码错误由路由层经 user_repo.verify_password 校验后返回 400。
    """

    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)
