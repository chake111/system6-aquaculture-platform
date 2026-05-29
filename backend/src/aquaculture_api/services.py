from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from aquaculture_api.models import (
    Alert,
    AuditLog,
    BenefitMetric,
    ControlExecution,
    DensityAnalysis,
    Device,
    MediaSample,
    NotificationDelivery,
    Pond,
    Recommendation,
    WaterReading,
)


def make_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def audit(session: Session, actor_id: str, action: str, resource_id: str, trace_id: str) -> None:
    session.add(
        AuditLog(
            id=make_id("audit"),
            actor_id=actor_id,
            action=action,
            resource_id=resource_id,
            trace_id=trace_id,
            occurred_at=datetime.now(UTC).isoformat(),
        )
    )


def pond_payload(pond: Pond) -> dict[str, object]:
    return {
        "id": pond.id,
        "name": pond.name,
        "base_id": pond.base_id,
        "source_mode": pond.source_mode,
    }


def reading_payload(reading: WaterReading) -> dict[str, object]:
    return {
        "id": reading.id,
        "pond_id": reading.pond_id,
        "captured_at": reading.captured_at,
        "dissolved_oxygen_mg_l": reading.dissolved_oxygen_mg_l,
        "ph": reading.ph,
        "source_mode": reading.source_mode,
        "verified": reading.verified,
        "quality_status": reading.quality_status,
        "source_qualifiers": reading.source_qualifiers,
        "source_url": reading.source_url,
    }


def device_payload(device: Device) -> dict[str, object]:
    return {
        "code": device.code,
        "pond_id": device.pond_id,
        "device_type": device.device_type,
        "source_mode": device.source_mode,
        "status": device.status,
    }


def recommendation_payload(recommendation: Recommendation) -> dict[str, object]:
    return {
        "id": recommendation.id,
        "pond_id": recommendation.pond_id,
        "source_mode": recommendation.source_mode,
        "status": recommendation.status,
        "reason": recommendation.reason,
        "recommendation_type": recommendation.recommendation_type,
        "risk_level": recommendation.risk_level,
        "rule_version": recommendation.rule_version,
        "proposed_minutes": recommendation.proposed_minutes,
        "weather_source": recommendation.weather_source,
        "reviewed_by": recommendation.reviewed_by,
        "agent_mode": recommendation.agent_mode,
    }


def execution_payload(execution: ControlExecution) -> dict[str, object]:
    return {
        "id": execution.id,
        "recommendation_id": execution.recommendation_id,
        "execution_mode": execution.execution_mode,
        "status": execution.status,
    }


def alert_payload(
    alert: Alert, deliveries: list[NotificationDelivery] | None = None
) -> dict[str, object]:
    return {
        "id": alert.id,
        "pond_id": alert.pond_id,
        "source_mode": alert.source_mode,
        "status": alert.status,
        "delivery_status": alert.delivery_status,
        "recommendation_id": alert.recommendation_id,
        "deliveries": [
            {
                "channel": delivery.channel,
                "provider_mode": delivery.provider_mode,
                "status": delivery.status,
                "attempts": delivery.attempts,
                "failure_reason": delivery.failure_reason,
            }
            for delivery in (deliveries or [])
        ],
    }


def media_sample_payload(sample: MediaSample) -> dict[str, object]:
    return {
        "id": sample.id,
        "pond_id": sample.pond_id,
        "sample_type": sample.sample_type,
        "object_ref": sample.object_ref,
        "source_mode": sample.source_mode,
    }


def density_payload(analysis: DensityAnalysis) -> dict[str, object]:
    return {
        "id": analysis.id,
        "sample_id": analysis.sample_id,
        "source_mode": analysis.source_mode,
        "review_status": analysis.review_status,
        "estimated_density_fish_m2": analysis.estimated_density_fish_m2,
        "error_margin_fish_m2": analysis.error_margin_fish_m2,
        "model_version": analysis.model_version,
        "recommendation_id": analysis.recommendation_id,
    }


def metric_payload(metric: BenefitMetric) -> dict[str, object]:
    return {
        "label": metric.label,
        "value": metric.value,
        "unit": metric.unit,
        "period": metric.period,
        "source_mode": metric.source_mode,
        "verified": metric.verified,
    }
