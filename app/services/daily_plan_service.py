"""每日计划 agent 服务的接入层（预留接口，具体 agent 实现由业务方填充）。

=========================== 如何接入你自己的 agent ===========================
只需实现本文件底部的 `_call_agent(ctx, req)`，其余（规整、校验、降级、路由）均已就绪：

    async def _call_agent(ctx, req):
        result = await your_agent.plan(
            destination=ctx["destination"],
            date=req.date,
            ...
        )
        return result          # dict / str / None

入参：
  ctx  第一步填写的计划信息（服务端按 plan_id 从计划本体读出后注入，不信任客户端）：
       destination / depart_date / return_date / people_count / total_budget / day_index
  req  DailyPlanGenReq，当日参数：
       date 必填 / tour_time 可选 / daily_budget 可选

返回（三选一）：
  dict  形如 {"weather": "晴 26°C", "attractions": [{...}]}
  str   原始文本（通常是大模型输出），本层会尝试从中解析出 JSON 对象
  None  表示本次没拿到结果 → 返回空结果（attractions=[]，weather=""）

attractions 每项字段：
  name 景点名称 / type 景点类型 / suggested_duration 建议游玩小时数(可小数) /
  budget_per_person 人均预算(整数元) / description 景点描述

_sync/async 均可：若你的 agent 是同步阻塞的，参考 assistant_service 用
`asyncio.get_event_loop().run_in_executor(None, ...)` 包一层，避免阻塞事件循环。
=============================================================================

无兜底：_call_agent 默认返回 None；拿不到结果或调用异常时，接口返回空结构
{date, weather: "", attractions: []}，不产出样例数据，由前端展示空态。
"""

import asyncio
import json
import logging
import re
import threading

from app.schemas.daily_plan import DailyPlanGenReq

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict | None:
    """从文本中截取第一个完整 JSON 对象（容忍前后说明文字与 ```json 围栏）。"""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start = cleaned.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : i + 1])
                except ValueError:
                    return None
    return None


def _to_float(value, default: float = 0.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return default


def _to_int(value, default: int = 0) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return default


def _normalize(raw: dict, day) -> dict:
    """把 agent 原始输出规整为契约结构，并收敛类型与长度（防止脏数据打爆字段）。"""
    attractions = []
    for item in (raw.get("attractions") or [])[:8]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        attractions.append(
            {
                "name": name[:50],
                "type": str(item.get("type") or "").strip()[:20],
                "suggested_duration": _to_float(item.get("suggested_duration")),
                "budget_per_person": _to_int(item.get("budget_per_person")),
                "description": str(item.get("description") or "").strip()[:200],
            }
        )
    return {
        "date": day,
        "weather": str(raw.get("weather") or "").strip()[:50],
        "attractions": attractions,
    }


_agent_instance = None
_agent_lock = threading.Lock()  # 保护单例创建
_run_lock = threading.Lock()  # 串行化 agent 执行，避免共享实例并发串扰


def _build_messages(ctx: dict, req: DailyPlanGenReq) -> list[dict]:
    """把注入的计划上下文与当日参数拼成一条 user 消息，交给 RecommendAgent。"""
    destination = ctx.get("destination") or "未知"
    depart = ctx.get("depart_date") or "未知"
    ret = ctx.get("return_date") or "未知"
    people = ctx.get("people_count") or 1
    total = ctx.get("total_budget") or 0
    day_index = ctx.get("day_index") or 1

    tour_time = req.tour_time or "不限"
    daily_budget = f"{req.daily_budget} 元" if req.daily_budget is not None else "不限"

    user_content = (
        "请基于以下行程参数，生成单日景点推荐计划：\n\n"
        f"【计划信息】\n"
        f"- 目的地：{destination}\n"
        f"- 出发日期：{depart}\n"
        f"- 返回日期：{ret}\n"
        f"- 同行人数：{people}\n"
        f"- 全程总预算：{total} 元\n"
        f"- 当前为第 {day_index} 天\n\n"
        f"【当日参数】\n"
        f"- 日期：{req.date}\n"
        f"- 游玩时间段：{tour_time}\n"
        f"- 当日预算：{daily_budget}\n\n"
        "请严格按系统提示词要求的 JSON 结构返回当日计划。"
    )
    return [{"role": "user", "content": user_content}]


def _get_agent():
    """懒加载 RecommendAgent 单例（__init__ 会加载知识库，较重，仅首次构建）。"""
    global _agent_instance
    if _agent_instance is None:
        with _agent_lock:
            if _agent_instance is None:
                from agents.agent.RecommendAgent import RecommendAgent
                _agent_instance = RecommendAgent()
    return _agent_instance


def _run_agent(agent, messages: list[dict]) -> str:
    """在线程池内消费流式输出；取最后一个完整回答片段，避免 ReAct 中间态重复拼接。"""
    last = ""
    with _run_lock:
        for chunk in agent.execute_stream(messages):
            if chunk:
                last = chunk
    return last


def _fetch_weather(city: str, date: str = "") -> str:
    """调用高德天气工具获取目的地指定日期的天气，解析为 '晴 26°C' 简写；失败返回空串。

    由后端在 agent 返回后强制覆盖 weather 字段，保证天气是真实数据、
    而非模型照抄提示词示例（如 '晴 26°C'）产生的「假数据」。
    date 缺省时取当天；传入行程日期时按高德预报窗口（未来 3-4 天）匹配。
    """
    try:
        from agents.tools.agent_tools import get_weather

        # get_weather 是 @tool 装饰出的 StructuredTool 对象，不能直接当函数调用；
        # 用 .func 取回被装饰的原函数，才能以普通 Python 函数方式传参调用。
        raw = get_weather.func(city, date)
        if not raw or "失败" in raw or "未能查询" in raw:
            return ""
        import re

        w = re.search(r"天气：([^\n]+)", raw)
        t = re.search(r"温度：([^\n]+)", raw)
        if w and t:
            return f"{w.group(1).strip()} {t.group(1).strip()}"
        return ""
    except Exception as e:  # noqa: BLE001
        logger.warning("[daily-plan] 获取天气失败：%s", e)
        return ""


async def _call_agent(ctx: dict, req: DailyPlanGenReq) -> dict | str | None:
    """【agent 接入点】调用 RecommendAgent 生成单日计划。

    返回 str（流式输出的 JSON 文本，由上层 _extract_json 解析）；
    加载/调用失败或返回空时返回 None，由 generate_daily_plan 降级为空结构。
    """
    try:
        agent = _get_agent()
    except Exception as e:  # noqa: BLE001
        logger.warning("[daily-plan] 加载 RecommendAgent 失败，返回空结果：%s", e)
        return None

    messages = _build_messages(ctx, req)
    try:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, _run_agent, agent, messages)
    except Exception as e:  # noqa: BLE001
        logger.warning("[daily-plan] RecommendAgent 调用失败，返回空结果：%s", e)
        return None
    return text or None


async def generate_daily_plan(ctx: dict, req: DailyPlanGenReq) -> dict:
    """生成单日计划：调用 agent，拿不到有效结果时返回空结构（不兜底）。

    Returns:
        符合 DailyPlanGenOut 结构的 dict：{date, weather, attractions[]}
        agent 未返回 / 无有效景点 / 调用异常时，attractions=[]、weather=""。
    """
    try:
        result = await _call_agent(ctx, req)
        if isinstance(result, str):
            result = _extract_json(result)
        if isinstance(result, dict):
            plan = _normalize(result, req.date)
            city = (ctx.get("destination") or "").strip()
            if city:
                try:
                    loop = asyncio.get_running_loop()
                    real = await loop.run_in_executor(None, _fetch_weather, city, req.date)
                    if real:
                        plan["weather"] = real
                except Exception as e:  # noqa: BLE001
                    logger.warning("[daily-plan] 覆盖天气失败，保留 agent 返回值：%s", e)
            return plan
        if result is not None:
            logger.warning("[daily-plan] agent 返回类型非 dict/str/None，按空结果处理")
    except Exception as e:  # noqa: BLE001  任何异常都不应让生成接口 500
        logger.warning("[daily-plan] agent 调用失败，返回空结果：%s", e)
    return {"date": req.date, "weather": "", "attractions": []}
