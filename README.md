# Journey Plan API

Journey Plan 智能旅行计划 — 后端服务（FastAPI + MySQL）

## 技术栈

| 层 | 选型 |
| --- | --- |
| 框架 | FastAPI（Python 3.10+） |
| 数据库 | MySQL 8.x（开发期可 SQLite 过渡） |
| ORM | SQLAlchemy 2.x |
| 迁移 | Alembic |
| 鉴权 | JWT（Bearer） |
| 运行 | uvicorn |

## 目录结构（规划）

```
journey-plan-api/
├── main.py            应用入口（当前为最小 FastAPI 实例）
├── app/               规划：随功能拆分
│   ├── routers/       路由：auth / plans / user / assistant
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
FastAPI 同时自动生成交互式文档：`/docs`（Swagger UI）与 `/redoc`，可直接在线调试。

### 通用约定

- **Base URL**：`http://<host>:<port>`（本地默认 `http://127.0.0.1:8000`）。
- **鉴权**：除 `/auth/*` 外所有接口需在请求头带 `Authorization: Bearer <access_token>`；缺失/无效返回 401。
- **数据隔离**：业务接口仅返回当前登录用户自己的数据；访问他人资源表现为 404（不暴露资源是否存在）。
- **错误格式**：业务错误以 `HTTPException` 抛出，响应体为 `{ "detail": "..." }`；字段校验失败返回 422。
- **CORS**：开发期放行 `http://localhost:*` 与 `http://127.0.0.1:*`，供 uni-app H5 直连联调。

### 认证 `/auth`（无需鉴权）

| 方法 | 路径 | 说明 | 请求体 | 响应 |
| --- | --- | --- | --- | --- |
| POST | `/auth/register` | 注册账号（201） | `RegisterIn` | `UserOut` |
| POST | `/auth/login` | 登录并签发 token | `LoginIn` | `LoginOut` |

- **RegisterIn**：`username`(2-20 字符，去空格)、`password`(≥6 位)、`confirm_password`（须与 password 一致）。
- **LoginIn**：`username`、`password`。
- **LoginOut**：`access_token`、`token_type`(="bearer")、`user`(UserOut)。
- **UserOut**：`id`、`username`、`plan_count`(默认 0)、`completed_count`(默认 0)、`travel_days`(默认 0)。
- 错误：注册重名 → 400；账号/密码非法 → 422；登录失败（账号不存在或密码错）统一 → 401「账号或密码错误」。

### 计划 `/plans`（Bearer 鉴权）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| GET | `/plans` | 计划列表（关键字+分页，updated_at 倒序） | Query: `keyword?` `page?`(默认1) `page_size?`(默认20, 1-100) | `PlanListOut` |
| POST | `/plans` | 新建草稿计划（201） | `PlanIn{name}` | `PlanOut` |
| GET | `/plans/{plan_id}` | 计划详情 | — | `PlanOut` |
| PATCH | `/plans/{plan_id}` | 部分更新（名称/目的地/日期/人数/预算/完成态） | `PlanPatch` | `PlanOut` |
| DELETE | `/plans/{plan_id}` | 物理删除（级联清 day_plans，204） | — | 204 |
| POST | `/plans/{plan_id}/days` | 🤖 **Agent 生成某日计划**（只生成不落库） | `DailyPlanGenReq` | `DailyPlanGenOut` |
| GET | `/plans/{plan_id}/days` | 已保存每日计划列表 | — | `DayPlanListOut` |
| PUT | `/plans/{plan_id}/days/{day_index}` | 幂等新增/更新某天计划 | `DayPlanUpsertIn` | `DayPlanOut` |

- **PlanOut 字段**
  - 存储字段：`id` `user_id` `name` `destination?` `depart_date?` `return_date?` `people_count?` `completed`(bool) `total_budget`(int) `created_at` `updated_at`（日期/时间为 ISO8601 字符串）。
  - **派生字段**（DB 不存储）：
    - `total_days`：行程天数 = 返回日 − 出发日 + 1（含首尾，同日往返=1）；任一日缺失为 `null`（草稿）。
    - `generated_days`：该计划下**已保存的每日计划数**（来自 `day_plans` 表计数，驱动卡片「已生成 X/N」）；默认 0（如新建草稿）。
- **PlanIn**：`name`（去空格后 1-20 字符）。
- **PlanPatch**：`name?` `destination?` `depart_date?` `return_date?` `people_count?`(1-99) `completed?` `total_budget?`(≥0)；未提供字段保持原值。
- **PlanListOut**：`items[PlanOut]` `total` `page` `page_size`。
- **DailyPlanGenReq**：`date`(必填) `tour_time?` `daily_budget?`。计划级事实（目的地/往返/人数/总预算）由服务端按 `plan_id` 读取后注入 Agent，不取自请求体。
- **DailyPlanGenOut**：`date` `weather` `attractions[Attraction]`。**不落库**，需经下面的 `PUT` 接口保存。
  - **Attraction**：`name` `type` `suggested_duration`(小时) `budget_per_person`(元) `description`。
- **DayPlanUpsertIn**：`date`(必填) `weather?` `tour_time?` `daily_budget?` `attractions?`(Attraction 数组，传空数组=清空路线）。
- **DayPlanOut**：`id` `plan_id` `day_index` `day_date` `weather?` `tour_time?` `daily_budget?` `attractions[Attraction]` `ai_generated`(bool) `created_at` `updated_at`。
- **DayPlanListOut**：`items[DayPlanOut]` `total`。
- 错误：`{plan_id}` 不存在/越权 → 404；`POST .../days` 日期超出行程范围 → 422。

### 用户中心 `/user`（Bearer 鉴权）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| GET | `/user/me` | 当前用户资料 | — | `UserOut` |
| PATCH | `/user/profile` | 修改昵称 | `UserProfileUpdate{username}` | `UserOut` |
| PATCH | `/user/password` | 校验原密码并改密 | `UserPasswordUpdate` | `{success:true}` |

- **UserProfileUpdate**：`username`（2-20 字符，去空格）；与他人重名 → 400。
- **UserPasswordUpdate**：`old_password`(必填) `new_password`(≥6 位)；原密码错误 → 400。
- `GET /user/me` 中统计字段（`plan_count` 等）当前固定为 0，后续接真实聚合查询。

### 旅行助手 `/assistant`（Bearer 鉴权，🤖 Agent）

| 方法 | 路径 | 说明 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| POST | `/assistant/ask` | AI 问答 | `AssistantAskReq` | `{reply: string}` |

- **AssistantAskReq**：`message`(1-2000 字符，本轮提问) `history[ChatMessage]`（不含本轮的上下文，`role` ∈ user/ai/system/assistant，`text` 非空）。
- 响应：`{ "reply": "..." }`。
- 错误：AI 服务不可用/无有效返回 → **502**，前端据此回退本地 mock。

---

> **Agent（AI）相关接口共 2 个**：`POST /plans/{plan_id}/days`（生成单日计划）与 `POST /assistant/ask`（旅行助手问答）。
> 两者均由后端 `app/services/` 调用外部 Agent 服务；`generated_days` 等"已生成几分之几"类派生数据来自已落库的 `day_plans` 行，而非 Agent 生成动作本身。
