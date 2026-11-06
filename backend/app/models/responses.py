"""REST API response payload schemas for CivicFork endpoints."""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field
from app.models.domain import (
    ContextSummary,
    CounterfactualResult,
    FeasibilityVerdict,
    InfrastructureGap,
    NarrativeResponse,
    PlotLocation,
    RankedScenario,
    Scenario,
    ScoreMatrix,
    StabilityResult,
    WeightConfig,
)

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Standard error description block."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional diagnostic details"
    )


class StandardResponse(BaseModel, Generic[T]):
    """Standard CivicFork response envelope."""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(..., description="Whether operation succeeded")
    data: Optional[T] = Field(default=None, description="Response payload")
    error: Optional[ErrorDetail] = Field(default=None, description="Error block if failed")


# -------------------------------------------------------------------------
# Endpoint Response Payloads
# -------------------------------------------------------------------------

class AnalyzeBounds(BaseModel):
    """Map bounds metadata for the analyzed plot."""

    model_config = ConfigDict(extra="ignore")

    center: List[float] = Field(..., description="[lat, lng] coordinates")
    radius_m: int = Field(..., description="Radius in metres")


class AnalyzeResponseData(BaseModel):
    """Data payload for POST /api/analyze."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    plot: PlotLocation
    context_summary: ContextSummary
    gaps: List[InfrastructureGap]
    scenarios: Optional[List[Scenario]] = None
    poi_geojson: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "FeatureCollection", "features": []}
    )
    landuse_geojson: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "FeatureCollection", "features": []}
    )
    transport_geojson: Dict[str, Any] = Field(
        default_factory=lambda: {"type": "FeatureCollection", "features": []}
    )
    bounds: AnalyzeBounds


class SimulateResponseData(BaseModel):
    """Data payload for POST /api/simulate."""

    model_config = ConfigDict(extra="ignore")

    scenarios: List[Scenario]
    score_matrix: ScoreMatrix
    default_weights: WeightConfig
    default_ranking: List[RankedScenario]


class RankResponseData(BaseModel):
    """Data payload for POST /api/rank."""

    model_config = ConfigDict(extra="ignore")

    ranking: List[RankedScenario]
    weights_applied: WeightConfig
    stability: Optional[StabilityResult] = None


class FeasibilityResponseData(BaseModel):
    """Data payload for POST /api/feasibility."""

    model_config = ConfigDict(extra="ignore")

    verdicts: List[FeasibilityVerdict]


class CounterfactualResponseData(BaseModel):
    """Data payload for POST /api/counterfactual."""

    model_config = ConfigDict(extra="ignore")

    result: CounterfactualResult


class StabilityResponseData(BaseModel):
    """Data payload for POST /api/stability."""

    model_config = ConfigDict(extra="ignore")

    result: StabilityResult


class ExplainResponseData(BaseModel):
    """Data payload for POST /api/explain."""

    model_config = ConfigDict(extra="ignore")

    narrative: NarrativeResponse


class HealthResponseData(BaseModel):
    """Data payload for GET /api/health."""

    model_config = ConfigDict(extra="ignore")

    status: str
    osm_data_loaded: bool
    config_loaded: bool
    active_sessions: int
    demo_area: str


# Typed Envelope Aliases
AnalyzeResponse = StandardResponse[AnalyzeResponseData]
SimulateResponse = StandardResponse[SimulateResponseData]
RankResponse = StandardResponse[RankResponseData]
FeasibilityResponse = StandardResponse[FeasibilityResponseData]
CounterfactualResponse = StandardResponse[CounterfactualResponseData]
StabilityResponse = StandardResponse[StabilityResponseData]
ExplainResponse = StandardResponse[ExplainResponseData]
HealthResponse = StandardResponse[HealthResponseData]
