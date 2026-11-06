"""Unit and integration tests for Scenario Generator (Phase 2.4).

Verifies deterministic scenario generation across all seven canonical policy options,
configuration-driven estimation, gap association, explainability provenance traces,
handling of sparse context / missing gaps, and dependency injection.
"""

import pytest
from app.api.dependencies import get_scenario_generator as get_scenario_generator_dep
from app.config_loader import get_app_config
from app.models.domain import (
    ContextSummary,
    InfrastructureGap,
    PlotLocation,
    SCENARIO_IDS,
    Scenario,
    UrbanContext,
)
from app.services.context_analyzer import get_context_analyzer
from app.services.gap_analyzer import get_gap_analyzer
from app.services.scenario_generator import (
    ORDERED_SCENARIO_IDS,
    SCENARIO_PRIMARY_GAP,
    ScenarioGenerator,
    get_scenario_generator,
)

# Reference Saraswathipuram plot from documentation worked example
SARASWATHIPURAM_PLOT = PlotLocation(
    lat=12.3100,
    lng=76.6500,
    radius_m=2000,
    area_sqm=3000.0,
    label="Saraswathipuram Baseline",
)


@pytest.fixture
def baseline_context_and_gaps():
    """Produce authoritative context and gaps for Saraswathipuram baseline."""
    ctx_analyzer = get_context_analyzer()
    gap_analyzer = get_gap_analyzer()

    urban_ctx = ctx_analyzer.analyze(SARASWATHIPURAM_PLOT)
    gaps = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx)
    return urban_ctx, gaps


def test_exactly_seven_canonical_scenarios_generated(baseline_context_and_gaps):
    """Verify that exactly 7 scenarios are generated in approved canonical order."""
    urban_ctx, gaps = baseline_context_and_gaps
    generator = get_scenario_generator()

    scenarios = generator.generate(urban_ctx, gaps)

    assert len(scenarios) == 7
    generated_ids = [s.id for s in scenarios]
    assert generated_ids == list(ORDERED_SCENARIO_IDS)
    assert generated_ids == [
        "park",
        "healthcare",
        "education",
        "parking",
        "commercial",
        "community_centre",
        "public_transport",
    ]


def test_unique_scenario_ids(baseline_context_and_gaps):
    """Verify that each scenario in the returned list has a distinct, unique scenario ID."""
    urban_ctx, gaps = baseline_context_and_gaps
    generator = get_scenario_generator()

    scenarios = generator.generate(urban_ctx, gaps)
    ids = [s.id for s in scenarios]
    assert len(set(ids)) == 7
    for sid in ids:
        assert sid in SCENARIO_IDS


def test_every_scenario_maps_to_correct_gap(baseline_context_and_gaps):
    """Verify that each scenario correctly associates with its primary InfrastructureGap."""
    urban_ctx, gaps = baseline_context_and_gaps
    generator = get_scenario_generator()

    scenarios = generator.generate(urban_ctx, gaps)
    gaps_by_cat = {g.category: g for g in gaps}

    for scenario in scenarios:
        expected_primary_gap = SCENARIO_PRIMARY_GAP[scenario.id]
        assert scenario.attributes.get("associated_gap_category") == expected_primary_gap

        associated_gap = gaps_by_cat[expected_primary_gap]
        assert scenario.attributes.get("primary_gap_severity") == associated_gap.gap_severity
        assert scenario.attributes.get("primary_gap_type") == associated_gap.gap_type

        # Verify traces also reflect this association
        trace = generator.get_scenario_trace(scenario.id)
        assert trace["associated_gap"]["category"] == expected_primary_gap
        assert trace["associated_gap"]["gap_severity"] == associated_gap.gap_severity


def test_scenarios_yaml_values_are_consumed(baseline_context_and_gaps):
    """Verify that scenario parameters are strictly consumed from scenarios.yaml via AppConfig."""
    urban_ctx, gaps = baseline_context_and_gaps
    config = get_app_config()
    generator = get_scenario_generator(config=config)

    scenarios = generator.generate(urban_ctx, gaps)
    templates = config.scenarios.scenarios

    for scenario in scenarios:
        template = templates[scenario.id]
        assert scenario.name == template.name
        assert scenario.description == template.description
        assert scenario.category == template.category
        assert scenario.addresses_gaps == list(template.addresses_gaps)

        # Check that attributes preserve YAML defined attributes
        for k, v in template.attributes.items():
            assert scenario.attributes[k] == v

        # Check formula consumption: cost = proposed_area * cost_per_sqm
        expected_cost = round(scenario.proposed_area_sqm * template.cost_per_sqm, 2)
        assert scenario.estimated_cost_inr == expected_cost

        # Operating cost = cost * operating_ratio
        expected_operating = round(expected_cost * template.operating_ratio, 2)
        assert scenario.estimated_annual_operating_cost_inr == expected_operating

        # Surface deltas
        assert scenario.green_space_delta_sqm == round(template.green_ratio * scenario.proposed_area_sqm, 1)
        assert scenario.impervious_surface_delta_sqm == round(
            template.impervious_ratio * scenario.proposed_area_sqm, 1
        )


def test_deterministic_repeated_generation(baseline_context_and_gaps):
    """Verify that repeated generations produce bitwise-identical scenario definitions."""
    urban_ctx, gaps = baseline_context_and_gaps
    generator = get_scenario_generator()

    run1 = generator.generate(urban_ctx, gaps)
    run2 = generator.generate(urban_ctx, gaps)

    assert len(run1) == len(run2)
    for s1, s2 in zip(run1, run2):
        assert s1.id == s2.id
        assert s1.name == s2.name
        assert s1.proposed_area_sqm == s2.proposed_area_sqm
        assert s1.estimated_cost_inr == s2.estimated_cost_inr
        assert s1.estimated_annual_operating_cost_inr == s2.estimated_annual_operating_cost_inr
        assert s1.estimated_daily_visitors == s2.estimated_daily_visitors
        assert s1.estimated_jobs_created == s2.estimated_jobs_created
        assert s1.estimated_traffic_change_pct == s2.estimated_traffic_change_pct
        assert s1.green_space_delta_sqm == s2.green_space_delta_sqm
        assert s1.impervious_surface_delta_sqm == s2.impervious_surface_delta_sqm
        assert s1.attributes == s2.attributes


def test_missing_gap_data_handled_safely():
    """Verify that scenario generation gracefully handles None or empty gaps."""
    ctx_analyzer = get_context_analyzer()
    urban_ctx = ctx_analyzer.analyze(SARASWATHIPURAM_PLOT)
    generator = get_scenario_generator()

    # Pass None for gaps
    scenarios = generator.generate(urban_ctx, gaps=None)
    assert len(scenarios) == 7
    for s in scenarios:
        assert s.attributes.get("primary_gap_severity") is None
        assert s.attributes.get("primary_gap_type") is None
        assert s.attributes.get("associated_gap_category") in SCENARIO_PRIMARY_GAP.values()
        trace = generator.get_scenario_trace(s)
        assert trace["associated_gap"] is None

    # Pass empty list for gaps
    scenarios_empty = generator.generate(urban_ctx, gaps=[])
    assert len(scenarios_empty) == 7


def test_sparse_urban_context_does_not_crash():
    """Verify that empty / sparse UrbanContext executes without division by zero or errors."""
    plot = PlotLocation(lat=12.3100, lng=76.6500, radius_m=2000, area_sqm=1000.0)
    sparse_summary = ContextSummary(
        total_pois=0,
        poi_counts_by_category={},
        poi_density_per_sqkm=0.0,
        road_network_length_m=0.0,
        road_density_m_per_sqkm=0.0,
        major_road_count=0,
        nearest_major_road_m=2000.0,
        dominant_landuse="residential",
        landuse_distribution={},
        residential_pct=0.0,
        commercial_pct=0.0,
        green_space_pct=0.0,
        industrial_pct=0.0,
        transit_stop_count=0,
        nearest_transit_m=2000.0,
        population_density_estimate=0.0,
        building_density_estimate=0.0,
    )
    sparse_ctx = UrbanContext(
        plot=plot,
        pois=[],
        roads=[],
        landuse_zones=[],
        transport_stops=[],
        summary=sparse_summary,
    )

    generator = get_scenario_generator()
    scenarios = generator.generate(sparse_ctx, gaps=[])

    assert len(scenarios) == 7
    for s in scenarios:
        assert s.proposed_area_sqm == 1000.0
        assert s.estimated_daily_visitors == 0  # 0 pop density -> 0 factor
        assert s.estimated_traffic_change_pct == 0.0
        assert s.estimated_jobs_created >= 0
        assert s.estimated_cost_inr > 0


def test_future_impact_simulator_fields_present():
    """Verify all fields required by downstream Impact Simulator and Feasibility Checker are populated."""
    ctx_analyzer = get_context_analyzer()
    urban_ctx = ctx_analyzer.analyze(SARASWATHIPURAM_PLOT)
    generator = get_scenario_generator()

    scenarios = generator.generate(urban_ctx)

    for s in scenarios:
        assert isinstance(s.required_area_sqm, float) and s.required_area_sqm > 0
        assert isinstance(s.proposed_area_sqm, float) and s.proposed_area_sqm > 0
        assert isinstance(s.estimated_cost_inr, float) and s.estimated_cost_inr >= 0
        assert isinstance(s.estimated_annual_operating_cost_inr, float) and s.estimated_annual_operating_cost_inr >= 0
        assert isinstance(s.estimated_daily_visitors, int) and s.estimated_daily_visitors >= 0
        assert isinstance(s.estimated_jobs_created, int) and s.estimated_jobs_created >= 0
        assert isinstance(s.estimated_traffic_change_pct, float)
        assert isinstance(s.green_space_delta_sqm, float)
        assert isinstance(s.impervious_surface_delta_sqm, float)
        assert isinstance(s.addresses_gaps, list) and len(s.addresses_gaps) > 0

        # Required downstream simulation coefficients in attributes
        assert "trip_rate" in s.attributes
        assert "operating_ratio" in s.attributes
        assert "cost_per_sqm" in s.attributes
        assert "ref_area_sqm" in s.attributes
        assert "revenue_generating" in s.attributes


def test_no_final_scores_or_rankings_produced():
    """Verify that ScenarioGenerator produces NO scores, composite ranking, or feasibility verdicts."""
    ctx_analyzer = get_context_analyzer()
    urban_ctx = ctx_analyzer.analyze(SARASWATHIPURAM_PLOT)
    generator = get_scenario_generator()

    scenarios = generator.generate(urban_ctx)

    # Scenarios must be purely scenario alternatives, without scores or ranks
    for s in scenarios:
        scenario_dict = s.model_dump()
        assert "score" not in scenario_dict
        assert "scores" not in scenario_dict
        assert "composite_score" not in scenario_dict
        assert "rank" not in scenario_dict
        assert "is_feasible" not in scenario_dict
        assert "verdict" not in scenario_dict


def test_traceability_and_provenance():
    """Verify generator-level trace exposes configured, observed, and modelled parameters."""
    ctx_analyzer = get_context_analyzer()
    gap_analyzer = get_gap_analyzer()

    urban_ctx = ctx_analyzer.analyze(SARASWATHIPURAM_PLOT)
    gaps = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx)
    generator = get_scenario_generator()

    scenarios = generator.generate(urban_ctx, gaps)

    assert len(generator.last_traces) == 7
    for s in scenarios:
        trace = generator.get_scenario_trace(s.id)
        assert trace["scenario_id"] == s.id
        assert trace["template_source"] == "scenarios.yaml"
        assert "configured_params" in trace
        assert "observed_context" in trace
        assert "modelled_estimations" in trace
        assert "data_integrity_notes" in trace

        # Check distinction between observed and modelled
        notes = trace["data_integrity_notes"]
        assert "scenarios.yaml" in notes["configured"]
        assert "OSM observations" in notes["observed"]
        assert "rule-based model estimates" in notes["modelled"]
        assert "Impact Simulator" in notes["calculated_impacts"]


def test_dependency_injection():
    """Verify FastAPI dependency injection wiring for get_scenario_generator."""
    dep_instance = get_scenario_generator_dep()
    assert isinstance(dep_instance, ScenarioGenerator)
    assert dep_instance.config is not None

    inst1 = get_scenario_generator()
    inst2 = get_scenario_generator()
    assert inst1 is inst2

    inst3 = get_scenario_generator(force_reload=True)
    assert inst3 is not None
