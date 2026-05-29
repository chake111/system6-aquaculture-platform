from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from aquaculture_api.deps import ApiError, session_dependency, trace_id
from aquaculture_api.models import (
    Alert,
    EdgeNonce,
    NotificationDelivery,
    Recommendation,
    SyncBatch,
    ThresholdRule,
    WaterReading,
)
from aquaculture_api.schemas import EdgeBatchRequest
from aquaculture_api.security import valid_edge_signature
from aquaculture_api.services import audit, make_id


def router() -> APIRouter:
    r = APIRouter(tags=["edge"])

    @r.post("/api/v1/edge/readings:batch")
    def edge_readings(
        body: EdgeBatchRequest,
        request: Request,
        session: Annotated[Session, Depends(session_dependency)],
        x_edge_timestamp: Annotated[str | None, Header()] = None,
        x_edge_nonce: Annotated[str | None, Header()] = None,
        x_edge_signature: Annotated[str | None, Header()] = None,
    ) -> dict[str, object]:
        from aquaculture_api.deps import get_settings

        settings = get_settings()
        if (
            x_edge_timestamp is None
            or x_edge_nonce is None
            or x_edge_signature is None
            or body.node_id != "edge-hz-001"
        ):
            raise ApiError(401, "unauthorized", "Invalid edge node identity")
        try:
            signed_at = datetime.fromisoformat(x_edge_timestamp)
        except ValueError as error:
            raise ApiError(401, "unauthorized", "Invalid edge signature timestamp") from error
        if abs(datetime.now(UTC) - signed_at.astimezone(UTC)) > timedelta(minutes=5):
            raise ApiError(401, "unauthorized", "Expired edge signature")
        if not valid_edge_signature(
            body.model_dump(), x_edge_timestamp, x_edge_nonce, x_edge_signature, settings
        ):
            raise ApiError(401, "unauthorized", "Invalid edge signature")
        if session.get(EdgeNonce, x_edge_nonce) is not None:
            raise ApiError(409, "replayed_request", "Edge request nonce was already processed")
        session.add(EdgeNonce(nonce=x_edge_nonce, seen_at=datetime.now(UTC).isoformat()))
        prior_batch = session.scalar(select(SyncBatch).where(SyncBatch.batch_key == body.batch_key))
        if prior_batch is not None:
            duplicate_events = [
                event.event_id
                for event in body.events
                if session.scalar(
                    select(WaterReading).where(WaterReading.event_id == event.event_id)
                )
                is not None
            ]
            rejected_events = [
                {"event_id": event.event_id, "reason": "pond_outside_node_scope"}
                for event in body.events
                if event.pond_id != "pond-hz-01"
            ]
            audit(session, body.node_id, "edge.batch_retried", body.batch_key, trace_id(request))
            session.commit()
            return {
                "accepted": [],
                "duplicates": duplicate_events,
                "rejected": rejected_events,
                "acknowledged_at": prior_batch.acknowledged_at,
                "source_mode": "simulation",
            }
        accepted: list[str] = []
        duplicates: list[str] = []
        rejected: list[dict[str, str]] = []
        for event in body.events:
            if event.pond_id != "pond-hz-01":
                rejected.append({"event_id": event.event_id, "reason": "pond_outside_node_scope"})
                continue
            existing = session.scalar(
                select(WaterReading).where(WaterReading.event_id == event.event_id)
            )
            if existing is not None:
                duplicates.append(event.event_id)
                continue
            reading = WaterReading(
                id=make_id("reading"),
                event_id=event.event_id,
                pond_id=event.pond_id,
                captured_at=event.captured_at,
                dissolved_oxygen_mg_l=event.dissolved_oxygen_mg_l,
                ph=event.ph,
                source_mode="simulation",
                verified=False,
                quality_status=event.quality_status,
                source_qualifiers="",
                source_url="",
            )
            session.add(reading)
            accepted.append(event.event_id)
            threshold = session.get(ThresholdRule, "do-warning")
            if (
                event.quality_status == "valid"
                and threshold is not None
                and event.dissolved_oxygen_mg_l < threshold.warning_below
            ):
                recommendation = Recommendation(
                    id=make_id("recommendation"),
                    pond_id=event.pond_id,
                    source_mode="simulation",
                    status="generated",
                    reason="Low dissolved oxygen demonstration input",
                    recommendation_type="aeration",
                    risk_level="high",
                    rule_version=threshold.version,
                    proposed_minutes=30,
                    weather_source="simulation-weather-v1",
                )
                alert = Alert(
                    id=make_id("alert"),
                    pond_id=event.pond_id,
                    source_mode="simulation",
                    status=(
                        "delivery_failed"
                        if event.notification_scenario == "failed"
                        else "delivered"
                    ),
                    delivery_status=(
                        "delivery_failed"
                        if event.notification_scenario == "failed"
                        else "delivered"
                    ),
                    recommendation_id=recommendation.id,
                )
                session.add_all([recommendation, alert])
                session.flush()
                session.add_all(_simulation_deliveries(alert.id, event.notification_scenario))
                audit(
                    session,
                    body.node_id,
                    "recommendation.generated",
                    recommendation.id,
                    trace_id(request),
                )
                audit(session, body.node_id, "alert.delivered", alert.id, trace_id(request))
        session.add(
            SyncBatch(
                id=make_id("sync"),
                node_id=body.node_id,
                batch_key=body.batch_key,
                accepted_count=len(accepted),
                duplicate_count=len(duplicates),
                rejected_count=len(rejected),
                acknowledged_at=datetime.now(UTC).isoformat(),
            )
        )
        audit(session, body.node_id, "edge.batch_received", body.batch_key, trace_id(request))
        session.commit()
        return {
            "accepted": accepted,
            "duplicates": duplicates,
            "rejected": rejected,
            "acknowledged_at": datetime.now(UTC).isoformat(),
            "source_mode": "simulation",
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
