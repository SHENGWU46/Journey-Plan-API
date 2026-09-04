"""用户数据访问层（UserRepository，对齐 app/repository/plan_repo.py 的写法）。

同 plan_repo：读方法只查询，写方法内部完成 add/commit/refresh；
不抛 HTTPException，由路由层（routers/auth_router.py）决定 400/401。
"""

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    """users 表的数据访问对象，持有调用方注入的会话。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_username(self, username: str) -> User | None:
        """按账号取用户（登录与重名检查共用），不存在返回 None。"""
        return await self.session.scalar(
            select(User).where(User.username == username)
        )

    async def username_exists(self, username: str) -> bool:
        """账号是否已存在（注册重名检查）。"""
        return bool(
            await self.session.scalar(
                select(exists().where(User.username == username))
            )
        )

    async def create(self, username: str, password: str) -> User:
        """创建用户：明文密码在模型内转为 bcrypt 哈希后落库。"""
        user = User(username=username)
        user.set_password(password)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        """按主键取用户，不存在返回 None。"""
        return await self.session.get(User, user_id)

    async def update_profile(self, user: User, username: str) -> User:
        """修改昵称（username）；密码变更走专用方法。"""
        user.username = username
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def change_password(self, user: User, new_password: str) -> User:
        """重设密码：明文在模型内转 bcrypt 哈希后落库。"""
        user.set_password(new_password)
        await self.session.commit()
        await self.session.refresh(user)
        return user
