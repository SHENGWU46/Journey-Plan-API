"""journey-plan-api 应用包。

分层（对齐 fastapi学习/AN-API）：
- app.settings   全局配置常量（DB_URI / JWT_*，均从环境变量解析）
- app.models     ORM 模型包，集中管理异步 engine / 会话工厂 / Base
- app.repository 数据访问层（Repository），封装表级查询与持久化
- app.routers    HTTP 路由层，负责参数校验、编排 repo、响应序列化
- app.core       与业务无关的可复用能力（JWT 鉴权、外部服务封装）
"""

__version__ = "0.1.0"
