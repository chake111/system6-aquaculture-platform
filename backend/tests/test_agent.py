"""Tests for the aquaculture agent: status, chat, analyze, sessions, fallback."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from aquaculture_api.agent import AquacultureAgent, AgentResponse, StructuredAdvice
from aquaculture_api.config import Settings
from aquaculture_api.main import create_app

_env = Settings.from_environment()
_test_settings = Settings(
    app_env=_env.app_env,
    jwt_secret=_env.jwt_secret,
    edge_secret=_env.edge_secret,
    database_url="sqlite+pysqlite:///:memory:",
    seed=True,
    deepseek_api_key="",
    deepseek_base_url="https://api.deepseek.com",
)

_test_settings_with_key = Settings(
    app_env=_env.app_env,
    jwt_secret=_env.jwt_secret,
    edge_secret=_env.edge_secret,
    database_url="sqlite+pysqlite:///:memory:",
    seed=True,
    deepseek_api_key="test-key",
    deepseek_base_url="https://api.deepseek.com",
)


def client(settings: Settings | None = None) -> TestClient:
    return TestClient(create_app(settings or _test_settings))


def login(api: TestClient, phone: str) -> dict[str, str]:
    response = api.post("/api/v1/auth/login", json={"phone": phone, "credential": "demo-246810"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# --- Status endpoint ---


def test_agent_status_without_key() -> None:
    api = client()
    headers = login(api, "13800000001")
    response = api.get("/api/v1/agent/status", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "fallback"
    assert body["model"] == "rule_engine"
    assert body["provider"] == "local"


def test_agent_status_with_key() -> None:
    api = client(_test_settings_with_key)
    headers = login(api, "13800000001")
    response = api.get("/api/v1/agent/status", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "online"
    assert body["model"] == "deepseek-chat"
    assert body["provider"] == "deepseek"


# --- Chat endpoint (fallback mode, no API key) ---


def test_chat_without_key_returns_fallback() -> None:
    api = client()
    headers = login(api, "13800000001")
    response = api.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={
            "session_id": "test-session-1",
            "message": "溶氧太低了怎么办？",
            "pond_id": "pond-hz-01",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    # Parse SSE events
    events = _parse_sse(response.text)
    tokens = [e for e in events if e.get("type") == "token"]
    assert len(tokens) > 0
    # Should contain advice about aeration
    full_text = "".join(t["content"] for t in tokens)
    assert "增氧" in full_text


def test_chat_feed_question() -> None:
    api = client()
    headers = login(api, "13800000001")
    response = api.post(
        "/api/v1/agent/chat",
        headers=headers,
        json={
            "session_id": "test-session-2",
            "message": "投喂量怎么调整？",
            "pond_id": "pond-hz-01",
        },
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    tokens = [e for e in events if e.get("type") == "token"]
    full_text = "".join(t["content"] for t in tokens)
    assert "投喂" in full_text or "饲料" in full_text


# --- Analyze endpoint (fallback mode) ---


def test_analyze_without_key_returns_fallback() -> None:
    api = client()
    headers = login(api, "13800000002")
    response = api.post(
        "/api/v1/agent/analyze",
        headers=headers,
        json={"pond_id": "pond-hz-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "summary" in body
    assert "risk_level" in body
    assert body["risk_level"] in ("low", "medium", "high", "critical")
    assert isinstance(body["actions"], list)


# --- Chat with mocked LLM ---


def test_chat_with_mocked_llm() -> None:
    mock_response = AgentResponse(
        content="溶氧3.2mg/L偏低，建议立即启动1号增氧机，30分钟后复核。",
        mode="llm",
        model="deepseek-chat",
    )

    with patch.object(
        AquacultureAgent, "_chat_one_shot", new_callable=AsyncMock, return_value=mock_response
    ):
        api = client(_test_settings_with_key)
        headers = login(api, "13800000001")
        response = api.post(
            "/api/v1/agent/chat",
            headers=headers,
            json={
                "session_id": "test-mock-1",
                "message": "溶氧多少？",
                "pond_id": "pond-hz-01",
            },
        )
        assert response.status_code == 200


# --- Analyze with mocked LLM ---


def test_analyze_with_mocked_llm() -> None:
    mock_advice = StructuredAdvice(
        summary="溶氧偏低，需要关注",
        risk_level="high",
        category="water_quality",
        actions=["启动增氧机", "1小时后复测"],
        explanation="最近溶氧呈下降趋势",
        data_refs={"latest_do": 3.2, "latest_ph": 7.3, "trend": "下降"},
    )

    with patch.object(
        AquacultureAgent, "analyze", new_callable=AsyncMock, return_value=mock_advice
    ):
        api = client(_test_settings_with_key)
        headers = login(api, "13800000001")
        response = api.post(
            "/api/v1/agent/analyze",
            headers=headers,
            json={"pond_id": "pond-hz-01"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["summary"] == "溶氧偏低，需要关注"
        assert body["risk_level"] == "high"
        assert "启动增氧机" in body["actions"]


# --- Session endpoints ---


def test_session_history_empty() -> None:
    api = client(_test_settings_with_key)
    headers = login(api, "13800000001")
    response = api.get("/api/v1/agent/sessions/nonexistent/history", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "nonexistent"
    assert body["messages"] == []


def test_session_clear() -> None:
    api = client(_test_settings_with_key)
    headers = login(api, "13800000001")
    response = api.delete("/api/v1/agent/sessions/test-session-1", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cleared"


# --- Authentication ---


def test_agent_requires_authentication() -> None:
    api = client()
    assert api.get("/api/v1/agent/status").status_code == 401
    assert api.post(
        "/api/v1/agent/chat",
        json={"session_id": "s1", "message": "hi", "pond_id": "pond-hz-01"},
    ).status_code == 401
    assert api.post(
        "/api/v1/agent/analyze",
        json={"pond_id": "pond-hz-01"},
    ).status_code == 401


# --- Demo route still works ---


def test_demo_inject_still_works() -> None:
    from aquaculture_api.agent import AgentResponse as AR

    mock_response = AR(
        content="AI generated advice for demo",
        mode="llm",
        model="deepseek-chat",
    )

    with patch.object(
        AquacultureAgent, "_chat_one_shot", new_callable=AsyncMock, return_value=mock_response
    ):
        api = client(_test_settings_with_key)
        headers = login(api, "13800000001")
        response = api.post(
            "/api/v1/demo/ponds/pond-hz-01/low-oxygen",
            headers=headers,
            json={"notification_scenario": "retry_success"},
        )
        assert response.status_code == 200
        rec = response.json()["recommendation"]
        assert rec["agent_mode"] == "llm"
        assert rec["reason"] == "AI generated advice for demo"


# --- Helpers ---


def _parse_sse(text: str) -> list[dict]:
    """Parse SSE text into a list of JSON data objects."""
    events = []
    for line in text.split("\n"):
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload == "[DONE]":
                continue
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return events
