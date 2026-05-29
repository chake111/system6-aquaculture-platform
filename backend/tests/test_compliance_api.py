import base64
import json
from datetime import UTC, datetime, timedelta

import jwt.api_jwt
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from aquaculture_api.config import Settings
from aquaculture_api.main import create_app
from aquaculture_api.models import User
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


def client() -> TestClient:
    return TestClient(create_app(_test_settings))


def login(api: TestClient, phone: str = "13800000003") -> dict[str, str]:
    response = api.post("/api/v1/auth/login", json={"phone": phone, "credential": "demo-246810"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def signed_headers(body: dict[str, object], nonce: str) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat()
    return {
        "X-Edge-Timestamp": timestamp,
        "X-Edge-Nonce": nonce,
        "X-Edge-Signature": sign_edge_payload(body, timestamp, nonce),
    }


def event(event_id: str, pond_id: str = "pond-hz-01", quality: str = "valid") -> dict[str, object]:
    return {
        "event_id": event_id,
        "device_code": "DO-HZ-001",
        "pond_id": pond_id,
        "captured_at": "2026-05-26T08:30:00Z",
        "dissolved_oxygen_mg_l": 3.6,
        "ph": 7.3,
        "quality_status": quality,
        "payload_checksum": f"sha256:{event_id}",
        "source_mode": "simulation",
        "notification_scenario": "success",
    }


def test_auth_stores_no_plaintext_credentials_supports_refresh_and_audits_failure() -> None:
    api = client()
    assert not hasattr(User, "credential")

    failed = api.post(
        "/api/v1/auth/login", json={"phone": "13800000001", "credential": "wrong-value"}
    )
    assert failed.status_code == 401
    login_response = api.post(
        "/api/v1/auth/login", json={"phone": "13800000003", "credential": "demo-246810"}
    ).json()
    refreshed = api.post(
        "/api/v1/auth/refresh", json={"refresh_token": login_response["refresh_token"]}
    )
    assert refreshed.status_code == 200

    admin = {"Authorization": f"Bearer {login_response['access_token']}"}
    audits = api.get("/api/v1/audit-logs", headers=admin).json()
    assert any(item["action"] == "auth.login_failed" for item in audits)

    grant = api.post("/api/v1/auth/offline-grants", headers=admin).json()
    assert grant["expires_at"]
    assert grant["signed_grant"]


def test_offline_grant_signature_covers_authorized_scope_and_restricted_permissions() -> None:
    api = client()
    farmer = login(api, "13800000001")

    grant = api.post("/api/v1/auth/offline-grants", headers=farmer).json()
    parts = grant["signed_grant"].split(".")
    assert len(parts) == 3, "Expected standard 3-part JWT"
    encoded_payload = parts[1]
    padding = "=" * (-len(encoded_payload) % 4)
    payload = json.loads(base64.urlsafe_b64decode(encoded_payload + padding))

    assert payload["pond_scope"] == grant["pond_scope"]
    assert payload["permissions"] == ["read_cached_dashboard", "draft_alert_resolution"]


def test_expired_refresh_token_rejection_is_audited(monkeypatch: MonkeyPatch) -> None:
    api = client()
    auth = api.post(
        "/api/v1/auth/login", json={"phone": "13800000001", "credential": "demo-246810"}
    ).json()
    admin = login(api)

    # PyJWT uses datetime.now() for expiry checks; monkeypatch it to simulate future time
    real_datetime = jwt.api_jwt.datetime
    future = datetime.now(tz=UTC) + timedelta(hours=25)

    class _FakeDatetime:
        @staticmethod
        def now(**kwargs: object) -> datetime:
            return future

        def __getattr__(self, name: str) -> object:
            return getattr(real_datetime, name)

    monkeypatch.setattr(jwt.api_jwt, "datetime", _FakeDatetime())

    rejected = api.post("/api/v1/auth/refresh", json={"refresh_token": auth["refresh_token"]})

    monkeypatch.setattr(jwt.api_jwt, "datetime", real_datetime)
    assert rejected.status_code == 401
    audits = api.get("/api/v1/audit-logs", headers=admin).json()
    assert any(item["action"] == "auth.token_refresh_failed" for item in audits)


def test_edge_signature_replay_partial_rejection_and_invalid_quality_control_gate() -> None:
    api = client()
    admin = login(api)
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": "mixed-batch",
        "events": [event("invalid-quality", quality="invalid"), event("wrong-scope", "pond-ref")],
    }
    headers = signed_headers(body, "mixed-nonce")
    response = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert response.status_code == 200
    assert response.json()["accepted"] == ["invalid-quality"]
    assert response.json()["rejected"][0]["event_id"] == "wrong-scope"
    assert response.json()["acknowledged_at"]
    assert api.get("/api/v1/ponds/pond-hz-01/recommendations", headers=admin).json() == []

    replay = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert replay.status_code == 409
    sync = api.get("/api/v1/operations/sync-batches", headers=admin).json()
    assert sync[0]["rejected_count"] == 1

    retried = api.post(
        "/api/v1/edge/readings:batch",
        headers=signed_headers(body, "mixed-nonce-new-signature"),
        json=body,
    )
    assert retried.status_code == 200
    assert retried.json()["duplicates"] == ["invalid-quality"]


def test_failed_simulated_notification_preserves_manual_acknowledgement_path() -> None:
    api = client()
    farmer = login(api, "13800000001")
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": "failed-delivery-batch",
        "events": [
            {
                **event("failed-delivery"),
                "notification_scenario": "failed",
            }
        ],
    }
    assert (
        api.post(
            "/api/v1/edge/readings:batch",
            headers=signed_headers(body, "failed-delivery-nonce"),
            json=body,
        ).status_code
        == 200
    )
    alert = api.get("/api/v1/alerts", headers=farmer).json()[0]
    assert alert["delivery_status"] == "delivery_failed"
    assert all(item["attempts"] == 3 for item in alert["deliveries"])
    assert api.post(f"/api/v1/alerts/{alert['id']}/acknowledge", headers=farmer).status_code == 200


def test_export_archive_idempotency_and_evidence_link() -> None:
    api = client()
    technician = login(api, "13800000002")
    admin = login(api)
    request = {
        "purpose": "验收导出",
        "pond_id": "pond-hz-01",
        "idempotency_key": "export-repeat",
    }
    first = api.post("/api/v1/exports", headers=technician, json=request).json()
    second = api.post("/api/v1/exports", headers=technician, json=request).json()
    assert first["id"] == second["id"]

    archive_request = {
        "action": "archive",
        "scope": first["id"],
        "approval_ref": "DEMO-APPROVAL-002",
        "idempotency_key": "archive-repeat",
    }
    archived = api.post("/api/v1/archives", headers=admin, json=archive_request).json()
    repeated = api.post("/api/v1/archives", headers=admin, json=archive_request).json()
    assert archived["id"] == repeated["id"]
    assert archived["export_id"] == first["id"]


def test_device_master_data_is_scoped_and_admin_mutation_is_audited() -> None:
    api = client()
    technician = login(api, "13800000002")
    admin = login(api)
    listed = api.get("/api/v1/devices", headers=technician)
    assert listed.status_code == 200
    assert listed.json()[0]["pond_id"] == "pond-hz-01"
    assert (
        api.post(
            "/api/v1/devices",
            headers=technician,
            json={"code": "DO-NEW", "pond_id": "pond-hz-01", "device_type": "oxygen_sensor"},
        ).status_code
        == 403
    )
    created = api.post(
        "/api/v1/devices",
        headers=admin,
        json={"code": "DO-NEW", "pond_id": "pond-hz-01", "device_type": "oxygen_sensor"},
    )
    assert created.status_code == 200
    audits = api.get("/api/v1/audit-logs", headers=admin).json()
    assert any(item["action"] == "device.created" for item in audits)
