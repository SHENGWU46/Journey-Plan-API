"""旅行助手 AI 服务：封装 agents 子项目中的 ReactAgent。

- agents 子项目直接读取环境变量 AMAP_KEY（高德）与 DASHSCOPE_API_KEY（通义千问）；
  项目 .env 中变量名为 AMAP_API_KEY，这里做桥接，避免改动 agents 代码本身。
- ReactAgent 首次构建会加载 RAG 向量库（联网 embedding），约数秒，故懒加载并缓存单例。
- 智能体为同步阻塞调用，放到线程池执行，避免阻塞 asyncio 事件循环。
"""
import os
import ipaddress
import asyncio
from threading import Lock

from dotenv import load_dotenv

# 1) 确保 .env 已注入环境（agents 直接读 os.environ）
load_dotenv()
# 2) 桥接变量名：.env 中是 AMAP_API_KEY，agents 读的是 AMAP_KEY
os.environ.setdefault("AMAP_KEY", os.environ.get("AMAP_API_KEY", ""))

from agents.agent.react_agent import ReactAgent  # noqa: E402

_agent_instance = None
_agent_lock = Lock()


def _get_agent() -> ReactAgent:
    global _agent_instance
    if _agent_instance is None:
        with _agent_lock:
            if _agent_instance is None:
                _agent_instance = ReactAgent()
    return _agent_instance


def _is_public_ip(ip: str) -> bool:
    """仅当为可用的公网 IPv4/IPv6 时才认为可注入，排除私网/回环/保留地址。"""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    )


def _run_agent(messages: list[dict], client_ip: str = "") -> str:
    """同步执行智能体，返回完整回复文本。

    client_ip 为用户真实公网 IP：经校验为可用公网地址时才作为系统上下文注入，
    引导智能体在需要定位时把 ip 参数传给 get_user_location 以准确定位；
    私网/回环/空地址一律不注入，由定位工具走兜底。
    """
    if client_ip and _is_public_ip(client_ip):
        messages = [
            {
                "role": "system",
                "content": (
                    f"[系统上下文] 用户的真实公网IP地址为：{client_ip}。"
                    "当用户询问当前位置、天气、周边景点或出行信息且未明确指定城市时，"
                    f"调用 get_user_location 工具必须把 ip 参数设为 {client_ip} 以准确定位。"
                ),
            }
        ] + messages
    agent = _get_agent()
    parts = []
    for chunk in agent.execute_stream(messages):
        if chunk:
            parts.append(chunk)
    return "".join(parts).strip()


async def ask_assistant(messages: list[dict], client_ip: str = "") -> str:
    loop = asyncio.get_event_loop()
    # run_in_executor 的额外位置参数会按顺序传给 _run_agent
    return await loop.run_in_executor(None, _run_agent, messages, client_ip)
