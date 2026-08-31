# Journey Plan API

Journey Plan 智能旅行计划 — 后端服务（FastAPI + MySQL）

## 技术栈

| 层 | 选型 |
| --- | --- |
| 框架 | FastAPI（Python 3.10+） |
| 数据库 | MySQL 8.x（开发期可 SQLite 过渡） |
| ORM | SQLAlchemy 2.x（规划） |
| 迁移 | Alembic（规划） |
| 鉴权 | JWT（规划） |
| 运行 | uvicorn |

## 目录结构（规划）

```
journey-plan-api/
├── main.py            应用入口（当前为最小 FastAPI 实例）
├── app/               规划：随功能拆分
│   ├── routers/       路由：auth / plans / days / assistant / user
│   ├── models/        SQLAlchemy 模型（User / Plan / DayPlan / Spot / ChatMessage）
│   ├── schemas/       Pydantic 模型
│   ├── services/      AI Agent、天气等外部服务封装
│   └── core/          配置、数据库连接、安全
└── requirements.txt   依赖清单（待补）
```

## 快速开始

```bash
python -m venv .venv
pip install fastapi uvicorn sqlalchemy pymysql
uvicorn main:app --reload --port 8000
```

- 交互式接口文档：<http://127.0.0.1:8000/docs>
- 数据库连接配置位于 `app/core/config.py`（规划中）

## 接口契约

以《Journey-Plan-需求分析文档.md》第 6 章接口需求为基准；前端调用见 `../journey-plan-app/api`。
