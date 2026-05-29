from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    phone: Mapped[str] = mapped_column(String, unique=True, index=True)
    credential_hash: Mapped[str] = mapped_column(String)
    credential_salt: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    pond_scope: Mapped[str] = mapped_column(String)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Pond(Base):
    __tablename__ = "ponds"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    base_id: Mapped[str] = mapped_column(String)
    source_mode: Mapped[str] = mapped_column(String)


class Device(Base):
    __tablename__ = "devices"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    pond_id: Mapped[str] = mapped_column(ForeignKey("ponds.id"), index=True)
    device_type: Mapped[str] = mapped_column(String)
    source_mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="online")


class WaterReading(Base):
    __tablename__ = "water_readings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    pond_id: Mapped[str] = mapped_column(ForeignKey("ponds.id"), index=True)
    captured_at: Mapped[str] = mapped_column(String, index=True)
    dissolved_oxygen_mg_l: Mapped[float] = mapped_column(Float)
    ph: Mapped[float] = mapped_column(Float)
    source_mode: Mapped[str] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean)
    quality_status: Mapped[str] = mapped_column(String, default="unreviewed")
    source_qualifiers: Mapped[str] = mapped_column(String, default="")
    source_url: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String, index=True)
    resource_id: Mapped[str] = mapped_column(String)
    trace_id: Mapped[str] = mapped_column(String, index=True)
    occurred_at: Mapped[str] = mapped_column(String)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    pond_id: Mapped[str] = mapped_column(ForeignKey("ponds.id"), index=True)
    source_mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    recommendation_type: Mapped[str] = mapped_column(String, default="aeration")
    risk_level: Mapped[str] = mapped_column(String, default="high")
    rule_version: Mapped[str] = mapped_column(String, default="demo-v1")
    proposed_minutes: Mapped[int] = mapped_column(default=30)
    weather_source: Mapped[str] = mapped_column(String, default="simulation")
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_mode: Mapped[str] = mapped_column(String, default="rule_engine")


class ControlExecution(Base):
    __tablename__ = "control_executions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id"))
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    execution_mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    dissolved_oxygen_mg_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    pond_id: Mapped[str] = mapped_column(ForeignKey("ponds.id"), index=True)
    source_mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    delivery_status: Mapped[str] = mapped_column(String)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(String, nullable=True)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), index=True)
    channel: Mapped[str] = mapped_column(String)
    provider_mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    attempts: Mapped[int] = mapped_column()
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class MediaSample(Base):
    __tablename__ = "media_samples"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    pond_id: Mapped[str] = mapped_column(ForeignKey("ponds.id"), index=True)
    sample_type: Mapped[str] = mapped_column(String)
    object_ref: Mapped[str] = mapped_column(String)
    source_mode: Mapped[str] = mapped_column(String)


class DensityAnalysis(Base):
    __tablename__ = "density_analyses"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sample_id: Mapped[str] = mapped_column(ForeignKey("media_samples.id"))
    source_mode: Mapped[str] = mapped_column(String)
    review_status: Mapped[str] = mapped_column(String)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_density_fish_m2: Mapped[float] = mapped_column(Float)
    error_margin_fish_m2: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    recommendation_id: Mapped[str | None] = mapped_column(String, nullable=True)


class ThresholdRule(Base):
    __tablename__ = "threshold_rules"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    warning_below: Mapped[float] = mapped_column(Float)
    version: Mapped[str] = mapped_column(String)
    source_mode: Mapped[str] = mapped_column(String)


class ExportRecord(Base):
    __tablename__ = "export_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String)
    pond_id: Mapped[str] = mapped_column(String)
    purpose: Mapped[str] = mapped_column(String)
    redacted: Mapped[bool] = mapped_column(Boolean)
    content: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    redaction_policy: Mapped[str] = mapped_column(String)
    expires_at: Mapped[str] = mapped_column(String)


class BenefitMetric(Base):
    __tablename__ = "benefit_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    pond_id: Mapped[str] = mapped_column(String)
    label: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String)
    period: Mapped[str] = mapped_column(String)
    source_mode: Mapped[str] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean)


class ArchiveRecord(Base):
    __tablename__ = "archive_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    scope: Mapped[str] = mapped_column(String)
    approval_ref: Mapped[str] = mapped_column(String)
    evidence_only: Mapped[bool] = mapped_column(Boolean)
    idempotency_key: Mapped[str] = mapped_column(String, unique=True)
    export_id: Mapped[str] = mapped_column(String)


class SyncBatch(Base):
    __tablename__ = "sync_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    node_id: Mapped[str] = mapped_column(String)
    batch_key: Mapped[str] = mapped_column(String, unique=True)
    accepted_count: Mapped[int] = mapped_column()
    duplicate_count: Mapped[int] = mapped_column()
    rejected_count: Mapped[int] = mapped_column(default=0)
    acknowledged_at: Mapped[str] = mapped_column(String)


class EdgeNonce(Base):
    __tablename__ = "edge_nonces"

    nonce: Mapped[str] = mapped_column(String, primary_key=True)
    seen_at: Mapped[str] = mapped_column(String)
