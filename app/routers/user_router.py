"""用户中心接口（非 AI）。

端点（路由前缀 /user，全部需 Bearer 鉴权）：
- GET    /user/me          当前用户资料 + 统计（统计字段暂以默认值返回）
- PATCH  /user/profile     修改昵称（username）
- PATCH  /user/password    校验原密码并修改密码

统一响应风格与 auth/plans 一致：成功直接返回业务对象（UserOut），
错误由 HTTPException 抛出具名 detail，由全局/框架默认处理器转 422/400/401。
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthHandler
from app.models import get_session
from app.repository.user_repo import UserRepository

auth_handler = AuthHandler()
from app.schemas.user import UserOut, UserProfileUpdate, UserPasswordUpdate

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/me", response_model=UserOut)
async def get_me(
    user_id: int = Depends(auth_handler.auth_access_dependency),
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已失效")
    return UserOut.model_validate(user)


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    payload: UserProfileUpdate,
    user_id: int = Depends(auth_handler.auth_access_dependency),
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已失效")

    # 重名检查：昵称变化且与他人冲突则拒绝
    if payload.username != user.username:
        existing = await repo.get_by_username(payload.username)
        if existing is not None and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该昵称已被占用")

    user = await repo.update_profile(user, payload.username)
    return UserOut.model_validate(user)


@router.patch("/password")
async def change_password(
    payload: UserPasswordUpdate,
    user_id: int = Depends(auth_handler.auth_access_dependency),
    session: AsyncSession = Depends(get_session),
):
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已失效")

    if not user.check_password(payload.old_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")

    await repo.change_password(user, payload.new_password)
    return {"success": True}
