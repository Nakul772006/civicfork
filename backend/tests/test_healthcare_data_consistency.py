"""Regression tests for healthcare data consistency and POI categorization.

Ensures that:
1. Known healthcare POIs inside radius are correctly retrieved and counted.
2. Healthcare POIs outside radius are strictly excluded.
3. Raw OSM tags and subcategories correctly normalize to canonical 'healthcare'.
4. Previously underserved landmark presets (Palace, Vijayanagar, Hebbal) have
   non-zero healthcare facility coverage.
5. Infrastructure gap severity is sensitive to healthcare presence (not 1.0 absent).
6. Explainability diagnostics expose the complete calculation trace.
"""

import pytest
from app.models.domain import PlotLocation, POI
from app.services.context_analyzer import ContextAnalyzer
from app.services.gap_analyzer import GapAnalyzer
from app.services.osm_service import CachedOSMService, normalize_poi_category


@pytest.fixture
def osm_service():
    return CachedOSMService()


@pytest.fixture
def context_analyzer(osm_service):
    return ContextAnalyzer(osm_service=osm_service)


@pytest.fixture
def gap_analyzer():
    return GapAnalyzer()


def test_raw_tags_map_to_canonical_healthcare():
    """Verify that raw OSM category, subcategory, and tag variations map to 'healthcare'."""
    # 1. Direct category variations
    assert normalize_poi_category(category="healthcare") == "healthcare"
    assert normalize_poi_category(category="hospital") == "healthcare"
    assert normalize_poi_category(category="clinic") == "healthcare"
    assert normalize_poi_category(category="doctors") == "healthcare"
    assert normalize_poi_category(category="pharmacy") == "healthcare"
    assert normalize_poi_category(category="medical_centre") == "healthcare"

    # 2. Subcategory under generic/other category
    assert normalize_poi_category(category="other", subcategory="hospital") == "healthcare"
    assert normalize_poi_category(category="other", subcategory="clinic") == "healthcare"
    assert normalize_poi_category(category="other", subcategory="doctors") == "healthcare"
    assert normalize_poi_category(category="other", subcategory="pharmacy") == "healthcare"
    assert normalize_poi_category(category="other", subcategory="health_post") == "healthcare"
    assert normalize_poi_category(category="other", subcategory="dispensary") == "healthcare"

    # 3. Amenity tag under generic category
    assert normalize_poi_category(category="other", tags={"amenity": "hospital"}) == "healthcare"
    assert normalize_poi_category(category="other", tags={"amenity": "clinic"}) == "healthcare"
    assert normalize_poi_category(category="other", tags={"amenity": "pharmacy"}) == "healthcare"
    assert normalize_poi_category(category="other", tags={"amenity": "doctors"}) == "healthcare"

    # 4. Healthcare tag
    assert normalize_poi_category(category="other", tags={"healthcare": "hospital"}) == "healthcare"
    assert normalize_poi_category(category="other", tags={"healthcare": "centre"}) == "healthcare"

    # 5. Non-healthcare categories are preserved
    assert normalize_poi_category(category="education", subcategory="school") == "education"
    assert normalize_poi_category(category="parks", subcategory="park") == "parks"
    assert normalize_poi_category(category="other", subcategory="library") == "other"


def test_known_healthcare_poi_inside_radius_is_counted(osm_service):
    """Verify known healthcare POIs inside radius are retrieved and counted."""
    # Palace / Central (12.3051, 76.6551) at 1000m radius
    palace_lat, palace_lng = 12.3051, 76.6551
    pois = osm_service.get_pois(palace_lat, palace_lng, radius_m=1000, category="healthcare")

    assert len(pois) >= 2
    poi_names = [p.name for p in pois]
    assert "District Tuberculosis Centre & Clinic" in poi_names
    assert "Government Ayurveda Medical College & Hospital" in poi_names

    # Check distance constraints
    for p in pois:
        assert p.category == "healthcare"
        assert p.distance_m <= 1000.0


def test_healthcare_poi_outside_radius_is_not_counted(osm_service):
    """Verify healthcare POIs beyond the query radius are excluded."""
    # Palace / Central (12.3051, 76.6551) at 1000m radius
    palace_lat, palace_lng = 12.3051, 76.6551
    pois_1000 = osm_service.get_pois(palace_lat, palace_lng, radius_m=1000, category="healthcare")
    names_1000 = [p.name for p in pois_1000]

    # Facilities known to be located beyond 1000m from Palace
    assert "Kamakshi Community Hospital" not in names_1000  # ~1.35km away
    assert "KR Hospital (Government District Hospital)" not in names_1000  # ~2.86km away
    assert "Apollo BGS Hospital Kuvempunagar" not in names_1000  # ~2.4km away

    # Expanding radius to 5000m should include them
    pois_5000 = osm_service.get_pois(palace_lat, palace_lng, radius_m=5000, category="healthcare")
    names_5000 = [p.name for p in pois_5000]
    assert "Kamakshi Community Hospital" in names_5000
    assert "KR Hospital (Government District Hospital)" in names_5000
    assert "Apollo BGS Hospital Kuvempunagar" in names_5000


def test_preset_locations_produce_nonzero_healthcare_coverage(context_analyzer, gap_analyzer):
    """Verify all Mysuru presets now produce non-zero healthcare coverage and realistic gaps."""
    presets = [
        ("Palace / Central", 12.3051, 76.6551, 1000),
        ("Vijayanagar", 12.3320, 76.6150, 1000),
        ("Hebbal / KRS Road", 12.3550, 76.6100, 1000),
        ("Kuvempunagar", 12.2850, 76.6350, 1000),
    ]

    for name, lat, lng, radius_m in presets:
        plot = PlotLocation(lat=lat, lng=lng, radius_m=radius_m, area_sqm=3000.0, label=name)
        ctx = context_analyzer.analyze(plot)
        gaps = gap_analyzer.analyze(ctx)

        hc_gap = next(g for g in gaps if g.category == "healthcare")

        # Must NOT report 0 facilities
        assert hc_gap.facilities_in_radius > 0, f"{name} reported 0 healthcare facilities"
        # Must identify nearest facility
        assert hc_gap.nearest_facility_name is not None
        assert hc_gap.nearest_facility_distance_m is not None
        assert hc_gap.nearest_facility_distance_m <= radius_m
        # Must not be critical / absent (severity < 1.0)
        assert hc_gap.gap_severity < 1.0, f"{name} reported absent gap severity 1.0"
        assert hc_gap.gap_type in ("adequate", "distant", "insufficient")


def test_gap_severity_sensitivity_with_healthcare_presence(gap_analyzer):
    """Verify gap severity formula responds properly when facilities are present vs absent."""
    # 1. Plot with real healthcare facilities
    plot_with_hc = PlotLocation(lat=12.3051, lng=76.6551, radius_m=1000, area_sqm=3000.0)
    ctx_analyzer = ContextAnalyzer()
    ctx_with_hc = ctx_analyzer.analyze(plot_with_hc)
    gaps_with_hc = gap_analyzer.analyze(ctx_with_hc)
    hc_gap = next(g for g in gaps_with_hc if g.category == "healthcare")

    assert hc_gap.facilities_in_radius == 2
    assert hc_gap.gap_severity < 0.50  # Served (distant or adequate)
    assert hc_gap.gap_type in ("distant", "adequate")

    # 2. Simulated empty context (0 facilities)
    plot_empty = PlotLocation(lat=12.2100, lng=76.5600, radius_m=1000, area_sqm=3000.0)
    ctx_empty = ctx_analyzer.analyze(plot_empty)
    gaps_empty = gap_analyzer.analyze(ctx_empty)
    hc_gap_empty = next(g for g in gaps_empty if g.category == "healthcare")

    assert hc_gap_empty.facilities_in_radius == 0
    assert hc_gap_empty.gap_severity == 1.0
    assert hc_gap_empty.gap_type == "absent"


def test_diagnostic_calculation_trace_structure(context_analyzer, gap_analyzer):
    """Verify that calculation traces contain the complete diagnostic chain."""
    plot = PlotLocation(lat=12.3051, lng=76.6551, radius_m=1000, area_sqm=3000.0, label="Palace Plot")
    ctx = context_analyzer.analyze(plot)
    gaps = gap_analyzer.analyze(ctx)
    hc_gap = next(g for g in gaps if g.category == "healthcare")

    trace = gap_analyzer.get_calculation_trace(hc_gap)

    # Required diagnostic fields
    assert trace["plot_lat"] == 12.3051
    assert trace["plot_lng"] == 76.6551
    assert trace["radius_m"] == 1000
    assert trace["total_pois_in_radius"] == ctx.summary.total_pois
    assert trace["category_pois_in_radius"] == hc_gap.facilities_in_radius
    assert trace["nearest_facility_name"] == hc_gap.nearest_facility_name
    assert trace["nearest_facility_distance_m"] == hc_gap.nearest_facility_distance_m
    assert trace["gap_severity"] == hc_gap.gap_severity
    assert trace["gap_type"] == hc_gap.gap_type

    # Diagnostic chain format: Plot -> Radius -> Total POIs -> Healthcare POIs -> Nearest -> Severity
    diag = trace["diagnostic_chain"]
    assert "Plot (12.3051, 76.6551)" in diag
    assert "Radius: 1000m" in diag
    assert f"Total POIs in radius: {ctx.summary.total_pois}" in diag
    assert f"healthcare POIs: {hc_gap.facilities_in_radius}" in diag
    assert hc_gap.nearest_facility_name in diag
    assert f"Gap severity: {hc_gap.gap_severity}" in diag
