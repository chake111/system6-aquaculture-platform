"""Agent API routes: chat (SSE), analyze, sessions, status."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aquaculture_api.agent import AgentResponse, AquacultureAgent, StructuredAdvice
from aquaculture_api.deps import current_user, get_settings, session_dependency, trace_id
from aquaculture_api.models import User
from aquaculture_api.services import audit

# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str
    message: str
    pond_id: str


class AnalyzeRequest(BaseModel):
    pond_id: str


class AgentStatusResponse(BaseModel):
    status: Literal["online", "fallback"]
    model: str
    provider: str


class AgentAdviceResponse(BaseModel):
    content: str
    mode: str
    model: str


class StructuredAdviceResponse(BaseModel):
    summary: str
    risk_level: str
    category: str
    actions: list[str]
    explanation: str
    data_refs: dict[str, object]


class ChatMessageResponse(BaseModel):
    role: str
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, object]] | None = None
    name: str | None = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessageResponse]


# ---------------------------------------------------------------------------
# Agent singleton
# ---------------------------------------------------------------------------

_agent: AquacultureAgent | None = None


def _get_agent() -> AquacultureAgent | None:
    global _agent
    settings = get_settings()
    if not settings.deepseek_api_key:
        return None
    if _agent is None:
        _agent = AquacultureAgent(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _agent


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def router() -> APIRouter:
    r = APIRouter(tags=["agent"])

    @r.get("/api/v1/agent/status")
    def agent_status(
        user: Annotated[User, Depends(current_user)],
    ) -> AgentStatusResponse:
        agent = _get_agent()
        if agent is None:
            return AgentStatusResponse(status="fallback", model="rule_engine", provider="local")
        return AgentStatusResponse(status="online", model="deepseek-chat", provider="deepseek")

    @r.post("/api/v1/agent/chat")
    async def agent_chat(
        body: ChatRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> StreamingResponse:
        agent = _get_agent()
        audit(session, user.id, "agent.chat", body.pond_id, trace_id(request))
        session.commit()

        if agent is None:
            # Fallback: single-turn rule engine
            from aquaculture_api.agent import _fallback_reply

            reply = _fallback_reply(body.message)
            async def fallback_stream():
                yield f"data: {json.dumps({'type': 'token', 'content': reply}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                fallback_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        async def event_stream():
            async for chunk in agent.chat(
                session_id=body.session_id,
                user_message=body.message,
                pond_id=body.pond_id,
                db_session=session,
            ):
                yield chunk

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @r.post("/api/v1/agent/analyze")
    async def agent_analyze(
        body: AnalyzeRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> StructuredAdviceResponse:
        agent = _get_agent()
        audit(session, user.id, "agent.analysis", body.pond_id, trace_id(request))
        session.commit()

        if agent is None:
            from aquaculture_api.agent import _fallback_analysis

            # Get latest reading for fallback
            from sqlalchemy import select
            from aquaculture_api.models import WaterReading

            latest = session.scalars(
                select(WaterReading)
                .where(WaterReading.pond_id == body.pond_id)
                .order_by(WaterReading.captured_at.desc())
                .limit(1)
            ).first()

            if latest:
                result = _fallback_analysis(
                    latest.dissolved_oxygen_mg_l, latest.ph, "数据不足"
                )
            else:
                result = StructuredAdvice(
                    summary="暂无数据",
                    risk_level="low",
                    category="water_quality",
                    actions=["安装传感器"],
                    explanation="该塘口暂无监测数据。",
                )
        else:
            result = await agent.analyze(body.pond_id, session)

        return StructuredAdviceResponse(
            summary=result.summary,
            risk_level=result.risk_level,
            category=result.category,
            actions=result.actions,
            explanation=result.explanation,
            data_refs=result.data_refs,
        )

    @r.get("/api/v1/agent/sessions/{session_id}/history")
    def session_history(
        session_id: str,
        user: Annotated[User, Depends(current_user)],
    ) -> ChatHistoryResponse:
        agent = _get_agent()
        if agent is None:
            return ChatHistoryResponse(session_id=session_id, messages=[])

        history = agent.get_session_history(session_id)
        return ChatHistoryResponse(
            session_id=session_id,
            messages=[
                ChatMessageResponse(
                    role=m.role,
                    content=m.content,
                    tool_call_id=m.tool_call_id,
                    tool_calls=m.tool_calls,
                    name=m.name,
                )
                for m in history
            ],
        )

    @r.delete("/api/v1/agent/sessions/{session_id}")
    def session_clear(
        session_id: str,
        user: Annotated[User, Depends(current_user)],
    ) -> dict[str, str]:
        agent = _get_agent()
        if agent is not None:
            agent.reset_session(session_id)
        return {"status": "cleared", "session_id": session_id}

    return r
