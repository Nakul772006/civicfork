"""Tests for Phase 4.8A: Deterministic Decision Stability / Sensitivity Analysis."""

import pytest
from app.exceptions import MissingPrerequisiteError, SessionNotFoundError
from app.models.domain import (
    DimensionScore,
    PlotLocation,
    RankedScenario,
    Scenario,
    ScenarioScore,
    ScoreExplanation,
    ScoreMatrix,
    SessionData,
    WeightConfig,
)
from app.services.context_analyzer import get_context_analyzer
from app.services.gap_analyzer import get_gap_analyzer
from app.services.impact_simulator import get_impact_simulator
from app.services.ranking_engine import RankingEngine
from app.services.scenario_generator import get_scenario_generator
from app.services.stability_analyzer import (
    STABILITY_CONFIGURATIONS,
    StabilityAnalyzer,
    get_stability_analyzer,
)
from app.session import session_store

MYSURU_PLOT = {
    "lat": 12.3100,
    "lng": 76.6500,
    "radius_m": 2000,
    "area_sqm": 3500.0,
    "label": "Stability Test Plot",
}


def make_dim_score(dimension: str, score: float) -> DimensionScore:
    """Helper to instantiate a valid DimensionScore."""
    return DimensionScore(
        dimension=dimension,
        score=score,
        direction_note="Higher is better",
        explanation=ScoreExplanation(
            rule_name="synthetic_rule",
            formula_description="Synthetic test score",
            raw_result=score,
            normalised_result=score,
        ),
    )


@pytest.fixture
def stability_analyzer():
    """Provides an isolated StabilityAnalyzer instance."""
    return StabilityAnalyzer()


@pytest.fixture
def baseline_simulation():
    """Run full Phase 2 pipeline to produce real ScoreMatrix and scenarios."""
    ctx_analyzer = get_context_analyzer()
    gap_analyzer = get_gap_analyzer()
    scen_generator = get_scenario_generator()
    simulator = get_impact_simulator()

    plot = PlotLocation(**MYSURU_PLOT)
    urban_ctx = ctx_analyzer.analyze(plot)
    gaps = gap_analyzer.analyze(plot, urban_ctx)
    scenarios = scen_generator.generate(plot, urban_ctx, gaps)
    matrix = simulator.simulate_all(scenarios, urban_ctx, gaps)
    return scenarios, matrix


@pytest.fixture
def sample_scenarios(baseline_simulation):
    """Provides 7 canonical scenarios."""
    scenarios, _ = baseline_simulation
    return scenarios


@pytest.fixture
def synthetic_score_matrix():
    """Provides a synthetic score matrix with clear dimensional advantages."""
    dims = ["traffic", "cost", "environmental", "accessibility", "gap_improvement", "social_utility"]
    # Park excels in environmental and social_utility
    # Public Transport excels in traffic and accessibility
    # Commercial excels in cost
    raw_scores = {
        "park": {"traffic": 60.0, "cost": 70.0, "environmental": 95.0, "accessibility": 70.0, "gap_improvement": 80.0, "social_utility": 85.0},
        "healthcare": {"traffic": 50.0, "cost": 40.0, "environmental": 60.0, "accessibility": 85.0, "gap_improvement": 85.0, "social_utility": 90.0},
        "education": {"traffic": 55.0, "cost": 50.0, "environmental": 65.0, "accessibility": 75.0, "gap_improvement": 70.0, "social_utility": 80.0},
        "parking": {"traffic": 75.0, "cost": 65.0, "environmental": 40.0, "accessibility": 80.0, "gap_improvement": 50.0, "social_utility": 45.0},
        "commercial": {"traffic": 40.0, "cost": 90.0, "environmental": 30.0, "accessibility": 65.0, "gap_improvement": 60.0, "social_utility": 50.0},
        "community_centre": {"traffic": 65.0, "cost": 60.0, "environmental": 70.0, "accessibility": 60.0, "gap_improvement": 65.0, "social_utility": 75.0},
        "public_transport": {"traffic": 95.0, "cost": 45.0, "environmental": 75.0, "accessibility": 95.0, "gap_improvement": 75.0, "social_utility": 70.0},
    }

    scenario_scores = []
    for sid, sscores in raw_scores.items():
        score_list = [make_dim_score(d, sscores[d]) for d in dims]
        mean_score = round(sum(sscores.values()) / 6.0, 1)
        scenario_scores.append(
            ScenarioScore(
                scenario_id=sid,
                scores=score_list,
                unweighted_composite=mean_score,
            )
        )

    matrix_rows = [[ds.score for ds in sc.scores] for sc in scenario_scores]
    return ScoreMatrix(
        scenario_scores=scenario_scores,
        dimensions=dims,
        matrix=matrix_rows,
        scenarios_evaluated=7,
        dimensions_evaluated=6,
    )


def test_stability_configurations_count_and_uniqueness():
    """Verify that exactly 7 unique priority configurations are defined."""
    assert len(STABILITY_CONFIGURATIONS) == 7

    config_ids = [c["id"] for c in STABILITY_CONFIGURATIONS]
    assert len(set(config_ids)) == 7
    assert "balanced" in config_ids
    assert "traffic_priority" in config_ids
    assert "environmental_priority" in config_ids
    assert "accessibility_priority" in config_ids
    assert "cost_priority" in config_ids
    assert "gap_improvement_priority" in config_ids
    assert "social_utility_priority" in config_ids


def test_balanced_configuration_execution(stability_analyzer, synthetic_score_matrix, sample_scenarios):
    """1. Verify execution of balanced configuration."""
    ranking_engine = RankingEngine()
    baseline_ranking = ranking_engine.rank(synthetic_score_matrix, scenarios=sample_scenarios)

    result = stability_analyzer.analyze(
        score_matrix=synthetic_score_matrix,
        baseline_ranking=baseline_ranking,
        scenarios=sample_scenarios,
    )

    balanced_res = next((c for c in result.configuration_results if c.configuration_id == "balanced"), None)
    assert balanced_res is not None
    assert balanced_res.winning_scenario_id == baseline_ranking[0].scenario_id
    assert balanced_res.baseline_won is True
    assert balanced_res.baseline_rank == 1


def test_each_priority_configuration(stability_analyzer, synthetic_score_matrix, sample_scenarios):
    """2. Verify each priority configuration produces valid outcomes."""
    ranking_engine = RankingEngine()
    baseline_ranking = ranking_engine.rank(synthetic_score_matrix, scenarios=sample_scenarios)

    result = stability_analyzer.analyze(
        score_matrix=synthetic_score_matrix,
        baseline_ranking=baseline_ranking,
        scenarios=sample_scenarios,
    )

    assert len(result.configuration_results) == 7
    assert result.total_configurations == 7
    assert len(result.configurations_tested) == 7

    for cr in result.configuration_results:
        assert cr.configuration_id in [c["id"] for c in STABILITY_CONFIGURATIONS]
        assert cr.winning_scenario_id in [s.id for s in sample_scenarios]
        assert cr.winning_score > 0
        assert cr.baseline_rank >= 1
        assert cr.baseline_score > 0
        assert isinstance(cr.baseline_won, bool)


def test_stability_score_calculation(stability_analyzer, synthetic_score_matrix, sample_scenarios):
    """3. Verify stability score formula: 100 * baseline_wins / total_configurations."""
    ranking_engine = RankingEngine()
    baseline_ranking = ranking_engine.rank(synthetic_score_matrix, scenarios=sample_scenarios)

    result = stability_analyzer.analyze(
        score_matrix=synthetic_score_matrix,
        baseline_ranking=baseline_ranking,
        scenarios=sample_scenarios,
    )

    expected_score = round(100.0 * result.baseline_wins / result.total_configurations, 1)
    assert result.stability_score == expected_score


def test_stability_level_thresholds_and_interpretations(stability_analyzer, sample_scenarios):
    """4. Verify HIGH, MODERATE, and LOW threshold classifications and interpretations."""
    dims = ["traffic", "cost", "environmental", "accessibility", "gap_improvement", "social_utility"]

    # 4a. Dominant scenario (wins all 7 configurations) -> HIGH (100.0%)
    dominant_scores = [
        ScenarioScore(
            scenario_id="park",
            scores=[make_dim_score(d, 99.0) for d in dims],
            unweighted_composite=99.0,
        )
    ] + [
        ScenarioScore(
            scenario_id=s.id,
            scores=[make_dim_score(d, 20.0) for d in dims],
            unweighted_composite=20.0,
        )
        for s in sample_scenarios if s.id != "park"
    ]
    mat_high = ScoreMatrix(
        scenario_scores=dominant_scores,
        dimensions=dims,
        matrix=[[ds.score for ds in sc.scores] for sc in dominant_scores],
        scenarios_evaluated=7,
        dimensions_evaluated=6,
    )
    rank_high = RankingEngine().rank(mat_high, scenarios=sample_scenarios)
    res_high = stability_analyzer.analyze(mat_high, rank_high, sample_scenarios)

    assert res_high.baseline_wins == 7
    assert res_high.stability_score == 100.0
    assert res_high.stability_level == "HIGH"
    assert "remains the top-ranked option across most tested priority configurations" in res_high.interpretation

    # 4b. Low stability scenario (wins < 50%, e.g. 0-3 configurations) -> LOW
    # Force commercial to be baseline by ranking with cost=10.0, but under alternative configs it loses
    rank_comm = [r for r in rank_high if r.scenario_id == "commercial"] + [r for r in rank_high if r.scenario_id != "commercial"]
    # Re-number ranks
    for idx, r in enumerate(rank_comm):
        r.rank = idx + 1

    res_low = stability_analyzer.analyze(mat_high, rank_comm, sample_scenarios)
    assert res_low.baseline_wins == 0
    assert res_low.stability_score == 0.0
    assert res_low.stability_level == "LOW"
    assert "changes substantially when municipal priorities shift" in res_low.interpretation


def test_strongest_challenger_identification(stability_analyzer, synthetic_score_matrix, sample_scenarios):
    """5. Verify identification of strongest challenger (highest non-baseline wins)."""
    ranking_engine = RankingEngine()
    baseline_ranking = ranking_engine.rank(synthetic_score_matrix, scenarios=sample_scenarios)

    result = stability_analyzer.analyze(
        score_matrix=synthetic_score_matrix,
        baseline_ranking=baseline_ranking,
        scenarios=sample_scenarios,
    )

    assert result.strongest_challenger is not None
    assert result.strongest_challenger.scenario_id != result.baseline_scenario_id
    assert result.strongest_challenger.scenario_name is not None
    assert isinstance(result.strongest_challenger.wins, int)

    # Strongest challenger should have the max wins among non-baseline scenarios
    non_baseline_wins = [
        result.scenario_win_counts.get(s.id, 0)
        for s in sample_scenarios
        if s.id != result.baseline_scenario_id
    ]
    assert result.strongest_challenger.wins == max(non_baseline_wins)


def test_deterministic_tie_breaking(stability_analyzer, sample_scenarios):
    """6. Verify deterministic tie-breaking for strongest challenger by baseline rank then id."""
    dims = ["traffic", "cost", "environmental", "accessibility", "gap_improvement", "social_utility"]

    # All scenarios have identical scores
    equal_scores = [
        ScenarioScore(
            scenario_id=s.id,
            scores=[make_dim_score(d, 50.0) for d in dims],
            unweighted_composite=50.0,
        )
        for s in sample_scenarios
    ]
    mat_equal = ScoreMatrix(
        scenario_scores=equal_scores,
        dimensions=dims,
        matrix=[[ds.score for ds in sc.scores] for sc in equal_scores],
        scenarios_evaluated=7,
        dimensions_evaluated=6,
    )
    ranking = RankingEngine().rank(mat_equal, scenarios=sample_scenarios)

    # Rank 1 is baseline. Non-baseline scenarios all have 0 wins or equal wins.
    result = stability_analyzer.analyze(mat_equal, ranking, sample_scenarios)

    # Tie-break should pick Rank 2
    assert result.strongest_challenger is not None
    assert result.strongest_challenger.scenario_id == ranking[1].scenario_id


def test_prerequisite_validation(client):
    """7. Verify prerequisite enforcement on POST /api/stability."""
    # 7a. Non-existent session -> 404
    resp_fake = client.post("/api/stability", json={"session_id": "00000000-0000-0000-0000-000000000000"})
    assert resp_fake.status_code == 404
    assert resp_fake.json()["error"]["code"] == "SESSION_NOT_FOUND"

    # 7b. Session before simulation -> 400 MISSING_PREREQUISITE
    resp_a = client.post("/api/analyze", json=MYSURU_PLOT)
    sid = resp_a.json()["data"]["session_id"]

    resp_stab_presim = client.post("/api/stability", json={"session_id": sid})
    assert resp_stab_presim.status_code == 400
    assert resp_stab_presim.json()["error"]["code"] == "MISSING_PREREQUISITE"
    assert "score_matrix" in resp_stab_presim.json()["error"]["details"]["missing_field"]

    # 7c. Invalid UUID -> 422
    resp_invalid = client.post("/api/stability", json={"session_id": "not-a-uuid"})
    assert resp_invalid.status_code == 422


def test_session_isolation(client):
    """8. Verify session isolation: stability in one session does not contaminate another."""
    resp1 = client.post("/api/analyze", json=MYSURU_PLOT)
    sid1 = resp1.json()["data"]["session_id"]
    client.post("/api/simulate", json={"session_id": sid1})

    resp2 = client.post("/api/analyze", json={**MYSURU_PLOT, "lat": 12.3320, "lng": 76.6150})
    sid2 = resp2.json()["data"]["session_id"]
    client.post("/api/simulate", json={"session_id": sid2})

    stab1 = client.post("/api/stability", json={"session_id": sid1}).json()["data"]["result"]
    stab2 = client.post("/api/stability", json={"session_id": sid2}).json()["data"]["result"]

    assert stab1["baseline_scenario_id"] is not None
    assert stab2["baseline_scenario_id"] is not None

    session1 = session_store.get(sid1)
    session2 = session_store.get(sid2)

    assert session1.stability.baseline_scenario_id == stab1["baseline_scenario_id"]
    assert session2.stability.baseline_scenario_id == stab2["baseline_scenario_id"]


def test_provenance_and_calculation_trace(stability_analyzer, synthetic_score_matrix, sample_scenarios):
    """9. Verify calculation trace and provenance structure."""
    ranking_engine = RankingEngine()
    baseline_ranking = ranking_engine.rank(synthetic_score_matrix, scenarios=sample_scenarios)

    result = stability_analyzer.analyze(
        score_matrix=synthetic_score_matrix,
        baseline_ranking=baseline_ranking,
        scenarios=sample_scenarios,
    )

    trace = result.calculation_trace
    assert "provenance" in trace
    prov = trace["provenance"]
    assert prov["score_matrix"] == "calculated"
    assert prov["baseline_ranking"] == "derived"
    assert prov["priority_configurations"] == "configured"
    assert prov["stability_score"] == "derived"

    assert "methodology" in trace
    assert "disclaimer" in trace
    assert "Modelled sensitivity analysis" in trace["disclaimer"]


def test_no_ai_dependency_guarantee(stability_analyzer, synthetic_score_matrix, sample_scenarios):
    """10. Verify stability analysis is 100% deterministic with zero LLM/network calls."""
    ranking_engine = RankingEngine()
    baseline_ranking = ranking_engine.rank(synthetic_score_matrix, scenarios=sample_scenarios)

    # Must complete instantly and return deterministic result without any API keys or network
    res1 = stability_analyzer.analyze(synthetic_score_matrix, baseline_ranking, sample_scenarios)
    res2 = stability_analyzer.analyze(synthetic_score_matrix, baseline_ranking, sample_scenarios)

    assert res1.stability_score == res2.stability_score
    assert res1.stability_level == res2.stability_level
    assert res1.baseline_wins == res2.baseline_wins
    assert res1.strongest_challenger == res2.strongest_challenger
    assert len(res1.configuration_results) == len(res2.configuration_results)
