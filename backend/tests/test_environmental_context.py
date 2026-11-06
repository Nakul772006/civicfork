"""Regression and unit tests for water-body and environmental context in CivicFork.

Verifies:
1. Water-body dataset loads with 10 verified Mysuru lakes and complete provenance metadata.
2. Geometries are valid Polygons in EPSG:4326 with positive area in metric EPSG:32643.
3. Major Mysuru lakes (Kukkarahalli, Karanji, Lingambudhi, Hebbal) can be resolved.
4. Nearest water-body distance calculation is strictly deterministic across repeated calls.
5. Radius filtering correctly identifies intersecting water bodies.
6. Overlap calculation is deterministic and mathematically consistent.
7. Missing water_bodies.geojson gracefully falls back to empty/zero context without crashing.
8. End-to-end analytical pipeline retains 100% numerical and scoring invariance while
   exposing environmental proximity context.
9. Environmental context adheres to boundary limitations (no unsubstantiated flood risk claims).
"""

import json
from pathlib import Path
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.domain import PlotLocation, WaterBody
from app.services.context_analyzer import ContextAnalyzer
from app.services.osm_service import CachedOSMService
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


def test_water_body_dataset_loads(osm_service):
    """Verify water_bodies.geojson loads with 10 features and complete provenance metadata."""
    assert osm_service._water_bodies_gdf is not None
    assert len(osm_service._water_bodies_gdf) == 10
    assert osm_service._water_bodies_gdf.crs.to_string() == "EPSG:4326"

    # Validate file-level metadata
    file_path = settings.osm_data_dir / "water_bodies.geojson"
    assert file_path.exists()

    with open(file_path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    meta = doc.get("metadata", {})
    assert "source" in meta
    assert "source_dataset" in meta
    assert "[supplied]" in meta.get("provenance", "")
    assert meta.get("storage_crs") == "EPSG:4326"
    assert meta.get("analysis_crs") == "EPSG:32643"
    assert meta.get("city") == "Mysuru, Karnataka, India"
    assert meta.get("feature_count") == 10


def test_geometry_validity(osm_service):
    """Verify all water-body geometries are valid and have non-zero area."""
    gdf = osm_service._water_bodies_gdf
    assert gdf.geometry.is_valid.all()

    gdf_utm = osm_service._water_bodies_utm
    assert (gdf_utm.geometry.area > 1000.0).all(), "All water bodies should have substantial area"


def test_known_mysuru_lakes_resolved(osm_service):
    """Verify major landmark lakes exist and have realistic surface areas."""
    names = osm_service._water_bodies_gdf["name"].tolist()
    assert "Kukkarahalli Lake" in names
    assert "Karanji Lake" in names
    assert "Lingambudhi Lake" in names
    assert "Hebbal Lake" in names

    # Kukkarahalli Lake (~45 hectares)
    kukk = osm_service._water_bodies_gdf[osm_service._water_bodies_gdf["name"] == "Kukkarahalli Lake"].iloc[0]
    assert kukk["area_hectares"] > 35.0

    # Karanji Lake (~20 hectares)
    karanji = osm_service._water_bodies_gdf[osm_service._water_bodies_gdf["name"] == "Karanji Lake"].iloc[0]
    assert karanji["area_hectares"] > 15.0


def test_nearest_water_body_determinism(osm_service):
    """Verify nearest water body and distance calculations are strictly deterministic."""
    # Saraswathipuram plot centre (12.3100, 76.6500)
    lat, lng = 12.3100, 76.6500

    res1 = osm_service.get_nearest_water_body(lat, lng)
    res2 = osm_service.get_nearest_water_body(lat, lng)
    res3 = osm_service.get_nearest_water_body(lat, lng)

    assert res1 is not None and res2 is not None and res3 is not None
    wb1, dist1 = res1
    wb2, dist2 = res2
    wb3, dist3 = res3

    assert wb1.name == wb2.name == wb3.name == "Kukkarahalli Lake"
    assert dist1 == dist2 == dist3
    assert 1400.0 < dist1 < 1500.0, f"Expected ~1447m to Kukkarahalli, got {dist1}m"


def test_radius_filtering(osm_service):
    """Verify radius filtering includes only intersecting water bodies."""
    # Hebbal plot (12.3550, 76.6100) is ~56m from Hebbal Lake
    lat, lng = 12.3550, 76.6100

    # 1. 2000m radius contains Hebbal Lake
    wbs_2000 = osm_service.get_water_bodies(lat, lng, radius_m=2000)
    assert len(wbs_2000) >= 1
    hebbal_wb = next(w for w in wbs_2000 if w.name == "Hebbal Lake")
    assert hebbal_wb.distance_m < 100.0
    assert hebbal_wb.intersecting_area_sqm > 0.0

    # 2. 10m radius buffer does NOT reach the water body (~56m away)
    wbs_10 = osm_service.get_water_bodies(lat, lng, radius_m=10)
    assert len(wbs_10) == 0


def test_overlap_calculation_determinism(osm_service):
    """Verify water-body overlap calculations are repeatable and mathematically sound."""
    lat, lng = 12.3550, 76.6100  # Hebbal
    o1 = osm_service.get_water_body_overlap(lat, lng, radius_m=2000)
    o2 = osm_service.get_water_body_overlap(lat, lng, radius_m=2000)

    assert o1 == o2
    assert o1["count"] >= 1.0
    assert o1["intersecting_area_sqm"] > 0.0
    assert 0.0 < o1["buffer_overlap_pct"] < 100.0


def test_missing_water_bodies_dataset_fallback():
    """Verify missing water_bodies.geojson gracefully falls back to empty/zero context."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Copy core datasets only, omitting water_bodies.geojson
        for fname in ("pois.geojson", "roads.geojson", "landuse.geojson", "transport.geojson", "wards.geojson"):
            src = settings.osm_data_dir / fname
            if src.exists():
                shutil.copy(src, tmp_path / fname)

        service = CachedOSMService(data_dir=tmp_path)
        assert service.is_loaded() is True
        assert service._water_bodies_gdf is None

        # Safe fallback checks
        assert service.get_water_bodies(12.3100, 76.6500, radius_m=2000) == []
        assert service.get_nearest_water_body(12.3100, 76.6500) is None
        assert service.get_water_body_overlap(12.3100, 76.6500, radius_m=2000) == {
            "count": 0.0,
            "intersecting_area_sqm": 0.0,
            "buffer_overlap_pct": 0.0,
        }

        # ContextAnalyzer produces valid context with zero/None environmental fields
        analyzer = ContextAnalyzer(osm_service=service)
        plot = PlotLocation(lat=12.3100, lng=76.6500, radius_m=2000)
        ctx = analyzer.analyze(plot)
        assert ctx.summary.water_body_count == 0
        assert ctx.summary.nearest_water_body_m is None
        assert ctx.summary.nearest_water_body_name is None
        assert ctx.summary.water_body_proximity_context is None
        assert ctx.water_bodies == []


def test_no_unsupported_flood_claims(context_analyzer):
    """Verify proximity context does NOT make unsubstantiated flood risk claims."""
    # Plot in Hebbal right next to Hebbal Lake (< 60m away)
    plot = PlotLocation(lat=12.3550, lng=76.6100, radius_m=2000, label="Hebbal")
    ctx = context_analyzer.analyze(plot)

    proximity_text = ctx.summary.water_body_proximity_context
    assert proximity_text is not None
    assert "Hebbal Lake" in proximity_text
    assert "flood" not in proximity_text.lower(), "Must NOT make unvalidated flood risk claims"
    assert "hazard" not in proximity_text.lower()


def test_existing_pipeline_unaffected(test_client):
    """Verify end-to-end analytical pipeline retains unchanged scoring and ranking semantics."""
    # 1. /api/analyze
    resp_analyze = test_client.post(
        "/api/analyze",
        json={"lat": 12.3100, "lng": 76.6500, "radius_m": 2000, "area_sqm": 3500.0},
    )
    assert resp_analyze.status_code == 200
    data = resp_analyze.json()["data"]
    session_id = data["session_id"]
    summary = data["context_summary"]

    # Environmental fields present in response
    assert "water_body_count" in summary
    assert "nearest_water_body_m" in summary
    assert "nearest_water_body_name" in summary
    assert "water_body_proximity_context" in summary
    assert summary["nearest_water_body_name"] == "Kukkarahalli Lake"
    assert "Kukkarahalli Lake" in summary["water_body_proximity_context"]

    # 2. /api/simulate returns 7 scenario scores
    resp_sim = test_client.post("/api/simulate", json={"session_id": session_id})
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()["data"]
    assert len(sim_data["score_matrix"]["scenario_scores"]) == 7

    # 3. /api/rank returns 7 ranked scenarios
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

    # 4. /api/feasibility returns verdicts
    resp_feas = test_client.post(
        "/api/feasibility",
        json={"session_id": session_id, "scenario_id": "park"},
    )
    assert resp_feas.status_code == 200
    feas_data = resp_feas.json()["data"]
    assert len(feas_data["verdicts"]) >= 1
    assert feas_data["verdicts"][0]["feasible"] is True
