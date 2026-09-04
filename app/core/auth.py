"""JWT 鉴权（对齐 fastapi学习/AN-API/core/auth.py）。

- AuthHandler 为线程安全单例（SingletonMeta），全局复用同一份密钥与 HTTPBearer。
- auth_access_dependency / auth_refresh_dependency 可直接用于 FastAPI 的 Depends，
  返回当前登录用户的 user_id（即 payload 的 iss 字段）。
- Token 用 sub 字段区分类型：1=access、2=refresh，防止互换使用。

与 AN-API 的差异：密钥来自 app.settings（环境变量注入），不硬编码在源码中
（遵循 AGENTS.md「禁止硬编码密钥」）。

用法示例（后续 user / plan 接口接入鉴权时）：
    auth_handler = AuthHandler()

    @router.get("/me")
    async def me(user_id: int = Depends(auth_handler.auth_access_dependency)):
        ...
"""

from datetime import datetime
from enum import Enum
from threading import Lock

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from app import settings

# PyJWT：pip install pyjwt


class SingletonMeta(type):
    """线程安全单例元类（与 AN-API 同款实现）。"""

    _instances = {}
    _lock: Lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class TokenTypeEnum(Enum):
    ACCESS_TOKEN = 1
    REFRESH_TOKEN = 2


class AuthHandler(metaclass=SingletonMeta):
    security = HTTPBearer()  # Authorization: Bearer {token}

    # 模块导入时求值一次（与 AN-API 一致）；密钥由 settings 从环境变量解析。
    secret = settings.JWT_SECRET_KEY

    def _encode_token(self, user_id: int, type: TokenTypeEnum):
        # PyJWT >= 2.10 要求 iss 为字符串（AN-API 原写法 iss=user_id 会抛
        # "Issuer (iss) must be a string."），故存字符串、解析时再转回 int。
        payload = dict(iss=str(user_id), sub=str(type.value))
        to_encode = payload.copy()
        if type == TokenTypeEnum.ACCESS_TOKEN:
            exp = datetime.now() + settings.JWT_ACCESS_TOKEN_EXPIRES
        else:
            exp = datetime.now() + settings.JWT_REFRESH_TOKEN_EXPIRES
        to_encode.update({"exp": int(exp.timestamp())})
        return jwt.encode(to_encode, self.secret, algorithm=settings.JWT_ALGORITHM)

    def encode_login_token(self, user_id: int):
        """登录成功：同时签发 access 与 refresh token。"""
        access_token = self._encode_token(user_id, TokenTypeEnum.ACCESS_TOKEN)
        refresh_token = self._encode_token(user_id, TokenTypeEnum.REFRESH_TOKEN)
        return dict(access_token=f"{access_token}", refresh_token=f"{refresh_token}")

    def encode_update_token(self, user_id: int):
        """刷新/更新资料：只签发新的 access token。"""
        access_token = self._encode_token(user_id, TokenTypeEnum.ACCESS_TOKEN)
        return dict(access_token=f"{access_token}")

    def decode_access_token(self, token):
        """access token 不可用（过期/类型错/无效）统一返回 403。"""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[settings.JWT_ALGORITHM])
            if payload["sub"] != str(TokenTypeEnum.ACCESS_TOKEN.value):
                raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Token类型错误！")
            return int(payload["iss"])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Access Token已过期！")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Access Token不可用！")

    def decode_refresh_token(self, token):
        """refresh token 不可用统一返回 401（客户端应重新登录）。"""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[settings.JWT_ALGORITHM])
            if payload["sub"] != str(TokenTypeEnum.REFRESH_TOKEN.value):
                raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Token类型错误！")
            return int(payload["iss"])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Refresh Token已过期！")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Refresh Token不可用！")

    def auth_access_dependency(self, auth: HTTPAuthorizationCredentials = Security(security)):
        return self.decode_access_token(auth.credentials)

    def auth_refresh_dependency(self, auth: HTTPAuthorizationCredentials = Security(security)):
        return self.decode_refresh_token(auth.credentials)
