from datetime import UTC, datetime

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


def client() -> TestClient:
    return TestClient(create_app(_test_settings))


def login(api: TestClient, phone: str) -> dict[str, str]:
    response = api.post("/api/v1/auth/login", json={"phone": phone, "credential": "demo-246810"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def edge_headers(body: dict[str, object], nonce: str) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat()
    return {
        "X-Edge-Timestamp": timestamp,
        "X-Edge-Nonce": nonce,
        "X-Edge-Signature": sign_edge_payload(body, timestamp, nonce),
    }


def reading_event(
    event_id: str,
    *,
    pond_id: str = "pond-hz-01",
    quality_status: str = "valid",
    notification_scenario: str = "success",
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "device_code": "DO-HZ-001",
        "pond_id": pond_id,
        "captured_at": "2026-05-26T08:30:00Z",
        "dissolved_oxygen_mg_l": 3.9,
        "ph": 7.3,
        "quality_status": quality_status,
        "payload_checksum": f"sha256:{event_id}",
        "source_mode": "simulation",
        "notification_scenario": notification_scenario,
    }


def test_auth_role_scope_offline_grant_and_audit() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    admin = login(api, "13800000003")

    anonymous = api.get("/api/v1/ponds")
    assert anonymous.status_code == 401
    assert anonymous.json()["error"]["code"] == "unauthorized"
    assert anonymous.headers["X-Trace-Id"]

    assert api.get("/api/v1/me", headers=farmer).json()["role"] == "farmer"
    assert api.get("/api/v1/me", headers=technician).json()["role"] == "technician"
    assert api.get("/api/v1/me", headers=admin).json()["role"] == "admin"

    pond_ids = {item["id"] for item in api.get("/api/v1/ponds", headers=farmer).json()}
    assert pond_ids == {"pond-hz-01", "pond-ref", "pond-empty"}

    grant = api.post("/api/v1/auth/offline-grants", headers=farmer).json()
    assert grant["max_days"] == 7
    assert grant["permissions"] == ["read_cached_dashboard", "draft_alert_resolution"]
    assert grant["expires_at"]
    assert grant["signed_grant"]
    assert "export" not in grant["permissions"]

    assert api.get("/api/v1/operations/health", headers=farmer).status_code == 403
    audit = api.get("/api/v1/audit-logs", headers=admin)
    assert audit.status_code == 200
    assert any(event["action"] == "auth.login_succeeded" for event in audit.json())


def test_official_reference_monitoring_readings_are_traceable() -> None:
    api = client()
    headers = login(api, "13800000002")

    history = api.get("/api/v1/ponds/pond-ref/readings", headers=headers)
    assert history.status_code == 200
    body = history.json()
    assert len(body["items"]) >= 20
    assert body["items"][0]["source_mode"] == "crawled"
    assert body["items"][0]["verified"] is True
    assert body["items"][0]["quality_status"] == "valid"
    assert body["items"][0]["source_qualifiers"] == "C"
    assert "广西" in body["items"][0]["source_url"]


def test_simulated_low_oxygen_closes_reviewed_recommendation_and_alert_loop() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    batch: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": "low-do-batch",
        "events": [reading_event("sim-low-do-001", notification_scenario="retry_success")],
    }
    edge_response = api.post(
        "/api/v1/edge/readings:batch",
        headers=edge_headers(batch, "low-do-nonce-1"),
        json=batch,
    )
    assert edge_response.status_code == 200
    assert edge_response.json()["accepted"] == ["sim-low-do-001"]
    assert edge_response.json()["acknowledged_at"]

    duplicate: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": "low-do-batch-retry",
        "events": [reading_event("sim-low-do-001")],
    }
    duplicate_response = api.post(
        "/api/v1/edge/readings:batch",
        headers=edge_headers(duplicate, "low-do-nonce-2"),
        json=duplicate,
    )
    assert duplicate_response.json()["duplicates"] == ["sim-low-do-001"]

    recommendation = api.get("/api/v1/ponds/pond-hz-01/recommendations", headers=farmer).json()[0]
    assert recommendation["status"] == "generated"
    assert recommendation["rule_version"] == "demo-v1"
    assert (
        api.post(
            f"/api/v1/recommendations/{recommendation['id']}/confirm", headers=farmer
        ).status_code
        == 409
    )
    reviewed = api.patch(
        f"/api/v1/recommendations/{recommendation['id']}/review",
        headers=technician,
        json={"approved": True, "comment": "模拟阈值复核"},
    ).json()
    assert reviewed["status"] == "reviewed"
    confirmed = api.post(
        f"/api/v1/recommendations/{recommendation['id']}/confirm", headers=farmer
    ).json()
    assert confirmed["status"] == "confirmed"
    execution = api.post(
        f"/api/v1/recommendations/{recommendation['id']}/executions",
        headers=farmer,
        json={"idempotency_key": "execute-low-do-001"},
    ).json()
    assert execution["execution_mode"] == "simulation"
    feedback = api.patch(
        f"/api/v1/executions/{execution['id']}/feedback",
        headers=farmer,
        json={"dissolved_oxygen_mg_l": 6.3, "note": "现场演示反馈"},
    ).json()
    assert feedback["status"] == "evaluated"
    updated_recommendation = api.get(
        "/api/v1/ponds/pond-hz-01/recommendations", headers=farmer
    ).json()[0]
    assert updated_recommendation["status"] == "evaluated"

    alert = api.get("/api/v1/alerts", headers=farmer).json()[0]
    assert alert["delivery_status"] == "delivered"
    assert alert["recommendation_id"] == recommendation["id"]
    assert {item["channel"] for item in alert["deliveries"]} == {"sms", "dingtalk"}
    assert all(item["provider_mode"] == "simulation" for item in alert["deliveries"])
    assert any(item["attempts"] == 2 for item in alert["deliveries"])
    assert (
        api.post(f"/api/v1/alerts/{alert['id']}/acknowledge", headers=farmer).json()["status"]
        == "acknowledged"
    )
    assert (
        api.post(
            f"/api/v1/alerts/{alert['id']}/resolve",
            headers=farmer,
            json={"resolution": "模拟增氧完成"},
        ).json()["status"]
        == "resolved"
    )
    assert (
        api.post(f"/api/v1/alerts/{alert['id']}/close", headers=technician).json()["status"]
        == "closed"
    )


def test_authenticated_demo_injection_drives_server_side_simulation_workflow() -> None:
    api = client()
    farmer = login(api, "13800000001")
    admin = login(api, "13800000003")

    injected = api.post(
        "/api/v1/demo/ponds/pond-hz-01/low-oxygen",
        headers=farmer,
        json={"notification_scenario": "retry_success"},
    )
    assert injected.status_code == 200
    payload = injected.json()
    assert payload["reading"]["source_mode"] == "simulation"
    assert payload["recommendation"]["status"] == "generated"
    assert payload["alert"]["source_mode"] == "simulation"
    assert {delivery["channel"] for delivery in payload["alert"]["deliveries"]} == {
        "sms",
        "dingtalk",
    }

    recommendations = api.get("/api/v1/ponds/pond-hz-01/recommendations", headers=farmer).json()
    assert recommendations[0]["id"] == payload["recommendation"]["id"]
    audits = api.get("/api/v1/audit-logs", headers=admin).json()
    assert any(event["action"] == "demo.low_oxygen_injected" for event in audits)


def test_density_reports_exports_and_admin_operations_are_guarded() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    admin = login(api, "13800000003")

    sample = api.post(
        "/api/v1/media-samples",
        headers=technician,
        json={
            "pond_id": "pond-hz-01",
            "sample_type": "sonar",
            "object_ref": "sample://sonar-demo-01",
            "source_mode": "simulation",
        },
    ).json()
    analysis = api.post(f"/api/v1/media-samples/{sample['id']}/analyses", headers=technician).json()
    assert analysis["review_status"] == "pending"
    assert analysis["estimated_density_fish_m2"] == 38.0
    assert analysis["error_margin_fish_m2"] == 4.0
    assert analysis["model_version"] == "density-demo-v1"
    reviewed = api.patch(
        f"/api/v1/density-analyses/{analysis['id']}/review",
        headers=technician,
        json={"approved": True, "comment": "演示样本复核"},
    ).json()
    assert reviewed["review_status"] == "approved"
    assert reviewed["recommendation_id"]

    assert api.get("/api/v1/reports/benefits", headers=farmer).status_code == 403
    report = api.get("/api/v1/reports/benefits", headers=technician).json()
    assert report["verified"] is False
    assert "演示" in report["disclaimer"]
    assert len(report["metrics"]) == 5
    assert all(metric["source_mode"] == "simulation" for metric in report["metrics"])

    exported = api.post(
        "/api/v1/exports",
        headers=technician,
        json={
            "purpose": "课程验收",
            "pond_id": "pond-hz-01",
            "idempotency_key": "export-demo-1",
        },
    ).json()
    assert exported["redacted"] is True
    assert exported["redaction_policy"] == "mask-identifiers-v1"
    assert exported["expires_at"]

    health = api.get("/api/v1/operations/health", headers=admin).json()
    assert health["environment"] == "demonstration"
    assert health["crawled_observation_count"] >= 20
    assert health["components"]["sync"]["retention_days"] == 7
    assert health["components"]["notifications"]["provider_mode"] == "simulation"

    missing_approval = api.post(
        "/api/v1/archives", headers=admin, json={"action": "archive", "scope": exported["id"]}
    )
    assert missing_approval.status_code == 422
    archive = api.post(
        "/api/v1/archives",
        headers=admin,
        json={
            "action": "archive",
            "scope": exported["id"],
            "approval_ref": "DEMO-APPROVAL-001",
            "idempotency_key": "archive-demo-1",
        },
    ).json()
    assert archive["evidence_only"] is True
    assert archive["export_id"] == exported["id"]
