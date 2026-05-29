from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from aquaculture_api.deps import (
    current_user,
    role_required,
    session_dependency,
    trace_id,
)
from aquaculture_api.models import (
    AuditLog,
    SyncBatch,
    ThresholdRule,
    User,
    WaterReading,
)
from aquaculture_api.schemas import ThresholdRuleRequest
from aquaculture_api.services import audit


def router() -> APIRouter:
    r = APIRouter(tags=["operations"])

    @r.get("/api/v1/operations/health")
    def operations_health(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"admin"})
        observations = session.scalars(
            select(WaterReading).where(WaterReading.source_mode.in_(["simulation", "crawled"]))
        ).all()
        return {
            "environment": "demonstration",
            "crawled_observation_count": len(observations),
            "adapter_mode": "simulation",
            "components": {
                "api": {"status": "healthy"},
                "database": {"status": "healthy"},
                "sync": {"status": "healthy", "retention_days": 7},
                "notifications": {"status": "healthy", "provider_mode": "simulation"},
                "object_storage": {"status": "simulation"},
            },
        }

    @r.get("/api/v1/operations/sync-batches")
    def sync_batches(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> list[dict[str, object]]:
        role_required(user, {"admin"})
        batches = session.scalars(
            select(SyncBatch).order_by(SyncBatch.acknowledged_at.desc())
        ).all()
        return [
            {
                "batch_key": batch.batch_key,
                "accepted_count": batch.accepted_count,
                "duplicate_count": batch.duplicate_count,
                "rejected_count": batch.rejected_count,
                "acknowledged_at": batch.acknowledged_at,
                "retention_days": 7,
            }
            for batch in batches
        ]

    @r.get("/api/v1/audit-logs")
    def audit_logs(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> list[dict[str, object]]:
        role_required(user, {"admin"})
        records = session.scalars(select(AuditLog).order_by(AuditLog.occurred_at.desc())).all()
        return [
            {
                "id": record.id,
                "actor_id": record.actor_id,
                "action": record.action,
                "resource_id": record.resource_id,
                "trace_id": record.trace_id,
                "occurred_at": record.occurred_at,
            }
            for record in records
        ]

    @r.put("/api/v1/threshold-rules/{rule_id}")
    def update_threshold_rule(
        rule_id: str,
        body: ThresholdRuleRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"admin"})
        rule = session.get(ThresholdRule, rule_id)
        if rule is None:
            rule = ThresholdRule(
                id=rule_id,
                warning_below=body.warning_below,
                version=body.version,
                source_mode="simulation",
            )
            session.add(rule)
        else:
            rule.warning_below = body.warning_below
            rule.version = body.version
            rule.source_mode = "simulation"
        audit(session, user.id, "threshold_rule.updated", rule.id, trace_id(request))
        session.commit()
        return {
            "id": rule.id,
            "warning_below": rule.warning_below,
            "version": rule.version,
            "source_mode": rule.source_mode,
        }

    return r
