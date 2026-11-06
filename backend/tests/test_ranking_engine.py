"""Unit and integration tests for Ranking and Weighting Engine (Phase 2.6).

Verifies priority weight normalization, weighted composite scores,
tie-breaking logic, dimension contribution decomposition, score delta calculation,
traceability, and session compatibility.
"""

import pytest
from app.api.dependencies import get_ranking_engine as get_ranking_engine_dep
from app.config_loader import get_app_config
from app.models.domain import (
    DimensionScore,
    PlotLocation,
    RankedScenario,
    SCENARIO_IDS,
    ScenarioScore,
    ScoreExplanation,
    ScoreMatrix,
    SessionData,
    WeightConfig,
)
from app.services.context_analyzer import get_context_analyzer
from app.services.gap_analyzer import get_gap_analyzer
from app.services.impact_simulator import get_impact_simulator
from app.services.ranking_engine import (
    RankingEngine,
    get_ranking_engine,
)
from app.services.scenario_generator import get_scenario_generator

SARASWATHIPURAM_PLOT = PlotLocation(
    lat=12.3100,
    lng=76.6500,
    radius_m=2000,
    area_sqm=3000.0,
    label="Saraswathipuram Baseline",
)


@pytest.fixture
def baseline_simulation():
    """Run full Phase 2.1 - 2.5 pipeline to produce ScoreMatrix and scenarios."""
    ctx_analyzer = get_context_analyzer()
    gap_analyzer = get_gap_analyzer()
    scen_generator = get_scenario_generator()
    simulator = get_impact_simulator()

    urban_ctx = ctx_analyzer.analyze(SARASWATHIPURAM_PLOT)
    gaps = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx)
    scenarios = scen_generator.generate(SARASWATHIPURAM_PLOT, urban_ctx, gaps)
    matrix = simulator.simulate_all(scenarios, urban_ctx, gaps)
    return urban_ctx, gaps, scenarios, matrix


def test_ranking_produces_all_seven_scenarios(baseline_simulation):
    """Verify that ranking produces exactly 7 RankedScenario instances with ranks 1 to 7."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    ranked = engine.rank(matrix, scenarios=scenarios)

    assert len(ranked) == 7
    ranks = [r.rank for r in ranked]
    assert ranks == [1, 2, 3, 4, 5, 6, 7]

    for r in ranked:
        assert isinstance(r, RankedScenario)
        assert r.scenario_id in SCENARIO_IDS
        assert len(r.scenario_name) > 0
        assert 0.0 <= r.weighted_score <= 100.0
        assert r.score_delta_from_top >= 0.0
        assert len(r.dimension_contributions) == 6


def test_rank_one_has_zero_delta(baseline_simulation):
    """Verify that the top-ranked scenario has delta_from_top of 0.0."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    ranked = engine.rank(matrix, scenarios=scenarios)

    top = ranked[0]
    assert top.rank == 1
    assert top.score_delta_from_top == 0.0

    for lower in ranked[1:]:
        assert lower.score_delta_from_top >= 0.0
        assert lower.score_delta_from_top == pytest.approx(
            round(top.weighted_score - lower.weighted_score, 1), abs=0.1
        )


def test_default_equal_weights(baseline_simulation):
    """Verify that default weights equal 1/6 for all dimensions and match unweighted average."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    ranked = engine.rank(matrix, weights=None, scenarios=scenarios)
    trace = engine.get_calculation_trace()

    # Check normalized weights are equal 1/6
    for dim, w in trace["weights_normalized"].items():
        assert w == pytest.approx(1.0 / 6.0, abs=1e-4)

    # For each scenario, weighted score should closely track unweighted composite
    scores_by_id = {s.scenario_id: s.unweighted_composite for s in matrix.scenario_scores}
    for r in ranked:
        unweighted = scores_by_id[r.scenario_id]
        assert r.weighted_score == pytest.approx(unweighted, abs=0.2)


def test_custom_priority_weights_change_ranking(baseline_simulation):
    """Verify that user-adjusted weights dynamically alter composite scores and scenario ranking."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    # Weight set A: Heavy focus on Cost (favoring low-cost/parking/park)
    cost_heavy_weights = WeightConfig(
        traffic=0.0,
        cost=10.0,
        environmental=0.0,
        accessibility=0.0,
        gap_improvement=0.0,
        social_utility=0.0,
    )
    ranked_cost = engine.rank(matrix, weights=cost_heavy_weights, scenarios=scenarios)

    # Weight set B: Heavy focus on Social Utility (favoring healthcare/education)
    social_heavy_weights = WeightConfig(
        traffic=0.0,
        cost=0.0,
        environmental=0.0,
        accessibility=0.0,
        gap_improvement=0.0,
        social_utility=10.0,
    )
    ranked_social = engine.rank(matrix, weights=social_heavy_weights, scenarios=scenarios)

    # Scenarios at top should differ based on priority
    assert [r.scenario_id for r in ranked_cost] != [r.scenario_id for r in ranked_social]
    # In social-heavy, healthcare or community_centre or education should be near top
    assert ranked_social[0].scenario_id in ("healthcare", "community_centre", "park")


def test_arbitrary_positive_weights_normalization(baseline_simulation):
    """Verify weights with arbitrary positive sums are normalized such that sum = 1.0."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    # Weights summing to 50
    custom_weights = WeightConfig(
        traffic=10.0,
        cost=15.0,
        environmental=5.0,
        accessibility=10.0,
        gap_improvement=5.0,
        social_utility=5.0,
    )
    ranked = engine.rank(matrix, weights=custom_weights, scenarios=scenarios)
    trace = engine.get_calculation_trace()

    normalized = trace["weights_normalized"]
    assert sum(normalized.values()) == pytest.approx(1.0, abs=1e-5)
    assert normalized["traffic"] == pytest.approx(10.0 / 50.0, abs=1e-5)
    assert normalized["cost"] == pytest.approx(15.0 / 50.0, abs=1e-5)


def test_dict_weights_with_environment_alias(baseline_simulation):
    """Verify passing weights as dict supports both 'environmental' and 'environment' keys."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    dict_weights = {
        "traffic": 1.0,
        "cost": 1.0,
        "environment": 2.0,  # alias key
        "accessibility": 1.0,
        "gap_improvement": 1.0,
        "social_utility": 1.0,
    }
    ranked = engine.rank(matrix, weights=dict_weights, scenarios=scenarios)
    trace = engine.get_calculation_trace()

    assert trace["weights_normalized"]["environmental"] == pytest.approx(2.0 / 7.0, abs=1e-5)


def test_dimension_contributions_decomposition(baseline_simulation):
    """Verify that dimension contributions accurately decompose the final composite score."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    weights = WeightConfig(traffic=0.2, cost=0.3, environmental=0.1, accessibility=0.15, gap_improvement=0.15, social_utility=0.1)
    ranked = engine.rank(matrix, weights=weights, scenarios=scenarios)

    for r in ranked:
        contrib_sum = sum(r.dimension_contributions.values())
        # The sum of rounded contributions should be within 0.1 of the rounded weighted score
        assert contrib_sum == pytest.approx(r.weighted_score, abs=0.15)


def test_deterministic_repeated_ranking(baseline_simulation):
    """Verify that ranking the same inputs twice yields bitwise identical results."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    weights = WeightConfig(traffic=1.0, cost=2.0, environmental=1.5, accessibility=1.0, gap_improvement=2.0, social_utility=1.0)
    run1 = engine.rank(matrix, weights=weights, scenarios=scenarios)
    run2 = engine.rank(matrix, weights=weights, scenarios=scenarios)

    assert [r.model_dump() for r in run1] == [r.model_dump() for r in run2]


def test_tie_breaking_logic():
    """Verify tie-breaking rules: 1st by gap_improvement descending, 2nd by scenario_id alphabetical."""
    engine = get_ranking_engine()

    def make_explanation():
        return ScoreExplanation(
            rule_name="test",
            formula_description="test",
            raw_result=50.0,
            normalised_result=50.0,
        )

    # Create two scenarios with identical composite score (all 50), but different gap scores
    # Scenario A: education, gap_improvement = 80, others adjusted so average is 50
    # Scenario B: healthcare, gap_improvement = 40, others adjusted so average is 50
    sc_education = ScenarioScore(
        scenario_id="education",
        scores=[
            DimensionScore(dimension="traffic", score=44.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="cost", score=44.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="environmental", score=44.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="accessibility", score=44.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="gap_improvement", score=80.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="social_utility", score=44.0, direction_note="", explanation=make_explanation()),
        ],
        unweighted_composite=50.0,
    )

    sc_healthcare = ScenarioScore(
        scenario_id="healthcare",
        scores=[
            DimensionScore(dimension="traffic", score=52.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="cost", score=52.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="environmental", score=52.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="accessibility", score=52.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="gap_improvement", score=40.0, direction_note="", explanation=make_explanation()),
            DimensionScore(dimension="social_utility", score=52.0, direction_note="", explanation=make_explanation()),
        ],
        unweighted_composite=50.0,
    )

    # Equal weights -> both have composite = 50.0
    ranked = engine.rank([sc_education, sc_healthcare], weights=WeightConfig())

    assert ranked[0].weighted_score == 50.0
    assert ranked[1].weighted_score == 50.0
    # Education has gap=80 vs Healthcare gap=40 -> Education must win the tie-break
    assert ranked[0].scenario_id == "education"
    assert ranked[0].rank == 1
    assert ranked[1].scenario_id == "healthcare"
    assert ranked[1].rank == 2

    # Now test secondary alphabetical tie-breaker:
    # Both commercial and parking with exact same scores on all dimensions
    sc_parking = ScenarioScore(
        scenario_id="parking",
        scores=[
            DimensionScore(dimension=d, score=60.0, direction_note="", explanation=make_explanation())
            for d in ("traffic", "cost", "environmental", "accessibility", "gap_improvement", "social_utility")
        ],
        unweighted_composite=60.0,
    )
    sc_commercial = ScenarioScore(
        scenario_id="commercial",
        scores=[
            DimensionScore(dimension=d, score=60.0, direction_note="", explanation=make_explanation())
            for d in ("traffic", "cost", "environmental", "accessibility", "gap_improvement", "social_utility")
        ],
        unweighted_composite=60.0,
    )

    ranked_alpha = engine.rank([sc_parking, sc_commercial], weights=WeightConfig())
    # 'commercial' < 'parking' alphabetically
    assert ranked_alpha[0].scenario_id == "commercial"
    assert ranked_alpha[1].scenario_id == "parking"


def test_calculation_trace_explainability(baseline_simulation):
    """Verify trace contains both per-scenario explainability and full ranking overview."""
    _, _, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    engine.rank(matrix, scenarios=scenarios)

    # Full trace
    full_trace = engine.get_calculation_trace()
    assert "weights_supplied" in full_trace
    assert "weights_normalized" in full_trace
    assert "ranking_order" in full_trace
    assert "scenarios" in full_trace
    assert len(full_trace["scenarios"]) == 7

    # Single scenario trace
    park_trace = engine.get_calculation_trace("park")
    assert park_trace["scenario_id"] == "park"
    assert "weighted_score" in park_trace
    assert "dimension_contributions" in park_trace
    assert "weights_applied" in park_trace


def test_session_data_integration(baseline_simulation):
    """Verify ranking directly from SessionData updates session.ranking and session.weights_used."""
    urban_ctx, gaps, scenarios, matrix = baseline_simulation
    engine = get_ranking_engine()

    session = SessionData(
        session_id="session-ranking-test",
        plot=SARASWATHIPURAM_PLOT,
        context=urban_ctx,
        gaps=gaps,
        scenarios=scenarios,
        score_matrix=matrix,
    )

    weights = WeightConfig(traffic=1.0, cost=2.0, environmental=1.0, accessibility=1.0, gap_improvement=3.0, social_utility=1.0)
    ranked = engine.rank(session, weights=weights)

    assert isinstance(ranked, list)
    assert len(ranked) == 7
    assert session.ranking is not None
    assert len(session.ranking) == 7
    assert session.weights_used is not None
    assert session.weights_used.gap_improvement == pytest.approx(3.0 / 9.0, abs=1e-5)


def test_dependency_injection():
    """Verify FastAPI dependency injection wiring for get_ranking_engine."""
    dep_instance = get_ranking_engine_dep()
    assert isinstance(dep_instance, RankingEngine)
    assert dep_instance.config is not None

    inst1 = get_ranking_engine()
    inst2 = get_ranking_engine()
    assert inst1 is inst2

    inst3 = get_ranking_engine(force_reload=True)
    assert inst3 is not None
