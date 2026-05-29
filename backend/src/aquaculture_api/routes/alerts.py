from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from aquaculture_api.deps import (
    current_user,
    get_entity_or_404,
    require_state,
    role_required,
    scoped_alert,
    session_dependency,
    trace_id,
)
from aquaculture_api.models import (
    Alert,
    ControlExecution,
    NotificationDelivery,
    Recommendation,
    User,
)
from aquaculture_api.schemas import ResolutionRequest
from aquaculture_api.services import alert_payload, audit, make_id


def router() -> APIRouter:
    r = APIRouter(tags=["alerts"])

    @r.get("/api/v1/alerts")
    def alerts(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> list[dict[str, object]]:
        records = session.scalars(
            select(Alert).where(Alert.pond_id.in_(user.pond_scope.split(",")))
        ).all()
        return [
            alert_payload(
                record,
                list(
                    session.scalars(
                        select(NotificationDelivery).where(
                            NotificationDelivery.alert_id == record.id
                        )
                    ).all()
                ),
            )
            for record in records
        ]

    @r.post("/api/v1/alerts/{alert_id}/acknowledge")
    def acknowledge_alert(
        alert_id: str,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        alert = scoped_alert(session, user, alert_id)
        require_state(alert.status, {"delivered", "delivery_failed"}, "Alert")
        alert.status = "acknowledged"
        audit(session, user.id, "alert.acknowledged", alert.id, trace_id(request))
        session.commit()
        return alert_payload(alert)

    @r.post("/api/v1/alerts/{alert_id}/resolve")
    def resolve_alert(
        alert_id: str,
        body: ResolutionRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"farmer", "technician"})
        alert = scoped_alert(session, user, alert_id)
        require_state(alert.status, {"acknowledged"}, "Alert")
        alert.status = "resolved"
        alert.resolution = body.resolution
        audit(session, user.id, "alert.resolved", alert.id, trace_id(request))
        session.commit()
        return alert_payload(alert)

    @r.post("/api/v1/alerts/{alert_id}/close")
    def close_alert(
        alert_id: str,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"technician", "admin"})
        alert = scoped_alert(session, user, alert_id)
        require_state(alert.status, {"resolved"}, "Alert")
        alert.status = "closed"
        audit(session, user.id, "alert.closed", alert.id, trace_id(request))
        session.commit()
        return alert_payload(alert)

    @r.post("/api/v1/alerts/{alert_id}/quick-response")
    def quick_response(
        alert_id: str,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"farmer", "admin"})
        alert = scoped_alert(session, user, alert_id)
        require_state(alert.status, {"delivered", "delivery_failed"}, "Alert")
        tid = trace_id(request)
        recommendation = get_entity_or_404(
            session, Recommendation, alert.recommendation_id, "Recommendation"
        )
        require_state(recommendation.status, {"generated"}, "Recommendation")
        recommendation.status = "reviewed"
        recommendation.reviewed_by = user.id
        recommendation.review_note = "Quick response demo review"
        audit(session, user.id, "recommendation.reviewed", recommendation.id, tid)
        recommendation.status = "confirmed"
        audit(session, user.id, "recommendation.confirmed", recommendation.id, tid)
        execution = ControlExecution(
            id=make_id("execution"),
            recommendation_id=recommendation.id,
            idempotency_key=f"quick-{alert.id}",
            execution_mode="simulation",
            status="completed",
        )
        session.add(execution)
        session.flush()
        audit(session, user.id, "control.simulated_execution", execution.id, tid)
        execution.dissolved_oxygen_mg_l = 6.3
        execution.note = "Quick response demo feedback"
        execution.status = "evaluated"
        recommendation.status = "evaluated"
        audit(session, user.id, "control.feedback_recorded", execution.id, tid)
        alert.status = "acknowledged"
        audit(session, user.id, "alert.acknowledged", alert.id, tid)
        alert.status = "resolved"
        alert.resolution = "Quick response demo resolution"
        audit(session, user.id, "alert.resolved", alert.id, tid)
        alert.status = "closed"
        audit(session, user.id, "alert.closed", alert.id, tid)
        session.commit()
        return alert_payload(alert)

    return r
