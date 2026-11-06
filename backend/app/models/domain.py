"""CivicFork domain models and data types.

Defines the core data structures used across context analysis, gap detection,
simulation, ranking, feasibility, counterfactual evaluation, and reporting.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator

# -------------------------------------------------------------------------
# Constants & Permitted Literals
# -------------------------------------------------------------------------

SCENARIO_IDS = (
    "park",
    "healthcare",
    "education",
    "parking",
    "commercial",
    "community_centre",
    "public_transport",
)

ScenarioId = Literal[
    "park",
    "healthcare",
    "education",
    "parking",
    "commercial",
    "community_centre",
    "public_transport",
]

DIMENSION_NAMES = (
    "traffic",
    "cost",
    "environmental",
    "accessibility",
    "gap_improvement",
    "social_utility",
)

DimensionName = Literal[
    "traffic",
    "cost",
    "environmental",
    "accessibility",
    "gap_improvement",
    "social_utility",
]

GAP_CATEGORIES = (
    "healthcare",
    "education",
    "parks",
    "transport",
    "parking",
    "commercial",
    "community",
)

GapCategory = Literal[
    "healthcare",
    "education",
    "parks",
    "transport",
    "parking",
    "commercial",
    "community",
]

GAP_TYPES = ("absent", "insufficient", "distant", "adequate")
GapType = Literal["absent", "insufficient", "distant", "adequate"]

SEVERITIES = ("warning", "blocker")
CheckSeverity = Literal["warning", "blocker"]

DIRECTIONS = ("a_better", "b_better", "neutral")
DeltaDirection = Literal["a_better", "b_better", "neutral"]

MAGNITUDES = ("negligible", "minor", "moderate", "significant", "major")
DeltaMagnitude = Literal["negligible", "minor", "moderate", "significant", "major"]

NARRATIVE_TYPES = (
    "context_summary",
    "score_explanation",
    "counterfactual_explanation",
    "full_report",
)
NarrativeType = Literal[
    "context_summary",
    "score_explanation",
    "counterfactual_explanation",
    "full_report",
]

MYSURU_LAT_MIN = 12.20
MYSURU_LAT_MAX = 12.45
MYSURU_LNG_MIN = 76.55
MYSURU_LNG_MAX = 76.75
VALID_RADII = (1000, 2000, 5000)

# -------------------------------------------------------------------------
# 1. Plot Location
# -------------------------------------------------------------------------

class PlotLocation(BaseModel):
    """User-selected land plot for analysis."""

    model_config = ConfigDict(extra="ignore")

    lat: float = Field(..., description="Latitude of plot centre")
    lng: float = Field(..., description="Longitude of plot centre")
    radius_m: int = Field(default=2000, description="Analysis radius in metres")
    area_sqm: Optional[float] = Field(default=None, description="Plot area in m² if known")
    label: Optional[str] = Field(default=None, max_length=100, description="Optional plot label")

    @field_validator("lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (MYSURU_LAT_MIN <= v <= MYSURU_LAT_MAX):
            raise ValueError(
                f"Latitude {v} is outside Mysuru bounds [{MYSURU_LAT_MIN}, {MYSURU_LAT_MAX}]"
            )
        return v

    @field_validator("lng")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (MYSURU_LNG_MIN <= v <= MYSURU_LNG_MAX):
            raise ValueError(
                f"Longitude {v} is outside Mysuru bounds [{MYSURU_LNG_MIN}, {MYSURU_LNG_MAX}]"
            )
        return v

    @field_validator("radius_m")
    @classmethod
    def validate_radius(cls, v: int) -> int:
        if v not in VALID_RADII:
            raise ValueError(f"radius_m {v} must be one of {VALID_RADII}")
        return v

    @field_validator("area_sqm")
    @classmethod
    def validate_area(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 < v <= 50000):
            raise ValueError("area_sqm must be > 0 and <= 50000 m²")
        return v


# -------------------------------------------------------------------------
# 2. POI (Point of Interest)
# -------------------------------------------------------------------------

class POI(BaseModel):
    """A facility or amenity from cached OSM data within analysis radius."""

    model_config = ConfigDict(extra="ignore")

    osm_id: str = Field(..., description="OSM feature ID")
    name: Optional[str] = Field(default=None, description="Facility name")
    category: str = Field(..., description="Normalised category")
    subcategory: Optional[str] = Field(default=None, description="Finer classification")
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    distance_m: float = Field(..., ge=0, description="Distance from plot centre in metres")
    tags: Dict[str, str] = Field(default_factory=dict, description="Raw OSM tags")


# -------------------------------------------------------------------------
# 3. Road Segment
# -------------------------------------------------------------------------

class RoadSegment(BaseModel):
    """A road segment from cached OSM data within analysis radius."""

    model_config = ConfigDict(extra="ignore")

    osm_id: str = Field(..., description="OSM way ID")
    name: Optional[str] = Field(default=None, description="Road name")
    highway_type: str = Field(..., description="OSM highway tag value")
    length_m: float = Field(..., ge=0, description="Segment length in metres")
    distance_m: float = Field(..., ge=0, description="Nearest distance from plot centre")
    geometry_coords: List[List[float]] = Field(
        default_factory=list, description="[[lng, lat], ...] coordinate pairs"
    )


# -------------------------------------------------------------------------
# 4. Land Use Zone
# -------------------------------------------------------------------------

class LandUseZone(BaseModel):
    """A land-use polygon from cached OSM data within analysis radius."""

    model_config = ConfigDict(extra="ignore")

    osm_id: str = Field(..., description="OSM feature/relation ID")
    landuse_type: str = Field(..., description="OSM landuse tag value")
    area_sqm: float = Field(..., ge=0, description="Zone area in m²")
    distance_m: float = Field(..., ge=0, description="Distance to zone centroid")
    overlap_pct: float = Field(..., ge=0.0, le=100.0, description="Percentage of zone within radius")


# -------------------------------------------------------------------------
# 5. Transport Stop
# -------------------------------------------------------------------------

class TransportStop(BaseModel):
    """A public transport stop or station from cached OSM data."""

    model_config = ConfigDict(extra="ignore")

    osm_id: str = Field(..., description="OSM node ID")
    name: Optional[str] = Field(default=None, description="Stop/station name")
    transport_type: str = Field(..., description="bus_stop, railway_station, auto_stand, etc.")
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    distance_m: float = Field(..., ge=0, description="Distance from plot centre in metres")


# -------------------------------------------------------------------------
# 5b. Ward Data
# -------------------------------------------------------------------------

class WardData(BaseModel):
    """Administrative Mysuru City Corporation (MCC) ward context for a plot location."""

    model_config = ConfigDict(extra="ignore")

    ward_id: str = Field(..., description="MCC Ward identifier / number")
    ward_name: Optional[str] = Field(default=None, description="Official or recognised ward name")
    zone_id: Optional[str] = Field(default=None, description="Administrative MCC zone identifier")
    population: Optional[int] = Field(
        default=None, ge=0, description="Historical census population for the ward"
    )
    population_year: Optional[int] = Field(
        default=None, description="Reference year of the census population record"
    )
    area_sq_km: Optional[float] = Field(
        default=None, ge=0.0, description="Ward geographic area in km²"
    )
    population_density_per_sq_km: Optional[float] = Field(
        default=None, ge=0.0, description="Historical population density in people/km²"
    )
    lgd_ward_code: Optional[int] = Field(
        default=None, description="Local Government Directory (LGD) ward code"
    )


# -------------------------------------------------------------------------
# 5c. Water Body
# -------------------------------------------------------------------------

class WaterBody(BaseModel):
    """A natural or man-made water body or lake from cached spatial data."""

    model_config = ConfigDict(extra="ignore")

    osm_id: str = Field(..., description="OSM feature ID (way/... or relation/...)")
    name: str = Field(..., description="Canonical or common water body name")
    local_name: Optional[str] = Field(default=None, description="Local or vernacular name")
    water_type: str = Field(default="lake", description="lake, reservoir, pond, etc.")
    area_sqm: float = Field(..., ge=0, description="Total surface area in m²")
    distance_m: float = Field(..., ge=0, description="Shortest distance from plot center in metres")
    overlap_pct: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentage of water body area inside analysis buffer"
    )
    intersecting_area_sqm: float = Field(
        default=0.0, ge=0.0, description="Water body area overlapping analysis buffer in m²"
    )


# -------------------------------------------------------------------------
# 6. Context Summary
# -------------------------------------------------------------------------

class ContextSummary(BaseModel):
    """Aggregated statistics computed from raw OSM features."""

    model_config = ConfigDict(extra="ignore")

    total_pois: int = Field(..., ge=0, description="Total POIs within radius")
    poi_counts_by_category: Dict[str, int] = Field(
        default_factory=dict, description="Count per POI category"
    )
    poi_density_per_sqkm: float = Field(..., ge=0, description="POIs per km²")
    road_network_length_m: float = Field(..., ge=0, description="Total road length in metres")
    road_density_m_per_sqkm: float = Field(..., ge=0, description="Road length in m per km²")
    major_road_count: int = Field(..., ge=0, description="Primary/secondary/trunk road count")
    nearest_major_road_m: float = Field(..., ge=0, description="Distance to nearest major road")
    dominant_landuse: str = Field(..., description="Land-use type with largest area")
    landuse_distribution: Dict[str, float] = Field(
        default_factory=dict, description="Percentage breakdown by land-use type"
    )
    residential_pct: float = Field(..., ge=0.0, le=100.0, description="% residential land")
    commercial_pct: float = Field(..., ge=0.0, le=100.0, description="% commercial land")
    green_space_pct: float = Field(..., ge=0.0, le=100.0, description="% green space")
    industrial_pct: float = Field(..., ge=0.0, le=100.0, description="% industrial land")
    transit_stop_count: int = Field(..., ge=0, description="Transit stops within radius")
    nearest_transit_m: float = Field(..., ge=0, description="Distance to nearest transit stop")
    population_density_estimate: float = Field(
        ..., ge=0, description="Estimated population density in people/km²"
    )
    building_density_estimate: float = Field(
        ..., ge=0.0, le=1.0, description="Estimated building coverage ratio"
    )
    ward: Optional[WardData] = Field(
        default=None, description="MCC Ward administrative context if plot is covered"
    )
    # Environmental / Water-body Context [Observed / Calculated]
    water_body_count: int = Field(
        default=0, ge=0, description="Number of water bodies within radius [calculated]"
    )
    nearest_water_body_m: Optional[float] = Field(
        default=None, ge=0.0, description="Distance to nearest water body in metres [calculated]"
    )
    nearest_water_body_name: Optional[str] = Field(
        default=None, description="Name of nearest water body [supplied]"
    )
    water_body_area_within_radius_sqm: float = Field(
        default=0.0, ge=0.0, description="Total water surface area overlapping radius in m² [calculated]"
    )
    water_body_proximity_context: Optional[str] = Field(
        default=None, description="Descriptive environmental proximity context"
    )


# -------------------------------------------------------------------------
# 7. Urban Context
# -------------------------------------------------------------------------

class UrbanContext(BaseModel):
    """Complete urban context package bundling raw features with summary."""

    model_config = ConfigDict(extra="ignore")

    plot: PlotLocation
    pois: List[POI] = Field(default_factory=list)
    roads: List[RoadSegment] = Field(default_factory=list)
    landuse_zones: List[LandUseZone] = Field(default_factory=list)
    transport_stops: List[TransportStop] = Field(default_factory=list)
    ward: Optional[WardData] = Field(
        default=None, description="MCC Ward administrative context if plot is covered"
    )
    water_bodies: List[WaterBody] = Field(
        default_factory=list, description="Water bodies within or intersecting analysis radius"
    )
    summary: ContextSummary


# -------------------------------------------------------------------------
# 8. Infrastructure Gap
# -------------------------------------------------------------------------

class InfrastructureGap(BaseModel):
    """An identified gap in municipal infrastructure coverage near the plot."""

    model_config = ConfigDict(extra="ignore")

    category: GapCategory = Field(..., description="Category assessed")
    gap_type: GapType = Field(..., description="absent, insufficient, distant, adequate")
    nearest_facility_name: Optional[str] = Field(default=None, description="Nearest facility name")
    nearest_facility_distance_m: Optional[float] = Field(
        default=None, ge=0, description="Distance to nearest facility in metres"
    )
    coverage_threshold_m: float = Field(..., gt=0, description="Expected service distance threshold")
    facilities_in_radius: int = Field(..., ge=0, description="Matching facilities count in radius")
    expected_facilities: int = Field(..., ge=0, description="Expected facilities count")
    gap_severity: float = Field(..., ge=0.0, le=1.0, description="0.0 (served) to 1.0 (critical gap)")
    description: str = Field(..., description="Human-readable gap description")


# -------------------------------------------------------------------------
# 9. Scenario Definition
# -------------------------------------------------------------------------

class Scenario(BaseModel):
    """One of the 7 fixed development scenario definitions tailored to the plot."""

    model_config = ConfigDict(extra="ignore")

    id: ScenarioId = Field(..., description="Unique scenario identifier")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Brief scenario description")
    category: str = Field(..., description="Scenario grouping category")
    required_area_sqm: float = Field(..., gt=0, description="Minimum area needed in m²")
    proposed_area_sqm: float = Field(..., gt=0, description="Proposed area in m²")
    estimated_cost_inr: float = Field(..., ge=0, description="Estimated capital cost in INR")
    estimated_annual_operating_cost_inr: float = Field(
        ..., ge=0, description="Estimated annual operating cost in INR"
    )
    estimated_daily_visitors: int = Field(..., ge=0, description="Estimated daily visitors")
    estimated_jobs_created: int = Field(..., ge=0, description="Estimated direct jobs created")
    estimated_traffic_change_pct: float = Field(
        ..., description="Estimated % change in local traffic volume"
    )
    green_space_delta_sqm: float = Field(
        ..., description="Net change in green space area in m²"
    )
    impervious_surface_delta_sqm: float = Field(
        ..., description="Net change in impervious surface area in m²"
    )
    addresses_gaps: List[str] = Field(
        default_factory=list, description="List of gap categories addressed"
    )
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Scenario-specific attributes"
    )


# -------------------------------------------------------------------------
# 10. Score Explanation
# -------------------------------------------------------------------------

class ScoreExplanation(BaseModel):
    """Transparent calculation explanation for a single dimension score."""

    model_config = ConfigDict(extra="ignore")

    rule_name: str = Field(..., description="Scoring rule applied")
    formula_description: str = Field(..., description="Human-readable formula")
    input_factors: Dict[str, float] = Field(default_factory=dict)
    intermediate_values: Dict[str, float] = Field(default_factory=dict)
    raw_result: float = Field(..., description="Unnormalised formula output")
    normalised_result: float = Field(..., ge=0.0, le=100.0, description="Clamped 0-100 score")
    normalisation_range: List[float] = Field(
        default_factory=lambda: [0.0, 100.0], description="[min, max] range"
    )


# -------------------------------------------------------------------------
# 11. Dimension Score
# -------------------------------------------------------------------------

class DimensionScore(BaseModel):
    """Score for one dimension of one scenario (0–100, higher is better)."""

    model_config = ConfigDict(extra="ignore")

    dimension: DimensionName = Field(..., description="Dimension key")
    score: float = Field(..., ge=0.0, le=100.0, description="Normalised score (0-100)")
    direction_note: str = Field(..., description="Clarification note (e.g. Higher = better)")
    explanation: ScoreExplanation = Field(..., description="Calculation explanation")


# -------------------------------------------------------------------------
# 12. Scenario Score
# -------------------------------------------------------------------------

class ScenarioScore(BaseModel):
    """All 6 dimension scores for a single development scenario."""

    model_config = ConfigDict(extra="ignore")

    scenario_id: ScenarioId = Field(..., description="Scenario ID reference")
    scores: List[DimensionScore] = Field(
        ..., min_length=6, max_length=6, description="Exactly 6 dimension scores"
    )
    unweighted_composite: float = Field(
        ..., ge=0.0, le=100.0, description="Mean of all 6 scores"
    )


# -------------------------------------------------------------------------
# 13. Score Matrix
# -------------------------------------------------------------------------

class ScoreMatrix(BaseModel):
    """Complete 7x6 deterministic simulation output matrix."""

    model_config = ConfigDict(extra="ignore")

    scenario_scores: List[ScenarioScore] = Field(
        ..., min_length=7, max_length=7, description="Scores for all 7 scenarios"
    )
    dimensions: List[str] = Field(
        default_factory=lambda: list(DIMENSION_NAMES), description="Dimension names"
    )
    matrix: List[List[float]] = Field(
        ..., description="7x6 numeric matrix [scenario_idx][dimension_idx]"
    )
    scenarios_evaluated: int = Field(default=7, description="Always 7")
    dimensions_evaluated: int = Field(default=6, description="Always 6")


# -------------------------------------------------------------------------
# 14. Weight Configuration
# -------------------------------------------------------------------------

class WeightConfig(BaseModel):
    """User-configured or default priority weights for ranking scenarios."""

    model_config = ConfigDict(extra="ignore")

    traffic: float = Field(default=1.0, ge=0.0)
    cost: float = Field(default=1.0, ge=0.0)
    environmental: float = Field(default=1.0, ge=0.0)
    accessibility: float = Field(default=1.0, ge=0.0)
    gap_improvement: float = Field(default=1.0, ge=0.0)
    social_utility: float = Field(default=1.0, ge=0.0)

    def normalised(self) -> "WeightConfig":
        """Return a new WeightConfig with weights normalised to sum to 1.0."""
        total = (
            self.traffic
            + self.cost
            + self.environmental
            + self.accessibility
            + self.gap_improvement
            + self.social_utility
        )
        if total <= 0:
            equal = 1.0 / 6.0
            return WeightConfig(
                traffic=equal,
                cost=equal,
                environmental=equal,
                accessibility=equal,
                gap_improvement=equal,
                social_utility=equal,
            )
        return WeightConfig(
            traffic=self.traffic / total,
            cost=self.cost / total,
            environmental=self.environmental / total,
            accessibility=self.accessibility / total,
            gap_improvement=self.gap_improvement / total,
            social_utility=self.social_utility / total,
        )


# -------------------------------------------------------------------------
# 15. Ranked Scenario
# -------------------------------------------------------------------------

class RankedScenario(BaseModel):
    """A scenario's position in the priority-weighted ranking."""

    model_config = ConfigDict(extra="ignore")

    rank: int = Field(..., ge=1, le=7, description="1 (best) to 7 (worst)")
    scenario_id: ScenarioId = Field(...)
    scenario_name: str = Field(...)
    weighted_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite score")
    dimension_contributions: Dict[str, float] = Field(
        default_factory=dict, description="Contribution per dimension"
    )
    score_delta_from_top: float = Field(
        ..., ge=0.0, description="Difference from rank-1 weighted score"
    )


# -------------------------------------------------------------------------
# 16. Feasibility Check
# -------------------------------------------------------------------------

class FeasibilityCheck(BaseModel):
    """Outcome of a single feasibility rule check on a scenario."""

    model_config = ConfigDict(extra="ignore")

    check_name: str = Field(..., description="Rule key (min_area, etc.)")
    passed: bool = Field(..., description="Whether rule passed")
    severity: CheckSeverity = Field(..., description="warning or blocker")
    message: str = Field(..., description="Human-readable result message")
    details: Dict[str, Any] = Field(default_factory=dict)


# -------------------------------------------------------------------------
# 17. Feasibility Verdict
# -------------------------------------------------------------------------

class FeasibilityVerdict(BaseModel):
    """Complete feasibility evaluation for a single scenario."""

    model_config = ConfigDict(extra="ignore")

    scenario_id: ScenarioId = Field(...)
    feasible: bool = Field(..., description="True if no blockers failed")
    blocker_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    checks: List[FeasibilityCheck] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# -------------------------------------------------------------------------
# 18. Dimension Delta (Counterfactual)
# -------------------------------------------------------------------------

class DimensionDelta(BaseModel):
    """Delta between two scenarios on a single impact dimension."""

    model_config = ConfigDict(extra="ignore")

    dimension: DimensionName = Field(...)
    score_a: float = Field(..., ge=0.0, le=100.0)
    score_b: float = Field(..., ge=0.0, le=100.0)
    delta: float = Field(..., description="score_a - score_b (positive = A is better)")
    abs_delta: float = Field(..., ge=0.0)
    direction: DeltaDirection = Field(..., description="a_better, b_better, neutral")
    magnitude: DeltaMagnitude = Field(..., description="negligible to major")
    explanation_a_summary: str = Field(...)
    explanation_b_summary: str = Field(...)


# -------------------------------------------------------------------------
# 19. Counterfactual Result
# -------------------------------------------------------------------------

class CounterfactualResult(BaseModel):
    """Pairwise counterfactual comparison between Scenario A and Scenario B."""

    model_config = ConfigDict(extra="ignore")

    scenario_a_id: ScenarioId = Field(...)
    scenario_a_name: str = Field(...)
    scenario_b_id: ScenarioId = Field(...)
    scenario_b_name: str = Field(...)
    deltas: List[DimensionDelta] = Field(..., min_length=6, max_length=6)
    a_wins_dimensions: List[str] = Field(default_factory=list)
    b_wins_dimensions: List[str] = Field(default_factory=list)
    neutral_dimensions: List[str] = Field(default_factory=list)
    net_advantage: str = Field(..., description="scenario_a_id, scenario_b_id, or balanced")
    net_delta: float = Field(..., description="Sum of all 6 deltas")
    headline: str = Field(..., description="Summary headline")
    verdict: Optional[str] = Field(default=None, description="meaningfully_better, meaningfully_worse, or practically_equivalent")


# -------------------------------------------------------------------------
# 19b. Decision Stability / Sensitivity Analysis Models
# -------------------------------------------------------------------------

class ConfigurationResult(BaseModel):
    """Result of evaluating scenarios under a single priority configuration."""

    model_config = ConfigDict(extra="ignore")

    configuration_id: str = Field(..., description="Unique configuration key")
    configuration_name: str = Field(..., description="Human-readable title")
    weights: Dict[str, float] = Field(..., description="Raw priority weights used")
    winning_scenario_id: str = Field(..., description="Top-ranked scenario ID")
    winning_scenario_name: str = Field(..., description="Top-ranked scenario display name")
    winning_score: float = Field(..., description="Composite weighted score of winner")
    baseline_rank: int = Field(..., description="Rank of baseline scenario under this configuration")
    baseline_score: float = Field(..., description="Composite score of baseline scenario")
    baseline_won: bool = Field(..., description="Whether baseline scenario ranked #1")


class ChallengerInfo(BaseModel):
    """Details of the strongest competing alternative scenario."""

    model_config = ConfigDict(extra="ignore")

    scenario_id: str = Field(..., description="Challenger scenario ID")
    scenario_name: str = Field(..., description="Challenger scenario display name")
    wins: int = Field(..., description="Number of priority configurations won by challenger")


class StabilityResult(BaseModel):
    """Deterministic decision stability / sensitivity analysis result."""

    model_config = ConfigDict(extra="ignore")

    baseline_scenario_id: str = Field(..., description="Current recommended baseline scenario ID")
    baseline_scenario_name: str = Field(..., description="Baseline scenario display name")
    configurations_tested: List[str] = Field(..., description="Names or IDs of configurations tested")
    baseline_wins: int = Field(..., description="Number of configurations won by baseline")
    total_configurations: int = Field(default=7, description="Total unique configurations tested")
    stability_score: float = Field(..., description="Percentage of configurations won by baseline (0-100)")
    stability_level: str = Field(..., description="HIGH (>=75), MODERATE (>=50), or LOW (<50)")
    scenario_win_counts: Dict[str, int] = Field(..., description="Map of scenario ID to win count")
    strongest_challenger: Optional[ChallengerInfo] = Field(
        default=None, description="Non-baseline scenario with most wins"
    )
    interpretation: str = Field(..., description="Deterministic interpretation of stability")
    configuration_results: List[ConfigurationResult] = Field(
        default_factory=list, description="Per-configuration ranking outcomes"
    )
    calculation_trace: Dict[str, Any] = Field(
        default_factory=dict, description="Provenance and methodology trace"
    )


# -------------------------------------------------------------------------
# 20. Narrative Request & Response
# -------------------------------------------------------------------------

class NarrativeRequest(BaseModel):
    """Structured pre-computed data passed to Gemini for narrative generation."""

    model_config = ConfigDict(extra="ignore")

    narrative_type: NarrativeType = Field(...)
    plot: PlotLocation
    context_summary: ContextSummary
    gaps: List[InfrastructureGap] = Field(default_factory=list)
    scenarios: List[Scenario] = Field(default_factory=list)
    score_matrix: Optional[ScoreMatrix] = None
    ranking: Optional[List[RankedScenario]] = None
    feasibility: Optional[List[FeasibilityVerdict]] = None
    counterfactual: Optional[CounterfactualResult] = None


class DecisionRationale(BaseModel):
    """Structured context-aware municipal decision rationale for the recommended scenario."""

    model_config = ConfigDict(extra="ignore")

    headline: str = Field(default="", description="Executive recommendation headline")
    rationale: str = Field(default="", description="Municipal decision rationale paragraph")
    strengths: List[str] = Field(default_factory=list, description="Key strength highlights and gaps alleviated")
    trade_offs: List[str] = Field(default_factory=list, description="Key trade-offs or weaker dimensions")
    recommendation_context: str = Field(
        default="", description="Feasibility and comparative runner-up context"
    )


class NarrativeResponse(BaseModel):
    """Narrative text generated by an AI provider (or deterministic fallback)."""

    model_config = ConfigDict(extra="ignore")

    narrative_type: NarrativeType = Field(...)
    sections: Dict[str, str] = Field(
        default_factory=dict, description="Named narrative sections"
    )
    decision_rationale: Optional[DecisionRationale] = Field(
        default=None, description="Structured context-aware municipal decision rationale"
    )
    generated_by: Literal["gemini", "groq", "fallback", "deterministic"] = Field(
        default="gemini", description="Source of narrative"
    )
    fallback_reason: Optional[str] = Field(
        default=None, description="Reason if fallback was used"
    )


# -------------------------------------------------------------------------
# 21. Report Data
# -------------------------------------------------------------------------

class ReportData(BaseModel):
    """Complete dataset compiled to render the final ReportLab PDF report."""

    model_config = ConfigDict(extra="ignore")

    report_title: str = Field(default="CivicFork Urban Policy Impact Assessment")
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    plot: PlotLocation
    context_summary: ContextSummary
    gaps: List[InfrastructureGap] = Field(default_factory=list)
    scenarios: List[Scenario] = Field(default_factory=list)
    score_matrix: Optional[ScoreMatrix] = None
    ranking: Optional[List[RankedScenario]] = None
    weights_used: Optional[WeightConfig] = None
    feasibility: Optional[List[FeasibilityVerdict]] = None
    counterfactual: Optional[CounterfactualResult] = None
    narratives: Optional[NarrativeResponse] = None
    methodology_note: str = Field(
        default="Deterministic rule-based simulation. All scoring is derived through explicit formulas."
    )
    disclaimer: str = Field(
        default="Decision-support only. Not official zoning, legal, or construction advice."
    )


# -------------------------------------------------------------------------
# 22. Session Data Container
# -------------------------------------------------------------------------

class SessionData(BaseModel):
    """In-memory state container for an active simulation session."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    plot: Optional[Union[PlotLocation, Dict[str, Any]]] = None
    context: Optional[Union[UrbanContext, Dict[str, Any]]] = None
    gaps: Optional[Union[List[InfrastructureGap], List[Dict[str, Any]]]] = None
    scenarios: Optional[Union[List[Scenario], List[Dict[str, Any]]]] = None
    score_matrix: Optional[Union[ScoreMatrix, Dict[str, Any]]] = None
    ranking: Optional[Union[List[RankedScenario], List[Dict[str, Any]]]] = None
    weights_used: Optional[Union[WeightConfig, Dict[str, Any]]] = None
    feasibility: Optional[Union[List[FeasibilityVerdict], List[Dict[str, Any]]]] = None
    counterfactual: Optional[Union[CounterfactualResult, Dict[str, Any]]] = None
    stability: Optional[Union[StabilityResult, Dict[str, Any]]] = None
    narratives: Dict[str, Any] = Field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        if item in self.__dict__:
            return self.__dict__[item]
        raise KeyError(item)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) or item in self.__dict__

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.__dict__.get(key, default)

    def update(self, updates: Dict[str, Any]) -> None:
        for k, v in updates.items():
            setattr(self, k, v)

    def keys(self):
        return {**self.__dict__}.keys()

    def values(self):
        return {**self.__dict__}.values()

    def items(self):
        return {**self.__dict__}.items()
