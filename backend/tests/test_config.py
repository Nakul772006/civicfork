"""Tests for configuration loading, validation, and session foundation (Phase 1.5)."""

import pytest
from pathlib import Path
from pydantic import ValidationError as PydanticValidationError

from app.api.dependencies import get_config, get_valid_session
from app.config_loader import (
    REQUIRED_DIMENSIONS,
    REQUIRED_GAP_CATEGORIES,
    REQUIRED_SCENARIOS,
    AppConfig,
    get_app_config,
    load_app_config,
    load_yaml_file,
    reset_config_cache,
    validate_feasibility_config,
    validate_scenarios_config,
    validate_scoring_config,
)
from app.exceptions import ConfigurationError, SessionNotFoundError
from app.models.domain import (
    PlotLocation,
    SessionData,
    WeightConfig,
)
from app.session import SessionStore, session_store


# -----------------------------------------------------------------------------
# Configuration Loading & Validation Tests
# -----------------------------------------------------------------------------

def test_load_app_config_success():
    """Verify load_app_config loads and validates all 3 YAML files correctly."""
    reset_config_cache()
    config = load_app_config(force_reload=True)

    assert isinstance(config, AppConfig)

    # 1. Scoring checks
    assert len(config.scoring.base_scores) == 7
    for scenario_id in REQUIRED_SCENARIOS:
        assert scenario_id in config.scoring.base_scores
        scores = config.scoring.base_scores[scenario_id]
        for dim in REQUIRED_DIMENSIONS:
            val = getattr(scores, dim)
            assert 0.0 <= val <= 100.0

    # Gap relevance matrix completeness
    assert len(config.scoring.gap_relevance) == 7
    for scenario_id in REQUIRED_SCENARIOS:
        assert scenario_id in config.scoring.gap_relevance
        for cat in REQUIRED_GAP_CATEGORIES:
            assert cat in config.scoring.gap_relevance[scenario_id]

    # Gap thresholds completeness
    assert len(config.scoring.gap_thresholds) == 7
    for cat in REQUIRED_GAP_CATEGORIES:
        assert cat in config.scoring.gap_thresholds
        assert config.scoring.gap_thresholds[cat].coverage_threshold_m > 0
        assert config.scoring.gap_thresholds[cat].expected_facilities > 0

    # References
    assert config.scoring.references.road_density_m_per_sqkm == 10000.0
    assert config.scoring.references.poi_count == 100
    assert config.scoring.references.population_density_ref == 5000.0

    # 2. Scenarios checks
    assert len(config.scenarios.scenarios) == 7
    for scenario_id in REQUIRED_SCENARIOS:
        template = config.scenarios.scenarios[scenario_id]
        assert template.id == scenario_id
        assert template.name
        assert template.category in ("green_space", "public_service", "infrastructure", "economic")
        assert template.default_area_sqm > 0
        assert template.cost_per_sqm > 0
        assert template.base_visitors > 0
        assert template.jobs_per_1000sqm >= 0

    # 3. Feasibility checks
    assert len(config.feasibility.scenarios) == 7
    assert len(config.feasibility.rules) == 4
    for scenario_id in REQUIRED_SCENARIOS:
        f_thresh = config.feasibility.scenarios[scenario_id]
        assert f_thresh.min_area_sqm > 0
        assert f_thresh.conflict_radius_m > 0
        assert f_thresh.saturation_limit > 0
        assert isinstance(f_thresh.incompatible_zones, list)


def test_config_immutability():
    """Verify that configuration objects are frozen and read-only."""
    config = get_app_config()

    with pytest.raises((PydanticValidationError, TypeError)):
        config.scoring = None  # type: ignore

    with pytest.raises((PydanticValidationError, TypeError)):
        config.scoring.references.poi_count = 999  # type: ignore


def test_missing_config_directory_raises():
    """Verify ConfigurationError when configuration directory does not exist."""
    missing_dir = Path("/tmp/non_existent_config_dir_civicfork_12345")
    with pytest.raises(ConfigurationError) as exc_info:
        load_app_config(config_dir=missing_dir, force_reload=True)
    assert "Configuration directory does not exist" in exc_info.value.message


def test_missing_yaml_file_raises(tmp_path):
    """Verify ConfigurationError when a required YAML file is missing."""
    empty_dir = tmp_path / "empty_config"
    empty_dir.mkdir()
    with pytest.raises(ConfigurationError) as exc_info:
        load_app_config(config_dir=empty_dir, force_reload=True)
    assert "Configuration file not found" in exc_info.value.message


def test_malformed_yaml_syntax_raises(tmp_path):
    """Verify ConfigurationError when YAML file contains syntax errors."""
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("key: [unclosed list", encoding="utf-8")
    with pytest.raises(ConfigurationError) as exc_info:
        load_yaml_file(bad_file)
    assert "Failed to parse YAML file" in exc_info.value.message


def test_non_dict_yaml_content_raises(tmp_path):
    """Verify ConfigurationError when YAML file contains a list instead of mapping."""
    bad_file = tmp_path / "list.yaml"
    bad_file.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ConfigurationError) as exc_info:
        load_yaml_file(bad_file)
    assert "must contain a YAML mapping/dictionary" in exc_info.value.message


def test_missing_scenario_in_scoring_raises(tmp_path):
    """Verify ConfigurationError when scoring config misses a required scenario."""
    incomplete_scoring = {
        "base_scores": {
            "park": {"traffic": 80, "cost": 75, "environmental": 90, "accessibility": 55, "social_utility": 65}
            # healthcare, education, etc. omitted
        },
        "modifiers": {
            "traffic": {"road_capacity_bonus_weight": 10, "road_capacity_max_multiplier": 1.5, "major_road_bonus_close_m": 500, "major_road_bonus_close_points": 10, "major_road_bonus_medium_m": 1000, "major_road_bonus_medium_points": 5, "congestion_penalty_weight": 15, "visitor_load_penalty_weight": 20, "reference_daily_trips": 5000},
            "cost": {"area_scaling_penalty_weight": 15, "revenue_offset_bonus": 15},
            "environmental": {"green_change_weight": 20, "impervious_penalty_weight": 15, "green_deficit_threshold_pct": 15, "green_deficit_bonus_weight": 10, "industrial_adjacency_threshold_pct": 20, "industrial_adjacency_penalty": 5},
            "accessibility": {"transit_proximity_weight": 15, "transit_coverage_weight": 10, "transit_coverage_target_stops": 5, "road_connectivity_weight": 10, "population_density_weight": 10, "population_density_target": 10000, "remoteness_transit_threshold_m": 2000, "remoteness_road_density_factor": 0.5, "remoteness_penalty": 10},
            "social_utility": {"population_reach_weight": 15, "population_reach_target": 10000, "employment_weight": 10, "employment_target_jobs": 50, "gap_bonus_weight": 10, "underserved_area_bonus": 5, "underserved_poi_threshold_factor": 0.5},
        },
        "references": {"road_density_m_per_sqkm": 10000, "poi_count": 100, "population_density_ref": 5000},
        "gap_relevance": {},
        "gap_thresholds": {},
    }
    with pytest.raises(ConfigurationError) as exc_info:
        validate_scoring_config(incomplete_scoring, Path("scoring.yaml"))
    assert "Missing base scores for scenario" in exc_info.value.message


# -----------------------------------------------------------------------------
# Session Foundation & SessionData Tests
# -----------------------------------------------------------------------------

def test_session_store_create_with_session_data():
    """Verify creating a session from an authoritative SessionData object."""
    store = SessionStore()
    custom_plot = PlotLocation(lat=12.3150, lng=76.6550, radius_m=2000, area_sqm=3000.0)
    session_data = SessionData(
        session_id="custom-session-uuid-1",
        plot=custom_plot,
    )

    sid = store.create(session_data)
    assert sid == "custom-session-uuid-1"
    assert store.count() == 1

    retrieved = store.get(sid)
    assert isinstance(retrieved, SessionData)
    assert retrieved.session_id == "custom-session-uuid-1"
    assert retrieved.plot.lat == 12.3150
    assert retrieved.plot.area_sqm == 3000.0


def test_session_store_update_with_session_data():
    """Verify updating a session with a SessionData instance."""
    store = SessionStore()
    sid = store.create()

    weights = WeightConfig(traffic=0.2, cost=0.2, environmental=0.2, accessibility=0.2, gap_improvement=0.1, social_utility=0.1)
    new_data = SessionData(
        session_id=sid,
        plot=PlotLocation(lat=12.31, lng=76.65, radius_m=1000),
        weights_used=weights,
    )

    updated = store.update(sid, new_data)
    assert isinstance(updated, SessionData)
    assert updated.plot.radius_m == 1000
    assert updated.weights_used.traffic == 0.2


def test_session_data_dict_compatibility():
    """Verify SessionData supports dict-like subscription, containment, and iteration."""
    session = SessionData(
        session_id="dict-compat-sid",
        plot=PlotLocation(lat=12.31, lng=76.65, radius_m=2000),
    )

    # __getitem__
    assert session["session_id"] == "dict-compat-sid"
    assert session["plot"].lat == 12.31
    with pytest.raises(KeyError):
        _ = session["non_existent_key"]

    # __contains__
    assert "session_id" in session
    assert "plot" in session
    assert "non_existent_key" not in session

    # get()
    assert session.get("session_id") == "dict-compat-sid"
    assert session.get("missing_key", "default_val") == "default_val"

    # __setitem__
    session["custom_key"] = "custom_value"
    assert session["custom_key"] == "custom_value"

    # update()
    session.update({"narratives": {"overview": "Sample text"}})
    assert session.narratives == {"overview": "Sample text"}

    # keys(), values(), items()
    assert "session_id" in session.keys()
    assert "dict-compat-sid" in session.values()
    items_dict = dict(session.items())
    assert items_dict["session_id"] == "dict-compat-sid"


def test_session_store_get_session_data_and_set():
    """Verify get_session_data and set_session_data methods."""
    store = SessionStore()
    sid = "explicit-session-id"
    data = SessionData(session_id=sid)

    store.set_session_data(sid, data)
    assert store.count() == 1

    fetched = store.get_session_data(sid)
    assert fetched is not None
    assert fetched.session_id == sid


# -----------------------------------------------------------------------------
# Dependency Injection Tests
# -----------------------------------------------------------------------------

def test_get_config_dependency():
    """Verify get_config dependency provides AppConfig singleton."""
    config = get_config()
    assert isinstance(config, AppConfig)
    assert len(config.scenarios.scenarios) == 7


def test_get_valid_session_dependency():
    """Verify get_valid_session resolves existing session and raises on missing."""
    sid = session_store.create()
    resolved = get_valid_session(session_id=sid)
    assert isinstance(resolved, SessionData)
    assert resolved.session_id == sid

    with pytest.raises(SessionNotFoundError):
        get_valid_session(session_id="missing-non-existent-session-id")
