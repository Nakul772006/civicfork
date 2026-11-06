"""Tests for the deterministic Feasibility Checker and /api/feasibility endpoint."""

import uuid
import pytest
from app.models.domain import PlotLocation, SessionData
from app.services.feasibility_checker import get_feasibility_checker
from app.session import session_store

MYSURU_VALID_PLOT = {
    "lat": 12.3100,
    "lng": 76.6500,
    "radius_m": 2000,
    "area_sqm": 3500.0,
    "label": "Feasibility Test Plot",
}


def test_feasibility_checker_evaluates_all_scenarios(client):
    """Verify FeasibilityChecker evaluates 4 rules per scenario deterministically."""
    checker = get_feasibility_checker()

    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]
    session = session_store.get(sid)

    verdicts = checker.evaluate_all(
        scenarios=session.scenarios,
        plot=session.plot,
        context=session.urban_context or session.context,
        gaps=session.gaps,
    )

    assert len(verdicts) == 7
    for v in verdicts:
        assert v.scenario_id in [s.id for s in session.scenarios]
        assert len(v.checks) == 4
        check_names = {c.check_name for c in v.checks}
        assert check_names == {
            "minimum_area",
            "proximity_conflict",
            "service_saturation",
            "zoning_compatibility",
        }

        # Blocker rule consistency
        assert v.feasible == (v.blocker_count == 0)
        assert len(v.blockers) == v.blocker_count
        assert len(v.warnings) == v.warning_count


def test_feasibility_checker_insufficient_area_triggers_blocker(client):
    """A small plot below healthcare's 2000m² minimum triggers minimum_area blocker."""
    checker = get_feasibility_checker()

    # Small plot of 300 m²
    small_plot_req = {**MYSURU_VALID_PLOT, "area_sqm": 300.0}
    resp_a = client.post("/api/analyze", json=small_plot_req)
    sid = resp_a.json()["data"]["session_id"]
    session = session_store.get(sid)

    hc_scenario = next(s for s in session.scenarios if s.id == "healthcare")
    verdict = checker.evaluate(
        scenario=hc_scenario,
        plot=session.plot,
        context=session.urban_context or session.context,
        gaps=session.gaps,
    )

    # Healthcare requires 2000m² -> 300m² must fail blocker
    assert verdict.feasible is False
    assert verdict.blocker_count >= 1
    area_check = next(c for c in verdict.checks if c.check_name == "minimum_area")
    assert area_check.passed is False
    assert area_check.severity == "blocker"
    assert "below minimum required area" in area_check.message


def test_feasibility_api_endpoint_all_scenarios(client):
    """Full HTTP API test for POST /api/feasibility returning all 7 verdicts."""
    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]

    resp = client.post("/api/feasibility", json={"session_id": sid})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None

    verdicts = body["data"]["verdicts"]
    assert len(verdicts) == 7
    for v in verdicts:
        assert "scenario_id" in v
        assert "feasible" in v
        assert len(v["checks"]) == 4

    # Verify session mutated
    session = session_store.get(sid)
    assert session.feasibility is not None
    assert len(session.feasibility) == 7


def test_feasibility_api_endpoint_single_scenario(client):
    """Calling POST /api/feasibility with scenario_id returns that specific verdict."""
    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]

    resp = client.post(
        "/api/feasibility",
        json={"session_id": sid, "scenario_id": "park"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    verdicts = body["data"]["verdicts"]
    assert len(verdicts) == 1
    assert verdicts[0]["scenario_id"] == "park"


def test_feasibility_api_prerequisites_and_validation(client):
    """Enforces prerequisites, UUID validation, and scenario validation."""
    # 1. Non-existent session
    bad_resp = client.post(
        "/api/feasibility",
        json={"session_id": str(uuid.uuid4())},
    )
    assert bad_resp.status_code == 404
    assert bad_resp.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # 2. Missing analysis prerequisite
    empty_sid = str(uuid.uuid4())
    session_store.set_session_data(empty_sid, SessionData(session_id=empty_sid))
    uninit_resp = client.post("/api/feasibility", json={"session_id": empty_sid})
    assert uninit_resp.status_code == 400
    assert uninit_resp.json()["error"]["code"] == "MISSING_PREREQUISITE"

    # 3. Invalid scenario_id rejected
    resp_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = resp_a.json()["data"]["session_id"]
    inv_resp = client.post(
        "/api/feasibility",
        json={"session_id": sid, "scenario_id": "airport_terminal"},
    )
    assert inv_resp.status_code == 422
    assert inv_resp.json()["error"]["code"] == "VALIDATION_ERROR"
