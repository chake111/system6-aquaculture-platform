import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from aquaculture_api.config import Settings
from aquaculture_api.models import (
    Base,
    BenefitMetric,
    Device,
    Pond,
    ThresholdRule,
    User,
    WaterReading,
)
from aquaculture_api.security import hash_credential


@dataclass(frozen=True)
class Store:
    engine: Engine
    sessions: sessionmaker[Session]


def create_store(settings: Settings | None = None) -> Store:
    if settings is None:
        settings = Settings(
            app_env="demonstration",
            jwt_secret="demo-only-jwt-secret-not-for-production",
            edge_secret="demo-only-edge-secret-not-for-production",
            database_url="sqlite+pysqlite:///:memory:",
            seed=True,
            deepseek_api_key="",
            deepseek_base_url="https://api.deepseek.com",
        )

    is_in_memory = ":memory:" in settings.database_url
    engine_kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    if is_in_memory:
        engine_kwargs["poolclass"] = StaticPool

    engine = create_engine(settings.database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)

    if settings.seed:
        _seed_if_empty(sessions)

    return Store(engine=engine, sessions=sessions)


def _seed_if_empty(sessions: sessionmaker[Session]) -> None:
    with sessions.begin() as session:
        existing = session.execute(select(User.id).limit(1)).scalar_one_or_none()
        if existing is not None:
            return
        _seed_application_data(session)


def _seed_application_data(session: Session) -> None:
    shared_scope = "pond-hz-01,pond-ref,pond-empty"
    credential_salt = "system6-demo-salt"
    credential_hash = hash_credential("demo-246810", credential_salt)
    session.add_all(
        [
            User(
                id="user-farmer",
                phone="13800000001",
                credential_hash=credential_hash,
                credential_salt=credential_salt,
                role="farmer",
                pond_scope=shared_scope,
                active=True,
            ),
            User(
                id="user-technician",
                phone="13800000002",
                credential_hash=credential_hash,
                credential_salt=credential_salt,
                role="technician",
                pond_scope=shared_scope,
                active=True,
            ),
            User(
                id="user-admin",
                phone="13800000003",
                credential_hash=credential_hash,
                credential_salt=credential_salt,
                role="admin",
                pond_scope=shared_scope,
                active=True,
            ),
            Pond(
                id="pond-hz-01",
                name="Huizhou demonstration pond",
                base_id="base-hz",
                source_mode="simulation",
            ),
            Pond(
                id="pond-ref",
                name="广西惠州鲈鱼养殖基地观测站",
                base_id="base-guangxi",
                source_mode="simulation",
            ),
            Pond(
                id="pond-empty",
                name="测试空塘口",
                base_id="base-hz",
                source_mode="simulation",
            ),
            Device(
                code="DO-HZ-001",
                pond_id="pond-hz-01",
                device_type="oxygen_sensor",
                source_mode="simulation",
                status="online",
            ),
            ThresholdRule(
                id="do-warning", warning_below=5.0, version="demo-v1", source_mode="simulation"
            ),
            BenefitMetric(
                id="metric-electricity",
                pond_id="pond-hz-01",
                label="增氧用电成本",
                value=128.4,
                unit="CNY",
                period="2026-05-demo",
                source_mode="simulation",
                verified=False,
            ),
            BenefitMetric(
                id="metric-survival",
                pond_id="pond-hz-01",
                label="成活率",
                value=92.1,
                unit="%",
                period="2026-05-demo",
                source_mode="simulation",
                verified=False,
            ),
            BenefitMetric(
                id="metric-yield",
                pond_id="pond-hz-01",
                label="亩产",
                value=420.0,
                unit="kg/mu",
                period="2026-05-demo",
                source_mode="simulation",
                verified=False,
            ),
            BenefitMetric(
                id="metric-feed",
                pond_id="pond-hz-01",
                label="饲料成本",
                value=2100.0,
                unit="CNY",
                period="2026-05-demo",
                source_mode="simulation",
                verified=False,
            ),
            BenefitMetric(
                id="metric-total",
                pond_id="pond-hz-01",
                label="综合养殖成本",
                value=3520.0,
                unit="CNY",
                period="2026-05-demo",
                source_mode="simulation",
                verified=False,
            ),
        ]
    )
    _seed_demo_readings(session)
    _seed_external_observations(session)


def _seed_demo_readings(session: Session) -> None:
    """Seed realistic water readings for the Huizhou demonstration pond."""
    from datetime import UTC, datetime, timedelta

    base_time = datetime.now(UTC)
    # Simulate 24 hours of readings, one every 2 hours
    demo_data = [
        (5.8, 7.20),
        (5.5, 7.18),
        (5.1, 7.15),
        (4.6, 7.12),
        (4.2, 7.10),
        (3.8, 7.08),
        (3.5, 7.05),
        (3.9, 7.10),
        (4.4, 7.15),
        (5.0, 7.20),
        (5.6, 7.22),
        (6.0, 7.25),
    ]
    for i, (do_val, ph_val) in enumerate(demo_data):
        ts = (base_time - timedelta(hours=24 - i * 2)).isoformat().replace("+00:00", "Z")
        session.add(
            WaterReading(
                id=f"demo-reading-{i + 1}",
                event_id=f"demo-event-{i + 1}",
                pond_id="pond-hz-01",
                captured_at=ts,
                dissolved_oxygen_mg_l=do_val,
                ph=ph_val,
                source_mode="simulation",
                verified=False,
                quality_status="valid",
                source_qualifiers="",
                source_url="",
            )
        )


def _seed_external_observations(session: Session) -> None:
    csv_path = Path(__file__).parents[2] / "data" / "guangxi_reference_readings.csv"
    if not csv_path.exists():
        return
    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        for sequence, row in enumerate(csv.DictReader(csv_file), start=1):
            if row["source_verified"] != "true":
                raise ValueError("Reference fixture must contain only verified observations")
            session.add(
                WaterReading(
                    id=f"reference-reading-{sequence}",
                    event_id=f"reference-event-{sequence}",
                    pond_id="pond-ref",
                    captured_at=row["datetime"],
                    dissolved_oxygen_mg_l=float(row["dissolved_oxygen_mg_l"]),
                    ph=float(row["ph"]),
                    source_mode=row["source_mode"],
                    verified=True,
                    quality_status=row["quality_status"],
                    source_qualifiers=row["source_qualifiers"],
                    source_url=row["source_url"],
                )
            )
