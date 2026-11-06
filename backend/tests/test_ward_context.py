"""Regression and unit tests for MCC Ward administrative context.

Verifies:
1. Ward dataset loads successfully with 65 features and valid provenance metadata.
2. Known Mysuru plots resolve to typed WardData instances.
3. Saraswathipuram preset resolves to containing ward.
4. Vijayanagar preset resolves to containing ward.
5. Hebbal preset resolves or safely returns None when outside boundary perimeter.
6. Outside-covered-area lookup returns None safely without raising unhandled errors.
7. Ward lookup is strictly deterministic across repeated calls.
8. Missing wards.geojson does not break CachedOSMService or ContextAnalyzer.
9. Historical census population is isolated from modelled population density estimates.
10. End-to-end analytical pipeline (/api/analyze) preserves ward context while keeping
    scoring, simulation, ranking, and feasibility calculations unchanged.
"""

from pathlib import Path
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.domain import PlotLocation, WardData
from app.services.context_analyzer import ContextAnalyzer
from app.services.feasibility_checker import FeasibilityChecker
from app.services.gap_analyzer import GapAnalyzer
from app.services.impact_simulator import ImpactSimulator
from app.services.osm_service import CachedOSMService
from app.services.ranking_engine import RankingEngine
from app.services.scenario_generator import ScenarioGenerator
from app.settings import settings


@pytest.fixture
def osm_service():
    return CachedOSMService()


@pytest.fixture
def context_analyzer(osm_service):
    return ContextAnalyzer(osm_service=osm_service)


@pytest.fixture
def test_client():
    return TestClient(app)


def test_ward_dataset_loads_successfully(osm_service):
    """Verify wards.geojson exists, has 65 features, and carries provenance metadata."""
    assert osm_service._wards_gdf is not None
    assert len(osm_service._wards_gdf) == 65
    assert osm_service._wards_gdf.crs.to_string() == "EPSG:4326"
    assert osm_service._wards_gdf.geometry.is_valid.all()

    # Check top-level metadata from raw file
    wards_file = settings.osm_data_dir / "wards.geojson"
    assert wards_file.exists()
    import json
    with open(wards_file) as f:
        doc = json.load(f)

    meta = doc.get("metadata", {})
    assert "source" in meta
    assert "source_dataset" in meta
    assert "source_year" in meta
    assert "[supplied]" in meta.get("provenance", "")
    assert meta.get("storage_crs") == "EPSG:4326"
    assert meta.get("analysis_crs") == "EPSG:32643"
    assert meta.get("city") == "Mysuru, Karnataka, India"
    assert meta.get("feature_count") == 65


def test_known_mysuru_plot_resolves_to_ward(osm_service):
    """Verify known Mysuru core location resolves to a valid WardData model."""
    # Mysore Palace centre (12.3051, 76.6551)
    ward = osm_service.get_ward(12.3051, 76.6551)
    assert ward is not None
    assert isinstance(ward, WardData)
    assert ward.ward_id == "51"
    assert ward.ward_name == "Agrahara"
    assert ward.population is not None and ward.population > 0
    assert ward.population_year == 2011
    assert ward.area_sq_km is not None and ward.area_sq_km > 0
    assert ward.population_density_per_sq_km is not None and ward.population_density_per_sq_km > 0


def test_saraswathipuram_preset_resolves(context_analyzer, osm_service):
    """Verify Saraswathipuram preset resolves to Ward 41."""
    plot = PlotLocation(lat=12.3100, lng=76.6500, radius_m=2000, label="Saraswathipuram")
    ward = osm_service.get_ward(plot.lat, plot.lng)
    assert ward is not None
    assert ward.ward_id == "41"
    assert ward.ward_name == "Devarajamohalla"

    ctx = context_analyzer.analyze(plot)
    assert ctx.summary.ward is not None
    assert ctx.summary.ward.ward_id == "41"
    assert ctx.summary.ward.ward_name == "Devarajamohalla"
    assert ctx.ward == ctx.summary.ward


def test_vijayanagar_preset_resolves(context_analyzer, osm_service):
    """Verify Vijayanagar preset resolves to Ward 20."""
    plot = PlotLocation(lat=12.3320, lng=76.6150, radius_m=2000, label="Vijayanagar")
    ward = osm_service.get_ward(plot.lat, plot.lng)
    assert ward is not None
    assert ward.ward_id == "20"
    assert ward.ward_name == "Vijayanagara 1St & 2Nd Stage"

    ctx = context_analyzer.analyze(plot)
    assert ctx.summary.ward is not None
    assert ctx.summary.ward.ward_id == "20"
    assert ctx.summary.ward.ward_name == "Vijayanagara 1St & 2Nd Stage"


def test_hebbal_preset_lookup(context_analyzer, osm_service):
    """Verify Hebbal preset lookup handles boundaries safely."""
    # Hebbal preset (12.3550, 76.6100) is ~157m NW of the 65-ward boundary perimeter
    plot_outer = PlotLocation(lat=12.3550, lng=76.6100, radius_m=2000, label="Hebbal Outer")
    ward_outer = osm_service.get_ward(plot_outer.lat, plot_outer.lng)
    assert ward_outer is None

    ctx_outer = context_analyzer.analyze(plot_outer)
    assert ctx_outer.summary.ward is None
    assert ctx_outer.ward is None

    # A coordinate inside Hebbal Ward 1 (12.3500, 76.6100) correctly resolves to Ward 1
    ward_inner = osm_service.get_ward(12.3500, 76.6100)
    assert ward_inner is not None
    assert ward_inner.ward_id == "1"
    assert ward_inner.ward_name == "Hebbalu Lakshmikanthanagar"


def test_outside_covered_area_safe(osm_service):
    """Verify coordinates outside the ward boundary return None safely."""
    # Coordinates outside dataset bounds
    assert osm_service.get_ward(12.4500, 76.6500) is None
    assert osm_service.get_ward(12.2000, 76.5500) is None

    # Extreme or invalid coordinates return None safely without raising exceptions
    assert osm_service.get_ward(0.0, 0.0) is None
    assert osm_service.get_ward(90.0, 180.0) is None


def test_ward_lookup_determinism(osm_service):
    """Verify ward lookup yields identical results across multiple calls."""
    lat, lng = 12.3100, 76.6500
    res1 = osm_service.get_ward(lat, lng)
    res2 = osm_service.get_ward(lat, lng)
    res3 = osm_service.get_ward(lat, lng)

    assert res1 == res2 == res3
    assert res1.ward_id == res2.ward_id == "41"
    assert res1.population == res2.population


def test_missing_wards_geojson_graceful_handling():
    """Verify missing wards.geojson does not break application startup or lookups."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Copy core datasets only, omitting wards.geojson
        for fname in ("pois.geojson", "roads.geojson", "landuse.geojson", "transport.geojson"):
            src = settings.osm_data_dir / fname
            if src.exists():
                shutil.copy(src, tmp_path / fname)

        service = CachedOSMService(data_dir=tmp_path)
        assert service.is_loaded() is True
        assert service._wards_gdf is None

        # get_ward should return None without error
        assert service.get_ward(12.3100, 76.6500) is None

        # ContextAnalyzer should operate normally with ward=None
        analyzer = ContextAnalyzer(osm_service=service)
        plot = PlotLocation(lat=12.3100, lng=76.6500, radius_m=1000)
        ctx = analyzer.analyze(plot)
        assert ctx.summary.ward is None
        assert ctx.ward is None
        assert ctx.summary.population_density_estimate > 0


def test_modelled_population_density_isolated_from_historical_ward_population(context_analyzer):
    """Verify modelled population density estimate is NOT overwritten by census numbers."""
    plot = PlotLocation(lat=12.3100, lng=76.6500, radius_m=2000, label="Saraswathipuram")
    ctx = context_analyzer.analyze(plot)

    # Ward has historical census population of 9,726 and density 18,420.5/km²
    assert ctx.summary.ward is not None
    assert ctx.summary.ward.population == 9726
    assert ctx.summary.ward.population_density_per_sq_km == 18420.5

    # Modelled population density remains strictly the landuse-derived estimate
    # (residential_pct=65.0% -> ~7505.0 people/km²)
    assert ctx.summary.population_density_estimate == 7505.0
    assert ctx.summary.population_density_estimate != ctx.summary.ward.population_density_per_sq_km


def test_pipeline_e2e_preserves_ward_context(test_client):
    """Verify end-to-end /api/analyze exposes ward data and downstream pipeline succeeds."""
    # 1. /api/analyze
    resp_analyze = test_client.post(
        "/api/analyze",
        json={"lat": 12.3100, "lng": 76.6500, "radius_m": 2000, "area_sqm": 3500.0},
    )
    assert resp_analyze.status_code == 200
    data = resp_analyze.json()["data"]
    session_id = data["session_id"]
    summary = data["context_summary"]

    assert "ward" in summary
    assert summary["ward"] is not None
    assert summary["ward"]["ward_id"] == "41"
    assert summary["ward"]["ward_name"] == "Devarajamohalla"
    assert summary["ward"]["population"] == 9726
    assert summary["ward"]["population_year"] == 2011

    # 2. Downstream simulation works with unchanged semantics
    resp_sim = test_client.post("/api/simulate", json={"session_id": session_id})
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()["data"]
    assert len(sim_data["score_matrix"]["scenario_scores"]) == 7

    # 3. Downstream ranking works with unchanged semantics
    resp_rank = test_client.post(
        "/api/rank",
        json={
            "session_id": session_id,
            "weights": {
                "economic_development": 0.20,
                "social_utility": 0.20,
                "environmental_balance": 0.15,
                "traffic_impact": 0.15,
                "infrastructure_cost": 0.15,
                "implementation_speed": 0.15,
            },
        },
    )
    assert resp_rank.status_code == 200
    rank_data = resp_rank.json()["data"]
    assert len(rank_data["ranking"]) == 7

    # 4. Downstream feasibility works with unchanged semantics
    resp_feas = test_client.post(
        "/api/feasibility",
        json={"session_id": session_id, "scenario_id": "park"},
    )
    assert resp_feas.status_code == 200
    feas_data = resp_feas.json()["data"]
    assert len(feas_data["verdicts"]) >= 1
    assert feas_data["verdicts"][0]["feasible"] is True
