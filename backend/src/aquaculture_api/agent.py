"""Aquaculture intelligent agent with multi-turn conversation and tool calling."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from aquaculture_api.models import Alert, Pond, WaterReading

logger = logging.getLogger(__name__)

MAX_HISTORY_ROUNDS = 20

SYSTEM_PROMPT = (
    "你是广东惠州50亩鲈鱼养殖基地的智能养殖顾问「渔智」。\n"
    "你的职责：\n"
    "1. 根据水质监测数据（溶氧、pH）提供专业、可操作的养殖建议\n"
    "2. 分析水质趋势，识别异常并评估风险\n"
    "3. 提供投喂、病害防治、密度管理等方面的专业建议\n"
    "4. 主动调用工具查询实时数据，不要凭空猜测\n\n"
    "重要规则：\n"
    "- 用户消息中的 [当前塘口: xxx] 标记了当前塘口 ID\n"
    "- 回答水质相关问题时，**必须先调用 query_water_readings 工具**获取实时数据\n"
    "- 回答告警相关问题时，**必须先调用 query_alerts 工具**获取告警记录\n"
    "- 工具调用时使用用户消息中的塘口 ID\n"
    "- 可用塘口: pond-hz-01（惠州示范塘）、pond-ref（广西观测站）\n\n"
    "回复要求：\n"
    "- 直接给出建议，不要寒暄\n"
    "- 溶氧低于4mg/L时必须建议增氧，并标注风险等级\n"
    "- 结合鲈鱼生长阶段给出针对性建议\n"
    "- 回复使用 markdown 格式，用 **加粗** 标注关键信息\n"
    "- 回复控制在300字以内"
)

ANALYSIS_SYSTEM_PROMPT = (
    "你是鲈鱼养殖基地的水质分析专家。\n"
    "你需要对水质数据进行全面分析，输出结构化的分析报告。\n"
    "分析维度：溶氧水平、pH 偏差、趋势变化、综合风险。\n"
    "输出格式为 JSON，包含以下字段：\n"
    '  "summary": 一句话结论\n'
    '  "risk_level": "low" | "medium" | "high" | "critical"\n'
    '  "category": "water_quality" | "feed" | "disease" | "density" | "weather"\n'
    '  "actions": [具体操作步骤列表]\n'
    '  "explanation": 详细分析说明\n'
    '  "data_refs": {"latest_do": 数值, "latest_ph": 数值, "trend": "上升|下降|稳定"}'
)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_water_readings",
            "description": "查询指定塘口最近的水质监测数据（溶氧、pH）",
            "parameters": {
                "type": "object",
                "properties": {
                    "pond_id": {"type": "string", "description": "塘口 ID"},
                    "limit": {
                        "type": "integer",
                        "description": "返回条数，默认 10",
                        "default": 10,
                    },
                },
                "required": ["pond_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_alerts",
            "description": "查询指定塘口的告警记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "pond_id": {"type": "string", "description": "塘口 ID"},
                    "status": {
                        "type": "string",
                        "description": "告警状态筛选，如 generated, confirmed, resolved",
                    },
                },
                "required": ["pond_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_pond_info",
            "description": "查询塘口基本信息（名称、基地）",
            "parameters": {
                "type": "object",
                "properties": {
                    "pond_id": {"type": "string", "description": "塘口 ID"},
                },
                "required": ["pond_id"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentResponse:
    content: str
    mode: str  # "llm" | "fallback"
    model: str


@dataclass
class StructuredAdvice:
    summary: str
    risk_level: str  # low / medium / high / critical
    category: str  # water_quality / feed / disease / density / weather
    actions: list[str]
    explanation: str
    data_refs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    role: str  # user / assistant / system / tool
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    name: str | None = None


# ---------------------------------------------------------------------------
# Tool execution (runs inside route handlers with a DB session)
# ---------------------------------------------------------------------------


def execute_tool(session: Session, name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool call against the database and return JSON result."""
    if name == "query_water_readings":
        pond_id = arguments["pond_id"]
        limit = arguments.get("limit", 10)
        readings = session.scalars(
            select(WaterReading)
            .where(WaterReading.pond_id == pond_id)
            .order_by(WaterReading.captured_at.desc())
            .limit(limit)
        ).all()
        return json.dumps(
            [
                {
                    "captured_at": r.captured_at,
                    "dissolved_oxygen_mg_l": r.dissolved_oxygen_mg_l,
                    "ph": r.ph,
                    "quality_status": r.quality_status,
                }
                for r in readings
            ],
            ensure_ascii=False,
        )

    if name == "query_alerts":
        pond_id = arguments["pond_id"]
        stmt = select(Alert).where(Alert.pond_id == pond_id)
        status = arguments.get("status")
        if status:
            stmt = stmt.where(Alert.status == status)
        stmt = stmt.order_by(Alert.id.desc()).limit(10)
        alerts = session.scalars(stmt).all()
        return json.dumps(
            [
                {
                    "id": a.id,
                    "status": a.status,
                    "delivery_status": a.delivery_status,
                    "recommendation_id": a.recommendation_id,
                }
                for a in alerts
            ],
            ensure_ascii=False,
        )

    if name == "query_pond_info":
        pond = session.get(Pond, arguments["pond_id"])
        if pond is None:
            return json.dumps({"error": "塘口不存在"}, ensure_ascii=False)
        return json.dumps(
            {"id": pond.id, "name": pond.name, "base_id": pond.base_id},
            ensure_ascii=False,
        )

    return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Aquaculture Agent
# ---------------------------------------------------------------------------


class AquacultureAgent:
    """Multi-turn conversational agent for aquaculture with tool calling."""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = "deepseek-chat"
        self._client: httpx.AsyncClient | None = None
        self._sessions: dict[str, list[ChatMessage]] = defaultdict(list)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def _chat_one_shot(self, system: str, user: str) -> AgentResponse:
        """Single-turn chat without session management. Used by demo route."""
        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 300,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return AgentResponse(content=content.strip(), mode="llm", model=self._model)
        except Exception:
            logger.exception("One-shot API call failed")
            return AgentResponse(content="", mode="fallback", model="rule_engine")

    def get_session_history(self, session_id: str) -> list[ChatMessage]:
        return list(self._sessions.get(session_id, []))

    def reset_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _trim_history(self, session_id: str) -> None:
        msgs = self._sessions[session_id]
        max_messages = MAX_HISTORY_ROUNDS * 2 + 1
        if len(msgs) > max_messages:
            self._sessions[session_id] = msgs[-max_messages:]

    def _build_messages(
        self, session_id: str, system: str
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for msg in self._sessions.get(session_id, []):
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.name:
                entry["name"] = msg.name
            messages.append(entry)
        return messages

    async def chat(
        self,
        session_id: str,
        user_message: str,
        pond_id: str,
        db_session: Session | None = None,
    ) -> AsyncIterator[str]:
        """Multi-turn chat with streaming output and tool calling.

        Yields SSE-formatted strings: ``data: {json}\n\n``
        Final message yields ``data: [DONE]\n\n``
        """
        # Prepend pond context so the LLM knows which pond to query
        context_msg = f"[当前塘口: {pond_id}] {user_message}"
        self._sessions[session_id].append(ChatMessage(role="user", content=context_msg))
        self._trim_history(session_id)

        client = await self._get_client()
        messages = self._build_messages(session_id, SYSTEM_PROMPT)

        try:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "tools": TOOL_DEFINITIONS,
                    "tool_choice": "auto",
                    "temperature": 0.7,
                    "max_tokens": 600,
                    "stream": True,
                },
            )
            resp.raise_for_status()

            collected_content = ""
            tool_calls_buf: dict[int, dict[str, Any]] = {}

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue

                delta = chunk.get("choices", [{}])[0].get("delta", {})

                # Accumulate content
                if delta.get("content"):
                    token = delta["content"]
                    collected_content += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

                # Accumulate tool calls
                if delta.get("tool_calls"):
                    for tc_delta in delta["tool_calls"]:
                        idx = tc_delta.get("index", 0)
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {
                                "id": tc_delta.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        buf = tool_calls_buf[idx]
                        if tc_delta.get("id"):
                            buf["id"] = tc_delta["id"]
                        fn = tc_delta.get("function", {})
                        if fn.get("name"):
                            buf["function"]["name"] += fn["name"]
                        if fn.get("arguments"):
                            buf["function"]["arguments"] += fn["arguments"]

            # Handle tool calls
            if tool_calls_buf and db_session is not None:
                tool_calls_list = [tool_calls_buf[i] for i in sorted(tool_calls_buf)]
                self._sessions[session_id].append(
                    ChatMessage(
                        role="assistant",
                        content=collected_content or "",
                        tool_calls=tool_calls_list,
                    )
                )

                for tc in tool_calls_list:
                    fn_name = tc["function"]["name"]
                    try:
                        fn_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        fn_args = {}

                    yield f"data: {json.dumps({'type': 'tool_call', 'name': fn_name, 'args': fn_args}, ensure_ascii=False)}\n\n"

                    result = execute_tool(db_session, fn_name, fn_args)
                    self._sessions[session_id].append(
                        ChatMessage(
                            role="tool",
                            content=result,
                            tool_call_id=tc["id"],
                            name=fn_name,
                        )
                    )

                    yield f"data: {json.dumps({'type': 'tool_result', 'name': fn_name, 'result': json.loads(result)}, ensure_ascii=False)}\n\n"

                # Follow-up call with tool results
                follow_messages = self._build_messages(session_id, SYSTEM_PROMPT)
                follow_resp = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._model,
                        "messages": follow_messages,
                        "temperature": 0.7,
                        "max_tokens": 600,
                        "stream": True,
                    },
                )
                follow_resp.raise_for_status()

                follow_content = ""
                async for line in follow_resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    if delta.get("content"):
                        token = delta["content"]
                        follow_content += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

                self._sessions[session_id].append(
                    ChatMessage(role="assistant", content=follow_content)
                )
            elif collected_content:
                self._sessions[session_id].append(
                    ChatMessage(role="assistant", content=collected_content)
                )

        except Exception:
            logger.exception("Agent chat failed, falling back to rule engine")
            fallback = _fallback_reply(user_message)
            self._sessions[session_id].append(
                ChatMessage(role="assistant", content=fallback)
            )
            yield f"data: {json.dumps({'type': 'token', 'content': fallback}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    async def analyze(
        self,
        pond_id: str,
        db_session: Session,
    ) -> StructuredAdvice:
        """Structured water quality analysis. Returns structured advice."""
        readings = db_session.scalars(
            select(WaterReading)
            .where(WaterReading.pond_id == pond_id)
            .order_by(WaterReading.captured_at.desc())
            .limit(10)
        ).all()

        if not readings:
            return StructuredAdvice(
                summary="暂无水质数据",
                risk_level="low",
                category="water_quality",
                actions=["安装传感器并开始数据采集"],
                explanation="该塘口暂无水质监测数据，建议先部署传感器。",
            )

        lines = [f"塘口：{pond_id}", "最近水质数据："]
        for r in readings:
            lines.append(f"  {r.captured_at} - 溶氧: {r.dissolved_oxygen_mg_l} mg/L, pH: {r.ph}")

        latest_do = readings[0].dissolved_oxygen_mg_l
        latest_ph = readings[0].ph

        # Trend calculation
        if len(readings) >= 3:
            early = [r.dissolved_oxygen_mg_l for r in readings[len(readings) // 2 :]]
            late = [r.dissolved_oxygen_mg_l for r in readings[: len(readings) // 2]]
            avg_early = sum(early) / len(early)
            avg_late = sum(late) / len(late)
            if avg_late - avg_early > 0.5:
                trend = "上升"
            elif avg_early - avg_late > 0.5:
                trend = "下降"
            else:
                trend = "稳定"
        else:
            trend = "数据不足"

        lines.append(f"\n最新溶氧: {latest_do} mg/L, 最新pH: {latest_ph}, 趋势: {trend}")
        lines.append("请以 JSON 格式输出分析结果。")

        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                        {"role": "user", "content": "\n".join(lines)},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 400,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return StructuredAdvice(
                summary=parsed.get("summary", "分析完成"),
                risk_level=parsed.get("risk_level", "medium"),
                category=parsed.get("category", "water_quality"),
                actions=parsed.get("actions", []),
                explanation=parsed.get("explanation", ""),
                data_refs=parsed.get("data_refs", {}),
            )
        except Exception:
            logger.exception("Agent analysis failed, using rule engine fallback")
            return _fallback_analysis(latest_do, latest_ph, trend)


# ---------------------------------------------------------------------------
# Fallback rule engine
# ---------------------------------------------------------------------------


def _fallback_reply(user_message: str) -> str:
    msg = user_message.lower()
    if any(k in msg for k in ("溶氧", "增氧", "缺氧", "低氧")):
        return (
            "**溶氧管理建议**\n\n"
            "- 溶氧低于 4 mg/L 时，立即启动增氧机 30 分钟\n"
            "- 夜间和凌晨是溶氧低谷期，需重点关注\n"
            "- 建议安排人工复核读数，确认传感器准确性"
        )
    if any(k in msg for k in ("喂", "饲料", "投喂")):
        return (
            "**投喂建议**\n\n"
            "- 水温 25-30°C 时，日投喂量为鱼体重的 3-5%\n"
            "- 溶氧低于 4 mg/L 时减少投喂量 50%\n"
            "- 分 2-3 次投喂，避免一次过量"
        )
    if any(k in msg for k in ("病", "害", "防病")):
        return (
            "**病害防治建议**\n\n"
            "- 定期消毒水体，保持水质清洁\n"
            "- 注意观察鱼的摄食和活动状态\n"
            "- 发现异常及时隔离病鱼，咨询兽医"
        )
    return (
        "建议启动增氧机 30 分钟，安排人工复核读数。"
        "如有具体问题（溶氧、投喂、病害），请直接提问获取针对性建议。"
    )


def _fallback_analysis(
    latest_do: float, latest_ph: float, trend: str
) -> StructuredAdvice:
    risk = "low"
    actions: list[str] = []

    if latest_do < 3.0:
        risk = "critical"
        actions = [
            "立即启动全部增氧机",
            "减少投喂量 50%",
            "安排人员 24 小时值守",
        ]
    elif latest_do < 4.0:
        risk = "high"
        actions = [
            "启动增氧机 30 分钟",
            "减少投喂量 30%",
            "1 小时后复测溶氧",
        ]
    elif latest_do < 5.0:
        risk = "medium"
        actions = [
            "关注溶氧变化趋势",
            "适当减少投喂量",
        ]
    else:
        actions = ["保持常规巡塘", "按时记录水质数据"]

    if latest_ph < 6.5 or latest_ph > 9.0:
        risk = max(risk, "high", key=lambda x: ["low", "medium", "high", "critical"].index(x))
        actions.append("pH 异常，建议检测水体酸碱度并调节")

    summary = f"溶氧 {latest_do} mg/L，pH {latest_ph}，趋势{trend}"
    return StructuredAdvice(
        summary=summary,
        risk_level=risk,
        category="water_quality",
        actions=actions,
        explanation=f"基于最近水质数据，{summary}。",
        data_refs={"latest_do": latest_do, "latest_ph": latest_ph, "trend": trend},
    )


# ---------------------------------------------------------------------------
# Legacy compatibility (for routes/demo.py)
# ---------------------------------------------------------------------------

_fallback_response = AgentResponse(
    content="建议启动增氧机30分钟，安排人工复核读数。当前溶氧偏低，需密切关注。",
    mode="fallback",
    model="rule_engine",
)


def get_agent_response_fallback() -> AgentResponse:
    return _fallback_response
