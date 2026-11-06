"""Tests for the deterministic Counterfactual Engine and /api/counterfactual endpoint."""

import uuid
import pytest
from app.models.domain import SessionData
from app.services.counterfactual_engine import get_counterfactual_engine
from app.session import session_store

MYSURU_VALID_PLOT = {
    "lat": 12.3100,
    "lng": 76.6500,
    "radius_m": 2000,
    "area_sqm": 3500.0,
    "label": "Counterfactual Test Plot",
}


def test_counterfactual_engine_deltas_and_thresholds(client):
    """Verify CounterfactualEngine produces 6 dimension deltas following approved rules."""
    engine = get_counterfactual_engine()

    # Setup simulated session
    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]
    resp_s = client.post("/api/simulate", json={"session_id": sid})
    sim_data = resp_s.json()["data"]

    session = session_store.get(sid)
    score_matrix = session.score_matrix
    scenarios = session.scenarios

    # Compare Park (A) vs Commercial (B)
    result = engine.compare("park", "commercial", score_matrix, scenarios)

    assert result.scenario_a_id == "park"
    assert result.scenario_b_id == "commercial"
    assert len(result.deltas) == 6

    # Verify each dimension delta
    for d in result.deltas:
        expected_delta = round(d.score_b - d.score_a, 1)
        assert d.delta == expected_delta
        assert d.abs_delta == round(abs(expected_delta), 1)

        # Approved threshold: ±2
        if d.delta > 2.0:
            assert d.direction == "b_better"
        elif d.delta < -2.0:
            assert d.direction == "a_better"
        else:
            assert d.direction == "neutral"

        # Magnitude
        if d.abs_delta < 5.0:
            assert d.magnitude == "negligible"
        elif d.abs_delta < 15.0:
            assert d.magnitude == "minor"
        elif d.abs_delta < 30.0:
            assert d.magnitude == "moderate"
        elif d.abs_delta < 50.0:
            assert d.magnitude == "significant"
        else:
            assert d.magnitude == "major"

    # Aggregates
    assert len(result.a_wins_dimensions) + len(result.b_wins_dimensions) + len(result.neutral_dimensions) == 6
    expected_net = round(sum(d.delta for d in result.deltas), 1)
    assert result.net_delta == expected_net
    assert result.verdict in ("meaningfully_better", "meaningfully_worse", "practically_equivalent")
    assert result.headline != ""


def test_counterfactual_engine_symmetry(client):
    """Comparing A vs B has opposite delta values to B vs A."""
    engine = get_counterfactual_engine()

    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]
    client.post("/api/simulate", json={"session_id": sid})

    session = session_store.get(sid)
    res_ab = engine.compare("park", "healthcare", session.score_matrix, session.scenarios)
    res_ba = engine.compare("healthcare", "park", session.score_matrix, session.scenarios)

    # Net deltas are exact opposites
    assert pytest.approx(res_ab.net_delta, abs=0.1) == -res_ba.net_delta

    # Dimension deltas are exact opposites
    for d_ab, d_ba in zip(res_ab.deltas, res_ba.deltas):
        assert d_ab.dimension == d_ba.dimension
        assert pytest.approx(d_ab.delta, abs=0.1) == -d_ba.delta


def test_counterfactual_api_endpoint(client):
    """Full HTTP API test for POST /api/counterfactual."""
    # 1. Analyze and simulate
    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]
    client.post("/api/simulate", json={"session_id": sid})

    # 2. Call /api/counterfactual
    cf_resp = client.post(
        "/api/counterfactual",
        json={"session_id": sid, "scenario_a_id": "park", "scenario_b_id": "healthcare"},
    )
    assert cf_resp.status_code == 200
    body = cf_resp.json()
    assert body["success"] is True
    assert body["error"] is None

    result = body["data"]["result"]
    assert result["scenario_a_id"] == "park"
    assert result["scenario_b_id"] == "healthcare"
    assert len(result["deltas"]) == 6
    assert result["headline"] != ""
    assert result["verdict"] in ("meaningfully_better", "meaningfully_worse", "practically_equivalent")

    # Verify session mutated
    session = session_store.get(sid)
    assert session.counterfactual is not None
    assert session.counterfactual.scenario_a_id == "park"
    assert session.counterfactual.scenario_b_id == "healthcare"


def test_counterfactual_prerequisite_and_validation(client):
    """Enforces prerequisites and rejects invalid requests."""
    # 1. Non-existent session
    bad_resp = client.post(
        "/api/counterfactual",
        json={
            "session_id": str(uuid.uuid4()),
            "scenario_a_id": "park",
            "scenario_b_id": "healthcare",
        },
    )
    assert bad_resp.status_code == 404
    assert bad_resp.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # 2. Missing simulation prerequisite
    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]
    unsim_resp = client.post(
        "/api/counterfactual",
        json={
            "session_id": sid,
            "scenario_a_id": "park",
            "scenario_b_id": "healthcare",
        },
    )
    assert unsim_resp.status_code == 400
    assert unsim_resp.json()["error"]["code"] == "MISSING_PREREQUISITE"

    # 3. Same scenario on both sides rejected
    client.post("/api/simulate", json={"session_id": sid})
    same_resp = client.post(
        "/api/counterfactual",
        json={
            "session_id": sid,
            "scenario_a_id": "park",
            "scenario_b_id": "park",
        },
    )
    assert same_resp.status_code == 422
    assert same_resp.json()["error"]["code"] == "VALIDATION_ERROR"
