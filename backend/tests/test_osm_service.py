"""Tests for OSM geospatial data access service (Phase 2.1)."""

import pytest
from pathlib import Path
from shapely.geometry import Point

from app.api.dependencies import get_osm
from app.exceptions import OSMDataError
from app.models.domain import LandUseZone, POI, RoadSegment, TransportStop
from app.services.osm_service import (
    CachedOSMService,
    OSMServiceBase,
    get_osm_service,
    reset_osm_service,
)

SARASWATHIPURAM_LAT = 12.3100
SARASWATHIPURAM_LNG = 76.6500


# -----------------------------------------------------------------------------
# Initialization & Interface Compliance Tests
# -----------------------------------------------------------------------------

def test_osm_service_initialization():
    """Verify CachedOSMService initializes successfully with bundled Mysuru data."""
    reset_osm_service()
    service = get_osm_service(force_reload=True)

    assert isinstance(service, OSMServiceBase)
    assert isinstance(service, CachedOSMService)
    assert service.is_loaded() is True


def test_osm_service_interface_contract():
    """Verify CachedOSMService implements all abstract methods of OSMServiceBase."""
    methods = [
        "is_loaded",
        "get_pois",
        "get_nearest_poi",
        "get_poi_counts",
        "get_roads",
        "get_nearest_major_road",
        "get_landuse",
        "get_transport_stops",
        "get_nearest_transport_stop",
        "get_geojson",
    ]
    for method in methods:
        assert hasattr(CachedOSMService, method)
        assert callable(getattr(CachedOSMService, method))


# -----------------------------------------------------------------------------
# Spatial Query & Filtering Tests (using actual Mysuru data)
# -----------------------------------------------------------------------------

def test_spatial_filtering_by_radius():
    """Verify POI retrieval expands monotonically with increasing radius."""
    service = get_osm_service()

    pois_1000 = service.get_pois(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=1000)
    pois_2000 = service.get_pois(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000)
    pois_5000 = service.get_pois(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=5000)

    assert len(pois_1000) > 0
    assert len(pois_2000) >= len(pois_1000)
    assert len(pois_5000) >= len(pois_2000)

    # In 2000m, exactly 50 POIs in Saraswathipuram baseline after dataset expansion
    assert len(pois_2000) == 50

    # Check POI model fields
    sample_poi = pois_2000[0]
    assert isinstance(sample_poi, POI)
    assert sample_poi.osm_id.startswith("node/")
    assert sample_poi.distance_m <= 2000.0
    assert 12.20 <= sample_poi.lat <= 12.45
    assert 76.55 <= sample_poi.lng <= 76.75


def test_poi_category_filtering():
    """Verify filtering POIs by explicit category."""
    service = get_osm_service()

    healthcare_pois = service.get_pois(
        SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000, category="healthcare"
    )
    assert len(healthcare_pois) > 0
    for p in healthcare_pois:
        assert p.category == "healthcare"

    education_pois = service.get_pois(
        SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000, category="education"
    )
    assert len(education_pois) == 4
    for p in education_pois:
        assert p.category == "education"


def test_poi_counts_grouped():
    """Verify category count aggregation within radius."""
    service = get_osm_service()
    counts = service.get_poi_counts(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000)

    assert isinstance(counts, dict)
    assert counts.get("education") == 4
    assert counts.get("parks") == 1
    assert counts.get("parking") == 1
    assert sum(counts.values()) == 50


def test_nearest_poi_lookup():
    """Verify finding the nearest POI for specific categories."""
    service = get_osm_service()

    # Commercial nearest at ~200m
    nearest_comm = service.get_nearest_poi(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, "commercial")
    assert nearest_comm is not None
    assert nearest_comm.category == "commercial"
    assert 190.0 <= nearest_comm.distance_m <= 210.0
    assert "Devaraj" in (nearest_comm.name or "")

    # Healthcare nearest at ~800m
    nearest_health = service.get_nearest_poi(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, "healthcare")
    assert nearest_health is not None
    assert nearest_health.category == "healthcare"
    assert 790.0 <= nearest_health.distance_m <= 810.0

    # Non-existent category returns None
    assert service.get_nearest_poi(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, "non_existent_category") is None

    # Restrictive max_distance_m returns None if nearest is further
    assert (
        service.get_nearest_poi(
            SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, "healthcare", max_distance_m=500.0
        )
        is None
    )


def test_roads_spatial_query_and_nearest_major():
    """Verify road network spatial filtering and nearest major road resolution."""
    service = get_osm_service()

    roads = service.get_roads(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000)
    assert len(roads) > 0

    first_road = roads[0]
    assert isinstance(first_road, RoadSegment)
    assert first_road.osm_id.startswith("way/")
    assert first_road.length_m > 0
    assert len(first_road.geometry_coords) >= 2

    # Nearest major road (primary or secondary)
    result = service.get_nearest_major_road(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG)
    assert result is not None
    road, dist_m = result
    assert isinstance(road, RoadSegment)
    assert dist_m >= 0.0
    assert road.highway_type in ("motorway", "trunk", "primary", "secondary")


def test_landuse_spatial_query_and_metrics():
    """Verify land-use polygon retrieval, area calculation, and overlap percentage."""
    service = get_osm_service()

    zones = service.get_landuse(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000)
    assert len(zones) > 0

    first_zone = zones[0]
    assert isinstance(first_zone, LandUseZone)
    assert first_zone.osm_id.startswith("relation/")
    assert first_zone.area_sqm > 0
    assert 0.0 <= first_zone.overlap_pct <= 100.0
    assert first_zone.distance_m >= 0.0


def test_transport_stops_spatial_query():
    """Verify public transport stop filtering and nearest stop lookup."""
    service = get_osm_service()

    stops = service.get_transport_stops(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000)
    # Exactly 3 transit stops within 2000m
    assert len(stops) == 3

    first_stop = stops[0]
    assert isinstance(first_stop, TransportStop)
    assert first_stop.osm_id.startswith("node/")
    assert first_stop.transport_type in ("bus_stop", "bus_station", "railway_station", "auto_stand")

    # Nearest transit stop is ~600m away (Ramaswamy Circle)
    nearest_stop = service.get_nearest_transport_stop(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG)
    assert nearest_stop is not None
    assert 590.0 <= nearest_stop.distance_m <= 610.0
    assert "Ramaswamy" in (nearest_stop.name or "")


def test_geojson_export():
    """Verify exporting layers as GeoJSON FeatureCollection."""
    service = get_osm_service()

    for layer in ["pois", "roads", "landuse", "transport"]:
        data = service.get_geojson(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000, layer=layer)
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) > 0

    # Unknown layer raises OSMDataError
    with pytest.raises(OSMDataError) as exc_info:
        service.get_geojson(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=2000, layer="invalid_layer")
    assert "Unknown layer requested" in exc_info.value.message


# -----------------------------------------------------------------------------
# Edge Cases & Error Handling Tests
# -----------------------------------------------------------------------------

def test_empty_result_on_tight_radius():
    """Verify empty result behavior when no features exist in radius."""
    service = get_osm_service()

    # In a 1m radius around center, no POIs exist
    pois = service.get_pois(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=1)
    assert pois == []

    counts = service.get_poi_counts(SARASWATHIPURAM_LAT, SARASWATHIPURAM_LNG, radius_m=1)
    assert counts == {}


def test_missing_data_directory_raises(tmp_path):
    """Verify OSMDataError when data directory does not exist."""
    missing_dir = tmp_path / "non_existent_osm_data"
    with pytest.raises(OSMDataError) as exc_info:
        CachedOSMService(data_dir=missing_dir)
    assert "OSM data directory not found" in exc_info.value.message


def test_missing_required_file_raises(tmp_path):
    """Verify OSMDataError when a required GeoJSON file is missing."""
    empty_dir = tmp_path / "incomplete_osm"
    empty_dir.mkdir()
    with pytest.raises(OSMDataError) as exc_info:
        CachedOSMService(data_dir=empty_dir)
    assert "Required OSM dataset missing" in exc_info.value.message


def test_malformed_geojson_raises(tmp_path):
    """Verify OSMDataError when a GeoJSON file is malformed."""
    broken_dir = tmp_path / "broken_osm"
    broken_dir.mkdir()
    broken_file = broken_dir / "pois.geojson"
    broken_file.write_text("{ unclosed invalid json", encoding="utf-8")

    with pytest.raises(OSMDataError) as exc_info:
        CachedOSMService(data_dir=broken_dir)
    assert "Failed to read or parse GeoJSON dataset" in exc_info.value.message


# -----------------------------------------------------------------------------
# FastAPI Dependency & Integration Tests
# -----------------------------------------------------------------------------

def test_osm_dependency_injection():
    """Verify FastAPI get_osm dependency injects the loaded OSMService instance."""
    osm = get_osm()
    assert isinstance(osm, OSMServiceBase)
    assert osm.is_loaded() is True


def test_health_check_reflects_osm_loaded(client):
    """Verify GET /api/health reports osm_data_loaded: True."""
    response = client.get("/api/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["status"] == "healthy"
    assert data["osm_data_loaded"] is True
    assert data["config_loaded"] is True
    assert data["demo_area"] == "mysuru"
