import os
import requests
from langchain_core.tools import tool

from agents.rag.rag_service import RagSummarizeService
from agents.utils.logger_handler import logger

# 高德地图 API Key —— 从环境变量读取，部署时无需改代码
AMAP_KEY = os.environ["AMAP_API_KEY"]
rag = RagSummarizeService()


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    return rag.rag_summarize(query)


@tool(description="基于IP获取用户所在城市。传入ip参数可定位指定IP的城市，不传则默认定位请求来源IP。返回城市名称字符串（如'成都市'）。当已知用户真实公网IP时，务必传入ip参数以准确定位。")
def get_user_location(ip: str = "") -> str:
    """
    通过高德IP定位接口获取用户所在城市。

    Args:
        ip: 要定位的公网IP地址（可选）。传入空字符串则使用请求来源IP。
    """
    try:
        params: dict = {"key": AMAP_KEY}
        if ip and ip.strip():
            params["ip"] = ip.strip()
            logger.info(f"[定位工具] 指定IP定位：{ip.strip()}")

        resp = requests.get(
            "https://restapi.amap.com/v3/ip",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "1":
            city = data.get("city", "")
            province = data.get("province", "")
            if city:
                logger.info(f"[定位工具] 定位成功：{province}{city}")
                return city

        logger.warning(f"[定位工具] 高德IP接口返回异常：{data}")
        return "未知城市"
    except Exception as e:
        logger.error(f"[定位工具] IP定位失败：{str(e)}")
        return "未知城市"


@tool(description="获取指定城市的实时天气信息，入参为城市名称（纯文本字符串，支持市/区/县名），返回天气现象、温度、湿度、风向风力、体感温度")
def get_weather(city: str) -> str:
    """通过高德地图天气API获取指定城市的实时天气"""
    try:
        resp = requests.get(
            "https://restapi.amap.com/v3/weather/weatherInfo",
            params={"city": city, "key": AMAP_KEY, "extensions": "base"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "1" or not data.get("lives"):
            logger.warning(f"[天气工具] 高德天气接口返回异常：{data}")
            return f"未能查询到「{city}」的天气信息，请确认城市名称是否正确。"

        live = data["lives"][0]
        city_name = live["city"]
        return (
            f"城市：{live['province']}{city_name}\n"
            f"天气：{live['weather']}\n"
            f"温度：{live['temperature']}°C\n"
            f"湿度：{live['humidity']}%\n"
            f"风向：{live['winddirection']}\n"
            f"风力：{live['windpower']}级\n"
            f"更新时间：{live['reporttime']}\n"
            f"提示：可指定具体区/县/村获取更精准的局部天气"
        )
    except Exception as e:
        logger.error(f"[天气工具] 天气获取失败：{str(e)}")
        return f"天气查询失败：{str(e)}"
