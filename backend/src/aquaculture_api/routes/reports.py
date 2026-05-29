from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from aquaculture_api.deps import (
    current_user,
    get_entity_or_404,
    role_required,
    scoped_pond,
    session_dependency,
    trace_id,
)
from aquaculture_api.models import ArchiveRecord, BenefitMetric, ExportRecord, User
from aquaculture_api.schemas import ArchiveRequest, ExportRequest
from aquaculture_api.services import audit, make_id, metric_payload


def router() -> APIRouter:
    r = APIRouter(tags=["reports"])

    @r.get("/api/v1/reports/benefits")
    def benefits_report(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"technician", "admin"})
        records = session.scalars(
            select(BenefitMetric).where(BenefitMetric.pond_id.in_(user.pond_scope.split(",")))
        ).all()
        return {
            "verified": False,
            "source_mode": "simulation",
            "disclaimer": "演示评估数据未经真实养殖周期验证，不表示已实现生产收益。",
            "metrics": [metric_payload(metric) for metric in records],
        }

    @r.post("/api/v1/exports")
    def export_report(
        body: ExportRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"technician", "admin"})
        scoped_pond(session, user, body.pond_id)
        existing = session.scalar(
            select(ExportRecord).where(ExportRecord.idempotency_key == body.idempotency_key)
        )
        if existing is not None:
            return _export_payload(existing)
        content = "Redacted report; data reflects operational records for the specified period."
        record = ExportRecord(
            id=make_id("export"),
            actor_id=user.id,
            pond_id=body.pond_id,
            purpose=body.purpose,
            redacted=True,
            content=content,
            idempotency_key=body.idempotency_key,
            redaction_policy="mask-identifiers-v1",
            expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
        )
        session.add(record)
        audit(session, user.id, "report.export_created", record.id, trace_id(request))
        session.commit()
        return _export_payload(record)

    @r.post("/api/v1/archives")
    def create_archive(
        body: ArchiveRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"admin"})
        existing = session.scalar(
            select(ArchiveRecord).where(ArchiveRecord.idempotency_key == body.idempotency_key)
        )
        if existing is not None:
            return _archive_payload(existing)
        export = get_entity_or_404(session, ExportRecord, body.scope, "Export record")
        archive = ArchiveRecord(
            id=make_id("archive"),
            actor_id=user.id,
            action=body.action,
            scope=body.scope,
            approval_ref=body.approval_ref,
            evidence_only=True,
            idempotency_key=body.idempotency_key,
            export_id=export.id,
        )
        session.add(archive)
        audit(session, user.id, "archive.evidence_recorded", archive.id, trace_id(request))
        session.commit()
        return _archive_payload(archive)

    return r


def _export_payload(record: ExportRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "redacted": record.redacted,
        "content": record.content,
        "redaction_policy": record.redaction_policy,
        "expires_at": record.expires_at,
    }


def _archive_payload(record: ArchiveRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "evidence_only": record.evidence_only,
        "export_id": record.export_id,
        "approval_ref": record.approval_ref,
    }
