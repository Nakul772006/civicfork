"""Unit and integration tests for Infrastructure Gap Analyser (Phase 2.3).

Verifies deterministic gap evaluation across all seven canonical categories,
severity formulas, classification boundaries, explainability traces,
cautious semantics, sparse/empty edge cases, and dependency injection.
"""

import pytest
from app.api.dependencies import get_gap_analyzer as get_gap_analyzer_dep
from app.config_loader import get_app_config
from app.models.domain import (
    ContextSummary,
    GAP_CATEGORIES,
    InfrastructureGap,
    PlotLocation,
    POI,
    TransportStop,
    UrbanContext,
)
from app.services.context_analyzer import get_context_analyzer
from app.services.gap_analyzer import (
    GapAnalyzer,
    classify_gap,
    generate_cautious_description,
    get_gap_analyzer,
)

# Reference Saraswathipuram baseline plot from documentation worked example
SARASWATHIPURAM_PLOT = PlotLocation(
    lat=12.3100,
    lng=76.6500,
    radius_m=2000,
    area_sqm=3000.0,
    label="Saraswathipuram Baseline",
)


def _build_synthetic_context(
    plot: PlotLocation,
    pois: list = None,
    transport_stops: list = None,
) -> UrbanContext:
    """Helper to construct synthetic UrbanContext for controlled testing."""
    pois = pois or []
    transport_stops = transport_stops or []
    counts = {}
    for p in pois:
        counts[p.category] = counts.get(p.category, 0) + 1

    summary = ContextSummary(
        total_pois=len(pois),
        poi_counts_by_category=counts,
        poi_density_per_sqkm=len(pois) / 12.56,
        road_network_length_m=5000.0,
        road_density_m_per_sqkm=400.0,
        major_road_count=1,
        nearest_major_road_m=300.0,
        dominant_landuse="residential",
        landuse_distribution={"residential": 100.0},
        residential_pct=100.0,
        commercial_pct=0.0,
        green_space_pct=0.0,
        industrial_pct=0.0,
        transit_stop_count=len(transport_stops),
        nearest_transit_m=transport_stops[0].distance_m if transport_stops else float(plot.radius_m),
        population_density_estimate=5000.0,
        building_density_estimate=0.35,
    )
    return UrbanContext(
        plot=plot,
        pois=pois,
        roads=[],
        landuse_zones=[],
        transport_stops=transport_stops,
        summary=summary,
    )


def test_evaluate_all_seven_categories():
    """Verify that all 7 canonical categories are evaluated in exact approved order."""
    context_analyzer = get_context_analyzer()
    urban_ctx = context_analyzer.analyze(SARASWATHIPURAM_PLOT)

    gap_analyzer = get_gap_analyzer()
    gaps = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx)

    assert len(gaps) == 7
    categories = [g.category for g in gaps]
    assert categories == [
        "healthcare",
        "education",
        "parks",
        "transport",
        "parking",
        "commercial",
        "community",
    ]

    for gap in gaps:
        assert isinstance(gap, InfrastructureGap)
        assert gap.category in GAP_CATEGORIES
        assert gap.gap_type in ("adequate", "distant", "insufficient", "absent")
        assert 0.0 <= gap.gap_severity <= 1.0
        assert gap.coverage_threshold_m > 0
        assert gap.expected_facilities > 0
        assert gap.facilities_in_radius >= 0
        assert len(gap.description) > 0


def test_gap_severity_bounds_and_validity():
    """Verify gap severity values strictly respect [0.0, 1.0] and Pydantic validation."""
    gap_analyzer = get_gap_analyzer()
    context_analyzer = get_context_analyzer()
    urban_ctx = context_analyzer.analyze(SARASWATHIPURAM_PLOT)
    gaps = gap_analyzer.analyze(urban_ctx)

    for gap in gaps:
        assert 0.0 <= gap.gap_severity <= 1.0
        # Re-validate model through Pydantic
        dumped = gap.model_dump()
        revalidated = InfrastructureGap(**dumped)
        assert revalidated.gap_severity == gap.gap_severity


def test_classification_boundaries():
    """Verify exact numerical boundaries for gap_type classification."""
    assert classify_gap(0.0) == "adequate"
    assert classify_gap(0.10) == "adequate"
    assert classify_gap(0.20) == "adequate"

    assert classify_gap(0.2001) == "distant"
    assert classify_gap(0.35) == "distant"
    assert classify_gap(0.50) == "distant"

    assert classify_gap(0.5001) == "insufficient"
    assert classify_gap(0.65) == "insufficient"
    assert classify_gap(0.80) == "insufficient"

    assert classify_gap(0.8001) == "absent"
    assert classify_gap(0.95) == "absent"
    assert classify_gap(1.00) == "absent"


def test_deterministic_repeated_execution():
    """Verify that repeated analysis calls yield strictly identical results."""
    context_analyzer = get_context_analyzer()
    urban_ctx = context_analyzer.analyze(SARASWATHIPURAM_PLOT)

    gap_analyzer = get_gap_analyzer()
    gaps_run1 = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx)
    gaps_run2 = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx)

    assert len(gaps_run1) == len(gaps_run2)
    for g1, g2 in zip(gaps_run1, gaps_run2):
        assert g1.category == g2.category
        assert g1.gap_type == g2.gap_type
        assert g1.gap_severity == g2.gap_severity
        assert g1.facilities_in_radius == g2.facilities_in_radius
        assert g1.nearest_facility_distance_m == g2.nearest_facility_distance_m
        assert g1.nearest_facility_name == g2.nearest_facility_name
        assert g1.description == g2.description


def test_sensitivity_monotonicity():
    """Verify that weaker context increases gap severity while stronger context decreases it."""
    plot = SARASWATHIPURAM_PLOT
    gap_analyzer = get_gap_analyzer()

    # Context 1: Strong healthcare (4 facilities, very close)
    strong_pois = [
        POI(
            osm_id=f"h_{i}",
            name=f"Hospital {i}",
            category="healthcare",
            lat=12.31,
            lng=76.65,
            distance_m=100.0 * (i + 1),
        )
        for i in range(4)
    ]
    strong_ctx = _build_synthetic_context(plot, pois=strong_pois)
    gaps_strong = gap_analyzer.analyze(strong_ctx)
    healthcare_strong = next(g for g in gaps_strong if g.category == "healthcare")

    # Context 2: Weak healthcare (1 facility, far away)
    weak_pois = [
        POI(
            osm_id="h_far",
            name="Far Clinic",
            category="healthcare",
            lat=12.31,
            lng=76.65,
            distance_m=2800.0,
        )
    ]
    weak_ctx = _build_synthetic_context(plot, pois=weak_pois)
    gaps_weak = gap_analyzer.analyze(weak_ctx)
    healthcare_weak = next(g for g in gaps_weak if g.category == "healthcare")

    # Context 3: Absent healthcare (0 facilities)
    absent_ctx = _build_synthetic_context(plot, pois=[])
    gaps_absent = gap_analyzer.analyze(absent_ctx)
    healthcare_absent = next(g for g in gaps_absent if g.category == "healthcare")

    # Verify monotonic progression: Absent > Weak > Strong
    assert healthcare_absent.gap_severity > healthcare_weak.gap_severity
    assert healthcare_weak.gap_severity > healthcare_strong.gap_severity

    assert healthcare_absent.gap_type == "absent"
    assert healthcare_strong.gap_type == "adequate"


def test_explainability_and_calculation_trace():
    """Verify that calculation traces expose intermediate scores, weights, and formulas."""
    context_analyzer = get_context_analyzer()
    urban_ctx = context_analyzer.analyze(SARASWATHIPURAM_PLOT)

    gap_analyzer = get_gap_analyzer()
    gaps = gap_analyzer.analyze(urban_ctx)

    # 1. Verify trace via get_calculation_trace(gap)
    for gap in gaps:
        trace = gap_analyzer.get_calculation_trace(gap)
        assert trace["category"] == gap.category
        assert trace["facilities_in_radius"] == gap.facilities_in_radius
        assert trace["expected_facilities"] == gap.expected_facilities
        assert 0.0 <= trace["coverage_score"] <= 1.0
        assert 0.0 <= trace["proximity_score"] <= 1.0
        assert trace["coverage_weight"] == 0.6
        assert trace["proximity_weight"] == 0.4
        assert 0.0 <= trace["raw_severity"] <= 1.0
        assert trace["gap_severity"] == gap.gap_severity
        assert trace["gap_type"] == gap.gap_type
        assert "1.0 - (0.6 * coverage_score + 0.4 * proximity_score)" in trace["formula"]
        assert "OpenStreetMap" in trace["data_source_caveat"]

        # Check formula consistency: raw_severity = 1.0 - (0.6 * coverage + 0.4 * proximity)
        expected_raw = 1.0 - (0.6 * trace["coverage_score"] + 0.4 * trace["proximity_score"])
        assert trace["raw_severity"] == pytest.approx(expected_raw, abs=1e-4)

    # 2. Verify trace via category string lookup
    trace_by_str = gap_analyzer.get_calculation_trace("healthcare")
    assert trace_by_str["category"] == "healthcare"

    # 3. Verify last_traces property contains all 7 categories
    assert len(gap_analyzer.last_traces) == 7
    for cat in GAP_CATEGORIES:
        assert cat in gap_analyzer.last_traces

    # 4. Unknown category raises KeyError
    with pytest.raises(KeyError):
        gap_analyzer.get_calculation_trace("nonexistent_category")


def test_cautious_semantic_descriptions():
    """Verify descriptions explicitly frame findings in OSM observation and avoid real-world falsehoods."""
    context_analyzer = get_context_analyzer()
    urban_ctx = context_analyzer.analyze(SARASWATHIPURAM_PLOT)

    gap_analyzer = get_gap_analyzer()
    gaps = gap_analyzer.analyze(urban_ctx)

    for gap in gaps:
        desc = gap.description
        # All descriptions must attribute evidence to OSM or context
        assert any(
            phrase in desc
            for phrase in ("OSM-observed", "Context-indicated", "cached OSM data", "OSM")
        )

        if gap.gap_type == "absent":
            # For absent gaps, must caution that real-world facilities may exist outside cached OSM
            assert "Unmapped real-world facilities may exist" in desc
            assert "cached open records" in desc
            assert "potential municipal service gap" in desc
        elif gap.gap_type == "adequate":
            assert "adequate" in desc.lower()
        elif gap.gap_type == "insufficient":
            assert "deficit" in desc.lower()
        elif gap.gap_type == "distant":
            assert "service lag" in desc.lower()


def test_sparse_and_empty_context_handling():
    """Verify that an empty urban context gracefully returns absent gaps without crashing."""
    empty_ctx = _build_synthetic_context(SARASWATHIPURAM_PLOT, pois=[], transport_stops=[])
    gap_analyzer = get_gap_analyzer()
    gaps = gap_analyzer.analyze(empty_ctx)

    assert len(gaps) == 7
    for gap in gaps:
        assert gap.gap_severity == 1.0
        assert gap.gap_type == "absent"
        assert gap.facilities_in_radius == 0
        assert gap.nearest_facility_name is None
        assert gap.nearest_facility_distance_m is None
        assert "No " in gap.description
        assert "Unmapped real-world facilities may exist" in gap.description


def test_context_summary_only_input():
    """Verify analyzer operates correctly when provided only a ContextSummary."""
    context_analyzer = get_context_analyzer()
    urban_ctx = context_analyzer.analyze(SARASWATHIPURAM_PLOT)

    gap_analyzer = get_gap_analyzer()
    # Pass PlotLocation and ContextSummary directly
    gaps = gap_analyzer.analyze(SARASWATHIPURAM_PLOT, urban_ctx.summary)

    assert len(gaps) == 7
    for gap in gaps:
        assert isinstance(gap, InfrastructureGap)
        assert 0.0 <= gap.gap_severity <= 1.0


def test_dependency_injection():
    """Verify FastAPI dependency injection wiring for get_gap_analyzer."""
    dep_instance = get_gap_analyzer_dep()
    assert isinstance(dep_instance, GapAnalyzer)
    assert dep_instance.config is not None

    # Verify singleton behavior and reload
    inst1 = get_gap_analyzer()
    inst2 = get_gap_analyzer()
    assert inst1 is inst2

    inst3 = get_gap_analyzer(force_reload=True)
    assert inst3 is not None
