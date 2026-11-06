"""Tests for CivicFork shared data models, requests, and responses."""

import pytest
from pydantic import ValidationError
from app.models.domain import (
    ContextSummary,
    CounterfactualResult,
    DimensionDelta,
    DimensionScore,
    FeasibilityCheck,
    FeasibilityVerdict,
    InfrastructureGap,
    LandUseZone,
    NarrativeRequest,
    NarrativeResponse,
    POI,
    PlotLocation,
    RankedScenario,
    RoadSegment,
    Scenario,
    ScenarioScore,
    ScoreExplanation,
    ScoreMatrix,
    SessionData,
    TransportStop,
    UrbanContext,
    WeightConfig,
)
from app.models.requests import (
    AnalyzeRequest,
    CounterfactualRequest,
    ExplainRequest,
    FeasibilityRequest,
    RankRequest,
    ReportRequest,
    SimulateRequest,
)
from app.models.responses import (
    AnalyzeBounds,
    AnalyzeResponse,
    AnalyzeResponseData,
    CounterfactualResponse,
    CounterfactualResponseData,
    ErrorDetail,
    ExplainResponse,
    HealthResponse,
    HealthResponseData,
    RankResponse,
    RankResponseData,
    SimulateResponse,
    SimulateResponseData,
    StandardResponse,
)


# -------------------------------------------------------------------------
# Domain Model Tests
# -------------------------------------------------------------------------

def test_plot_location_valid():
    """Verify valid PlotLocation creation within Mysuru bounds."""
    plot = PlotLocation(lat=12.31, lng=76.65, radius_m=2000, area_sqm=3000.0, label="Test Plot")
    assert plot.lat == 12.31
    assert plot.lng == 76.65
    assert plot.radius_m == 2000
    assert plot.area_sqm == 3000.0
    assert plot.label == "Test Plot"


def test_plot_location_out_of_bounds_validation():
    """Verify validation triggers when coordinates exceed Mysuru demo bounds."""
    with pytest.raises(ValidationError) as exc:
        PlotLocation(lat=13.00, lng=76.65)  # Outside latitude
    assert "Latitude 13.0 is outside Mysuru bounds" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        PlotLocation(lat=12.31, lng=77.50)  # Outside longitude
    assert "Longitude 77.5 is outside Mysuru bounds" in str(exc.value)


def test_plot_location_radius_and_area_validation():
    """Verify radius must be in allowed list (1000, 2000, 5000) and area must be positive."""
    # Radius 500 must now be rejected
    with pytest.raises(ValidationError) as exc:
        PlotLocation(lat=12.31, lng=76.65, radius_m=500)
    assert "radius_m 500 must be one of (1000, 2000, 5000)" in str(exc.value)

    # Unsupported radius
    with pytest.raises(ValidationError) as exc:
        PlotLocation(lat=12.31, lng=76.65, radius_m=3000)
    assert "radius_m 3000 must be one of (1000, 2000, 5000)" in str(exc.value)

    # Valid radii: 1000, 2000, 5000
    for r in (1000, 2000, 5000):
        p = PlotLocation(lat=12.31, lng=76.65, radius_m=r)
        assert p.radius_m == r

    # Area validation
    with pytest.raises(ValidationError) as exc:
        PlotLocation(lat=12.31, lng=76.65, area_sqm=-100)
    assert "area_sqm must be > 0" in str(exc.value)


def test_score_range_validation():
    """Verify score clamping/validation between 0.0 and 100.0."""
    explanation = ScoreExplanation(
        rule_name="traffic_rule",
        formula_description="base + modifiers",
        raw_result=95.0,
        normalised_result=95.0,
    )
    dim_score = DimensionScore(
        dimension="traffic",
        score=95.0,
        direction_note="Higher = better",
        explanation=explanation,
    )
    assert dim_score.score == 95.0

    with pytest.raises(ValidationError):
        DimensionScore(
            dimension="traffic",
            score=105.0,  # Invalid: > 100
            direction_note="Higher = better",
            explanation=explanation,
        )

    with pytest.raises(ValidationError):
        DimensionScore(
            dimension="traffic",
            score=-5.0,  # Invalid: < 0
            direction_note="Higher = better",
            explanation=explanation,
        )


def test_infrastructure_gap_severity_validation():
    """Verify gap severity must be between 0.0 and 1.0."""
    gap = InfrastructureGap(
        category="healthcare",
        gap_type="insufficient",
        coverage_threshold_m=3000.0,
        facilities_in_radius=1,
        expected_facilities=3,
        gap_severity=0.6,
        description="Healthcare deficit",
    )
    assert gap.gap_severity == 0.6

    with pytest.raises(ValidationError):
        InfrastructureGap(
            category="healthcare",
            gap_type="insufficient",
            coverage_threshold_m=3000.0,
            facilities_in_radius=1,
            expected_facilities=3,
            gap_severity=1.5,  # Invalid: > 1.0
            description="Healthcare deficit",
        )


def test_weight_config_normalization():
    """Verify WeightConfig normalization logic."""
    weights = WeightConfig(traffic=2.0, cost=2.0, environmental=0.0, accessibility=0.0, gap_improvement=0.0, social_utility=0.0)
    norm = weights.normalised()
    assert norm.traffic == pytest.approx(0.5)
    assert norm.cost == pytest.approx(0.5)
    assert norm.environmental == 0.0

    # All zeros default to equal 1/6
    zero_weights = WeightConfig(traffic=0, cost=0, environmental=0, accessibility=0, gap_improvement=0, social_utility=0)
    equal_norm = zero_weights.normalised()
    assert equal_norm.traffic == pytest.approx(1.0 / 6.0)


# -------------------------------------------------------------------------
# Request Model Tests
# -------------------------------------------------------------------------

def test_analyze_request_valid():
    """Verify AnalyzeRequest validation."""
    req = AnalyzeRequest(lat=12.31, lng=76.65, radius_m=2000, area_sqm=4000.0)
    assert req.lat == 12.31
    assert req.radius_m == 2000

    # Radius 500 must be rejected
    with pytest.raises(ValidationError) as exc:
        AnalyzeRequest(lat=12.31, lng=76.65, radius_m=500)
    assert "radius_m 500 must be one of (1000, 2000, 5000)" in str(exc.value)


def test_counterfactual_request_validation():
    """Verify CounterfactualRequest requires distinct valid scenarios."""
    sid = "123e4567-e89b-12d3-a456-426614174000"
    valid_req = CounterfactualRequest(
        session_id=sid, scenario_a_id="park", scenario_b_id="commercial"
    )
    assert valid_req.scenario_a_id == "park"

    # Reject identical scenarios
    with pytest.raises(ValidationError) as exc:
        CounterfactualRequest(
            session_id=sid, scenario_a_id="park", scenario_b_id="park"
        )
    assert "scenario_a_id and scenario_b_id must be distinct" in str(exc.value)

    # Reject invalid UUID
    with pytest.raises(ValidationError) as exc:
        CounterfactualRequest(
            session_id="not-a-uuid", scenario_a_id="park", scenario_b_id="commercial"
        )
    assert "must be a valid UUID" in str(exc.value)


def test_rank_request_rejects_all_zero_weights():
    """Verify RankRequest rejects weights that sum to zero."""
    sid = "123e4567-e89b-12d3-a456-426614174000"
    with pytest.raises(ValidationError) as exc:
        RankRequest(
            session_id=sid,
            weights=WeightConfig(traffic=0, cost=0, environmental=0, accessibility=0, gap_improvement=0, social_utility=0),
        )
    assert "At least one weight dimension must be greater than zero" in str(exc.value)


def test_explain_request_validation():
    """Verify ExplainRequest narrative_type restriction."""
    sid = "123e4567-e89b-12d3-a456-426614174000"
    req = ExplainRequest(session_id=sid, narrative_type="context_summary")
    assert req.narrative_type == "context_summary"

    with pytest.raises(ValidationError):
        ExplainRequest(session_id=sid, narrative_type="unsupported_type")


# -------------------------------------------------------------------------
# Response & Serialization Tests
# -------------------------------------------------------------------------

def test_response_envelope_serialization():
    """Verify StandardResponse serializes and deserializes properly."""
    health_data = HealthResponseData(
        status="healthy",
        osm_data_loaded=True,
        config_loaded=True,
        active_sessions=3,
        demo_area="mysuru",
    )
    response = HealthResponse(success=True, data=health_data, error=None)

    json_str = response.model_dump_json()
    assert '"status":"healthy"' in json_str
    assert '"active_sessions":3' in json_str

    deserialized = HealthResponse.model_validate_json(json_str)
    assert deserialized.success is True
    assert deserialized.data.active_sessions == 3


def test_session_data_roundtrip():
    """Verify SessionData container roundtrips with dictionary representations."""
    plot = PlotLocation(lat=12.31, lng=76.65, radius_m=2000)
    session = SessionData(
        session_id="test-session-123",
        plot=plot,
    )
    dumped = session.model_dump()
    assert dumped["session_id"] == "test-session-123"
    assert dumped["plot"]["lat"] == 12.31

    reloaded = SessionData.model_validate(dumped)
    assert reloaded.session_id == "test-session-123"
    assert reloaded.plot.lat == 12.31
