from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth_router, plans, user_router
from app.routers.assistant import router as assistant_router

app = FastAPI()

# 设计决策 11：开发期 CORS 放行本地来源（http://localhost:*、http://127.0.0.1:*），
# 供 uni-app dev:h5 直连联调；生产再收紧为明确域名。
# 注：Starlette 的 allow_origins 为精确字符串匹配，不支持 `:*` 端口通配，
# 故用 allow_origin_regex 实现「本地任意端口」语义（决策 11 意图）。
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(plans.router)
app.include_router(user_router.router)
app.include_router(assistant_router)

# 数据库建表由 Alembic 迁移管理（alembic/versions/），不在应用启动时 create_all。
# 首次运行：pip install alembic && alembic upgrade head
