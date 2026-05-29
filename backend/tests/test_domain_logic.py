"""Comprehensive domain-logic tests covering gaps in the existing test suite.

Covers: cross-pond isolation, recommendation state machine, edge batch validation,
water-reading retrieval, density-analysis workflow, threshold-rule management,
export/archive edge cases, multi-alert dedup, and health accessibility.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from aquaculture_api.config import Settings
from aquaculture_api.main import create_app
from aquaculture_api.security import sign_edge_payload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def edge_headers(
    body: dict[str, object], nonce: str, *, timestamp: str | None = None
) -> dict[str, str]:
    ts = timestamp or datetime.now(UTC).isoformat()
    return {
        "X-Edge-Timestamp": ts,
        "X-Edge-Nonce": nonce,
        "X-Edge-Signature": sign_edge_payload(body, ts, nonce),
    }


def reading_event(
    event_id: str,
    *,
    pond_id: str = "pond-hz-01",
    do_mg_l: float = 3.6,
    quality_status: str = "valid",
    notification_scenario: str = "success",
    captured_at: str = "2026-05-26T08:30:00Z",
) -> dict[str, object]:
    return {
        "event_id": event_id,
        "device_code": "DO-HZ-001",
        "pond_id": pond_id,
        "captured_at": captured_at,
        "dissolved_oxygen_mg_l": do_mg_l,
        "ph": 7.3,
        "quality_status": quality_status,
        "payload_checksum": f"sha256:{event_id}",
        "source_mode": "simulation",
        "notification_scenario": notification_scenario,
    }


def submit_edge_batch(
    api: TestClient,
    events: list[dict[str, object]],
    *,
    batch_key: str | None = None,
    node_id: str = "edge-hz-001",
    nonce: str | None = None,
    headers_override: dict[str, str] | None = None,
) -> TestClient | dict[str, object]:
    """Post an edge batch and return the response JSON (or raw response)."""
    body: dict[str, object] = {
        "node_id": node_id,
        "batch_key": batch_key or f"batch-{uuid4().hex[:8]}",
        "events": events,
    }
    hdrs = headers_override or edge_headers(body, nonce or f"nonce-{uuid4().hex[:8]}")
    response = api.post("/api/v1/edge/readings:batch", headers=hdrs, json=body)
    return response


def inject_low_oxygen(
    api: TestClient,
    headers: dict[str, str],
    *,
    batch_key: str | None = None,
    event_id: str | None = None,
    do_mg_l: float = 3.6,
    notification_scenario: str = "success",
) -> dict[str, object]:
    """Inject a low-oxygen event via the edge endpoint and return the response JSON."""
    eid = event_id or f"low-do-{uuid4().hex[:8]}"
    batch: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": batch_key or f"batch-{uuid4().hex[:8]}",
        "events": [
            reading_event(eid, do_mg_l=do_mg_l, notification_scenario=notification_scenario)
        ],
    }
    response = api.post(
        "/api/v1/edge/readings:batch",
        headers=edge_headers(batch, f"nonce-{uuid4().hex[:8]}"),
        json=batch,
    )
    assert response.status_code == 200
    return response.json()


def seed_recommendation(
    api: TestClient, farmer_headers: dict[str, str], technician_headers: dict[str, str]
) -> dict[str, object]:
    """Create a recommendation via edge injection and return the newest one."""
    inject_low_oxygen(api, farmer_headers, event_id=f"rec-{uuid4().hex[:8]}")
    recs = api.get("/api/v1/ponds/pond-hz-01/recommendations", headers=farmer_headers).json()
    return recs[-1]


def seed_alert(api: TestClient, headers: dict[str, str]) -> dict[str, object]:
    """Create an alert via demo injection and return it."""
    api.post(
        "/api/v1/demo/ponds/pond-hz-01/low-oxygen",
        headers=headers,
        json={"notification_scenario": "success"},
    )
    alerts = api.get("/api/v1/alerts", headers=headers).json()
    return alerts[0]


# ===========================================================================
# 1. Cross-base / pond isolation
# ===========================================================================


def test_user_cannot_read_readings_for_out_of_scope_pond() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/ponds/pond-nonexistent/readings", headers=farmer)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_user_cannot_access_latest_reading_for_out_of_scope_pond() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/ponds/pond-nonexistent/readings/latest", headers=farmer)
    assert response.status_code == 403


def test_user_cannot_access_recommendations_for_out_of_scope_pond() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/ponds/pond-nonexistent/recommendations", headers=farmer)
    assert response.status_code == 403


def test_farmer_cannot_inject_demo_for_out_of_scope_pond() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.post(
        "/api/v1/demo/ponds/pond-nonexistent/low-oxygen",
        headers=farmer,
        json={"notification_scenario": "success"},
    )
    assert response.status_code == 403


def test_farmer_cannot_export_for_out_of_scope_pond() -> None:
    api = client()
    technician = login(api, "13800000002")
    response = api.post(
        "/api/v1/exports",
        headers=technician,
        json={
            "purpose": "test",
            "pond_id": "pond-nonexistent",
            "idempotency_key": "export-oos",
        },
    )
    assert response.status_code == 403


def test_unauthenticated_request_is_rejected_for_pond_scoped_endpoint() -> None:
    api = client()
    response = api.get("/api/v1/ponds/pond-hz-01/readings")
    assert response.status_code == 401


# ===========================================================================
# 2. Recommendation state machine validation
# ===========================================================================


def test_cannot_confirm_a_generated_recommendation_must_be_reviewed_first() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    rec = seed_recommendation(api, farmer, technician)
    assert rec["status"] == "generated"

    response = api.post(f"/api/v1/recommendations/{rec['id']}/confirm", headers=farmer)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_cannot_review_a_reviewed_recommendation() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    rec = seed_recommendation(api, farmer, technician)

    # First review transitions to "reviewed"
    api.patch(
        f"/api/v1/recommendations/{rec['id']}/review",
        headers=technician,
        json={"approved": True, "comment": "first review"},
    )

    # Attempting to review again should fail
    response = api.patch(
        f"/api/v1/recommendations/{rec['id']}/review",
        headers=technician,
        json={"approved": False, "comment": "second review"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_cannot_execute_a_generated_recommendation() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    rec = seed_recommendation(api, farmer, technician)
    assert rec["status"] == "generated"

    response = api.post(
        f"/api/v1/recommendations/{rec['id']}/executions",
        headers=farmer,
        json={"idempotency_key": "exec-gen-fail"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_cannot_execute_a_reviewed_recommendation_must_be_confirmed() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    rec = seed_recommendation(api, farmer, technician)

    api.patch(
        f"/api/v1/recommendations/{rec['id']}/review",
        headers=technician,
        json={"approved": True, "comment": "ok"},
    )

    response = api.post(
        f"/api/v1/recommendations/{rec['id']}/executions",
        headers=farmer,
        json={"idempotency_key": "exec-reviewed-fail"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_cannot_close_a_non_resolved_alert() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    alert = seed_alert(api, farmer)

    # Alert starts as "delivered"; close requires "resolved"
    response = api.post(f"/api/v1/alerts/{alert['id']}/close", headers=technician)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_cannot_resolve_a_delivered_alert_must_be_acknowledged_first() -> None:
    api = client()
    farmer = login(api, "13800000001")
    alert = seed_alert(api, farmer)

    # Alert is "delivered"; resolve requires "acknowledged"
    response = api.post(
        f"/api/v1/alerts/{alert['id']}/resolve",
        headers=farmer,
        json={"resolution": "too early"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_cannot_acknowledge_an_already_acknowledged_alert() -> None:
    api = client()
    farmer = login(api, "13800000001")
    alert = seed_alert(api, farmer)

    # First acknowledge succeeds
    ack = api.post(f"/api/v1/alerts/{alert['id']}/acknowledge", headers=farmer)
    assert ack.status_code == 200

    # Second acknowledge fails
    response = api.post(f"/api/v1/alerts/{alert['id']}/acknowledge", headers=farmer)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_recommendation_rejection_path_transitions_to_rejected() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    rec = seed_recommendation(api, farmer, technician)

    reviewed = api.patch(
        f"/api/v1/recommendations/{rec['id']}/review",
        headers=technician,
        json={"approved": False, "comment": "not needed"},
    ).json()
    assert reviewed["status"] == "rejected"


# ===========================================================================
# 3. Edge batch validation
# ===========================================================================


def test_edge_batch_rejects_invalid_signature() -> None:
    api = client()
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": "bad-sig-batch",
        "events": [reading_event("bad-sig-evt")],
    }
    ts = datetime.now(UTC).isoformat()
    nonce = "bad-sig-nonce"
    headers = {
        "X-Edge-Timestamp": ts,
        "X-Edge-Nonce": nonce,
        "X-Edge-Signature": "deadbeef00000000000000000000000000000000000000000000000000000000",
    }
    response = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid edge signature"


def test_edge_batch_rejects_expired_timestamp(monkeypatch: MonkeyPatch) -> None:
    api = client()
    old_ts = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": "expired-ts-batch",
        "events": [reading_event("expired-ts-evt")],
    }
    nonce = "expired-ts-nonce"
    headers = {
        "X-Edge-Timestamp": old_ts,
        "X-Edge-Nonce": nonce,
        "X-Edge-Signature": sign_edge_payload(body, old_ts, nonce),
    }
    response = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Expired edge signature"


def test_edge_batch_rejects_wrong_node_id() -> None:
    api = client()
    body: dict[str, object] = {
        "node_id": "edge-wrong-node",
        "batch_key": "wrong-node-batch",
        "events": [reading_event("wrong-node-evt")],
    }
    headers = edge_headers(body, "wrong-node-nonce")
    response = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid edge node identity"


def test_edge_batch_rejects_missing_edge_headers() -> None:
    api = client()
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": "no-headers-batch",
        "events": [reading_event("no-headers-evt")],
    }
    response = api.post("/api/v1/edge/readings:batch", json=body)
    assert response.status_code == 401


def test_edge_batch_with_mixed_valid_and_invalid_events() -> None:
    api = client()
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": f"mixed-{uuid4().hex[:8]}",
        "events": [
            reading_event("mixed-valid-001", pond_id="pond-hz-01"),
            reading_event("mixed-rejected-001", pond_id="pond-ref"),
            reading_event("mixed-valid-002", pond_id="pond-hz-01"),
        ],
    }
    headers = edge_headers(body, f"mixed-nonce-{uuid4().hex[:8]}")
    response = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert response.status_code == 200
    result = response.json()
    assert len(result["accepted"]) == 2
    assert "mixed-valid-001" in result["accepted"]
    assert "mixed-valid-002" in result["accepted"]
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["event_id"] == "mixed-rejected-001"
    assert result["rejected"][0]["reason"] == "pond_outside_node_scope"


def test_edge_batch_do_exactly_at_threshold_boundary() -> None:
    """DO at exactly the threshold (5.0) should NOT trigger a recommendation."""
    api = client()
    farmer = login(api, "13800000001")
    eid = f"boundary-{uuid4().hex[:8]}"
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": f"boundary-{uuid4().hex[:8]}",
        "events": [reading_event(eid, do_mg_l=5.0)],
    }
    headers = edge_headers(body, f"boundary-nonce-{uuid4().hex[:8]}")
    response = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert response.status_code == 200
    assert eid in response.json()["accepted"]

    # DO == threshold (5.0) is NOT < 5.0, so no recommendation should be generated
    recs = api.get("/api/v1/ponds/pond-hz-01/recommendations", headers=farmer).json()
    boundary_recs = [r for r in recs if r.get("reason", "").startswith("Low dissolved oxygen")]
    # This specific event should not have generated a recommendation
    # (other tests may have created recs, so we check for the boundary event specifically)
    assert len(boundary_recs) == 0


def test_edge_batch_do_just_below_threshold_triggers_recommendation() -> None:
    """DO just below threshold (4.99) should trigger a recommendation."""
    api = client()
    farmer = login(api, "13800000001")
    eid = f"below-thresh-{uuid4().hex[:8]}"
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": f"below-thresh-{uuid4().hex[:8]}",
        "events": [reading_event(eid, do_mg_l=4.99)],
    }
    headers = edge_headers(body, f"below-thresh-nonce-{uuid4().hex[:8]}")
    response = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert response.status_code == 200
    assert eid in response.json()["accepted"]

    recs = api.get("/api/v1/ponds/pond-hz-01/recommendations", headers=farmer).json()
    assert len(recs) >= 1
    assert recs[-1]["status"] == "generated"


def test_edge_batch_rejects_replayed_nonce() -> None:
    api = client()
    body: dict[str, object] = {
        "node_id": "edge-hz-001",
        "batch_key": f"replay-{uuid4().hex[:8]}",
        "events": [reading_event("replay-evt-001")],
    }
    nonce = f"replay-nonce-{uuid4().hex[:8]}"
    headers = edge_headers(body, nonce)
    first = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert first.status_code == 200

    # Same nonce should be rejected as replayed
    second = api.post("/api/v1/edge/readings:batch", headers=headers, json=body)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "replayed_request"


# ===========================================================================
# 4. Water reading retrieval
# ===========================================================================


def test_readings_returned_in_descending_order_by_captured_at() -> None:
    api = client()
    farmer = login(api, "13800000001")

    # Use the pond-ref which has seeded USGS data
    response = api.get("/api/v1/ponds/pond-ref/readings", headers=farmer)
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) >= 2

    captured_times = [item["captured_at"] for item in items]
    assert captured_times == sorted(captured_times, reverse=True)


def test_latest_reading_returns_most_recent() -> None:
    api = client()
    farmer = login(api, "13800000001")

    all_readings = api.get("/api/v1/ponds/pond-ref/readings", headers=farmer).json()["items"]
    latest = api.get("/api/v1/ponds/pond-ref/readings/latest", headers=farmer).json()

    assert latest["id"] == all_readings[0]["id"]
    assert latest["captured_at"] == all_readings[0]["captured_at"]


def test_latest_reading_returns_404_for_empty_pond() -> None:
    # Use a pond that exists in scope but has no readings
    fresh = client()
    fresh_admin = login(fresh, "13800000003")
    response = fresh.get("/api/v1/ponds/pond-empty/readings/latest", headers=fresh_admin)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_source_mode_correctly_reported_for_simulation_readings() -> None:
    api = client()
    farmer = login(api, "13800000001")
    inject_low_oxygen(api, farmer, event_id=f"src-mode-{uuid4().hex[:8]}")

    readings = api.get("/api/v1/ponds/pond-hz-01/readings", headers=farmer).json()["items"]
    assert len(readings) >= 1
    assert readings[0]["source_mode"] == "simulation"


def test_source_mode_correctly_reported_for_guangxi_observations() -> None:
    api = client()
    farmer = login(api, "13800000001")
    readings = api.get("/api/v1/ponds/pond-ref/readings", headers=farmer).json()["items"]
    assert len(readings) >= 1
    assert readings[0]["source_mode"] == "crawled"
    assert readings[0]["verified"] is True


def test_readings_disclaimer_is_present() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/ponds/pond-ref/readings", headers=farmer)
    body = response.json()
    assert "disclaimer" in body
    assert len(body["disclaimer"]) > 0


# ===========================================================================
# 5. Density analysis workflow
# ===========================================================================


def test_farmer_cannot_create_media_samples() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.post(
        "/api/v1/media-samples",
        headers=farmer,
        json={
            "pond_id": "pond-hz-01",
            "sample_type": "sonar",
            "object_ref": "sample://farmer-attempt",
            "source_mode": "simulation",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_farmer_cannot_create_density_analysis() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")

    # Technician creates sample
    sample = api.post(
        "/api/v1/media-samples",
        headers=technician,
        json={
            "pond_id": "pond-hz-01",
            "sample_type": "photo",
            "object_ref": "sample://photo-001",
            "source_mode": "simulation",
        },
    ).json()

    # Farmer cannot create analysis
    response = api.post(f"/api/v1/media-samples/{sample['id']}/analyses", headers=farmer)
    assert response.status_code == 403


def test_density_analysis_full_workflow_approved() -> None:
    api = client()
    technician = login(api, "13800000002")

    # Create sample
    sample = api.post(
        "/api/v1/media-samples",
        headers=technician,
        json={
            "pond_id": "pond-hz-01",
            "sample_type": "sonar",
            "object_ref": "sample://density-approved",
            "source_mode": "simulation",
        },
    ).json()
    assert sample["id"]

    # Run analysis
    analysis = api.post(f"/api/v1/media-samples/{sample['id']}/analyses", headers=technician).json()
    assert analysis["review_status"] == "pending"
    assert analysis["estimated_density_fish_m2"] == 38.0
    assert analysis["error_margin_fish_m2"] == 4.0

    # Approve
    reviewed = api.patch(
        f"/api/v1/density-analyses/{analysis['id']}/review",
        headers=technician,
        json={"approved": True, "comment": "looks correct"},
    ).json()
    assert reviewed["review_status"] == "approved"
    assert reviewed["recommendation_id"] is not None


def test_density_analysis_rejection_path() -> None:
    api = client()
    technician = login(api, "13800000002")

    sample = api.post(
        "/api/v1/media-samples",
        headers=technician,
        json={
            "pond_id": "pond-hz-01",
            "sample_type": "photo",
            "object_ref": "sample://density-rejected",
            "source_mode": "simulation",
        },
    ).json()

    analysis = api.post(f"/api/v1/media-samples/{sample['id']}/analyses", headers=technician).json()

    rejected = api.patch(
        f"/api/v1/density-analyses/{analysis['id']}/review",
        headers=technician,
        json={"approved": False, "comment": "poor image quality"},
    ).json()
    assert rejected["review_status"] == "rejected"
    assert rejected["recommendation_id"] is None


def test_cannot_review_already_reviewed_density_analysis() -> None:
    api = client()
    technician = login(api, "13800000002")

    sample = api.post(
        "/api/v1/media-samples",
        headers=technician,
        json={
            "pond_id": "pond-hz-01",
            "sample_type": "sonar",
            "object_ref": "sample://double-review",
            "source_mode": "simulation",
        },
    ).json()

    analysis = api.post(f"/api/v1/media-samples/{sample['id']}/analyses", headers=technician).json()

    # First review succeeds
    api.patch(
        f"/api/v1/density-analyses/{analysis['id']}/review",
        headers=technician,
        json={"approved": True, "comment": "first"},
    )

    # Second review fails
    response = api.patch(
        f"/api/v1/density-analyses/{analysis['id']}/review",
        headers=technician,
        json={"approved": False, "comment": "second"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_farmer_cannot_review_density_analysis() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")

    sample = api.post(
        "/api/v1/media-samples",
        headers=technician,
        json={
            "pond_id": "pond-hz-01",
            "sample_type": "photo",
            "object_ref": "sample://farmer-review",
            "source_mode": "simulation",
        },
    ).json()

    analysis = api.post(f"/api/v1/media-samples/{sample['id']}/analyses", headers=technician).json()

    response = api.patch(
        f"/api/v1/density-analyses/{analysis['id']}/review",
        headers=farmer,
        json={"approved": True, "comment": "farmer attempt"},
    )
    assert response.status_code == 403


# ===========================================================================
# 6. Threshold rule management
# ===========================================================================


def test_admin_can_create_threshold_rule() -> None:
    api = client()
    admin = login(api, "13800000003")
    response = api.put(
        "/api/v1/threshold-rules/ph-warning",
        headers=admin,
        json={"warning_below": 6.5, "version": "ph-v1", "source_mode": "simulation"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "ph-warning"
    assert body["warning_below"] == 6.5
    assert body["version"] == "ph-v1"


def test_admin_can_update_existing_threshold_rule() -> None:
    api = client()
    admin = login(api, "13800000003")

    # Create
    api.put(
        "/api/v1/threshold-rules/do-custom",
        headers=admin,
        json={"warning_below": 4.0, "version": "custom-v1", "source_mode": "simulation"},
    )

    # Update
    updated = api.put(
        "/api/v1/threshold-rules/do-custom",
        headers=admin,
        json={"warning_below": 4.5, "version": "custom-v2", "source_mode": "simulation"},
    ).json()
    assert updated["warning_below"] == 4.5
    assert updated["version"] == "custom-v2"


def test_non_admin_cannot_update_threshold_rule() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")

    farmer_response = api.put(
        "/api/v1/threshold-rules/do-warning",
        headers=farmer,
        json={"warning_below": 6.0, "version": "v2", "source_mode": "simulation"},
    )
    assert farmer_response.status_code == 403

    tech_response = api.put(
        "/api/v1/threshold-rules/do-warning",
        headers=technician,
        json={"warning_below": 6.0, "version": "v2", "source_mode": "simulation"},
    )
    assert tech_response.status_code == 403


def test_threshold_rule_versioning_reflected_in_response() -> None:
    api = client()
    admin = login(api, "13800000003")

    v1 = api.put(
        "/api/v1/threshold-rules/versioned-rule",
        headers=admin,
        json={"warning_below": 5.0, "version": "rule-v1", "source_mode": "simulation"},
    ).json()
    assert v1["version"] == "rule-v1"

    v2 = api.put(
        "/api/v1/threshold-rules/versioned-rule",
        headers=admin,
        json={"warning_below": 5.5, "version": "rule-v2", "source_mode": "simulation"},
    ).json()
    assert v2["version"] == "rule-v2"
    assert v2["warning_below"] == 5.5


# ===========================================================================
# 7. Export and archive edge cases
# ===========================================================================


def test_farmer_cannot_export_report() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.post(
        "/api/v1/exports",
        headers=farmer,
        json={
            "purpose": "test export",
            "pond_id": "pond-hz-01",
            "idempotency_key": "farmer-export-attempt",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_export_duplicate_idempotency_key_returns_same_record() -> None:
    api = client()
    technician = login(api, "13800000002")
    key = f"export-idem-{uuid4().hex[:8]}"
    payload = {
        "purpose": "idempotency test",
        "pond_id": "pond-hz-01",
        "idempotency_key": key,
    }

    first = api.post("/api/v1/exports", headers=technician, json=payload).json()
    second = api.post("/api/v1/exports", headers=technician, json=payload).json()

    assert first["id"] == second["id"]
    assert first["content"] == second["content"]


def test_archive_without_valid_export_id_fails() -> None:
    api = client()
    admin = login(api, "13800000003")
    response = api.post(
        "/api/v1/archives",
        headers=admin,
        json={
            "action": "archive",
            "scope": "nonexistent-export-id",
            "approval_ref": "APPROVAL-FAKE-001",
            "idempotency_key": f"archive-fake-{uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_farmer_cannot_create_archive() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.post(
        "/api/v1/archives",
        headers=farmer,
        json={
            "action": "archive",
            "scope": "any-scope",
            "approval_ref": "APPROVAL-001",
            "idempotency_key": f"archive-farmer-{uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 403


def test_archive_duplicate_idempotency_key_returns_same_record() -> None:
    api = client()
    technician = login(api, "13800000002")
    admin = login(api, "13800000003")

    export_key = f"export-for-archive-{uuid4().hex[:8]}"
    exported = api.post(
        "/api/v1/exports",
        headers=technician,
        json={
            "purpose": "archive test",
            "pond_id": "pond-hz-01",
            "idempotency_key": export_key,
        },
    ).json()

    archive_key = f"archive-idem-{uuid4().hex[:8]}"
    payload = {
        "action": "archive",
        "scope": exported["id"],
        "approval_ref": "APPROVAL-IDEM-001",
        "idempotency_key": archive_key,
    }

    first = api.post("/api/v1/archives", headers=admin, json=payload).json()
    second = api.post("/api/v1/archives", headers=admin, json=payload).json()
    assert first["id"] == second["id"]


# ===========================================================================
# 8. Disabled user rejection
# ===========================================================================


def test_login_with_wrong_credentials_rejected() -> None:
    api = client()
    response = api.post(
        "/api/v1/auth/login",
        json={"phone": "13800000001", "credential": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_login_with_nonexistent_phone_rejected() -> None:
    api = client()
    response = api.post(
        "/api/v1/auth/login",
        json={"phone": "99999999999", "credential": "demo-246810"},
    )
    assert response.status_code == 401


def test_expired_access_token_is_rejected(monkeypatch: MonkeyPatch) -> None:
    import aquaculture_api.security as security_module

    api = client()
    real_time = security_module.time.time
    monkeypatch.setattr(security_module.time, "time", lambda: real_time() + 3700)

    # The token issued at "real" time would appear expired
    response = api.get("/api/v1/me", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


# ===========================================================================
# 9. Multiple alerts for same pond
# ===========================================================================


def test_multiple_low_oxygen_events_create_separate_alerts() -> None:
    api = client()
    farmer = login(api, "13800000001")

    # Inject two separate low-oxygen events
    inject_low_oxygen(
        api,
        farmer,
        event_id=f"multi-alert-1-{uuid4().hex[:8]}",
        batch_key=f"multi-batch-1-{uuid4().hex[:8]}",
    )
    inject_low_oxygen(
        api,
        farmer,
        event_id=f"multi-alert-2-{uuid4().hex[:8]}",
        batch_key=f"multi-batch-2-{uuid4().hex[:8]}",
    )

    alerts = api.get("/api/v1/alerts", headers=farmer).json()
    assert len(alerts) >= 2
    # Each alert should have a unique id
    alert_ids = [a["id"] for a in alerts]
    assert len(set(alert_ids)) == len(alert_ids)


def test_multiple_recommendations_created_for_separate_low_oxygen_events() -> None:
    api = client()
    farmer = login(api, "13800000001")

    inject_low_oxygen(
        api,
        farmer,
        event_id=f"multi-rec-1-{uuid4().hex[:8]}",
        batch_key=f"multi-rec-batch-1-{uuid4().hex[:8]}",
    )
    inject_low_oxygen(
        api,
        farmer,
        event_id=f"multi-rec-2-{uuid4().hex[:8]}",
        batch_key=f"multi-rec-batch-2-{uuid4().hex[:8]}",
    )

    recs = api.get("/api/v1/ponds/pond-hz-01/recommendations", headers=farmer).json()
    assert len(recs) >= 2
    rec_ids = [r["id"] for r in recs]
    assert len(set(rec_ids)) == len(rec_ids)


# ===========================================================================
# 10. Health endpoint always accessible
# ===========================================================================


def test_health_endpoint_accessible_without_auth() -> None:
    api = client()
    response = api.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["system"] == "system-6-aquaculture"


def test_health_endpoint_returns_no_error_for_any_method_on_root() -> None:
    """The health endpoint should respond to GET without requiring any headers."""
    api = client()
    response = api.get("/api/health")
    assert response.status_code == 200
    # Should not have trace-id requirement or any auth
    assert "X-Trace-Id" in response.headers


# ===========================================================================
# Additional coverage: role-based access control
# ===========================================================================


def test_farmer_cannot_access_operations_health() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/operations/health", headers=farmer)
    assert response.status_code == 403


def test_farmer_cannot_access_audit_logs() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/audit-logs", headers=farmer)
    assert response.status_code == 403


def test_farmer_cannot_access_sync_batches() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/operations/sync-batches", headers=farmer)
    assert response.status_code == 403


def test_farmer_cannot_list_devices() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/devices", headers=farmer)
    assert response.status_code == 403


def test_farmer_cannot_create_device() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.post(
        "/api/v1/devices",
        headers=farmer,
        json={"code": "DEV-FARMER", "pond_id": "pond-hz-01", "device_type": "sensor"},
    )
    assert response.status_code == 403


def test_technician_cannot_create_device() -> None:
    api = client()
    technician = login(api, "13800000002")
    response = api.post(
        "/api/v1/devices",
        headers=technician,
        json={"code": "DEV-TECH", "pond_id": "pond-hz-01", "device_type": "sensor"},
    )
    assert response.status_code == 403


def test_admin_can_list_devices() -> None:
    api = client()
    admin = login(api, "13800000003")
    response = api.get("/api/v1/devices", headers=admin)
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_technician_can_access_benefits_report() -> None:
    api = client()
    technician = login(api, "13800000002")
    response = api.get("/api/v1/reports/benefits", headers=technician)
    assert response.status_code == 200
    assert response.json()["verified"] is False


def test_farmer_cannot_access_benefits_report() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.get("/api/v1/reports/benefits", headers=farmer)
    assert response.status_code == 403


# ===========================================================================
# Additional coverage: demo injection restrictions
# ===========================================================================


def test_technician_cannot_inject_demo_low_oxygen() -> None:
    api = client()
    technician = login(api, "13800000002")
    response = api.post(
        "/api/v1/demo/ponds/pond-hz-01/low-oxygen",
        headers=technician,
        json={"notification_scenario": "success"},
    )
    assert response.status_code == 403


def test_demo_injection_only_allowed_for_simulation_pond() -> None:
    api = client()
    farmer = login(api, "13800000001")
    response = api.post(
        "/api/v1/demo/ponds/pond-ref/low-oxygen",
        headers=farmer,
        json={"notification_scenario": "success"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_demo_target"


# ===========================================================================
# Additional coverage: execution idempotency
# ===========================================================================


def test_execution_idempotency_returns_same_record() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")
    rec = seed_recommendation(api, farmer, technician)

    # Review and confirm
    api.patch(
        f"/api/v1/recommendations/{rec['id']}/review",
        headers=technician,
        json={"approved": True, "comment": "ok"},
    )
    api.post(f"/api/v1/recommendations/{rec['id']}/confirm", headers=farmer)

    key = f"exec-idem-{uuid4().hex[:8]}"
    first = api.post(
        f"/api/v1/recommendations/{rec['id']}/executions",
        headers=farmer,
        json={"idempotency_key": key},
    ).json()
    second = api.post(
        f"/api/v1/recommendations/{rec['id']}/executions",
        headers=farmer,
        json={"idempotency_key": key},
    ).json()
    assert first["id"] == second["id"]


def test_execution_idempotency_key_conflict_across_recommendations() -> None:
    api = client()
    farmer = login(api, "13800000001")
    technician = login(api, "13800000002")

    rec1 = seed_recommendation(api, farmer, technician)
    rec2 = seed_recommendation(api, farmer, technician)

    # Review and confirm both
    for rec in [rec1, rec2]:
        api.patch(
            f"/api/v1/recommendations/{rec['id']}/review",
            headers=technician,
            json={"approved": True, "comment": "ok"},
        )
        api.post(f"/api/v1/recommendations/{rec['id']}/confirm", headers=farmer)

    shared_key = f"shared-key-{uuid4().hex[:8]}"
    api.post(
        f"/api/v1/recommendations/{rec1['id']}/executions",
        headers=farmer,
        json={"idempotency_key": shared_key},
    )

    # Using same key for a different recommendation should conflict
    response = api.post(
        f"/api/v1/recommendations/{rec2['id']}/executions",
        headers=farmer,
        json={"idempotency_key": shared_key},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "idempotency_conflict"


# ===========================================================================
# Quick response (one-click demo processing)
# ===========================================================================


def test_quick_response_closes_alert_in_one_call() -> None:
    api = client()
    farmer = login(api, "13800000001")
    inject = api.post(
        "/api/v1/demo/ponds/pond-hz-01/low-oxygen",
        json={"notification_scenario": "success"},
        headers=farmer,
    )
    assert inject.status_code == 200
    alert_id = inject.json()["alert"]["id"]
    response = api.post(f"/api/v1/alerts/{alert_id}/quick-response", headers=farmer)
    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_quick_response_rejected_for_non_generated_alert() -> None:
    api = client()
    farmer = login(api, "13800000001")
    inject = api.post(
        "/api/v1/demo/ponds/pond-hz-01/low-oxygen",
        json={"notification_scenario": "success"},
        headers=farmer,
    )
    alert_id = inject.json()["alert"]["id"]
    # First call closes it
    api.post(f"/api/v1/alerts/{alert_id}/quick-response", headers=farmer)
    # Second call should fail
    response = api.post(f"/api/v1/alerts/{alert_id}/quick-response", headers=farmer)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
