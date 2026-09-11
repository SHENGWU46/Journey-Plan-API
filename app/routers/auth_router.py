"""认证接口路由（注册 / 登录）。

接口：
- POST /auth/register：注册账号，返回 201 与用户信息（不返回密码哈希）
- POST /auth/login：   登录，返回 200 与 access_token

业务规则：
- 账号唯一，重名返回 400；
- 登录失败（账号不存在 / 密码错误）统一返回 401 且文案相同
  （"账号或密码错误"），避免暴露账号是否注册（安全惯例）；
- 账号/密码格式非法由 Pydantic 返回 422；
- 密码经 bcrypt 哈希存储，永不返回明文或哈希（AC-NF-02）。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthHandler
from app.models import get_session
from app.repository.user_repo import UserRepository
from app.schemas import LoginIn, LoginOut, RefreshIn, RefreshOut, RegisterIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

auth_handler = AuthHandler()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn, session: AsyncSession = Depends(get_session)
) -> UserOut:
    """注册：账号唯一、两次密码一致（Pydantic 校验）；成功返回 201 与用户信息。"""
    repo = UserRepository(session)
    if await repo.username_exists(payload.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该账号已存在")

    user = await repo.create(username=payload.username, password=payload.password)
    return UserOut.model_validate(user)


@router.post("/login", response_model=LoginOut)
async def login(
    payload: LoginIn, session: AsyncSession = Depends(get_session)
) -> LoginOut:
    """登录：校验账号密码，成功签发 access_token（JWT，Bearer）。"""
    repo = UserRepository(session)
    user = await repo.get_by_username(payload.username)

    # 账号不存在与密码错误返回同一文案，避免账号枚举。
    if user is None or not user.check_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号或密码错误")

    tokens = auth_handler.encode_login_token(user.id)
    return LoginOut(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=RefreshOut)
async def refresh(payload: RefreshIn) -> RefreshOut:
    """用 refresh_token 换取新的 access_token（无感续期，避免 access 过期后被迫重新登录）。"""
    try:
        user_id = auth_handler.decode_refresh_token(payload.refresh_token)
    except HTTPException:
        # decode_refresh_token 对过期/无效统一抛 401，直接透传
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh Token不可用，请重新登录"
        )
    new_access = auth_handler.encode_update_token(user_id)
    return RefreshOut(access_token=new_access["access_token"])
