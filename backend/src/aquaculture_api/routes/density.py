from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from aquaculture_api.deps import (
    current_user,
    get_entity_or_404,
    require_state,
    role_required,
    scoped_pond,
    session_dependency,
    trace_id,
)
from aquaculture_api.models import DensityAnalysis, MediaSample, Recommendation, User
from aquaculture_api.schemas import DensityReviewRequest, MediaSampleRequest
from aquaculture_api.services import audit, density_payload, make_id, media_sample_payload


def router() -> APIRouter:
    r = APIRouter(tags=["density"])

    @r.post("/api/v1/media-samples")
    def media_sample(
        body: MediaSampleRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"technician", "admin"})
        scoped_pond(session, user, body.pond_id)
        sample = MediaSample(
            id=make_id("sample"),
            pond_id=body.pond_id,
            sample_type=body.sample_type,
            object_ref=body.object_ref,
            source_mode="simulation",
        )
        session.add(sample)
        audit(session, user.id, "density.sample_created", sample.id, trace_id(request))
        session.commit()
        return media_sample_payload(sample)

    @r.post("/api/v1/media-samples/{sample_id}/analyses")
    def create_density_analysis(
        sample_id: str,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"technician", "admin"})
        sample = get_entity_or_404(session, MediaSample, sample_id, "Media sample")
        scoped_pond(session, user, sample.pond_id)
        analysis = DensityAnalysis(
            id=make_id("analysis"),
            sample_id=sample.id,
            source_mode="simulation",
            review_status="pending",
            estimated_density_fish_m2=38.0,
            error_margin_fish_m2=4.0,
            model_version="density-demo-v1",
        )
        session.add(analysis)
        audit(session, user.id, "density.analysis_created", analysis.id, trace_id(request))
        session.commit()
        return density_payload(analysis)

    @r.patch("/api/v1/density-analyses/{analysis_id}/review")
    def review_density_analysis(
        analysis_id: str,
        body: DensityReviewRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"technician", "admin"})
        analysis = get_entity_or_404(session, DensityAnalysis, analysis_id, "Density analysis")
        sample = get_entity_or_404(session, MediaSample, analysis.sample_id, "Media sample")
        scoped_pond(session, user, sample.pond_id)
        require_state(analysis.review_status, {"pending"}, "Density analysis")
        analysis.review_status = "approved" if body.approved else "rejected"
        analysis.comment = body.comment
        analysis.reviewer_id = user.id
        if body.approved:
            recommendation = Recommendation(
                id=make_id("recommendation"),
                pond_id=sample.pond_id,
                source_mode="simulation",
                status="reviewed",
                reason="Reviewed demonstration density result; reassess stocking plan",
                recommendation_type="density_adjustment",
                risk_level="medium",
                rule_version="density-demo-v1",
                proposed_minutes=0,
                weather_source="not_applicable",
                reviewed_by=user.id,
                review_note=body.comment,
            )
            session.add(recommendation)
            analysis.recommendation_id = recommendation.id
        audit(session, user.id, "density.analysis_reviewed", analysis.id, trace_id(request))
        session.commit()
        return density_payload(analysis)

    return r
