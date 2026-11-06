"""Pipeline-level calculation trace and explainability builder for CivicFork.

Stitches together evidence, calculations, and provenance across all stages:
Selected Plot -> Observed/Modelled Context -> Gaps -> Scenarios -> Simulation Scores -> Ranking
"""

from typing import Any, Dict, Optional, Union

from app.models.domain import ScenarioId, SessionData
from app.services.gap_analyzer import get_gap_analyzer
from app.services.impact_simulator import get_impact_simulator
from app.services.ranking_engine import get_ranking_engine
from app.services.scenario_generator import get_scenario_generator


def build_pipeline_trace(
    session: SessionData,
    scenario_id: Optional[Union[ScenarioId, str]] = None,
) -> Dict[str, Any]:
    """Assemble an end-to-end pipeline trace from an active SessionData instance.

    Traces:
    Plot -> Urban Context -> Infrastructure Gaps -> Scenarios -> Simulation Scores -> Ranking

    Args:
        session: Active SessionData containing pipeline stage outputs.
        scenario_id: Optional scenario ID to extract detailed single-scenario provenance.

    Returns:
        Structured dictionary detailing inputs, intermediate values, scores, and ranks.
    """
    plot = session.plot
    urban_ctx = getattr(session, "urban_context", None) or session.context
    summary = getattr(session, "context_summary", None) or (urban_ctx.summary if urban_ctx else None)
    gaps = session.gaps or []
    scenarios = session.scenarios or []
    matrix = session.score_matrix
    ranking = session.ranking
    weights = session.weights_used

    # Determine current workflow stage
    if ranking is not None:
        stage = "ranked"
    elif matrix is not None:
        stage = "simulated"
    elif scenarios:
        stage = "analyzed"
    else:
        stage = "empty"

    trace: Dict[str, Any] = {
        "session_id": session.session_id,
        "workflow_stage": stage,
        "plot": (
            {
                "lat": plot.lat if hasattr(plot, "lat") else plot.get("lat"),
                "lng": plot.lng if hasattr(plot, "lng") else plot.get("lng"),
                "radius_m": plot.radius_m if hasattr(plot, "radius_m") else plot.get("radius_m"),
                "area_sqm": plot.area_sqm if hasattr(plot, "area_sqm") else plot.get("area_sqm"),
                "label": plot.label if hasattr(plot, "label") else plot.get("label"),
            }
            if plot
            else None
        ),
        "urban_context": (
            {
                "observed": {
                    "total_pois": summary.total_pois,
                    "road_network_length_m": summary.road_network_length_m,
                    "road_density_m_per_sqkm": summary.road_density_m_per_sqkm,
                    "major_road_count": summary.major_road_count,
                    "nearest_major_road_m": summary.nearest_major_road_m,
                    "transit_stop_count": summary.transit_stop_count,
                    "nearest_transit_m": summary.nearest_transit_m,
                    "dominant_landuse": summary.dominant_landuse,
                    "green_space_pct": summary.green_space_pct,
                    "commercial_pct": summary.commercial_pct,
                    "industrial_pct": summary.industrial_pct,
                },
                "modelled": {
                    "population_density_estimate": summary.population_density_estimate,
                    "building_density_estimate": summary.building_density_estimate,
                },
            }
            if summary
            else None
        ),
        "infrastructure_gaps": [
            {
                "category": g.category,
                "gap_type": g.gap_type,
                "gap_severity": g.gap_severity,
                "facilities_in_radius": g.facilities_in_radius,
                "expected_facilities": g.expected_facilities,
                "coverage_threshold_m": g.coverage_threshold_m,
                "nearest_facility_distance_m": g.nearest_facility_distance_m,
            }
            for g in gaps
        ],
        "scenarios_generated": [
            {
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "required_area_sqm": s.required_area_sqm,
                "proposed_area_sqm": s.proposed_area_sqm,
                "estimated_cost_inr": s.estimated_cost_inr,
                "estimated_annual_operating_cost_inr": s.estimated_annual_operating_cost_inr,
                "estimated_daily_visitors": s.estimated_daily_visitors,
                "estimated_jobs_created": s.estimated_jobs_created,
                "estimated_traffic_change_pct": s.estimated_traffic_change_pct,
                "green_space_delta_sqm": s.green_space_delta_sqm,
                "impervious_surface_delta_sqm": s.impervious_surface_delta_sqm,
            }
            for s in scenarios
        ],
        "provenance_audit": {
            "configured": "scenarios.yaml templates, base scores, modifier weights, and gap relevance matrices.",
            "observed": "Cached OpenStreetMap POIs, roads, land-use zones, and transit stops.",
            "modelled": "Visitor numbers, direct jobs, traffic % changes, and population density approximations.",
            "calculated": "Gap severities (0-1), 6-dimension scores (0-100), and weighted composite rankings.",
        },
    }

    # Simulation stage trace
    if matrix is not None:
        simulator = get_impact_simulator()
        sim_scores_by_id = {}
        for sc in matrix.scenario_scores:
            try:
                sim_scores_by_id[sc.scenario_id] = simulator.get_calculation_trace(sc.scenario_id)
            except KeyError:
                sim_scores_by_id[sc.scenario_id] = {
                    "unweighted_composite": sc.unweighted_composite,
                    "dimensions": {ds.dimension: ds.score for ds in sc.scores},
                }
        trace["simulation"] = {
            "scenarios_evaluated": matrix.scenarios_evaluated,
            "dimensions_evaluated": matrix.dimensions_evaluated,
            "matrix": matrix.matrix,
            "scenario_traces": sim_scores_by_id,
        }

    # Ranking stage trace
    if ranking is not None:
        trace["ranking"] = {
            "weights_applied": weights.model_dump() if weights else None,
            "leaderboard": [
                {
                    "rank": r.rank,
                    "scenario_id": r.scenario_id,
                    "scenario_name": r.scenario_name,
                    "weighted_score": r.weighted_score,
                    "score_delta_from_top": r.score_delta_from_top,
                    "dimension_contributions": r.dimension_contributions,
                }
                for r in ranking
            ],
        }

    # Optional single-scenario end-to-end breakdown
    target_sid = scenario_id or (ranking[0].scenario_id if ranking else (scenarios[0].id if scenarios else None))
    if target_sid:
        scen_match = next((s for s in scenarios if s.id == target_sid), None)
        gap_match = next((g for g in gaps if g.category == (scen_match.attributes.get("associated_gap_category") if scen_match else target_sid)), None)
        rank_match = next((r for r in ranking if r.scenario_id == target_sid), None) if ranking else None

        trace["scenario_detail"] = {
            "scenario_id": target_sid,
            "scenario": scen_match.model_dump() if scen_match else None,
            "associated_gap": gap_match.model_dump() if gap_match else None,
            "ranking": rank_match.model_dump() if rank_match else None,
        }

    return trace
