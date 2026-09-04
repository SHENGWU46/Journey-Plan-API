"""旅行助手 AI 问答接口（对接 agents 子项目）。

端点：
- POST /assistant/ask  入参 {message, history}；返回 {reply}。
  返回风格与现有 auth/plans/user 一致：成功直接返回业务对象，错误由 HTTPException 抛出具名 detail。
- 要求 Bearer 鉴权（与其他 router 一致）。
- AI 服务异常时返回 502 + detail，前端据此回退本地 mock。
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.auth import AuthHandler
from app.schemas.assistant import AssistantAskReq
from app.services.assistant_service import ask_assistant, _is_public_ip

auth_handler = AuthHandler()
router = APIRouter(prefix="/assistant", tags=["assistant"])


def _extract_client_ip(request: Request) -> str:
    """从反向代理透传头或直连地址提取真实客户端 IP。

    部署顺序优先级：X-Forwarded-For（取第一个，真实客户端）> X-Real-IP > 直连地址。
    """
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri.strip()
    if request.client is not None:
        return request.client.host
    return ""


def _build_messages(payload: AssistantAskReq) -> list[dict]:
    messages = []
    for m in payload.history:
        role = "assistant" if m.role == "ai" else m.role
        messages.append({"role": role, "content": m.text})
    messages.append({"role": "user", "content": payload.message})
    return messages


@router.post("/ask")
async def ask(
    payload: AssistantAskReq,
    request: Request,
    user_id: int = Depends(auth_handler.auth_access_dependency),
):
    client_ip = _extract_client_ip(request)
    # 仅注入真实公网 IP；内网/回环地址（如本地开发 127.0.0.1）不传，由定位工具走兜底
    effective_ip = client_ip if _is_public_ip(client_ip) else ""
    try:
        reply = await ask_assistant(_build_messages(payload), client_ip=effective_ip)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 服务暂时不可用：{e}",
        )
    if not reply:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 未返回有效内容，请稍后再试",
        )
    return {"reply": reply}
