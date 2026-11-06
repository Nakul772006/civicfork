"""Configuration loader and validation models for CivicFork YAML configurations."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from app.exceptions import ConfigurationError
from app.settings import settings

logger = logging.getLogger("civicfork.config")

REQUIRED_SCENARIOS = (
    "park",
    "healthcare",
    "education",
    "parking",
    "commercial",
    "community_centre",
    "public_transport",
)

REQUIRED_DIMENSIONS = (
    "traffic",
    "cost",
    "environmental",
    "accessibility",
    "social_utility",
)

REQUIRED_GAP_CATEGORIES = (
    "healthcare",
    "education",
    "parks",
    "transport",
    "parking",
    "commercial",
    "community",
)


# -----------------------------------------------------------------------------
# Configuration Pydantic Models (Immutable / Read-only)
# -----------------------------------------------------------------------------

class DimensionScores(BaseModel):
    """Base score assignments across five core evaluation dimensions."""

    model_config = ConfigDict(frozen=True)

    traffic: float = Field(..., ge=0.0, le=100.0)
    cost: float = Field(..., ge=0.0, le=100.0)
    environmental: float = Field(..., ge=0.0, le=100.0)
    accessibility: float = Field(..., ge=0.0, le=100.0)
    social_utility: float = Field(..., ge=0.0, le=100.0)


class TrafficModifiers(BaseModel):
    """Traffic dimension context modifier parameters."""

    model_config = ConfigDict(frozen=True)

    road_capacity_bonus_weight: float
    road_capacity_max_multiplier: float
    major_road_bonus_close_m: float
    major_road_bonus_close_points: float
    major_road_bonus_medium_m: float
    major_road_bonus_medium_points: float
    congestion_penalty_weight: float
    visitor_load_penalty_weight: float
    reference_daily_trips: float


class CostModifiers(BaseModel):
    """Cost dimension context modifier parameters."""

    model_config = ConfigDict(frozen=True)

    area_scaling_penalty_weight: float
    revenue_offset_bonus: float


class EnvironmentalModifiers(BaseModel):
    """Environmental dimension context modifier parameters."""

    model_config = ConfigDict(frozen=True)

    green_change_weight: float
    impervious_penalty_weight: float
    green_deficit_threshold_pct: float
    green_deficit_bonus_weight: float
    industrial_adjacency_threshold_pct: float
    industrial_adjacency_penalty: float


class AccessibilityModifiers(BaseModel):
    """Accessibility dimension context modifier parameters."""

    model_config = ConfigDict(frozen=True)

    transit_proximity_weight: float
    transit_coverage_weight: float
    transit_coverage_target_stops: float
    road_connectivity_weight: float
    population_density_weight: float
    population_density_target: float
    remoteness_transit_threshold_m: float
    remoteness_road_density_factor: float
    remoteness_penalty: float


class SocialUtilityModifiers(BaseModel):
    """Social utility dimension context modifier parameters."""

    model_config = ConfigDict(frozen=True)

    population_reach_weight: float
    population_reach_target: float
    employment_weight: float
    employment_target_jobs: float
    gap_bonus_weight: float
    underserved_area_bonus: float
    underserved_poi_threshold_factor: float


class ScoringModifiers(BaseModel):
    """Aggregated modifiers container for scoring rules."""

    model_config = ConfigDict(frozen=True)

    traffic: TrafficModifiers
    cost: CostModifiers
    environmental: EnvironmentalModifiers
    accessibility: AccessibilityModifiers
    social_utility: SocialUtilityModifiers


class ScoringReferences(BaseModel):
    """Baseline reference parameters for normalisation."""

    model_config = ConfigDict(frozen=True)

    road_density_m_per_sqkm: float
    poi_count: int
    population_density_ref: float


class GapCategoryThreshold(BaseModel):
    """Expected coverage and baseline facility count for a gap category."""

    model_config = ConfigDict(frozen=True)

    coverage_threshold_m: float
    expected_facilities: int


class ScoringConfig(BaseModel):
    """Complete scoring configuration loaded from scoring.yaml."""

    model_config = ConfigDict(frozen=True)

    base_scores: Dict[str, DimensionScores]
    modifiers: ScoringModifiers
    references: ScoringReferences
    gap_relevance: Dict[str, Dict[str, float]]
    gap_thresholds: Dict[str, GapCategoryThreshold]


class ScenarioTemplate(BaseModel):
    """Scenario template definition loaded from scenarios.yaml."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    category: str
    description: str
    default_area_sqm: float
    ref_area_sqm: float
    cost_per_sqm: float
    operating_ratio: float
    base_visitors: int
    jobs_per_1000sqm: float
    base_traffic_pct: float
    trip_rate: float
    green_ratio: float
    impervious_ratio: float
    revenue_generating: bool
    addresses_gaps: List[str]
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ScenariosConfig(BaseModel):
    """Container for scenario templates loaded from scenarios.yaml."""

    model_config = ConfigDict(frozen=True)

    scenarios: Dict[str, ScenarioTemplate]


class FeasibilityRuleDefinition(BaseModel):
    """Rule metadata describing feasibility checks."""

    model_config = ConfigDict(frozen=True)

    severity: str
    description: str


class ScenarioFeasibilityThresholds(BaseModel):
    """Per-scenario feasibility check constraints."""

    model_config = ConfigDict(frozen=True)

    min_area_sqm: float
    conflict_radius_m: float
    saturation_limit: int
    incompatible_zones: List[str]


class FeasibilityConfig(BaseModel):
    """Container for feasibility rules and constraints loaded from feasibility.yaml."""

    model_config = ConfigDict(frozen=True)

    rules: Dict[str, FeasibilityRuleDefinition]
    scenarios: Dict[str, ScenarioFeasibilityThresholds]


class AppConfig(BaseModel):
    """Root configuration aggregating scoring, scenarios, and feasibility."""

    model_config = ConfigDict(frozen=True)

    scoring: ScoringConfig
    scenarios: ScenariosConfig
    feasibility: FeasibilityConfig


# -----------------------------------------------------------------------------
# Configuration Loader & Validator Functions
# -----------------------------------------------------------------------------

def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Safely read and parse a YAML file into a dictionary."""
    if not file_path.exists():
        raise ConfigurationError(
            f"Configuration file not found: {file_path}",
            details={"path": str(file_path)},
        )
    if not file_path.is_file():
        raise ConfigurationError(
            f"Configuration path is not a file: {file_path}",
            details={"path": str(file_path)},
        )
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                raise ConfigurationError(
                    f"Configuration file {file_path.name} must contain a YAML mapping/dictionary",
                    details={"path": str(file_path)},
                )
            return data
    except yaml.YAMLError as e:
        raise ConfigurationError(
            f"Failed to parse YAML file {file_path.name}: {e}",
            details={"path": str(file_path), "error": str(e)},
        ) from e
    except Exception as e:
        if isinstance(e, ConfigurationError):
            raise
        raise ConfigurationError(
            f"Failed to read configuration file {file_path.name}: {e}",
            details={"path": str(file_path), "error": str(e)},
        ) from e


def validate_scoring_config(raw: Dict[str, Any], path: Path) -> ScoringConfig:
    """Validate structure and completeness of scoring configuration."""
    try:
        config = ScoringConfig(**raw)
    except PydanticValidationError as e:
        raise ConfigurationError(
            f"Invalid scoring configuration in {path.name}",
            details={"errors": e.errors()},
        ) from e

    # Verify all 7 scenarios are present in base_scores
    for scenario_id in REQUIRED_SCENARIOS:
        if scenario_id not in config.base_scores:
            raise ConfigurationError(
                f"Missing base scores for scenario: '{scenario_id}' in {path.name}",
                details={"missing_scenario": scenario_id},
            )

    # Verify all 7 scenarios are present in gap_relevance
    for scenario_id in REQUIRED_SCENARIOS:
        if scenario_id not in config.gap_relevance:
            raise ConfigurationError(
                f"Missing gap relevance mapping for scenario: '{scenario_id}' in {path.name}",
                details={"missing_scenario": scenario_id},
            )

    # Verify all 7 gap categories are in gap_thresholds
    for gap_cat in REQUIRED_GAP_CATEGORIES:
        if gap_cat not in config.gap_thresholds:
            raise ConfigurationError(
                f"Missing gap threshold for category: '{gap_cat}' in {path.name}",
                details={"missing_category": gap_cat},
            )

    return config


def validate_scenarios_config(raw: Dict[str, Any], path: Path) -> ScenariosConfig:
    """Validate structure and completeness of scenario templates."""
    try:
        config = ScenariosConfig(**raw)
    except PydanticValidationError as e:
        raise ConfigurationError(
            f"Invalid scenarios configuration in {path.name}",
            details={"errors": e.errors()},
        ) from e

    for scenario_id in REQUIRED_SCENARIOS:
        if scenario_id not in config.scenarios:
            raise ConfigurationError(
                f"Missing scenario definition: '{scenario_id}' in {path.name}",
                details={"missing_scenario": scenario_id},
            )

    return config


def validate_feasibility_config(raw: Dict[str, Any], path: Path) -> FeasibilityConfig:
    """Validate structure and completeness of feasibility configuration."""
    try:
        config = FeasibilityConfig(**raw)
    except PydanticValidationError as e:
        raise ConfigurationError(
            f"Invalid feasibility configuration in {path.name}",
            details={"errors": e.errors()},
        ) from e

    for scenario_id in REQUIRED_SCENARIOS:
        if scenario_id not in config.scenarios:
            raise ConfigurationError(
                f"Missing feasibility thresholds for scenario: '{scenario_id}' in {path.name}",
                details={"missing_scenario": scenario_id},
            )

    return config


_app_config_cache: Optional[AppConfig] = None


def load_app_config(config_dir: Optional[Path] = None, force_reload: bool = False) -> AppConfig:
    """Safely load and validate all configuration files from the specified directory."""
    global _app_config_cache
    if _app_config_cache is not None and not force_reload:
        return _app_config_cache

    target_dir = config_dir or settings.config_dir
    if not target_dir.exists():
        raise ConfigurationError(
            f"Configuration directory does not exist: {target_dir}",
            details={"config_dir": str(target_dir)},
        )

    scoring_path = target_dir / "scoring.yaml"
    scenarios_path = target_dir / "scenarios.yaml"
    feasibility_path = target_dir / "feasibility.yaml"

    scoring_raw = load_yaml_file(scoring_path)
    scoring_config = validate_scoring_config(scoring_raw, scoring_path)

    scenarios_raw = load_yaml_file(scenarios_path)
    scenarios_config = validate_scenarios_config(scenarios_raw, scenarios_path)

    feasibility_raw = load_yaml_file(feasibility_path)
    feasibility_config = validate_feasibility_config(feasibility_raw, feasibility_path)

    loaded = AppConfig(
        scoring=scoring_config,
        scenarios=scenarios_config,
        feasibility=feasibility_config,
    )
    _app_config_cache = loaded
    logger.info("Successfully loaded and validated CivicFork configuration from %s", target_dir)
    return loaded


def get_app_config() -> AppConfig:
    """Return the cached active AppConfig or load it from the default directory."""
    global _app_config_cache
    if _app_config_cache is None:
        return load_app_config()
    return _app_config_cache


def reset_config_cache() -> None:
    """Reset cached config (primarily used during testing)."""
    global _app_config_cache
    _app_config_cache = None
