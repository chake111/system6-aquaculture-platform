from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from aquaculture_api.agent import AquacultureAgent
from aquaculture_api.deps import (
    ApiError,
    current_user,
    get_settings,
    role_required,
    scoped_pond,
    session_dependency,
    trace_id,
)
from aquaculture_api.models import (
    Alert,
    NotificationDelivery,
    Recommendation,
    ThresholdRule,
    User,
    WaterReading,
)
from aquaculture_api.schemas import InjectionRequest
from aquaculture_api.services import (
    alert_payload,
    audit,
    make_id,
    reading_payload,
    recommendation_payload,
)


def router() -> APIRouter:
    r = APIRouter(tags=["demo"])

    @r.post("/api/v1/demo/ponds/{pond_id}/low-oxygen")
    async def inject_demo_low_oxygen(
        pond_id: str,
        body: InjectionRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"farmer", "admin"})
        scoped_pond(session, user, pond_id)
        if pond_id != "pond-hz-01":
            raise ApiError(
                400, "invalid_demo_target", "Demo injection targets the pond simulator only"
            )
        threshold = session.get(ThresholdRule, "do-warning")
        if threshold is None:
            raise ApiError(409, "missing_rule", "Demo threshold rule is unavailable")

        do_value = 3.2
        ph_value = 7.3

        agent_reason = "Low dissolved oxygen demonstration input"
        agent_mode = "rule_engine"
        settings = get_settings()
        if settings.deepseek_api_key:
            agent = AquacultureAgent(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
            # One-shot analysis for demo injection
            result = await agent._chat_one_shot(
                system=(
                    "你是广东惠州50亩鲈鱼养殖基地的智能养殖顾问。"
                    "根据水质数据给出简短增氧建议，150字以内。"
                ),
                user=f"塘口：{pond_id}\n当前溶氧：{do_value} mg/L\n当前pH：{ph_value}\n"
                "补充信息：模拟低溶氧事件注入\n请给出增氧和养殖管理建议。",
            )
            if result.mode == "llm":
                agent_reason = result.content
                agent_mode = "llm"

        reading = WaterReading(
            id=make_id("reading"),
            event_id=make_id("demo-event"),
            pond_id=pond_id,
            captured_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            dissolved_oxygen_mg_l=do_value,
            ph=ph_value,
            source_mode="simulation",
            verified=False,
            quality_status="valid",
            source_qualifiers="",
            source_url="",
        )
        recommendation = Recommendation(
            id=make_id("recommendation"),
            pond_id=pond_id,
            source_mode="simulation",
            status="generated",
            reason=agent_reason,
            recommendation_type="aeration",
            risk_level="high",
            rule_version=threshold.version,
            proposed_minutes=30,
            weather_source="simulation-weather-v1",
            agent_mode=agent_mode,
        )
        alert = Alert(
            id=make_id("alert"),
            pond_id=pond_id,
            source_mode="simulation",
            status="delivery_failed" if body.notification_scenario == "failed" else "delivered",
            delivery_status=(
                "delivery_failed" if body.notification_scenario == "failed" else "delivered"
            ),
            recommendation_id=recommendation.id,
        )
        session.add_all([reading, recommendation, alert])
        session.flush()
        deliveries = _simulation_deliveries(alert.id, body.notification_scenario)
        session.add_all(deliveries)
        audit(session, user.id, "demo.low_oxygen_injected", reading.id, trace_id(request))
        audit(session, user.id, "recommendation.generated", recommendation.id, trace_id(request))
        audit(session, user.id, "alert.delivered", alert.id, trace_id(request))
        session.commit()
        return {
            "reading": reading_payload(reading),
            "recommendation": recommendation_payload(recommendation),
            "alert": alert_payload(alert, deliveries),
        }

    return r


def _simulation_deliveries(alert_id: str, scenario: str) -> list[NotificationDelivery]:
    status = "failed" if scenario == "failed" else "delivered"
    attempts = 2 if scenario == "retry_success" else (3 if scenario == "failed" else 1)
    failure_reason = "simulated provider failure after retries" if scenario == "failed" else None
    return [
        NotificationDelivery(
            id=make_id("delivery"),
            alert_id=alert_id,
            channel=channel,
            provider_mode="simulation",
            status=status,
            attempts=attempts,
            failure_reason=failure_reason,
        )
        for channel in ("sms", "dingtalk")
    ]
