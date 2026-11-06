"""Baseline API foundation and health check tests."""

import pytest
from app.exceptions import SessionNotFoundError
from app.session import session_store


def test_health_check_success(client):
    """Verify GET /api/health returns 200 with approved data contract."""
    response = client.get("/api/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None

    data = payload["data"]
    assert data["status"] == "healthy"
    assert data["demo_area"] == "mysuru"
    assert isinstance(data["osm_data_loaded"], bool)
    assert isinstance(data["config_loaded"], bool)
    assert data["active_sessions"] == 0


def test_health_check_reflects_active_sessions(client):
    """Verify GET /api/health reflects active sessions in in-memory store."""
    session_id = session_store.create({"test": "data"})
    assert session_id is not None

    response = client.get("/api/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["data"]["active_sessions"] == 1


def test_standard_error_envelope_on_404(client):
    """Verify non-existent routes return the standard CivicFork error envelope."""
    response = client.get("/api/invalid-endpoint-test")
    assert response.status_code == 404

    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"]["code"] == "NOT_FOUND"
    assert "Not Found" in payload["error"]["message"]


def test_session_store_crud():
    """Verify in-memory SessionStore operations."""
    # Create
    sid = session_store.create()
    assert session_store.count() == 1

    # Get
    session = session_store.get(sid)
    assert session is not None
    assert session["session_id"] == sid
    assert "created_at" in session

    # Update
    updated = session_store.update(sid, {"plot": {"lat": 12.31, "lng": 76.65}})
    assert updated["plot"] == {"lat": 12.31, "lng": 76.65}

    # Delete
    deleted = session_store.delete(sid)
    assert deleted is True
    assert session_store.count() == 0

    # Updating non-existent session raises SessionNotFoundError
    with pytest.raises(SessionNotFoundError):
        session_store.update("non-existent-id", {})
