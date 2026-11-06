"""FastAPI request dependencies for CivicFork."""

from typing import Any, Dict
from fastapi import Path
from app.config_loader import AppConfig, get_app_config
from app.exceptions import SessionNotFoundError
from app.models.domain import SessionData
from app.services.context_analyzer import ContextAnalyzer, get_context_analyzer
from app.services.counterfactual_engine import CounterfactualEngine, get_counterfactual_engine as get_counterfactual_engine_service
from app.services.feasibility_checker import FeasibilityChecker, get_feasibility_checker as get_feasibility_checker_service
from app.services.narrative_service import NarrativeService, get_narrative_service as get_narrative_service_service
from app.services.gap_analyzer import GapAnalyzer, get_gap_analyzer as get_gap_analyzer_service
from app.services.impact_simulator import ImpactSimulator, get_impact_simulator as get_impact_simulator_service
from app.services.osm_service import OSMServiceBase, get_osm_service
from app.services.ranking_engine import RankingEngine, get_ranking_engine as get_ranking_engine_service
from app.services.report_generator import ReportGenerator, get_report_generator as get_report_generator_service
from app.services.scenario_generator import ScenarioGenerator, get_scenario_generator as get_scenario_generator_service
from app.session import SessionStore, session_store
from app.settings import Settings, settings


def get_settings() -> Settings:
    """Dependency providing application settings."""
    return settings


def get_config() -> AppConfig:
    """Dependency providing validated application configuration."""
    return get_app_config()


def get_osm() -> OSMServiceBase:
    """Dependency providing the active OSM service instance."""
    return get_osm_service()


def get_analyzer() -> ContextAnalyzer:
    """Dependency providing the active ContextAnalyzer instance."""
    return get_context_analyzer()


def get_gap_analyzer() -> GapAnalyzer:
    """Dependency providing the active GapAnalyzer instance."""
    return get_gap_analyzer_service()


def get_scenario_generator() -> ScenarioGenerator:
    """Dependency providing the active ScenarioGenerator instance."""
    return get_scenario_generator_service()


def get_impact_simulator() -> ImpactSimulator:
    """Dependency providing the active ImpactSimulator instance."""
    return get_impact_simulator_service()


def get_ranking_engine() -> RankingEngine:
    """Dependency providing the active RankingEngine instance."""
    return get_ranking_engine_service()


def get_counterfactual_engine() -> CounterfactualEngine:
    """Dependency providing the active CounterfactualEngine instance."""
    return get_counterfactual_engine_service()


def get_feasibility_checker() -> FeasibilityChecker:
    """Dependency providing the active FeasibilityChecker instance."""
    return get_feasibility_checker_service()


def get_narrative_service() -> NarrativeService:
    """Dependency providing the active NarrativeService instance."""
    return get_narrative_service_service()


def get_report_generator() -> ReportGenerator:
    """Dependency providing the active ReportGenerator instance."""
    return get_report_generator_service()


def get_session_store() -> SessionStore:
    """Dependency providing the active in-memory session store."""
    return session_store


def get_valid_session(
    session_id: str = Path(..., description="UUID of the active simulation session")
) -> SessionData:
    """Dependency validating that a session exists and returning it."""
    session = session_store.get(session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session
