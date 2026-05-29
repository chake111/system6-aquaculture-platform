from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from aquaculture_api.deps import (
    ApiError,
    current_user,
    get_entity_or_404,
    require_state,
    role_required,
    scoped_pond,
    session_dependency,
    trace_id,
)
from aquaculture_api.models import ControlExecution, Recommendation, User
from aquaculture_api.schemas import ExecutionRequest, FeedbackRequest, RecommendationReviewRequest
from aquaculture_api.services import (
    audit,
    execution_payload,
    make_id,
    recommendation_payload,
)


def router() -> APIRouter:
    r = APIRouter(tags=["recommendations"])

    @r.get("/api/v1/ponds/{pond_id}/recommendations")
    def recommendations(
        pond_id: str,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> list[dict[str, object]]:
        scoped_pond(session, user, pond_id)
        records = session.scalars(
            select(Recommendation).where(Recommendation.pond_id == pond_id)
        ).all()
        return [recommendation_payload(record) for record in records]

    @r.patch("/api/v1/recommendations/{recommendation_id}/review")
    def review_recommendation(
        recommendation_id: str,
        body: RecommendationReviewRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"technician", "admin"})
        recommendation = get_entity_or_404(
            session, Recommendation, recommendation_id, "Recommendation"
        )
        scoped_pond(session, user, recommendation.pond_id)
        require_state(recommendation.status, {"generated"}, "Recommendation")
        recommendation.status = "reviewed" if body.approved else "rejected"
        recommendation.reviewed_by = user.id
        recommendation.review_note = body.comment
        audit(session, user.id, "recommendation.reviewed", recommendation.id, trace_id(request))
        session.commit()
        return recommendation_payload(recommendation)

    @r.post("/api/v1/recommendations/{recommendation_id}/confirm")
    def confirm_recommendation(
        recommendation_id: str,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"farmer", "technician"})
        recommendation = get_entity_or_404(
            session, Recommendation, recommendation_id, "Recommendation"
        )
        scoped_pond(session, user, recommendation.pond_id)
        require_state(recommendation.status, {"reviewed"}, "Recommendation")
        recommendation.status = "confirmed"
        audit(session, user.id, "recommendation.confirmed", recommendation.id, trace_id(request))
        session.commit()
        return recommendation_payload(recommendation)

    @r.post("/api/v1/recommendations/{recommendation_id}/executions")
    def execute_recommendation(
        recommendation_id: str,
        body: ExecutionRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"farmer", "technician"})
        recommendation = get_entity_or_404(
            session, Recommendation, recommendation_id, "Recommendation"
        )
        scoped_pond(session, user, recommendation.pond_id)
        existing = session.scalar(
            select(ControlExecution).where(ControlExecution.idempotency_key == body.idempotency_key)
        )
        if existing is not None:
            if existing.recommendation_id != recommendation.id:
                raise ApiError(
                    409, "idempotency_conflict", "Execution key belongs to another action"
                )
            return execution_payload(existing)
        if recommendation.status != "confirmed":
            raise ApiError(409, "invalid_state", "Recommendation must be confirmed first")
        execution = ControlExecution(
            id=make_id("execution"),
            recommendation_id=recommendation.id,
            idempotency_key=body.idempotency_key,
            execution_mode="simulation",
            status="completed",
        )
        session.add(execution)
        audit(session, user.id, "control.simulated_execution", execution.id, trace_id(request))
        session.commit()
        return execution_payload(execution)

    @r.patch("/api/v1/executions/{execution_id}/feedback")
    def execution_feedback(
        execution_id: str,
        body: FeedbackRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"farmer", "technician"})
        execution = get_entity_or_404(session, ControlExecution, execution_id, "Execution")
        recommendation = get_entity_or_404(
            session, Recommendation, execution.recommendation_id, "Recommendation"
        )
        scoped_pond(session, user, recommendation.pond_id)
        require_state(execution.status, {"completed"}, "Execution")
        execution.dissolved_oxygen_mg_l = body.dissolved_oxygen_mg_l
        execution.note = body.note
        execution.status = "evaluated"
        recommendation.status = "evaluated"
        audit(session, user.id, "control.feedback_recorded", execution.id, trace_id(request))
        session.commit()
        return execution_payload(execution)

    return r
