"""REST API request payload schemas for CivicFork endpoints."""

import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.domain import (
    MYSURU_LAT_MAX,
    MYSURU_LAT_MIN,
    MYSURU_LNG_MAX,
    MYSURU_LNG_MIN,
    NARRATIVE_TYPES,
    SCENARIO_IDS,
    VALID_RADII,
    NarrativeType,
    ScenarioId,
    WeightConfig,
)


def _validate_uuid(val: str, field_name: str = "session_id") -> str:
    """Helper to validate UUID format."""
    try:
        uuid.UUID(str(val))
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f"{field_name} must be a valid UUID string")
    return str(val)


class AnalyzeRequest(BaseModel):
    """Payload for POST /api/analyze."""

    model_config = ConfigDict(extra="ignore")

    lat: float = Field(..., description="Latitude of plot centre")
    lng: float = Field(..., description="Longitude of plot centre")
    radius_m: int = Field(default=2000, description="Analysis radius in metres")
    area_sqm: Optional[float] = Field(default=None, description="Plot area in m² (optional)")
    label: Optional[str] = Field(default=None, max_length=100, description="Optional plot label")

    @field_validator("lat")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (MYSURU_LAT_MIN <= v <= MYSURU_LAT_MAX):
            raise ValueError(
                f"Latitude {v} is outside Mysuru demo bounds [{MYSURU_LAT_MIN}, {MYSURU_LAT_MAX}]"
            )
        return v

    @field_validator("lng")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (MYSURU_LNG_MIN <= v <= MYSURU_LNG_MAX):
            raise ValueError(
                f"Longitude {v} is outside Mysuru demo bounds [{MYSURU_LNG_MIN}, {MYSURU_LNG_MAX}]"
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


class SimulateRequest(BaseModel):
    """Payload for POST /api/simulate."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Valid session UUID")

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        return _validate_uuid(v)


class RankRequest(BaseModel):
    """Payload for POST /api/rank."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Valid session UUID")
    weights: WeightConfig = Field(..., description="Municipal priority weights")

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        return _validate_uuid(v)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, v: WeightConfig) -> WeightConfig:
        total = (
            v.traffic
            + v.cost
            + v.environmental
            + v.accessibility
            + v.gap_improvement
            + v.social_utility
        )
        if total <= 0:
            raise ValueError("At least one weight dimension must be greater than zero")
        return v


class FeasibilityRequest(BaseModel):
    """Payload for POST /api/feasibility."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Valid session UUID")
    scenario_id: Optional[ScenarioId] = Field(default=None, description="Optional specific scenario ID to evaluate")

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        return _validate_uuid(v)

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in SCENARIO_IDS:
            raise ValueError(f"scenario_id must be one of {SCENARIO_IDS}")
        return v


class CounterfactualRequest(BaseModel):
    """Payload for POST /api/counterfactual."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Valid session UUID")
    scenario_a_id: ScenarioId = Field(..., description="Primary scenario ID to compare")
    scenario_b_id: ScenarioId = Field(..., description="Counterfactual scenario ID to compare against")

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        return _validate_uuid(v)

    @field_validator("scenario_a_id")
    @classmethod
    def validate_scenario_a(cls, v: str) -> str:
        if v not in SCENARIO_IDS:
            raise ValueError(f"scenario_a_id must be one of {SCENARIO_IDS}")
        return v

    @field_validator("scenario_b_id")
    @classmethod
    def validate_scenario_b(cls, v: str) -> str:
        if v not in SCENARIO_IDS:
            raise ValueError(f"scenario_b_id must be one of {SCENARIO_IDS}")
        return v

    @model_validator(mode="after")
    def validate_different_scenarios(self) -> "CounterfactualRequest":
        if self.scenario_a_id == self.scenario_b_id:
            raise ValueError("scenario_a_id and scenario_b_id must be distinct scenarios")
        return self


class ExplainRequest(BaseModel):
    """Payload for POST /api/explain."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Valid session UUID")
    narrative_type: NarrativeType = Field(
        ..., description="context_summary, score_explanation, counterfactual_explanation, or full_report"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        return _validate_uuid(v)

    @field_validator("narrative_type")
    @classmethod
    def validate_narrative_type(cls, v: str) -> str:
        if v not in NARRATIVE_TYPES:
            raise ValueError(f"narrative_type must be one of {NARRATIVE_TYPES}")
        return v


class ReportRequest(BaseModel):
    """Payload for POST /api/report."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Valid session UUID")
    include_narrative: bool = Field(
        default=True, description="Whether to include Gemini-generated narrative sections"
    )

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        return _validate_uuid(v)


class StabilityRequest(BaseModel):
    """Payload for POST /api/stability."""

    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(..., description="Valid session UUID")

    @field_validator("session_id")
    @classmethod
    def validate_session(cls, v: str) -> str:
        return _validate_uuid(v)

