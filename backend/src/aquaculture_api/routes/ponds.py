from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aquaculture_api.deps import (
    ApiError,
    current_user,
    role_required,
    scoped_pond,
    session_dependency,
    trace_id,
)
from aquaculture_api.models import Device, Pond, User, WaterReading
from aquaculture_api.schemas import DeviceRequest
from aquaculture_api.services import audit, device_payload, pond_payload, reading_payload


def router() -> APIRouter:
    r = APIRouter(tags=["ponds"])

    @r.get("/api/v1/ponds")
    def ponds(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> list[dict[str, object]]:
        allowed = user.pond_scope.split(",")
        records = session.scalars(select(Pond).where(Pond.id.in_(allowed))).all()
        return [pond_payload(pond) for pond in records]

    @r.get("/api/v1/devices")
    def devices(
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> list[dict[str, object]]:
        role_required(user, {"technician", "admin"})
        records = session.scalars(
            select(Device).where(Device.pond_id.in_(user.pond_scope.split(",")))
        ).all()
        return [device_payload(record) for record in records]

    @r.post("/api/v1/devices")
    def create_device(
        body: DeviceRequest,
        request: Request,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        role_required(user, {"admin"})
        scoped_pond(session, user, body.pond_id)
        if session.get(Device, body.code) is not None:
            raise ApiError(409, "conflict", "Device code already exists")
        device = Device(
            code=body.code,
            pond_id=body.pond_id,
            device_type=body.device_type,
            source_mode="simulation",
            status="online",
        )
        session.add(device)
        audit(session, user.id, "device.created", device.code, trace_id(request))
        session.commit()
        return device_payload(device)

    @r.get("/api/v1/ponds/{pond_id}/readings")
    def readings(
        pond_id: str,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, object]:
        scoped_pond(session, user, pond_id)
        page = max(1, page)
        page_size = max(1, min(200, page_size))
        base_query = select(WaterReading).where(WaterReading.pond_id == pond_id)
        total = session.scalar(
            select(func.count()).select_from(WaterReading).where(WaterReading.pond_id == pond_id)
        )
        records = session.scalars(
            base_query.order_by(WaterReading.captured_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "items": [reading_payload(reading) for reading in records],
            "total": total or 0,
            "page": page,
            "page_size": page_size,
            "disclaimer": "外部官方观测仅用于水质展示及来源追溯，不代表目标鱼塘生产数据。",
        }

    @r.get("/api/v1/ponds/{pond_id}/readings/latest")
    def latest_reading(
        pond_id: str,
        user: Annotated[User, Depends(current_user)],
        session: Annotated[Session, Depends(session_dependency)],
    ) -> dict[str, object]:
        scoped_pond(session, user, pond_id)
        record = session.scalar(
            select(WaterReading)
            .where(WaterReading.pond_id == pond_id)
            .order_by(WaterReading.captured_at.desc())
        )
        if record is None:
            raise ApiError(404, "not_found", "No readings are available for this pond")
        return reading_payload(record)

    return r
