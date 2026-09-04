"""旅行助手问答接口入参校验。"""
from typing import List, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "ai", "system", "assistant"] = "user"
    text: str = Field(..., min_length=1, description="消息文本")


class AssistantAskReq(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户本轮提问")
    history: List[ChatMessage] = Field(
        default_factory=list, description="历史对话（不含本轮），用于上下文"
    )
