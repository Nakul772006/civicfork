"""REST API route definitions for CivicFork.

Orchestrates the core analytical workflow:
1. POST /api/analyze: Plot validation, context analysis, gap analysis, and scenario generation.
2. POST /api/simulate: 6-dimension impact simulation for 7 policy alternatives.
3. POST /api/rank: Municipal priority weighting and scenario ranking.
4. GET  /api/health: Service readiness and active session tracking.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import (
    get_analyzer,
    get_config,
    get_counterfactual_engine,
    get_feasibility_checker,
    get_gap_analyzer,
    get_impact_simulator,
    get_narrative_service,
    get_osm,
    get_ranking_engine,
    get_report_generator,
    get_scenario_generator,
    get_session_store,
    get_settings,
    get_stability_analyzer,
)
from app.config_loader import AppConfig
from app.exceptions import MissingPrerequisiteError, ReportGenerationError, SessionNotFoundError
from app.models.domain import (
    ContextSummary,
    NarrativeRequest,
    NarrativeResponse,
    PlotLocation,
    ReportData,
    SessionData,
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
    StabilityRequest,
)
from app.models.responses import (
    AnalyzeBounds,
    AnalyzeResponse,
    AnalyzeResponseData,
    CounterfactualResponse,
    CounterfactualResponseData,
    ExplainResponse,
    ExplainResponseData,
    FeasibilityResponse,
    FeasibilityResponseData,
    HealthResponse,
    HealthResponseData,
    RankResponse,
    RankResponseData,
    SimulateResponse,
    SimulateResponseData,
    StabilityResponse,
    StabilityResponseData,
)
from app.services.context_analyzer import ContextAnalyzer
from app.services.counterfactual_engine import CounterfactualEngine
from app.services.feasibility_checker import FeasibilityChecker
from app.services.gap_analyzer import GapAnalyzer
from app.services.impact_simulator import ImpactSimulator
from app.services.narrative_service import NarrativeService
from app.services.osm_service import OSMServiceBase
from app.services.ranking_engine import RankingEngine
from app.services.report_generator import ReportGenerator
from app.services.scenario_generator import ScenarioGenerator
from app.services.stability_analyzer import StabilityAnalyzer
from app.session import SessionStore
from app.settings import Settings

logger = logging.getLogger("civicfork.routes")

api_router = APIRouter(prefix="/api", tags=["API"])


@api_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
)
async def health_check(
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
    config: AppConfig = Depends(get_config),
    osm: OSMServiceBase = Depends(get_osm),
) -> Dict[str, Any]:
    """Verify backend health, data readiness, and active session count."""
    is_config_loaded = config is not None and len(config.scenarios.scenarios) == 7
    is_osm_loaded = osm.is_loaded()

    return {
        "success": True,
        "data": HealthResponseData(
            status="healthy",
            osm_data_loaded=is_osm_loaded,
            config_loaded=is_config_loaded,
            active_sessions=store.count(),
            demo_area=settings.demo_area,
        ),
        "error": None,
    }


@api_router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Plot Location & Urban Context",
)
async def analyze_plot(
    request: AnalyzeRequest,
    analyzer: ContextAnalyzer = Depends(get_analyzer),
    gap_analyzer: GapAnalyzer = Depends(get_gap_analyzer),
    scenario_generator: ScenarioGenerator = Depends(get_scenario_generator),
    osm: OSMServiceBase = Depends(get_osm),
    store: SessionStore = Depends(get_session_store),
) -> Dict[str, Any]:
    """First stage of CivicFork workflow: validate plot, analyze context, compute gaps, generate scenarios."""
    # 1. Plot domain model from validated request
    plot = PlotLocation(
        lat=request.lat,
        lng=request.lng,
        radius_m=request.radius_m,
        area_sqm=request.area_sqm,
        label=request.label,
    )

    # 2. Pipeline execution: Context -> Gaps -> Scenarios
    urban_ctx = analyzer.analyze(plot)
    gaps = gap_analyzer.analyze(plot, urban_ctx)
    scenarios = scenario_generator.generate(plot, urban_ctx, gaps)

    # 3. GeoJSON layers for frontend map rendering
    poi_geojson = osm.get_geojson(plot.lat, plot.lng, plot.radius_m, layer="pois")
    landuse_geojson = osm.get_geojson(plot.lat, plot.lng, plot.radius_m, layer="landuse")
    transport_geojson = osm.get_geojson(plot.lat, plot.lng, plot.radius_m, layer="transport")

    # 4. Generate new session ID and persist SessionData
    session_id = str(uuid.uuid4())
    session = SessionData(
        session_id=session_id,
        plot=plot,
        context=urban_ctx,
        gaps=gaps,
        scenarios=scenarios,
    )
    # Store explicit workflow attributes
    session.urban_context = urban_ctx
    session.context_summary = urban_ctx.summary
    session.poi_geojson = poi_geojson
    session.landuse_geojson = landuse_geojson
    session.transport_geojson = transport_geojson

    store.set_session_data(session_id, session)

    data = AnalyzeResponseData(
        session_id=session_id,
        plot=plot,
        context_summary=urban_ctx.summary,
        gaps=gaps,
        scenarios=scenarios,
        poi_geojson=poi_geojson,
        landuse_geojson=landuse_geojson,
        transport_geojson=transport_geojson,
        bounds=AnalyzeBounds(
            center=[plot.lat, plot.lng],
            radius_m=plot.radius_m,
        ),
    )

    return {
        "success": True,
        "data": data,
        "error": None,
    }


@api_router.post(
    "/simulate",
    response_model=SimulateResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate Development Scenarios",
)
async def simulate_scenarios(
    request: SimulateRequest,
    simulator: ImpactSimulator = Depends(get_impact_simulator),
    ranking_engine: RankingEngine = Depends(get_ranking_engine),
    stability_analyzer: StabilityAnalyzer = Depends(get_stability_analyzer),
    store: SessionStore = Depends(get_session_store),
) -> Dict[str, Any]:
    """Second stage of CivicFork workflow: simulate 6 impact dimensions for all 7 alternatives."""
    session = store.get(request.session_id)
    if session is None:
        raise SessionNotFoundError(request.session_id)

    # Enforce workflow prerequisite: analysis must be completed
    scenarios = session.scenarios
    urban_ctx = getattr(session, "urban_context", None) or session.context

    if not scenarios or urban_ctx is None:
        raise MissingPrerequisiteError(
            message="Analysis must be completed before running simulation.",
            missing_field="scenarios",
        )

    gaps = session.gaps or []

    # Run Impact Simulator across all 7 scenarios and 6 dimensions
    score_matrix = simulator.simulate_all(scenarios, urban_ctx, gaps)

    # Compute default baseline ranking using equal priority weights
    default_weights = WeightConfig().normalised()
    default_ranking = ranking_engine.rank(
        score_matrix,
        weights=default_weights,
        scenarios=scenarios,
    )

    # Compute default stability
    default_stability = stability_analyzer.analyze(
        score_matrix=score_matrix,
        baseline_ranking=default_ranking,
        scenarios=scenarios,
    )

    # Update session state with simulation outputs
    session.score_matrix = score_matrix
    session.scenario_scores = score_matrix.scenario_scores
    session.ranking = default_ranking
    session.weights_used = default_weights
    session.stability = default_stability

    data = SimulateResponseData(
        scenarios=scenarios,
        score_matrix=score_matrix,
        default_weights=default_weights,
        default_ranking=default_ranking,
    )

    return {
        "success": True,
        "data": data,
        "error": None,
    }


@api_router.post(
    "/rank",
    response_model=RankResponse,
    status_code=status.HTTP_200_OK,
    summary="Rank Scenarios by Municipal Priority Weights",
)
async def rank_scenarios(
    request: RankRequest,
    ranking_engine: RankingEngine = Depends(get_ranking_engine),
    stability_analyzer: StabilityAnalyzer = Depends(get_stability_analyzer),
    store: SessionStore = Depends(get_session_store),
) -> Dict[str, Any]:
    """Third stage of CivicFork workflow: rank scenarios using user-supplied priority weights."""
    session = store.get(request.session_id)
    if session is None:
        raise SessionNotFoundError(request.session_id)

    # Enforce workflow prerequisite: simulation must be completed
    if session.score_matrix is None:
        raise MissingPrerequisiteError(
            message="Simulation must be completed before ranking scenarios.",
            missing_field="score_matrix",
        )

    scenarios = session.scenarios or []

    # Calculate weighted ranking with user-specified priority weights
    ranking = ranking_engine.rank(
        scores_or_matrix_or_session=session.score_matrix,
        weights=request.weights,
        scenarios=scenarios,
    )

    weights_applied = request.weights.normalised()

    # Calculate deterministic sensitivity analysis across alternative configurations
    stability = stability_analyzer.analyze(
        score_matrix=session.score_matrix,
        baseline_ranking=ranking,
        scenarios=scenarios,
    )

    # Update session state
    session.ranking = ranking
    session.weights_used = weights_applied
    session.stability = stability

    data = RankResponseData(
        ranking=ranking,
        weights_applied=weights_applied,
        stability=stability,
    )

    return {
        "success": True,
        "data": data,
        "error": None,
    }


@api_router.post(
    "/counterfactual",
    response_model=CounterfactualResponse,
    status_code=status.HTTP_200_OK,
    summary="Pairwise Counterfactual Scenario Comparison",
)
async def compare_counterfactual(
    request: CounterfactualRequest,
    engine: CounterfactualEngine = Depends(get_counterfactual_engine),
    store: SessionStore = Depends(get_session_store),
) -> Dict[str, Any]:
    """Fourth stage of CivicFork workflow: pairwise comparison between Scenario A and Scenario B."""
    session = store.get(request.session_id)
    if session is None:
        raise SessionNotFoundError(request.session_id)

    # Prerequisite: score_matrix must be present
    if session.score_matrix is None:
        raise MissingPrerequisiteError(
            message="Simulation must be completed before running counterfactual comparison.",
            missing_field="score_matrix",
        )

    scenarios = session.scenarios or []

    result = engine.compare(
        scenario_a_id=request.scenario_a_id,
        scenario_b_id=request.scenario_b_id,
        score_matrix=session.score_matrix,
        scenarios=scenarios,
    )

    # Mutate SessionData: sets counterfactual
    session.counterfactual = result

    data = CounterfactualResponseData(result=result)

    return {
        "success": True,
        "data": data,
        "error": None,
    }


@api_router.post(
    "/stability",
    response_model=StabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Decision Stability / Sensitivity Analysis",
)
async def evaluate_stability(
    request: StabilityRequest,
    analyzer: StabilityAnalyzer = Depends(get_stability_analyzer),
    store: SessionStore = Depends(get_session_store),
) -> Dict[str, Any]:
    """Evaluate robustness of the recommended scenario across alternative priority weight configurations."""
    session = store.get(request.session_id)
    if session is None:
        raise SessionNotFoundError(request.session_id)

    # Enforce workflow prerequisites: simulation and ranking must be completed
    if session.score_matrix is None:
        raise MissingPrerequisiteError(
            message="Simulation must be completed before running stability analysis.",
            missing_field="score_matrix",
        )
    if session.ranking is None:
        raise MissingPrerequisiteError(
            message="Ranking must be completed before running stability analysis.",
            missing_field="ranking",
        )

    scenarios = session.scenarios or []

    result = analyzer.analyze(
        score_matrix=session.score_matrix,
        baseline_ranking=session.ranking,
        scenarios=scenarios,
    )

    # Mutate SessionData: sets stability
    session.stability = result

    data = StabilityResponseData(result=result)

    return {
        "success": True,
        "data": data,
        "error": None,
    }


@api_router.post(
    "/feasibility",
    response_model=FeasibilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Scenario Feasibility Constraints",
)
async def check_feasibility(
    request: FeasibilityRequest,
    checker: FeasibilityChecker = Depends(get_feasibility_checker),
    store: SessionStore = Depends(get_session_store),
) -> Dict[str, Any]:
    """Evaluate physical and regulatory feasibility constraints for scenarios."""
    session = store.get(request.session_id)
    if session is None:
        raise SessionNotFoundError(request.session_id)

    # Prerequisite: scenarios, urban_context, and plot must be present
    scenarios = session.scenarios
    urban_ctx = getattr(session, "urban_context", None) or session.context
    plot = session.plot

    if not scenarios or urban_ctx is None or plot is None:
        raise MissingPrerequisiteError(
            message="Analysis must be completed before running feasibility evaluation.",
            missing_field="scenarios",
        )

    gaps = session.gaps or []

    all_verdicts = checker.evaluate_all(
        scenarios=scenarios,
        plot=plot,
        context=urban_ctx,
        gaps=gaps,
    )

    if request.scenario_id:
        verdicts = [v for v in all_verdicts if v.scenario_id == request.scenario_id]
        if not verdicts:
            matched_sc = next((s for s in scenarios if s.id == request.scenario_id), None)
            if matched_sc:
                verdicts = [checker.evaluate(matched_sc, plot, urban_ctx, gaps)]
            else:
                verdicts = all_verdicts
    else:
        verdicts = all_verdicts

    # Mutate SessionData: sets feasibility
    session.feasibility = all_verdicts

    data = FeasibilityResponseData(verdicts=verdicts)

    return {
        "success": True,
        "data": data,
        "error": None,
    }


@api_router.post(
    "/explain",
    response_model=ExplainResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI Narrative Explanation",
)
async def generate_explanation(
    request: ExplainRequest,
    narrative_svc: NarrativeService = Depends(get_narrative_service),
    store: SessionStore = Depends(get_session_store),
) -> Dict[str, Any]:
    """Generate AI narrative explanation or deterministic fallback from computed session metrics."""
    session = store.get(request.session_id)
    if session is None:
        raise SessionNotFoundError(request.session_id)

    # 1. Prerequisite: plot and urban_context
    plot = session.plot
    urban_ctx = getattr(session, "urban_context", None) or session.context

    if plot is None or urban_ctx is None:
        raise MissingPrerequisiteError(
            message="Plot analysis must be completed before generating explanations.",
            missing_field="context",
        )

    # Context summary resolution
    if hasattr(urban_ctx, "summary"):
        ctx_summary = urban_ctx.summary
    elif isinstance(urban_ctx, dict) and "summary" in urban_ctx:
        ctx_summary = urban_ctx["summary"]
    else:
        ctx_summary = getattr(session, "context_summary", None)

    if ctx_summary is None:
        raise MissingPrerequisiteError(
            message="Context summary is missing from session.",
            missing_field="context_summary",
        )

    # 2. Prerequisite: score_matrix for score, counterfactual, or full report
    if request.narrative_type in ("score_explanation", "full_report", "counterfactual_explanation"):
        if session.score_matrix is None:
            raise MissingPrerequisiteError(
                message=f"Simulation must be completed before generating a '{request.narrative_type}'.",
                missing_field="score_matrix",
            )

    # 3. Prerequisite: counterfactual comparison if specifically requesting counterfactual explanation
    if request.narrative_type == "counterfactual_explanation":
        if session.counterfactual is None:
            raise MissingPrerequisiteError(
                message="Counterfactual comparison must be completed before generating a counterfactual explanation.",
                missing_field="counterfactual",
            )

    # 4. Construct strictly bounded NarrativeRequest
    narrative_req = NarrativeRequest(
        narrative_type=request.narrative_type,
        plot=plot,
        context_summary=ctx_summary,
        gaps=session.gaps or [],
        scenarios=session.scenarios or [],
        score_matrix=session.score_matrix,
        ranking=session.ranking,
        feasibility=session.feasibility,
        counterfactual=session.counterfactual,
    )

    # 5. Synthesize narrative
    narrative = narrative_svc.generate_narrative(narrative_req)

    # 6. Mutate SessionData: cache in narratives dict
    if not hasattr(session, "narratives") or session.narratives is None:
        session.narratives = {}
    session.narratives[request.narrative_type] = narrative

    data = ExplainResponseData(narrative=narrative)

    return {
        "success": True,
        "data": data,
        "error": None,
    }


@api_router.post(
    "/report",
    summary="Generate Municipal Decision-Support PDF Report",
    response_class=Response,
)
async def generate_report(
    request: ReportRequest,
    store: SessionStore = Depends(get_session_store),
    report_gen: ReportGenerator = Depends(get_report_generator),
    ranking_engine: RankingEngine = Depends(get_ranking_engine),
    feasibility_checker: FeasibilityChecker = Depends(get_feasibility_checker),
    counterfactual_engine: CounterfactualEngine = Depends(get_counterfactual_engine),
    narrative_svc: NarrativeService = Depends(get_narrative_service),
) -> Response:
    """Generate professional 6-page Municipal Decision PDF report via ReportLab."""
    session = store.get(request.session_id)
    if session is None:
        raise SessionNotFoundError(request.session_id)

    # 1. Prerequisite: plot must be analyzed
    plot = session.plot
    if plot is None:
        raise MissingPrerequisiteError(
            message="Plot analysis must be completed before generating a report.",
            missing_field="plot",
        )
    if not isinstance(plot, PlotLocation):
        plot = PlotLocation(**plot)

    # 2. Extract ContextSummary
    urban_ctx = session.context
    if hasattr(urban_ctx, "summary"):
        ctx_summary = urban_ctx.summary
    elif isinstance(urban_ctx, dict) and "summary" in urban_ctx:
        ctx_summary = urban_ctx["summary"]
    else:
        ctx_summary = getattr(session, "context_summary", None)

    if ctx_summary is None:
        raise MissingPrerequisiteError(
            message="Context summary is missing from session.",
            missing_field="context_summary",
        )
    if not isinstance(ctx_summary, ContextSummary):
        ctx_summary = ContextSummary(**ctx_summary)

    # 3. Prerequisite: score_matrix
    if session.score_matrix is None:
        raise MissingPrerequisiteError(
            message="Simulation must be completed before generating a report.",
            missing_field="score_matrix",
        )

    # 4. Ensure ranking exists
    if session.ranking is None:
        default_weights = WeightConfig().normalised()
        session.ranking = ranking_engine.rank(
            session.score_matrix,
            weights=default_weights,
            scenarios=session.scenarios or [],
        )
        session.weights_used = default_weights

    # 5. Ensure feasibility verdicts exist
    if session.feasibility is None and session.scenarios:
        try:
            urban_ctx_full = getattr(session, "urban_context", None) or session.context
            session.feasibility = feasibility_checker.evaluate_all(
                scenarios=session.scenarios,
                plot=plot,
                context=urban_ctx_full,
                gaps=session.gaps or [],
            )
        except Exception as exc:
            logger.warning(f"Feasibility pre-check for report encountered warning: {exc}")

    # 6. Ensure counterfactual exists for Rank #1 vs Rank #2
    if session.counterfactual is None and session.ranking and len(session.ranking) >= 2:
        try:
            session.counterfactual = counterfactual_engine.compare(
                scenario_a_id=session.ranking[0].scenario_id,
                scenario_b_id=session.ranking[1].scenario_id,
                score_matrix=session.score_matrix,
                scenarios=session.scenarios,
            )
        except Exception as exc:
            logger.warning(f"Counterfactual pre-check for report encountered warning: {exc}")

    # 7. AI Narrative resolution with deterministic fallback guarantee
    narrative_res = None
    if request.include_narrative:
        if hasattr(session, "narratives") and session.narratives and "full_report" in session.narratives:
            narrative_res = session.narratives["full_report"]
        else:
            narrative_req = NarrativeRequest(
                narrative_type="full_report",
                plot=plot,
                context_summary=ctx_summary,
                gaps=session.gaps or [],
                scenarios=session.scenarios or [],
                score_matrix=session.score_matrix,
                ranking=session.ranking,
                feasibility=session.feasibility,
                counterfactual=session.counterfactual,
            )
            try:
                narrative_res = narrative_svc.generate_narrative(narrative_req)
                if not hasattr(session, "narratives") or session.narratives is None:
                    session.narratives = {}
                session.narratives["full_report"] = narrative_res
            except Exception as exc:
                logger.warning(f"AI narrative generation for PDF report failed ({exc}). Using deterministic fallback.")
                try:
                    narrative_res = narrative_svc._build_deterministic_fallback(
                        narrative_req, f"AI service unavailable ({exc})"
                    )
                except Exception:
                    narrative_res = None

    # 8. Compile authoritative ReportData
    report_data = ReportData(
        report_title="CivicFork Municipal Urban Decision-Support Assessment",
        generated_at=datetime.now(timezone.utc).isoformat(),
        plot=plot,
        context_summary=ctx_summary,
        gaps=session.gaps or [],
        scenarios=session.scenarios or [],
        score_matrix=session.score_matrix,
        ranking=session.ranking,
        weights_used=session.weights_used,
        feasibility=session.feasibility,
        counterfactual=session.counterfactual,
        narratives=narrative_res,
    )

    # 9. Generate ReportLab PDF bytes
    try:
        pdf_bytes = report_gen.generate_pdf(report_data, session_id=request.session_id)
    except Exception as exc:
        logger.error(f"Failed to generate PDF report: {exc}", exc_info=True)
        raise ReportGenerationError(f"Failed to render ReportLab PDF report: {exc}")

    filename = f"CivicFork_Decision_Report_{request.session_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
