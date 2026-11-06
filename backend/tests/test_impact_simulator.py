"""Unit and integration tests for Impact Simulation Engine (Phase 2.5).

Verifies multi-dimensional scoring across all 7 scenarios and 6 dimensions,
bounds checking (0-100), higher-is-better monotonicity, gap relevance weighting,
explainability calculation traces, edge case stability, and session integration.
"""

import copy
import math
import pytest
from app.api.dependencies import get_impact_simulator as get_impact_simulator_dep
from app.config_loader import get_app_config
from app.models.domain import (
    ContextSummary,
    DIMENSION_NAMES,
    DimensionScore,
    InfrastructureGap,
    PlotLocation,
    SCENARIO_IDS,
    Scenario,
    ScenarioScore,
    ScoreMatrix,
    SessionData,
    UrbanContext,
)
from app.services.context_analyzer import get_context_analyzer
from app.services.gap_analyzer import get_gap_analyzer
from app.services.impact_simulator import (
    ImpactSimulator,
    clamp_score,
    get_impact_simulator,
)
from app.services.scenario_generator import get_scenario_generator

# Reference Saraswathipuram plot from documentation worked example
SARASWATHIPURAM_PLOT = PlotLocation(
    lat=12.3100,
    lng=76.6500,
    radius_m=2000,
    area_sqm=3000.0,
    label="Saraswathipuram Baseline",
)


@pytest.fixture
def baseline_pipeline():
    """Run Phase 2.1 - 2.4 pipeline to produce authoritative inputs for simulation."""
    ctx_analyzer = get_context_analyzer()
    gap_analyzer = get_gap_analyzer()
    scen_generator = get_scenario_generator()

    urban_ctx = ctx_analyzer.analyze(SARASWATHIPURAM_PLOT)
    gaps = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx)
    scenarios = scen_generator.generate(SARASWATHIPURAM_PLOT, urban_ctx, gaps)
    return urban_ctx, gaps, scenarios


def test_all_seven_scenarios_produce_scores(baseline_pipeline):
    """Verify that all 7 canonical scenarios produce complete simulation scores."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    matrix = simulator.simulate_all(scenarios, urban_ctx, gaps)

    assert isinstance(matrix, ScoreMatrix)
    assert len(matrix.scenario_scores) == 7
    assert matrix.scenarios_evaluated == 7
    assert matrix.dimensions_evaluated == 6
    assert len(matrix.matrix) == 7

    for idx, sc_score in enumerate(matrix.scenario_scores):
        assert isinstance(sc_score, ScenarioScore)
        assert sc_score.scenario_id in SCENARIO_IDS
        assert len(matrix.matrix[idx]) == 6


def test_every_scenario_has_exactly_six_dimensions(baseline_pipeline):
    """Verify that every scenario contains exactly the 6 approved dimensions in order."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    matrix = simulator.simulate_all(scenarios, urban_ctx, gaps)

    for sc_score in matrix.scenario_scores:
        assert len(sc_score.scores) == 6
        dim_names = [d.dimension for d in sc_score.scores]
        assert dim_names == list(DIMENSION_NAMES)
        assert dim_names == [
            "traffic",
            "cost",
            "environmental",
            "accessibility",
            "gap_improvement",
            "social_utility",
        ]


def test_every_dimension_score_strictly_within_0_to_100(baseline_pipeline):
    """Verify all dimension scores and composite means stay strictly in [0.0, 100.0]."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    matrix = simulator.simulate_all(scenarios, urban_ctx, gaps)

    for sc_score in matrix.scenario_scores:
        assert 0.0 <= sc_score.unweighted_composite <= 100.0
        for dim_score in sc_score.scores:
            assert isinstance(dim_score, DimensionScore)
            assert 0.0 <= dim_score.score <= 100.0
            assert 0.0 <= dim_score.explanation.normalised_result <= 100.0
            assert "Higher = " in dim_score.direction_note


def test_deterministic_repeated_simulation(baseline_pipeline):
    """Verify that simulating identical inputs produces strictly identical results."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    matrix1 = simulator.simulate_all(scenarios, urban_ctx, gaps)
    matrix2 = simulator.simulate_all(scenarios, urban_ctx, gaps)

    assert matrix1.matrix == matrix2.matrix
    for s1, s2 in zip(matrix1.scenario_scores, matrix2.scenario_scores):
        assert s1.scenario_id == s2.scenario_id
        assert s1.unweighted_composite == s2.unweighted_composite
        for d1, d2 in zip(s1.scores, s2.scores):
            assert d1.dimension == d2.dimension
            assert d1.score == d2.score
            assert d1.explanation.formula_description == d2.explanation.formula_description


def test_traffic_score_monotonicity(baseline_pipeline):
    """Verify lower traffic burden produces a higher (better) Traffic score."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    base_scenario = next(s for s in scenarios if s.id == "commercial")

    # Scenario A: Low visitor traffic
    scen_low_traffic = base_scenario.model_copy(deep=True)
    scen_low_traffic.estimated_daily_visitors = 100

    # Scenario B: Heavy visitor traffic
    scen_high_traffic = base_scenario.model_copy(deep=True)
    scen_high_traffic.estimated_daily_visitors = 5000

    score_low = simulator.simulate_scenario(scen_low_traffic, urban_ctx, gaps)
    score_high = simulator.simulate_scenario(scen_high_traffic, urban_ctx, gaps)

    traffic_low = next(d.score for d in score_low.scores if d.dimension == "traffic")
    traffic_high = next(d.score for d in score_high.scores if d.dimension == "traffic")

    assert traffic_low > traffic_high


def test_cost_score_monotonicity(baseline_pipeline):
    """Verify lower financial/area burden produces a higher (better) Cost score."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    base_scenario = next(s for s in scenarios if s.id == "healthcare")

    # Scenario Small: proposed area matches reference area (no area scaling penalty)
    scen_small = base_scenario.model_copy(deep=True)
    scen_small.proposed_area_sqm = scen_small.attributes["ref_area_sqm"]

    # Scenario Large: proposed area far exceeds reference area (max area scaling penalty)
    scen_large = base_scenario.model_copy(deep=True)
    scen_large.proposed_area_sqm = scen_large.attributes["ref_area_sqm"] * 3.0

    score_small = simulator.simulate_scenario(scen_small, urban_ctx, gaps)
    score_large = simulator.simulate_scenario(scen_large, urban_ctx, gaps)

    cost_small = next(d.score for d in score_small.scores if d.dimension == "cost")
    cost_large = next(d.score for d in score_large.scores if d.dimension == "cost")

    assert cost_small > cost_large


def test_environmental_score_monotonicity(baseline_pipeline):
    """Verify increased green space and reduced paving improves Environmental score."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    base_scenario = next(s for s in scenarios if s.id == "park")

    # Scenario Green: mostly green space, minimal pavement
    scen_green = base_scenario.model_copy(deep=True)
    scen_green.green_space_delta_sqm = 2500.0
    scen_green.impervious_surface_delta_sqm = 100.0

    # Scenario Paved: zero green space, fully paved
    scen_paved = base_scenario.model_copy(deep=True)
    scen_paved.green_space_delta_sqm = 0.0
    scen_paved.impervious_surface_delta_sqm = 2500.0

    score_green = simulator.simulate_scenario(scen_green, urban_ctx, gaps)
    score_paved = simulator.simulate_scenario(scen_paved, urban_ctx, gaps)

    env_green = next(d.score for d in score_green.scores if d.dimension == "environmental")
    env_paved = next(d.score for d in score_paved.scores if d.dimension == "environmental")

    assert env_green > env_paved


def test_gap_improvement_score_reflects_severity(baseline_pipeline):
    """Verify higher gap severity rewards scenarios that specifically address that gap."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    hospital_scen = next(s for s in scenarios if s.id == "healthcare")

    # Severe healthcare gap
    gaps_severe = [
        InfrastructureGap(
            category="healthcare",
            gap_type="absent",
            coverage_threshold_m=3000.0,
            facilities_in_radius=0,
            expected_facilities=3,
            gap_severity=1.0,
            description="Critical healthcare gap",
        ),
        InfrastructureGap(
            category="education",
            gap_type="adequate",
            coverage_threshold_m=1500.0,
            facilities_in_radius=4,
            expected_facilities=4,
            gap_severity=0.0,
            description="Adequate education",
        ),
    ]

    # No healthcare gap (well served), but severe education gap
    gaps_mild = [
        InfrastructureGap(
            category="healthcare",
            gap_type="adequate",
            coverage_threshold_m=3000.0,
            facilities_in_radius=5,
            expected_facilities=3,
            gap_severity=0.0,
            description="Adequate healthcare",
        ),
        InfrastructureGap(
            category="education",
            gap_type="absent",
            coverage_threshold_m=1500.0,
            facilities_in_radius=0,
            expected_facilities=4,
            gap_severity=1.0,
            description="Critical education gap",
        ),
    ]

    score_severe = simulator.simulate_scenario(hospital_scen, urban_ctx, gaps_severe)
    score_mild = simulator.simulate_scenario(hospital_scen, urban_ctx, gaps_mild)

    gap_severe = next(d.score for d in score_severe.scores if d.dimension == "gap_improvement")
    gap_mild = next(d.score for d in score_mild.scores if d.dimension == "gap_improvement")

    # Hospital addressing critical healthcare gap gets 100%; addressing no healthcare gap gets ~10%
    assert gap_severe > gap_mild
    assert gap_severe == 100.0


def test_calculation_traces_exist_for_all_dimensions(baseline_pipeline):
    """Verify simulator-level trace exposes structured explainability for each dimension."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    simulator.simulate_all(scenarios, urban_ctx, gaps)

    assert len(simulator.last_traces) == 7
    for sid in SCENARIO_IDS:
        trace = simulator.get_calculation_trace(sid)
        assert trace["scenario_id"] == sid
        assert "unweighted_composite" in trace
        assert "dimensions" in trace
        assert len(trace["dimensions"]) == 6

        for dim in DIMENSION_NAMES:
            dim_trace = trace["dimensions"][dim]
            assert "score" in dim_trace
            assert "raw_result" in dim_trace
            assert "formula_description" in dim_trace
            assert "input_factors" in dim_trace
            assert "intermediate_values" in dim_trace


def test_no_weighted_ranking_performed(baseline_pipeline):
    """Verify that ImpactSimulator produces NO weighted composite scores or scenario ranks."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    matrix = simulator.simulate_all(scenarios, urban_ctx, gaps)

    # Matrix should only contain scenario_scores and raw 7x6 matrix
    matrix_dict = matrix.model_dump()
    assert "ranking" not in matrix_dict
    assert "rank" not in matrix_dict
    assert "weights_used" not in matrix_dict

    for sc_score in matrix.scenario_scores:
        sc_dict = sc_score.model_dump()
        assert "rank" not in sc_dict
        assert "weighted_score" not in sc_dict
        # Only unweighted mean is present
        assert "unweighted_composite" in sc_dict


def test_sparse_and_edge_inputs_stability():
    """Verify extreme/sparse inputs do not produce NaN, inf, or out-of-bounds scores."""
    simulator = get_impact_simulator()

    # Extreme scenario with zeros and huge numbers
    extreme_scenario = Scenario(
        id="park",
        name="Extreme Park",
        description="Edge testing",
        category="green_space",
        required_area_sqm=10.0,
        proposed_area_sqm=100000.0,
        estimated_cost_inr=0.0,
        estimated_annual_operating_cost_inr=0.0,
        estimated_daily_visitors=0,
        estimated_jobs_created=0,
        estimated_traffic_change_pct=0.0,
        green_space_delta_sqm=0.0,
        impervious_surface_delta_sqm=0.0,
        addresses_gaps=[],
        attributes={"trip_rate": 0.0, "ref_area_sqm": 0.0, "revenue_generating": False},
    )

    empty_summary = ContextSummary(
        total_pois=0,
        poi_counts_by_category={},
        poi_density_per_sqkm=0.0,
        road_network_length_m=0.0,
        road_density_m_per_sqkm=0.0,
        major_road_count=0,
        nearest_major_road_m=10000.0,
        dominant_landuse="residential",
        landuse_distribution={},
        residential_pct=0.0,
        commercial_pct=0.0,
        green_space_pct=0.0,
        industrial_pct=0.0,
        transit_stop_count=0,
        nearest_transit_m=10000.0,
        population_density_estimate=0.0,
        building_density_estimate=0.0,
    )

    score = simulator.simulate_scenario(extreme_scenario, empty_summary, gaps=[])

    assert 0.0 <= score.unweighted_composite <= 100.0
    for dim_score in score.scores:
        assert 0.0 <= dim_score.score <= 100.0
        assert not math.isnan(dim_score.score)
        assert not math.isinf(dim_score.score)


def test_session_data_integration(baseline_pipeline):
    """Verify that simulate(session) accepts SessionData and attaches score_matrix."""
    urban_ctx, gaps, scenarios = baseline_pipeline
    simulator = get_impact_simulator()

    session = SessionData(
        session_id="test-session-123",
        plot=SARASWATHIPURAM_PLOT,
        context=urban_ctx,
        gaps=gaps,
        scenarios=scenarios,
    )

    matrix = simulator.simulate(session)

    assert isinstance(matrix, ScoreMatrix)
    assert session.score_matrix is not None
    assert session.score_matrix.scenarios_evaluated == 7
    assert session.score_matrix.matrix == matrix.matrix


def test_dependency_injection():
    """Verify FastAPI dependency injection wiring for get_impact_simulator."""
    dep_instance = get_impact_simulator_dep()
    assert isinstance(dep_instance, ImpactSimulator)
    assert dep_instance.config is not None

    inst1 = get_impact_simulator()
    inst2 = get_impact_simulator()
    assert inst1 is inst2

    inst3 = get_impact_simulator(force_reload=True)
    assert inst3 is not None
