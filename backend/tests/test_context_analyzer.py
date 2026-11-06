"""Tests for Urban Context Analyser service (Phase 2.2)."""

import pytest
from unittest.mock import MagicMock

from app.api.dependencies import get_analyzer
from app.models.domain import (
    ContextSummary,
    PlotLocation,
    UrbanContext,
)
from app.services.context_analyzer import ContextAnalyzer, get_context_analyzer
from app.services.osm_service import OSMServiceBase, get_osm_service

SARASWATHIPURAM_LAT = 12.3100
SARASWATHIPURAM_LNG = 76.6500


@pytest.fixture
def valid_plot():
    return PlotLocation(
        lat=SARASWATHIPURAM_LAT,
        lng=SARASWATHIPURAM_LNG,
        radius_m=2000,
        area_sqm=3000.0,
        label="Saraswathipuram Test Plot",
    )


# -----------------------------------------------------------------------------
# Urban Context Analysis Execution Tests
# -----------------------------------------------------------------------------

def test_context_analysis_valid_plot(valid_plot):
    """Verify context analyzer returns valid UrbanContext and ContextSummary."""
    analyzer = get_context_analyzer()
    context = analyzer.analyze(valid_plot)

    # 1. Structural validation
    assert isinstance(context, UrbanContext)
    assert isinstance(context.summary, ContextSummary)
    assert context.plot == valid_plot

    # 2. Raw features populated in UrbanContext (50 features in Saraswathipuram 2000m buffer)
    assert len(context.pois) == 50
    assert len(context.roads) > 0
    assert len(context.landuse_zones) > 0
    assert len(context.transport_stops) == 3

    # 3. Summary metrics populated
    s = context.summary
    assert s.total_pois == 50
    assert s.poi_density_per_sqkm > 0.0
    assert s.road_network_length_m > 0.0
    assert s.road_density_m_per_sqkm > 0.0
    assert s.major_road_count > 0
    assert s.nearest_major_road_m >= 0.0
    assert s.dominant_landuse == "residential"
    assert s.residential_pct == 65.0
    assert s.commercial_pct == 19.2
    assert s.green_space_pct == 11.2
    assert s.industrial_pct == 4.6
    assert s.transit_stop_count == 3
    assert 590.0 <= s.nearest_transit_m <= 610.0
    assert 0.0 <= s.building_density_estimate <= 1.0
    assert s.population_density_estimate > 0.0


def test_radius_affects_context(valid_plot):
    """Verify expanding the analysis radius retrieves more features."""
    analyzer = get_context_analyzer()

    ctx_1000 = analyzer.analyze(valid_plot, radius_m=1000)
    ctx_2000 = analyzer.analyze(valid_plot, radius_m=2000)
    ctx_5000 = analyzer.analyze(valid_plot, radius_m=5000)

    # POI count should increase monotonically
    assert ctx_1000.summary.total_pois <= ctx_2000.summary.total_pois
    assert ctx_2000.summary.total_pois <= ctx_5000.summary.total_pois

    # Road network length should increase monotonically
    assert ctx_1000.summary.road_network_length_m <= ctx_2000.summary.road_network_length_m
    assert ctx_2000.summary.road_network_length_m <= ctx_5000.summary.road_network_length_m


def test_poi_category_aggregation(valid_plot):
    """Verify sum of categorical POI counts equals total_pois."""
    analyzer = get_context_analyzer()
    context = analyzer.analyze(valid_plot)

    s = context.summary
    cat_counts = s.poi_counts_by_category
    assert isinstance(cat_counts, dict)
    assert sum(cat_counts.values()) == s.total_pois
    assert len(context.pois) == s.total_pois


def test_nearest_facility_extraction(valid_plot):
    """Verify POIs and transit stops are sorted by distance."""
    analyzer = get_context_analyzer()
    context = analyzer.analyze(valid_plot)

    # POIs should be sorted ascending by distance
    poi_distances = [p.distance_m for p in context.pois]
    assert poi_distances == sorted(poi_distances)

    # Nearest transit matches summary
    transit_distances = [t.distance_m for t in context.transport_stops]
    assert transit_distances == sorted(transit_distances)
    assert context.summary.nearest_transit_m == transit_distances[0]


def test_landuse_composition_metrics(valid_plot):
    """Verify land-use composition percentages sum to realistic bounds."""
    analyzer = get_context_analyzer()
    context = analyzer.analyze(valid_plot)

    s = context.summary
    assert s.dominant_landuse in s.landuse_distribution
    assert 0.0 <= s.residential_pct <= 100.0
    assert 0.0 <= s.commercial_pct <= 100.0
    assert 0.0 <= s.green_space_pct <= 100.0
    assert 0.0 <= s.industrial_pct <= 100.0


def test_deterministic_repeated_analysis(valid_plot):
    """Verify repeated calls on the same plot produce strictly identical outputs."""
    analyzer = get_context_analyzer()

    ctx1 = analyzer.analyze(valid_plot)
    ctx2 = analyzer.analyze(valid_plot)

    assert ctx1.summary.model_dump() == ctx2.summary.model_dump()
    assert len(ctx1.pois) == len(ctx2.pois)
    for p1, p2 in zip(ctx1.pois, ctx2.pois):
        assert p1.osm_id == p2.osm_id
        assert p1.distance_m == p2.distance_m


def test_context_summary_is_compact(valid_plot):
    """Verify ContextSummary contains only scalar metrics, not raw feature lists."""
    analyzer = get_context_analyzer()
    context = analyzer.analyze(valid_plot)
    summary = context.summary

    # Ensure raw geometry collections do NOT leak into ContextSummary
    forbidden_keys = {"pois", "roads", "landuse_zones", "transport_stops", "geometry"}
    summary_fields = set(ContextSummary.model_fields.keys())
    assert not (forbidden_keys & summary_fields)

    # ContextSummary serializes to a clean, compact payload
    dumped = summary.model_dump()
    assert isinstance(dumped["total_pois"], int)
    assert isinstance(dumped["poi_counts_by_category"], dict)
    assert isinstance(dumped["dominant_landuse"], str)
    assert isinstance(dumped["residential_pct"], float)


# -----------------------------------------------------------------------------
# Edge Cases & Sparse Context Tests
# -----------------------------------------------------------------------------

def test_sparse_or_empty_context_handling():
    """Verify analyzer gracefully handles an area with zero OSM features."""
    mock_osm = MagicMock(spec=OSMServiceBase)
    mock_osm.is_loaded.return_value = True
    mock_osm.get_pois.return_value = []
    mock_osm.get_poi_counts.return_value = {}
    mock_osm.get_roads.return_value = []
    mock_osm.get_nearest_major_road.return_value = None
    mock_osm.get_landuse.return_value = []
    mock_osm.get_transport_stops.return_value = []
    mock_osm.get_nearest_transport_stop.return_value = None

    analyzer = ContextAnalyzer(osm_service=mock_osm)
    plot = PlotLocation(lat=12.2500, lng=76.6000, radius_m=1000)

    context = analyzer.analyze(plot)

    assert isinstance(context, UrbanContext)
    assert context.summary.total_pois == 0
    assert context.summary.poi_density_per_sqkm == 0.0
    assert context.summary.road_network_length_m == 0.0
    assert context.summary.road_density_m_per_sqkm == 0.0
    assert context.summary.major_road_count == 0
    assert context.summary.transit_stop_count == 0
    assert context.summary.residential_pct == 0.0
    assert context.summary.commercial_pct == 0.0
    assert context.summary.green_space_pct == 0.0
    assert context.summary.industrial_pct == 0.0
    assert context.summary.building_density_estimate == 0.0
    assert context.summary.population_density_estimate == 0.0


# -----------------------------------------------------------------------------
# Dependency Injection Tests
# -----------------------------------------------------------------------------

def test_context_analyzer_dependency():
    """Verify get_analyzer dependency returns a functional ContextAnalyzer."""
    analyzer = get_analyzer()
    assert isinstance(analyzer, ContextAnalyzer)
    assert isinstance(analyzer.osm_service, OSMServiceBase)
