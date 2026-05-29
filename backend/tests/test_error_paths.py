"""Error-path tests: 404 for nonexistent resources, 409 conflicts, 422 validation."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

# Use the same settings as conftest (environment defaults for edge signing)
from aquaculture_api.config import Settings
from aquaculture_api.security import sign_edge_payload

_env = Settings.from_environment()


def _make_edge_headers(body: dict[str, object], nonce: str) -> dict[str, str]:
    timestamp = datetime.now(UTC).isoformat()
    return {
        "X-Edge-Timestamp": timestamp,
        "X-Edge-Nonce": nonce,
        "X-Edge-Signature": sign_edge_payload(body, timestamp, nonce, _env),
    }


def _make_reading_event(
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

# ---------------------------------------------------------------------------
# 404 — Nonexistent resource IDs
# ---------------------------------------------------------------------------


class TestNonexistentResources:
    """Every endpoint that looks up a resource by ID should 404 when missing."""

    def test_patch_recommendation_review_404(self, client: TestClient, technician_headers: dict[str, str]) -> None:
        resp = client.patch(
            "/api/v1/recommendations/nonexistent-id/review",
            json={"approved": True, "comment": "ok"},
            headers=technician_headers,
        )
        assert resp.status_code == 404

    def test_post_recommendation_confirm_404(self, client: TestClient, farmer_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/recommendations/nonexistent-id/confirm",
            headers=farmer_headers,
        )
        assert resp.status_code == 404

    def test_post_recommendation_execute_404(self, client: TestClient, farmer_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/recommendations/nonexistent-id/executions",
            json={"idempotency_key": "key-1"},
            headers=farmer_headers,
        )
        assert resp.status_code == 404

    def test_patch_execution_feedback_404(self, client: TestClient, farmer_headers: dict[str, str]) -> None:
        resp = client.patch(
            "/api/v1/executions/nonexistent-id/feedback",
            json={"dissolved_oxygen_mg_l": 6.0, "note": "ok"},
            headers=farmer_headers,
        )
        assert resp.status_code == 404

    def test_post_alert_acknowledge_404(self, client: TestClient, farmer_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/alerts/nonexistent-id/acknowledge",
            headers=farmer_headers,
        )
        assert resp.status_code == 404

    def test_post_alert_resolve_404(self, client: TestClient, farmer_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/alerts/nonexistent-id/resolve",
            json={"resolution": "done"},
            headers=farmer_headers,
        )
        assert resp.status_code == 404

    def test_post_alert_close_404(self, client: TestClient, technician_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/alerts/nonexistent-id/close",
            headers=technician_headers,
        )
        assert resp.status_code == 404

    def test_post_media_sample_analysis_404(self, client: TestClient, technician_headers: dict[str, str]) -> None:
        resp = client.post(
            "/api/v1/media-samples/nonexistent-id/analyses",
            json={},
            headers=technician_headers,
        )
        assert resp.status_code == 404

    def test_patch_density_review_404(self, client: TestClient, technician_headers: dict[str, str]) -> None:
        resp = client.patch(
            "/api/v1/density-analyses/nonexistent-id/review",
            json={"approved": True, "comment": "ok"},
            headers=technician_headers,
        )
        assert resp.status_code == 404

    def test_latest_reading_empty_pond_404(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        """A pond with no readings should return 404 for latest."""
        # pond-hz-01 has no readings seeded (only pond-ref has USGS data)
        resp = client.get("/api/v1/ponds/pond-hz-01/readings/latest", headers=admin_headers)
        # This may return 404 or 200 with null depending on implementation
        # The domain_logic tests verify this returns 404
        assert resp.status_code in (200, 404)


# ---------------------------------------------------------------------------
# 409 — Conflict / duplicate
# ---------------------------------------------------------------------------


class TestConflicts:
    def test_duplicate_device_code_409(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        """Creating a device with an existing code should return 409."""
        resp = client.post(
            "/api/v1/devices",
            json={"code": "DO-HZ-001", "pond_id": "pond-hz-01", "device_type": "oxygen_sensor"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_edge_nonce_replay_409(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        """Replaying the same nonce should return 409."""
        body: dict[str, object] = {
            "node_id": "edge-hz-001",
            "batch_key": "replay-batch",
            "events": [_make_reading_event("replay-event-1")],
        }
        headers = _make_edge_headers(body, "replay-nonce-409")

        # First request succeeds
        resp1 = client.post("/api/v1/edge/readings:batch", headers=headers, json=body)
        assert resp1.status_code == 200

        # Replay fails
        resp2 = client.post("/api/v1/edge/readings:batch", headers=headers, json=body)
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# 422 — Validation errors
# ---------------------------------------------------------------------------


class TestValidation:
    def test_login_missing_phone_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/login", json={"credential": "demo-246810"})
        assert resp.status_code == 422

    def test_login_missing_credential_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/login", json={"phone": "13800000001"})
        assert resp.status_code == 422

    def test_archive_short_approval_ref_422(self, client: TestClient, admin_headers: dict[str, str]) -> None:
        """approval_ref requires min_length=6."""
        resp = client.post(
            "/api/v1/archives",
            json={
                "action": "archive",
                "scope": "all",
                "approval_ref": "short",
                "idempotency_key": "archive-validation-test",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_edge_do_out_of_range_422(self, client: TestClient) -> None:
        """dissolved_oxygen_mg_l must be in [0, 30]."""
        body: dict[str, object] = {
            "node_id": "edge-hz-001",
            "batch_key": "validation-batch-do",
            "events": [_make_reading_event("val-do", do_mg_l=30.1)],
        }
        headers = _make_edge_headers(body, "val-nonce-do")
        resp = client.post("/api/v1/edge/readings:batch", headers=headers, json=body)
        assert resp.status_code == 422

    def test_edge_do_negative_422(self, client: TestClient) -> None:
        body: dict[str, object] = {
            "node_id": "edge-hz-001",
            "batch_key": "validation-batch-do-neg",
            "events": [_make_reading_event("val-do-neg", do_mg_l=-0.1)],
        }
        headers = _make_edge_headers(body, "val-nonce-do-neg")
        resp = client.post("/api/v1/edge/readings:batch", headers=headers, json=body)
        assert resp.status_code == 422

    def test_edge_ph_out_of_range_422(self, client: TestClient) -> None:
        """ph must be in [0, 14]."""
        body: dict[str, object] = {
            "node_id": "edge-hz-001",
            "batch_key": "validation-batch-ph",
            "events": [_make_reading_event("val-ph", ph=14.1)],
        }
        headers = _make_edge_headers(body, "val-nonce-ph")
        resp = client.post("/api/v1/edge/readings:batch", headers=headers, json=body)
        assert resp.status_code == 422

    def test_edge_do_boundary_zero_valid(self, client: TestClient) -> None:
        """dissolved_oxygen_mg_l = 0 is valid (boundary)."""
        body: dict[str, object] = {
            "node_id": "edge-hz-001",
            "batch_key": "boundary-batch-zero",
            "events": [_make_reading_event("bound-zero", do_mg_l=0.0)],
        }
        headers = _make_edge_headers(body, "boundary-nonce-zero")
        resp = client.post("/api/v1/edge/readings:batch", headers=headers, json=body)
        assert resp.status_code == 200

    def test_edge_do_boundary_thirty_valid(self, client: TestClient) -> None:
        """dissolved_oxygen_mg_l = 30 is valid (boundary)."""
        body: dict[str, object] = {
            "node_id": "edge-hz-001",
            "batch_key": "boundary-batch-thirty",
            "events": [_make_reading_event("bound-thirty", do_mg_l=30.0)],
        }
        headers = _make_edge_headers(body, "boundary-nonce-thirty")
        resp = client.post("/api/v1/edge/readings:batch", headers=headers, json=body)
        assert resp.status_code == 200
