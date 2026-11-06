"""End-to-end pipeline integration tests for CivicFork Phase 2.7.

Exercises the full analytical sequence:
POST /api/analyze -> POST /api/simulate -> POST /api/rank

Verifies:
1. Complete happy-path pipeline flow across all three endpoints.
2. Workflow prerequisite enforcement:
   - /simulate rejected before /analyze (MISSING_PREREQUISITE)
   - /rank rejected before /simulate (MISSING_PREREQUISITE)
   - Non-existent session handling (SESSION_NOT_FOUND)
3. Input validation:
   - Out-of-bounds coordinates and invalid radii rejected on /analyze
   - All-zero weights rejected on /rank
4. Determinism of repeated simulations and rankings.
5. Multi-stage pipeline explainability trace generation.
6. Sensitivity of ranking results to varying municipal priority weights.
"""

import uuid
import pytest
from app.models.domain import SessionData
from app.services.pipeline_trace import build_pipeline_trace
from app.session import session_store


MYSURU_VALID_PLOT = {
    "lat": 12.3100,
    "lng": 76.6500,
    "radius_m": 2000,
    "area_sqm": 3500.0,
    "label": "Pipeline Integration Test Plot",
}


def test_pipeline_e2e_happy_path(client):
    """Test full happy-path: analyze -> simulate -> rank -> pipeline trace."""
    # -------------------------------------------------------------
    # Stage 1: POST /api/analyze
    # -------------------------------------------------------------
    analyze_resp = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    assert analyze_resp.status_code == 200
    analyze_body = analyze_resp.json()
    assert analyze_body["success"] is True
    assert analyze_body["error"] is None

    adata = analyze_body["data"]
    session_id = adata["session_id"]
    assert session_id is not None
    # Validate UUID format
    assert uuid.UUID(session_id)

    # Plot echo
    assert adata["plot"]["lat"] == 12.3100
    assert adata["plot"]["lng"] == 76.6500
    assert adata["plot"]["radius_m"] == 2000
    assert adata["plot"]["area_sqm"] == 3500.0

    # Urban context summary
    csummary = adata["context_summary"]
    assert csummary["total_pois"] > 0
    assert csummary["road_network_length_m"] > 0
    assert "dominant_landuse" in csummary

    # Infrastructure gaps (all 7 categories evaluated)
    gaps = adata["gaps"]
    assert len(gaps) == 7
    gap_categories = {g["category"] for g in gaps}
    assert gap_categories == {
        "parks", "healthcare", "education", "parking",
        "commercial", "community", "transport"
    }

    # GeoJSON layers
    assert adata["poi_geojson"]["type"] == "FeatureCollection"
    assert "features" in adata["poi_geojson"]
    assert adata["landuse_geojson"]["type"] == "FeatureCollection"
    assert adata["transport_geojson"]["type"] == "FeatureCollection"

    # Bounds
    assert adata["bounds"]["center"] == [12.3100, 76.6500]
    assert adata["bounds"]["radius_m"] == 2000

    # Verify session store contains scenarios
    session = session_store.get(session_id)
    assert session is not None
    assert len(session.scenarios) == 7

    # -------------------------------------------------------------
    # Stage 2: POST /api/simulate
    # -------------------------------------------------------------
    sim_resp = client.post("/api/simulate", json={"session_id": session_id})
    assert sim_resp.status_code == 200
    sim_body = sim_resp.json()
    assert sim_body["success"] is True
    assert sim_body["error"] is None

    sdata = sim_body["data"]
    assert len(sdata["scenarios"]) == 7
    assert sdata["score_matrix"]["scenarios_evaluated"] == 7
    assert sdata["score_matrix"]["dimensions_evaluated"] == 6

    # Verify 7x6 numeric matrix values are bounded [0, 100]
    matrix = sdata["score_matrix"]["matrix"]
    assert len(matrix) == 7
    for row in matrix:
        assert len(row) == 6
        for score in row:
            assert 0.0 <= score <= 100.0, f"Matrix score out of bounds: {score}"

    # Verify scenario_scores detailed objects
    scenario_scores = sdata["score_matrix"]["scenario_scores"]
    assert len(scenario_scores) == 7
    for sc in scenario_scores:
        assert len(sc["scores"]) == 6
        assert 0.0 <= sc["unweighted_composite"] <= 100.0
        for ds in sc["scores"]:
            assert 0.0 <= ds["score"] <= 100.0

    # Default ranking with equal weights
    def_ranking = sdata["default_ranking"]
    assert len(def_ranking) == 7
    assert def_ranking[0]["rank"] == 1
    assert def_ranking[0]["score_delta_from_top"] == 0.0

    # Session store updated
    session_after_sim = session_store.get(session_id)
    assert session_after_sim.score_matrix is not None
    assert session_after_sim.ranking is not None

    # -------------------------------------------------------------
    # Stage 3: POST /api/rank with custom weights
    # -------------------------------------------------------------
    custom_weights = {
        "traffic": 5.0,
        "cost": 2.0,
        "environmental": 4.0,
        "accessibility": 3.0,
        "gap_improvement": 5.0,
        "social_utility": 3.0,
    }
    rank_resp = client.post(
        "/api/rank",
        json={"session_id": session_id, "weights": custom_weights},
    )
    assert rank_resp.status_code == 200
    rank_body = rank_resp.json()
    assert rank_body["success"] is True
    assert rank_body["error"] is None

    rdata = rank_body["data"]
    ranking = rdata["ranking"]
    assert len(ranking) == 7

    # Check monotonic rank ordering and score deltas
    for i in range(len(ranking)):
        assert ranking[i]["rank"] == i + 1
        if i == 0:
            assert ranking[i]["score_delta_from_top"] == 0.0
        else:
            assert ranking[i]["weighted_score"] <= ranking[i - 1]["weighted_score"]
            assert ranking[i]["score_delta_from_top"] >= 0.0

        # Dimension contributions sum to weighted_score (within rounding tolerance)
        contribs = ranking[i]["dimension_contributions"]
        contrib_sum = sum(contribs.values())
        assert pytest.approx(ranking[i]["weighted_score"], abs=0.1) == contrib_sum

    # Applied weights normalized to 1.0
    weights_applied = rdata["weights_applied"]
    weight_sum = sum(weights_applied.values())
    assert pytest.approx(weight_sum, abs=0.001) == 1.0

    # -------------------------------------------------------------
    # Stage 4: Pipeline Trace
    # -------------------------------------------------------------
    session_final = session_store.get(session_id)
    trace = build_pipeline_trace(session_final)

    assert trace["session_id"] == session_id
    assert trace["workflow_stage"] == "ranked"
    assert trace["plot"]["lat"] == 12.3100
    assert trace["urban_context"]["observed"]["total_pois"] > 0
    assert len(trace["infrastructure_gaps"]) == 7
    assert len(trace["scenarios_generated"]) == 7
    assert "simulation" in trace
    assert "ranking" in trace
    assert len(trace["ranking"]["leaderboard"]) == 7
    assert "scenario_detail" in trace
    assert trace["scenario_detail"]["scenario_id"] is not None


def test_prerequisite_simulate_before_analyze_rejected(client):
    """Calling /api/simulate before /api/analyze fails with MISSING_PREREQUISITE."""
    # Create an empty session without prior analysis
    empty_session = SessionData(session_id=str(uuid.uuid4()))
    session_store.set_session_data(empty_session.session_id, empty_session)

    resp = client.post("/api/simulate", json={"session_id": empty_session.session_id})
    assert resp.status_code == 400
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "MISSING_PREREQUISITE"
    assert "Analysis must be completed" in body["error"]["message"]


def test_prerequisite_rank_before_simulate_rejected(client):
    """Calling /api/rank before /api/simulate fails with MISSING_PREREQUISITE."""
    # Analyze plot first to establish context & scenarios
    analyze_resp = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    assert analyze_resp.status_code == 200
    session_id = analyze_resp.json()["data"]["session_id"]

    # Directly attempt /api/rank without simulating
    rank_resp = client.post(
        "/api/rank",
        json={"session_id": session_id, "weights": {"traffic": 3, "cost": 3}},
    )
    assert rank_resp.status_code == 400
    body = rank_resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "MISSING_PREREQUISITE"
    assert "Simulation must be completed" in body["error"]["message"]


def test_nonexistent_session_returns_404(client):
    """Calling /api/simulate or /api/rank with non-existent UUID fails with SESSION_NOT_FOUND."""
    fake_id = str(uuid.uuid4())

    sim_resp = client.post("/api/simulate", json={"session_id": fake_id})
    assert sim_resp.status_code == 404
    sim_body = sim_resp.json()
    assert sim_body["success"] is False
    assert sim_body["error"]["code"] == "SESSION_NOT_FOUND"

    rank_resp = client.post("/api/rank", json={"session_id": fake_id, "weights": {"traffic": 1}})
    assert rank_resp.status_code == 404
    rank_body = rank_resp.json()
    assert rank_body["success"] is False
    assert rank_body["error"]["code"] == "SESSION_NOT_FOUND"


def test_analyze_out_of_bounds_rejected(client):
    """Coordinates outside Mysuru bounds or invalid radius are rejected with 422."""
    # Latitude out of bounds
    oob_lat = {**MYSURU_VALID_PLOT, "lat": 13.5000}
    resp = client.post("/api/analyze", json=oob_lat)
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

    # Longitude out of bounds
    oob_lng = {**MYSURU_VALID_PLOT, "lng": 77.5000}
    resp = client.post("/api/analyze", json=oob_lng)
    assert resp.status_code == 422

    # Invalid radius
    invalid_radius = {**MYSURU_VALID_PLOT, "radius_m": 3500}
    resp = client.post("/api/analyze", json=invalid_radius)
    assert resp.status_code == 422


def test_rank_all_zero_weights_rejected(client):
    """Calling /api/rank with all zero weights fails validation."""
    analyze_resp = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    session_id = analyze_resp.json()["data"]["session_id"]
    client.post("/api/simulate", json={"session_id": session_id})

    zero_weights = {
        "traffic": 0.0,
        "cost": 0.0,
        "environmental": 0.0,
        "accessibility": 0.0,
        "gap_improvement": 0.0,
        "social_utility": 0.0,
    }
    rank_resp = client.post(
        "/api/rank",
        json={"session_id": session_id, "weights": zero_weights},
    )
    assert rank_resp.status_code == 422
    body = rank_resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_pipeline_determinism(client):
    """Running identical analysis, simulation, and ranking calls twice yields identical results."""
    # Run 1
    resp1_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid1 = resp1_a.json()["data"]["session_id"]
    resp1_s = client.post("/api/simulate", json={"session_id": sid1})
    weights = {"traffic": 3.0, "environmental": 4.0, "gap_improvement": 5.0}
    resp1_r = client.post("/api/rank", json={"session_id": sid1, "weights": weights})

    # Run 2
    resp2_a = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid2 = resp2_a.json()["data"]["session_id"]
    resp2_s = client.post("/api/simulate", json={"session_id": sid2})
    resp2_r = client.post("/api/rank", json={"session_id": sid2, "weights": weights})

    # Compare simulation matrices
    mat1 = resp1_s.json()["data"]["score_matrix"]["matrix"]
    mat2 = resp2_s.json()["data"]["score_matrix"]["matrix"]
    assert mat1 == mat2

    # Compare rankings
    rank1 = resp1_r.json()["data"]["ranking"]
    rank2 = resp2_r.json()["data"]["ranking"]
    for r1, r2 in zip(rank1, rank2):
        assert r1["scenario_id"] == r2["scenario_id"]
        assert r1["rank"] == r2["rank"]
        assert r1["weighted_score"] == r2["weighted_score"]


def test_different_weights_produce_different_rankings(client):
    """Varying municipal priority weights alters scenario ranks or scores."""
    analyze_resp = client.post("/api/analyze", json=MYSURU_VALID_PLOT)
    sid = analyze_resp.json()["data"]["session_id"]
    client.post("/api/simulate", json={"session_id": sid})

    # Environmental-heavy weights
    env_heavy = {
        "traffic": 0.5,
        "cost": 0.5,
        "environmental": 10.0,
        "accessibility": 0.5,
        "gap_improvement": 0.5,
        "social_utility": 0.5,
    }
    env_rank_resp = client.post("/api/rank", json={"session_id": sid, "weights": env_heavy})
    env_ranking = env_rank_resp.json()["data"]["ranking"]

    # Traffic-heavy weights
    traffic_heavy = {
        "traffic": 10.0,
        "cost": 0.5,
        "environmental": 0.5,
        "accessibility": 0.5,
        "gap_improvement": 0.5,
        "social_utility": 0.5,
    }
    traffic_rank_resp = client.post("/api/rank", json={"session_id": sid, "weights": traffic_heavy})
    traffic_ranking = traffic_rank_resp.json()["data"]["ranking"]

    # Verify that the two ranking distributions differ
    env_top = env_ranking[0]["scenario_id"]
    traffic_top = traffic_ranking[0]["scenario_id"]
    # Even if top scenario happens to match in some tie case, the score vectors will differ
    assert env_ranking[0]["weighted_score"] != traffic_ranking[0]["weighted_score"] or env_top != traffic_top


def test_pipeline_trace_progressive_stages():
    """Verify build_pipeline_trace accurately reports each stage of session maturity."""
    session = SessionData(session_id="trace-test-session")

    # Stage: Empty
    trace_empty = build_pipeline_trace(session)
    assert trace_empty["workflow_stage"] == "empty"
    assert trace_empty["urban_context"] is None
    assert trace_empty["infrastructure_gaps"] == []
    assert trace_empty["scenarios_generated"] == []
    assert "simulation" not in trace_empty
    assert "ranking" not in trace_empty
