"""Regression tests for outer Mysuru spatial data enrichment.

Verifies:
1. Land use enrichment resolves residential coverage and non-zero population density
   in outer presets (Vijayanagar, Hebbal).
2. Elimination of false 100% industrial dominance and false zoning feasibility conflicts.
3. Road network connectivity, road density, and major road proximity in outer presets.
4. Public transit coverage and stop proximity in outer presets.
5. Deterministic execution and data provenance metadata.
"""

import json
from pathlib import Path
import pytest

from app.models.domain import PlotLocation
from app.services.context_analyzer import ContextAnalyzer
from app.services.feasibility_checker import FeasibilityChecker
from app.services.gap_analyzer import GapAnalyzer
from app.services.osm_service import CachedOSMService
from app.services.scenario_generator import ScenarioGenerator
from app.settings import settings


@pytest.fixture
def osm_service():
    return CachedOSMService()


@pytest.fixture
def context_analyzer(osm_service):
    return ContextAnalyzer(osm_service=osm_service)


@pytest.fixture
def gap_analyzer():
    return GapAnalyzer()


@pytest.fixture
def scenario_generator():
    return ScenarioGenerator()


@pytest.fixture
def feasibility_checker():
    return FeasibilityChecker()


def test_vijayanagar_and_hebbal_landuse_and_population_density(context_analyzer):
    """Verify outer presets have residential land-use and non-zero population density."""
    # 1. Vijayanagar (12.3320, 76.6150)
    plot_vijay = PlotLocation(lat=12.3320, lng=76.6150, radius_m=2000, label="Vijayanagar")
    ctx_vijay = context_analyzer.analyze(plot_vijay)
    s_vijay = ctx_vijay.summary

    assert s_vijay.residential_pct > 40.0, f"Expected residential_pct > 40%, got {s_vijay.residential_pct}%"
    assert s_vijay.dominant_landuse == "residential", f"Expected dominant residential, got {s_vijay.dominant_landuse}"
    assert s_vijay.industrial_pct < 50.0, f"Industrial share should not dominate, got {s_vijay.industrial_pct}%"
    assert s_vijay.population_density_estimate > 3000.0, f"Population density should be > 3000, got {s_vijay.population_density_estimate}"
    assert s_vijay.building_density_estimate > 0.0

    # 2. Hebbal / KRS Road (12.3550, 76.6100)
    plot_hebbal = PlotLocation(lat=12.3550, lng=76.6100, radius_m=2000, label="Hebbal")
    ctx_hebbal = context_analyzer.analyze(plot_hebbal)
    s_hebbal = ctx_hebbal.summary

    assert s_hebbal.residential_pct > 30.0, f"Expected residential_pct > 30%, got {s_hebbal.residential_pct}%"
    assert s_hebbal.dominant_landuse == "residential", f"Expected dominant residential, got {s_hebbal.dominant_landuse}"
    assert s_hebbal.industrial_pct < 50.0, f"Industrial share should not dominate, got {s_hebbal.industrial_pct}%"
    assert s_hebbal.population_density_estimate > 3000.0, f"Population density should be > 3000, got {s_hebbal.population_density_estimate}"


def test_outer_presets_road_network_and_connectivity(context_analyzer):
    """Verify outer presets have non-zero road density and resolve nearest major roads."""
    # 1. Vijayanagar
    plot_vijay = PlotLocation(lat=12.3320, lng=76.6150, radius_m=2000, label="Vijayanagar")
    ctx_vijay = context_analyzer.analyze(plot_vijay)
    s_vijay = ctx_vijay.summary

    assert s_vijay.road_network_length_m > 15000.0, f"Road length too low: {s_vijay.road_network_length_m}m"
    assert s_vijay.road_density_m_per_sqkm > 1000.0, f"Road density too low: {s_vijay.road_density_m_per_sqkm}m/km²"
    assert s_vijay.major_road_count >= 3
    assert s_vijay.nearest_major_road_m < 300.0, f"Nearest major road too far: {s_vijay.nearest_major_road_m}m"

    # 2. Hebbal / KRS Road
    plot_hebbal = PlotLocation(lat=12.3550, lng=76.6100, radius_m=2000, label="Hebbal")
    ctx_hebbal = context_analyzer.analyze(plot_hebbal)
    s_hebbal = ctx_hebbal.summary

    assert s_hebbal.road_network_length_m > 10000.0, f"Road length too low: {s_hebbal.road_network_length_m}m"
    assert s_hebbal.road_density_m_per_sqkm > 1000.0, f"Road density too low: {s_hebbal.road_density_m_per_sqkm}m/km²"
    assert s_hebbal.major_road_count >= 3
    assert s_hebbal.nearest_major_road_m < 300.0, f"Nearest major road too far: {s_hebbal.nearest_major_road_m}m"


def test_outer_presets_transport_coverage(context_analyzer):
    """Verify outer presets have transit stops and realistic proximity."""
    # 1. Vijayanagar (Vijayanagar TTMC Bus Station nearby)
    plot_vijay = PlotLocation(lat=12.3320, lng=76.6150, radius_m=2000, label="Vijayanagar")
    ctx_vijay = context_analyzer.analyze(plot_vijay)
    s_vijay = ctx_vijay.summary

    assert s_vijay.transit_stop_count >= 2, f"Expected >= 2 transit stops, got {s_vijay.transit_stop_count}"
    assert s_vijay.nearest_transit_m < 300.0, f"Expected nearest transit < 300m, got {s_vijay.nearest_transit_m}m"

    # 2. Hebbal / KRS Road (Hebbal Industrial Bus Stand nearby)
    plot_hebbal = PlotLocation(lat=12.3550, lng=76.6100, radius_m=2000, label="Hebbal")
    ctx_hebbal = context_analyzer.analyze(plot_hebbal)
    s_hebbal = ctx_hebbal.summary

    assert s_hebbal.transit_stop_count >= 3, f"Expected >= 3 transit stops, got {s_hebbal.transit_stop_count}"
    assert s_hebbal.nearest_transit_m < 200.0, f"Expected nearest transit < 200m, got {s_hebbal.nearest_transit_m}m"


def test_no_false_industrial_zoning_conflicts(
    context_analyzer, gap_analyzer, scenario_generator, feasibility_checker
):
    """Verify residential plots in Vijayanagar do not trigger false industrial zoning conflicts."""
    plot = PlotLocation(lat=12.3320, lng=76.6150, radius_m=2000, area_sqm=3000.0, label="Vijayanagar")
    ctx = context_analyzer.analyze(plot)
    gaps = gap_analyzer.analyze(ctx)
    scenarios = scenario_generator.generate(plot, ctx, gaps)

    verdicts = feasibility_checker.evaluate_all(scenarios, plot, ctx, gaps)

    sensitive_scenarios = ("park", "healthcare", "education", "community_centre")
    for v in verdicts:
        if v.scenario_id in sensitive_scenarios:
            for w in v.warnings:
                assert "industrial" not in w.lower(), (
                    f"Scenario {v.scenario_id} triggered unexpected industrial zoning warning: {w}"
                )


def test_road_and_spatial_determinism(context_analyzer):
    """Verify road and context calculations produce identical numbers across repeated runs."""
    plot = PlotLocation(lat=12.3320, lng=76.6150, radius_m=2000, label="Vijayanagar")
    ctx1 = context_analyzer.analyze(plot)
    ctx2 = context_analyzer.analyze(plot)

    assert ctx1.summary.road_network_length_m == ctx2.summary.road_network_length_m
    assert ctx1.summary.nearest_major_road_m == ctx2.summary.nearest_major_road_m
    assert ctx1.summary.population_density_estimate == ctx2.summary.population_density_estimate
    assert ctx1.summary.transit_stop_count == ctx2.summary.transit_stop_count


def test_data_provenance_metadata_present():
    """Verify updated datasets contain explicit [supplied] provenance metadata."""
    data_dir = settings.osm_data_dir

    for fname in ("landuse.geojson", "roads.geojson", "transport.geojson"):
        file_path = data_dir / fname
        assert file_path.exists(), f"File {file_path} missing"

        with open(file_path) as fp:
            data = json.load(fp)

        assert "metadata" in data, f"{fname} missing top-level 'metadata' block"
        meta = data["metadata"]
        assert "provenance" in meta, f"{fname} metadata missing 'provenance'"
        assert "[supplied]" in meta["provenance"], f"{fname} provenance must specify [supplied]"
        assert "storage_crs" in meta
        assert "analysis_crs" in meta
