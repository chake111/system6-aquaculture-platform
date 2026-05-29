from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    phone: str
    credential: str


class RefreshRequest(BaseModel):
    refresh_token: str


class DeviceRequest(BaseModel):
    code: str
    pond_id: str
    device_type: str


class EdgeReadingRequest(BaseModel):
    event_id: str
    device_code: str
    pond_id: str
    captured_at: str
    dissolved_oxygen_mg_l: float = Field(ge=0, le=30)
    ph: float = Field(ge=0, le=14)
    quality_status: Literal["valid", "invalid"]
    payload_checksum: str
    source_mode: Literal["simulation", "auto"]
    notification_scenario: Literal["success", "retry_success", "failed"] = "success"


class EdgeBatchRequest(BaseModel):
    node_id: str
    batch_key: str
    events: list[EdgeReadingRequest]


class InjectionRequest(BaseModel):
    notification_scenario: Literal["success", "retry_success", "failed"] = "retry_success"


class ExecutionRequest(BaseModel):
    idempotency_key: str


class FeedbackRequest(BaseModel):
    dissolved_oxygen_mg_l: float
    note: str


class ResolutionRequest(BaseModel):
    resolution: str


class MediaSampleRequest(BaseModel):
    pond_id: str
    sample_type: str
    object_ref: str
    source_mode: Literal["simulation", "auto"]


class DensityReviewRequest(BaseModel):
    approved: bool
    comment: str


class RecommendationReviewRequest(BaseModel):
    approved: bool
    comment: str


class ExportRequest(BaseModel):
    purpose: str
    pond_id: str
    idempotency_key: str


class ThresholdRuleRequest(BaseModel):
    warning_below: float
    version: str
    source_mode: Literal["simulation", "auto"]


class ArchiveRequest(BaseModel):
    action: Literal["archive", "destroy"]
    scope: str
    approval_ref: str = Field(min_length=6)
    idempotency_key: str
