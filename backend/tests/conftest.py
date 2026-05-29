from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from aquaculture_api.config import Settings
from aquaculture_api.main import create_app
from aquaculture_api.security import sign_edge_payload

_env = Settings.from_environment()
_test_settings = Settings(
    app_env=_env.app_env,
    jwt_secret=_env.jwt_secret,
    edge_secret=_env.edge_secret,
    database_url="sqlite+pysqlite:///:memory:",
    seed=True,
    deepseek_api_key="",
    deepseek_base_url="https://api.deepseek.com",
)


@pytest.fixture()
def app() -> TestClient:
    return TestClient(create_app(_test_settings))


@pytest.fixture()
def client(app: TestClient) -> TestClient:
    return app


@pytest.fixture()
def farmer_headers(app: TestClient) -> dict[str, str]:
    response = app.post(
        "/api/v1/auth/login", json={"phone": "13800000001", "credential": "demo-246810"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def technician_headers(app: TestClient) -> dict[str, str]:
    response = app.post(
        "/api/v1/auth/login", json={"phone": "13800000002", "credential": "demo-246810"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def admin_headers(app: TestClient) -> dict[str, str]:
    response = app.post(
        "/api/v1/auth/login", json={"phone": "13800000003", "credential": "demo-246810"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_edge_headers(body: dict[str, object], nonce: str) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat()
    return {
        "X-Edge-Timestamp": timestamp,
        "X-Edge-Nonce": nonce,
        "X-Edge-Signature": sign_edge_payload(body, timestamp, nonce, _test_settings),
    }


def make_reading_event(
    event_id: str,
    pond_id: str = "pond-hz-01",
    quality: str = "valid",
    do_mg_l: float = 3.6,
    ph: float = 7.3,
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "device_code": "DO-HZ-001",
        "pond_id": pond_id,
        "captured_at": "2026-05-26T08:30:00Z",
        "dissolved_oxygen_mg_l": do_mg_l,
        "ph": ph,
        "quality_status": quality,
        "payload_checksum": "sha256:abc123",
        "source_mode": "simulation",
        "notification_scenario": "success",
    }


@pytest.fixture()
def seeded_alert(app: TestClient, farmer_headers: dict[str, str]) -> str:
    """Create a low-oxygen alert via demo injection and return its ID."""
    response = app.post(
        "/api/v1/demo/ponds/pond-hz-01/low-oxygen",
        json={"notification_scenario": "success"},
        headers=farmer_headers,
    )
    assert response.status_code == 200
    return response.json()["alert"]["id"]
