import os
import requests
from langchain_core.tools import tool

from agents.rag.rag_service import RagSummarizeService
from agents.utils.logger_handler import logger

# 高德地图 API Key —— 从环境变量读取，部署时无需改代码
AMAP_KEY = os.environ["AMAP_API_KEY"]
rag = RagSummarizeService()

# 高德地理编码接口：把城市/区县名解析为天气接口需要的城市编码（adcode）
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"


def _resolve_adcode(city: str) -> str:
    """把城市/区县名解析为高德城市编码 adcode（天气接口 city 参数要求 adcode）。

    解析失败或该 key 未开通地理编码服务时，回退返回原始 city 名，不影响既有行为。
    """
    city = (city or "").strip()
    if not city:
        return city
    # 已是纯数字编码则直接用，避免无意义的地理编码请求
    if city.isdigit():
        return city
    try:
        resp = requests.get(
            AMAP_GEOCODE_URL,
            params={"address": city, "key": AMAP_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "1" and data.get("geocodes"):
            adcode = (data["geocodes"][0] or {}).get("adcode")
            if adcode:
                logger.info(f"[天气工具] 城市名「{city}」解析为 adcode：{adcode}")
                return adcode
        logger.warning(f"[天气工具] 地理编码未解析到 adcode（回退原名）：{data}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[天气工具] 地理编码请求失败（回退原名）：{e}")
    return city


@tool(description="从向量存储中检索参考资料并基于其总结回答。top_k 为必填整数，控制返回的参考分片数量：首次对目的地做整体宽泛检索（如'XX 必游景点推荐'）时传 10，检索单个具体景点细节（如'纳帕海 门票 开放时间'）时传 3，不可省略。")
def rag_summarize(query: str, top_k: int) -> str:
    return rag.rag_summarize(query, top_k)


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


@tool(description="获取指定城市的天气信息。入参 city（城市/区县名）与可选 date（YYYY-MM-DD，缺省为当天）；返回该日天气现象、温度区间、风向风力。注意：高德天气仅支持实况与未来 3-4 天预报，超出范围的 date 会明确提示暂不支持。")
def get_weather(city: str, date: str = "") -> str:
    """通过高德地图天气API获取指定城市的天气（默认当天，可指定未来日期）"""
    try:
        # 高德天气接口 city 参数要的是城市编码 adcode，而非城市名；先解析再查。
        # 注意：地理编码会把「省份 / 大范围区域」解析到其行政中心（如「云南省」→ 昆明一带），
        # 因此大范围目的地的天气只是城市级、可能不准确——属数据源限制，前端已在天气旁加提示。
        city_code = _resolve_adcode(city)
        resp = requests.get(
            "https://restapi.amap.com/v3/weather/weatherInfo",
            params={"city": city_code, "key": AMAP_KEY, "extensions": "all"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "1" or not data.get("forecasts"):
            logger.warning(f"[天气工具] 高德天气接口返回异常：{data}")
            return f"未能查询到「{city}」的天气信息，请确认城市名称是否正确。"

        forecast = data["forecasts"][0]
        casts = forecast.get("casts", [])
        if not casts:
            return f"未能查询到「{city}」的天气预报。"

        # 目标日期：传入 date 则在预报数组中精确匹配，否则取当天（casts[0]）
        target = None
        if date and date.strip():
            for cast in casts:
                if cast.get("date") == date.strip():
                    target = cast
                    break
            if target is None:
                available = "、".join(c.get("date", "") for c in casts)
                return (
                    f"「{city}」在 {date} 暂无天气预报"
                    f"（高德仅支持近几日预报，可查日期：{available}）。"
                )
        else:
            target = casts[0]

        day_weather = target.get("dayweather", "")
        night_weather = target.get("nightweather", "")
        day_temp = target.get("daytemp", "")
        night_temp = target.get("nighttemp", "")
        weather_desc = day_weather or night_weather
        temp_desc = (
            f"{night_temp}~{day_temp}°C" if day_temp and night_temp else (day_temp or night_temp)
        )
        return (
            f"城市：{forecast.get('province', '')}{forecast.get('city', '')}\n"
            f"日期：{target.get('date', '')}\n"
            f"天气：{weather_desc}\n"
            f"温度：{temp_desc}\n"
            f"白天风向：{target.get('daywind', '')}\n"
            f"白天风力：{target.get('daypower', '')}级\n"
            f"夜间天气：{night_weather}\n"
            f"提示：可指定具体区/县/村获取更精准的局部天气"
        )
    except Exception as e:
        logger.error(f"[天气工具] 天气获取失败：{str(e)}")
        return f"天气查询失败：{str(e)}"
