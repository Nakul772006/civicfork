"""Impact Simulation Engine for CivicFork.

Deterministically calculates multi-dimensional impact scores (0–100, higher is better)
for the seven generated urban development policy scenarios across the six approved dimensions:
1. Traffic (lower burden -> higher score)
2. Cost / Financial (lower lifecycle cost -> higher score)
3. Environmental Impact (more green space, less impervious surface -> higher score)
4. Accessibility (better transit & road connectivity -> higher score)
5. Infrastructure-Gap Improvement (closing severe identified gaps -> higher score)
6. Public / Social Utility (higher community reach, jobs, and service value -> higher score)

Preserves data integrity semantics:
- Contextual metrics from OSM are observed evidence, not authoritative zoning.
- Scenario visitor numbers, traffic changes, and costs are rule-based modelled estimates.
- Distance metrics are geospatial proximity, not routed travel times.
- Final dimension scores are clamped to [0.0, 100.0] and rounded to 1 decimal place.
- No weighted ranking or composite weighting is performed in this phase.
"""

import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config_loader import AppConfig, get_app_config
from app.models.domain import (
    ContextSummary,
    DIMENSION_NAMES,
    DimensionName,
    DimensionScore,
    InfrastructureGap,
    SCENARIO_IDS,
    Scenario,
    ScenarioId,
    ScenarioScore,
    ScoreExplanation,
    ScoreMatrix,
    SessionData,
    UrbanContext,
)

logger = logging.getLogger("civicfork.impact_simulator")

# Direction notes for transparent UI presentation
DIRECTION_NOTES: Dict[DimensionName, str] = {
    "traffic": "Higher = lower local traffic disruption (better flow)",
    "cost": "Higher = lower municipal financial burden (more affordable)",
    "environmental": "Higher = lower environmental impact and higher green space enhancement",
    "accessibility": "Higher = better resident access to transit and road network",
    "gap_improvement": "Higher = stronger closure of identified infrastructure gaps",
    "social_utility": "Higher = greater community reach, job creation, and service utility",
}

# Rule names for transparent explainability
RULE_NAMES: Dict[DimensionName, str] = {
    "traffic": "traffic_scoring_rule",
    "cost": "cost_scoring_rule",
    "environmental": "environmental_scoring_rule",
    "accessibility": "accessibility_scoring_rule",
    "gap_improvement": "gap_improvement_rule",
    "social_utility": "social_utility_rule",
}


def clamp_score(value: float) -> float:
    """Clamp numeric score strictly to [0.0, 100.0] and round to 1 decimal place."""
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return round(min(100.0, max(0.0, value)), 1)


class ImpactSimulator:
    """Deterministic simulation engine computing multi-dimensional impact scores."""

    def __init__(self, config: Optional[AppConfig] = None):
        self._config = config
        self._last_traces: Dict[str, Dict[str, Any]] = {}

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            self._config = get_app_config()
        return self._config

    @property
    def last_traces(self) -> Dict[str, Dict[str, Any]]:
        """Return a copy of traces from the latest simulation run."""
        return dict(self._last_traces)

    def simulate(
        self,
        scenarios_or_session: Union[List[Scenario], SessionData],
        context: Optional[Union[UrbanContext, ContextSummary]] = None,
        gaps: Optional[List[InfrastructureGap]] = None,
        config: Optional[AppConfig] = None,
    ) -> ScoreMatrix:
        """Simulate all development scenarios and return the complete ScoreMatrix.

        Supports invocation via:
        - simulate(session): extracts scenarios, context, gaps from SessionData and stores score_matrix
        - simulate(scenarios, context, gaps): standalone simulation
        """
        active_config = config or self._config or self.config

        if isinstance(scenarios_or_session, SessionData):
            session = scenarios_or_session
            scenarios = session.scenarios or []
            if not isinstance(scenarios, list) or len(scenarios) == 0:
                raise ValueError("SessionData must contain a non-empty list of Scenario models.")

            session_context = session.context
            session_gaps = session.gaps or []

            matrix = self.simulate_all(
                scenarios=scenarios,
                context=session_context,
                gaps=session_gaps,
                config=active_config,
            )
            session.score_matrix = matrix
            return matrix

        elif isinstance(scenarios_or_session, list):
            return self.simulate_all(
                scenarios=scenarios_or_session,
                context=context,
                gaps=gaps,
                config=active_config,
            )
        else:
            raise TypeError("Expected List[Scenario] or SessionData as first argument.")

    def simulate_all(
        self,
        scenarios: List[Scenario],
        context: Optional[Union[UrbanContext, ContextSummary]] = None,
        gaps: Optional[List[InfrastructureGap]] = None,
        config: Optional[AppConfig] = None,
    ) -> ScoreMatrix:
        """Simulate a list of 7 scenarios and assemble the 7x6 ScoreMatrix."""
        active_config = config or self._config or self.config

        if len(scenarios) != 7:
            logger.warning("Simulate called with %d scenarios instead of 7.", len(scenarios))

        summary = self._resolve_summary(context, active_config)
        resolved_gaps = gaps or []

        scenario_scores: List[ScenarioScore] = []
        matrix_rows: List[List[float]] = []
        new_traces: Dict[str, Dict[str, Any]] = {}

        for scenario in scenarios:
            sc_score, sc_trace = self._calculate_scenario_score(
                scenario=scenario,
                summary=summary,
                gaps=resolved_gaps,
                active_config=active_config,
            )
            scenario_scores.append(sc_score)
            matrix_rows.append([ds.score for ds in sc_score.scores])
            new_traces[scenario.id] = sc_trace

        self._last_traces = new_traces

        return ScoreMatrix(
            scenario_scores=scenario_scores,
            dimensions=list(DIMENSION_NAMES),
            matrix=matrix_rows,
            scenarios_evaluated=len(scenario_scores),
            dimensions_evaluated=len(DIMENSION_NAMES),
        )

    def simulate_scenario(
        self,
        scenario: Scenario,
        context: Optional[Union[UrbanContext, ContextSummary]] = None,
        gaps: Optional[List[InfrastructureGap]] = None,
        config: Optional[AppConfig] = None,
    ) -> ScenarioScore:
        """Simulate a single scenario and return its ScenarioScore."""
        active_config = config or self._config or self.config
        summary = self._resolve_summary(context, active_config)
        resolved_gaps = gaps or []

        sc_score, sc_trace = self._calculate_scenario_score(
            scenario=scenario,
            summary=summary,
            gaps=resolved_gaps,
            active_config=active_config,
        )
        self._last_traces[scenario.id] = sc_trace
        return sc_score

    def get_calculation_trace(
        self, scenario_or_id: Union[Scenario, ScenarioScore, str]
    ) -> Dict[str, Any]:
        """Retrieve the calculation and explainability trace for a scenario."""
        if isinstance(scenario_or_id, Scenario):
            sid = scenario_or_id.id
        elif isinstance(scenario_or_id, ScenarioScore):
            sid = scenario_or_id.scenario_id
        else:
            sid = str(scenario_or_id)

        if sid in self._last_traces:
            return dict(self._last_traces[sid])

        raise KeyError(f"No simulation calculation trace available for scenario '{sid}'.")

    # -------------------------------------------------------------------------
    # Scenario-level orchestration
    # -------------------------------------------------------------------------

    def _calculate_scenario_score(
        self,
        scenario: Scenario,
        summary: ContextSummary,
        gaps: List[InfrastructureGap],
        active_config: AppConfig,
    ) -> Tuple[ScenarioScore, Dict[str, Any]]:
        """Calculate all 6 dimension scores for one scenario."""
        sid = scenario.id
        base_scores = active_config.scoring.base_scores.get(sid)

        # 1. Traffic Dimension
        traffic_dim, traffic_trace = self.calculate_traffic_score(
            scenario=scenario,
            summary=summary,
            active_config=active_config,
        )

        # 2. Cost Dimension
        cost_dim, cost_trace = self.calculate_cost_score(
            scenario=scenario,
            summary=summary,
            active_config=active_config,
        )

        # 3. Environmental Dimension
        env_dim, env_trace = self.calculate_environment_score(
            scenario=scenario,
            summary=summary,
            active_config=active_config,
        )

        # 4. Accessibility Dimension
        access_dim, access_trace = self.calculate_accessibility_score(
            scenario=scenario,
            summary=summary,
            active_config=active_config,
        )

        # 5. Gap Improvement Dimension
        gap_dim, gap_trace = self.calculate_gap_improvement_score(
            scenario=scenario,
            gaps=gaps,
            active_config=active_config,
        )

        # 6. Social Utility Dimension
        social_dim, social_trace = self.calculate_social_utility_score(
            scenario=scenario,
            summary=summary,
            gaps=gaps,
            active_config=active_config,
        )

        scores = [traffic_dim, cost_dim, env_dim, access_dim, gap_dim, social_dim]
        unweighted_composite = round(sum(d.score for d in scores) / 6.0, 1)

        scenario_score = ScenarioScore(
            scenario_id=sid,
            scores=scores,
            unweighted_composite=unweighted_composite,
        )

        scenario_trace = {
            "scenario_id": sid,
            "unweighted_composite": unweighted_composite,
            "dimensions": {
                "traffic": traffic_trace,
                "cost": cost_trace,
                "environmental": env_trace,
                "accessibility": access_trace,
                "gap_improvement": gap_trace,
                "social_utility": social_trace,
            },
            "evidence_semantics": {
                "observed": "OSM road network density, transit stop count/distance, landuse fractions, and POI counts.",
                "modelled": "Estimated visitors, jobs created, traffic change %, surface deltas, and population density.",
                "configured": "Base dimension scores, modifier sensitivities, and gap relevance matrix from scoring.yaml.",
                "calculated": "Deterministic 0-100 scores where higher always means better.",
            },
        }

        return scenario_score, scenario_trace

    # -------------------------------------------------------------------------
    # Dimension Calculations
    # -------------------------------------------------------------------------

    def calculate_traffic_score(
        self,
        scenario: Scenario,
        summary: ContextSummary,
        active_config: AppConfig,
    ) -> Tuple[DimensionScore, Dict[str, Any]]:
        """Calculate Traffic Score (0-100, higher = lower local traffic disruption)."""
        sid = scenario.id
        base_score = active_config.scoring.base_scores[sid].traffic
        mods = active_config.scoring.modifiers.traffic
        refs = active_config.scoring.references

        trip_rate = float(scenario.attributes.get("trip_rate", 1.5))
        ref_daily_trips = max(1.0, mods.reference_daily_trips)
        ref_road_density = max(1.0, refs.road_density_m_per_sqkm)

        # Trip load = (daily_visitors * trip_rate) / reference_daily_trips
        trip_load = (scenario.estimated_daily_visitors * trip_rate) / ref_daily_trips

        # Road capacity bonus: +min(road_density / ref_road_density, max_multiplier) * weight
        road_ratio = summary.road_density_m_per_sqkm / ref_road_density
        road_cap_bonus = min(road_ratio, mods.road_capacity_max_multiplier) * mods.road_capacity_bonus_weight

        # Major road proximity bonus: close (<500m) -> +10, medium (<1000m) -> +5
        if summary.nearest_major_road_m < mods.major_road_bonus_close_m:
            major_road_bonus = mods.major_road_bonus_close_points
        elif summary.nearest_major_road_m < mods.major_road_bonus_medium_m:
            major_road_bonus = mods.major_road_bonus_medium_points
        else:
            major_road_bonus = 0.0

        # Existing congestion penalty: -(commercial_pct / 100) * weight
        congestion_penalty = (summary.commercial_pct / 100.0) * mods.congestion_penalty_weight

        # Visitor load penalty: -trip_load * weight
        visitor_load_penalty = trip_load * mods.visitor_load_penalty_weight

        raw_result = base_score + road_cap_bonus + major_road_bonus - congestion_penalty - visitor_load_penalty
        normalised_result = clamp_score(raw_result)

        formula_desc = (
            f"Base ({base_score:.1f}) + Road Capacity Bonus (+{road_cap_bonus:.1f}) "
            f"+ Major Road Bonus (+{major_road_bonus:.1f}) - Congestion Penalty (-{congestion_penalty:.1f}) "
            f"- Visitor Load Penalty (-{visitor_load_penalty:.1f})"
        )

        input_factors = {
            "estimated_daily_visitors": float(scenario.estimated_daily_visitors),
            "trip_rate": trip_rate,
            "road_density_m_per_sqkm": float(summary.road_density_m_per_sqkm),
            "nearest_major_road_m": float(summary.nearest_major_road_m),
            "commercial_pct": float(summary.commercial_pct),
        }
        intermediate_values = {
            "trip_load": round(trip_load, 4),
            "road_capacity_bonus": round(road_cap_bonus, 2),
            "major_road_bonus": round(major_road_bonus, 2),
            "congestion_penalty": round(congestion_penalty, 2),
            "visitor_load_penalty": round(visitor_load_penalty, 2),
        }

        explanation = ScoreExplanation(
            rule_name=RULE_NAMES["traffic"],
            formula_description=formula_desc,
            input_factors=input_factors,
            intermediate_values=intermediate_values,
            raw_result=round(raw_result, 2),
            normalised_result=normalised_result,
        )

        dim_score = DimensionScore(
            dimension="traffic",
            score=normalised_result,
            direction_note=DIRECTION_NOTES["traffic"],
            explanation=explanation,
        )
        trace_data = explanation.model_dump()
        trace_data["score"] = normalised_result
        trace_data["direction_note"] = DIRECTION_NOTES["traffic"]
        return dim_score, trace_data

    def calculate_cost_score(
        self,
        scenario: Scenario,
        summary: ContextSummary,
        active_config: AppConfig,
    ) -> Tuple[DimensionScore, Dict[str, Any]]:
        """Calculate Cost Score (0-100, higher = lower municipal financial burden)."""
        sid = scenario.id
        base_score = active_config.scoring.base_scores[sid].cost
        mods = active_config.scoring.modifiers.cost

        proposed_area = max(1.0, scenario.proposed_area_sqm)
        ref_area = max(1.0, float(scenario.attributes.get("ref_area_sqm", 2000.0)))
        revenue_generating = bool(scenario.attributes.get("revenue_generating", False))

        # Area scaling penalty: -min(max(0, (proposed - ref) / ref), 1.0) * weight
        area_diff_ratio = max(0.0, (proposed_area - ref_area) / ref_area)
        area_scaling = min(area_diff_ratio, 1.0) * mods.area_scaling_penalty_weight

        # Revenue offset bonus: +15 if scenario generates municipal revenue
        revenue_offset = mods.revenue_offset_bonus if revenue_generating else 0.0

        raw_result = base_score - area_scaling + revenue_offset
        normalised_result = clamp_score(raw_result)

        formula_desc = (
            f"Base ({base_score:.1f}) - Area Scaling Penalty (-{area_scaling:.1f}) "
            f"+ Revenue Offset Bonus (+{revenue_offset:.1f})"
        )

        input_factors = {
            "proposed_area_sqm": proposed_area,
            "ref_area_sqm": ref_area,
            "estimated_cost_inr": float(scenario.estimated_cost_inr),
            "estimated_annual_operating_cost_inr": float(scenario.estimated_annual_operating_cost_inr),
            "revenue_generating": 1.0 if revenue_generating else 0.0,
        }
        intermediate_values = {
            "area_scaling_penalty": round(area_scaling, 2),
            "revenue_offset_bonus": round(revenue_offset, 2),
        }

        explanation = ScoreExplanation(
            rule_name=RULE_NAMES["cost"],
            formula_description=formula_desc,
            input_factors=input_factors,
            intermediate_values=intermediate_values,
            raw_result=round(raw_result, 2),
            normalised_result=normalised_result,
        )

        dim_score = DimensionScore(
            dimension="cost",
            score=normalised_result,
            direction_note=DIRECTION_NOTES["cost"],
            explanation=explanation,
        )
        trace_data = explanation.model_dump()
        trace_data["score"] = normalised_result
        trace_data["direction_note"] = DIRECTION_NOTES["cost"]
        return dim_score, trace_data

    def calculate_environment_score(
        self,
        scenario: Scenario,
        summary: ContextSummary,
        active_config: AppConfig,
    ) -> Tuple[DimensionScore, Dict[str, Any]]:
        """Calculate Environmental Score (0-100, higher = net positive environmental outcome)."""
        sid = scenario.id
        base_score = active_config.scoring.base_scores[sid].environmental
        mods = active_config.scoring.modifiers.environmental

        proposed_area = max(1.0, scenario.proposed_area_sqm)
        green_ratio = scenario.green_space_delta_sqm / proposed_area
        imperv_ratio = scenario.impervious_surface_delta_sqm / proposed_area

        # Green change: +green_ratio * weight
        green_change = green_ratio * mods.green_change_weight

        # Impervious penalty: -impervious_ratio * weight
        impervious_penalty = imperv_ratio * mods.impervious_penalty_weight

        # Green deficit bonus: area with <15% green gets bonus for green-positive development
        if green_ratio > 0.0 and summary.green_space_pct < mods.green_deficit_threshold_pct:
            deficit_frac = max(0.0, 1.0 - (summary.green_space_pct / max(0.1, mods.green_deficit_threshold_pct)))
            green_deficit_bonus = deficit_frac * mods.green_deficit_bonus_weight
        else:
            green_deficit_bonus = 0.0

        # Industrial adjacency penalty: -5 if industrial > 20%
        if summary.industrial_pct > mods.industrial_adjacency_threshold_pct:
            industrial_penalty = mods.industrial_adjacency_penalty
        else:
            industrial_penalty = 0.0

        raw_result = base_score + green_change - impervious_penalty + green_deficit_bonus - industrial_penalty
        normalised_result = clamp_score(raw_result)

        formula_desc = (
            f"Base ({base_score:.1f}) + Green Change (+{green_change:.1f}) "
            f"- Impervious Penalty (-{impervious_penalty:.1f}) + Green Deficit Bonus (+{green_deficit_bonus:.1f}) "
            f"- Industrial Penalty (-{industrial_penalty:.1f})"
        )

        input_factors = {
            "green_space_delta_sqm": float(scenario.green_space_delta_sqm),
            "impervious_surface_delta_sqm": float(scenario.impervious_surface_delta_sqm),
            "green_space_pct": float(summary.green_space_pct),
            "industrial_pct": float(summary.industrial_pct),
        }
        intermediate_values = {
            "green_ratio": round(green_ratio, 3),
            "impervious_ratio": round(imperv_ratio, 3),
            "green_change": round(green_change, 2),
            "impervious_penalty": round(impervious_penalty, 2),
            "green_deficit_bonus": round(green_deficit_bonus, 2),
            "industrial_penalty": round(industrial_penalty, 2),
        }

        explanation = ScoreExplanation(
            rule_name=RULE_NAMES["environmental"],
            formula_description=formula_desc,
            input_factors=input_factors,
            intermediate_values=intermediate_values,
            raw_result=round(raw_result, 2),
            normalised_result=normalised_result,
        )

        dim_score = DimensionScore(
            dimension="environmental",
            score=normalised_result,
            direction_note=DIRECTION_NOTES["environmental"],
            explanation=explanation,
        )
        trace_data = explanation.model_dump()
        trace_data["score"] = normalised_result
        trace_data["direction_note"] = DIRECTION_NOTES["environmental"]
        return dim_score, trace_data

    def calculate_accessibility_score(
        self,
        scenario: Scenario,
        summary: ContextSummary,
        active_config: AppConfig,
    ) -> Tuple[DimensionScore, Dict[str, Any]]:
        """Calculate Accessibility Score (0-100, higher = better citizen reach and connectivity)."""
        sid = scenario.id
        base_score = active_config.scoring.base_scores[sid].accessibility
        mods = active_config.scoring.modifiers.accessibility
        refs = active_config.scoring.references

        ref_road_density = max(1.0, refs.road_density_m_per_sqkm)

        # Transit proximity bonus: +min(1000 / (nearest_transit_m + 1), 1.0) * weight
        transit_prox_frac = min(1000.0 / (max(0.0, summary.nearest_transit_m) + 1.0), 1.0)
        transit_prox = transit_prox_frac * mods.transit_proximity_weight

        # Transit coverage bonus: +min(transit_stops / target, 1.0) * weight
        target_stops = max(1.0, mods.transit_coverage_target_stops)
        transit_cov = min(summary.transit_stop_count / target_stops, 1.0) * mods.transit_coverage_weight

        # Road connectivity bonus: +min(road_density / ref_road_density, 1.0) * weight
        road_conn = min(summary.road_density_m_per_sqkm / ref_road_density, 1.0) * mods.road_connectivity_weight

        # Population density bonus: +min(pop_density_est / target, 1.0) * weight
        target_pop = max(1.0, mods.population_density_target)
        pop_dens = min(summary.population_density_estimate / target_pop, 1.0) * mods.population_density_weight

        # Remoteness penalty: -10 if transit > 2000m and road_density < 0.5 * ref
        remote_thresh_road = mods.remoteness_road_density_factor * ref_road_density
        if (
            summary.nearest_transit_m > mods.remoteness_transit_threshold_m
            and summary.road_density_m_per_sqkm < remote_thresh_road
        ):
            remoteness_penalty = mods.remoteness_penalty
        else:
            remoteness_penalty = 0.0

        raw_result = base_score + transit_prox + transit_cov + road_conn + pop_dens - remoteness_penalty
        normalised_result = clamp_score(raw_result)

        formula_desc = (
            f"Base ({base_score:.1f}) + Transit Proximity (+{transit_prox:.1f}) "
            f"+ Transit Coverage (+{transit_cov:.1f}) + Road Connectivity (+{road_conn:.1f}) "
            f"+ Population Density (+{pop_dens:.1f}) - Remoteness Penalty (-{remoteness_penalty:.1f})"
        )

        input_factors = {
            "nearest_transit_m": float(summary.nearest_transit_m),
            "transit_stop_count": float(summary.transit_stop_count),
            "road_density_m_per_sqkm": float(summary.road_density_m_per_sqkm),
            "population_density_estimate": float(summary.population_density_estimate),
        }
        intermediate_values = {
            "transit_proximity_bonus": round(transit_prox, 2),
            "transit_coverage_bonus": round(transit_cov, 2),
            "road_connectivity_bonus": round(road_conn, 2),
            "population_density_bonus": round(pop_dens, 2),
            "remoteness_penalty": round(remoteness_penalty, 2),
        }

        explanation = ScoreExplanation(
            rule_name=RULE_NAMES["accessibility"],
            formula_description=formula_desc,
            input_factors=input_factors,
            intermediate_values=intermediate_values,
            raw_result=round(raw_result, 2),
            normalised_result=normalised_result,
        )

        dim_score = DimensionScore(
            dimension="accessibility",
            score=normalised_result,
            direction_note=DIRECTION_NOTES["accessibility"],
            explanation=explanation,
        )
        trace_data = explanation.model_dump()
        trace_data["score"] = normalised_result
        trace_data["direction_note"] = DIRECTION_NOTES["accessibility"]
        return dim_score, trace_data

    def calculate_gap_improvement_score(
        self,
        scenario: Scenario,
        gaps: List[InfrastructureGap],
        active_config: AppConfig,
    ) -> Tuple[DimensionScore, Dict[str, Any]]:
        """Calculate Infrastructure-Gap Improvement Score (0-100, higher = greater gap closure)."""
        sid = scenario.id
        relevance_matrix = active_config.scoring.gap_relevance.get(sid, {})

        gaps_by_cat = {g.category: g.gap_severity for g in gaps}

        # Sum of G_c across all assessed categories
        max_possible = sum(gaps_by_cat.values())

        if max_possible <= 0.0 or not gaps:
            # Neutral baseline score of 50 if no gaps are identified in context
            raw_result = 50.0
            weighted_fill = 0.0
        else:
            # Weighted gap fill: sum(G_c * R_{s, c})
            weighted_fill = sum(
                severity * relevance_matrix.get(cat, 0.0)
                for cat, severity in gaps_by_cat.items()
            )
            raw_result = (weighted_fill / max_possible) * 100.0

        normalised_result = clamp_score(raw_result)

        formula_desc = (
            f"Weighted Gap Fill ({weighted_fill:.2f}) / Max Possible Gaps ({max_possible:.2f}) * 100"
            if max_possible > 0.0
            else "Neutral baseline score (50.0) because no infrastructure gaps were identified"
        )

        input_factors = {
            f"gap_severity_{cat}": float(sev)
            for cat, sev in gaps_by_cat.items()
        }
        intermediate_values = {
            "weighted_gap_fill": round(weighted_fill, 3),
            "max_possible_gaps": round(max_possible, 3),
        }

        explanation = ScoreExplanation(
            rule_name=RULE_NAMES["gap_improvement"],
            formula_description=formula_desc,
            input_factors=input_factors,
            intermediate_values=intermediate_values,
            raw_result=round(raw_result, 2),
            normalised_result=normalised_result,
        )

        dim_score = DimensionScore(
            dimension="gap_improvement",
            score=normalised_result,
            direction_note=DIRECTION_NOTES["gap_improvement"],
            explanation=explanation,
        )
        trace_data = explanation.model_dump()
        trace_data["score"] = normalised_result
        trace_data["direction_note"] = DIRECTION_NOTES["gap_improvement"]
        return dim_score, trace_data

    def calculate_social_utility_score(
        self,
        scenario: Scenario,
        summary: ContextSummary,
        gaps: List[InfrastructureGap],
        active_config: AppConfig,
    ) -> Tuple[DimensionScore, Dict[str, Any]]:
        """Calculate Public / Social Utility Score (0-100, higher = greater community utility)."""
        sid = scenario.id
        base_score = active_config.scoring.base_scores[sid].social_utility
        mods = active_config.scoring.modifiers.social_utility
        refs = active_config.scoring.references

        # Population reach bonus: +min(pop_density_est / target, 1.0) * weight
        target_pop = max(1.0, mods.population_reach_target)
        pop_reach = min(summary.population_density_estimate / target_pop, 1.0) * mods.population_reach_weight

        # Employment bonus: +min(jobs_created / target, 1.0) * weight
        target_jobs = max(1.0, mods.employment_target_jobs)
        employ = min(scenario.estimated_jobs_created / target_jobs, 1.0) * mods.employment_weight

        # Service gap bonus: +max(matching_gap_severities) * weight
        relevance = active_config.scoring.gap_relevance.get(sid, {})
        matching_severities = [
            g.gap_severity
            for g in gaps
            if g.category in scenario.addresses_gaps or relevance.get(g.category, 0.0) > 0.0
        ]
        max_gap = max(matching_severities, default=0.0)
        gap_bonus = max_gap * mods.gap_bonus_weight

        # Underserved area bonus: +5 if total_pois < ref_poi_count * threshold_factor
        poi_threshold = refs.poi_count * mods.underserved_poi_threshold_factor
        if summary.total_pois < poi_threshold:
            underserved_bonus = mods.underserved_area_bonus
        else:
            underserved_bonus = 0.0

        raw_result = base_score + pop_reach + employ + gap_bonus + underserved_bonus
        normalised_result = clamp_score(raw_result)

        formula_desc = (
            f"Base ({base_score:.1f}) + Population Reach (+{pop_reach:.1f}) "
            f"+ Employment (+{employ:.1f}) + Gap Bonus (+{gap_bonus:.1f}) "
            f"+ Underserved Area Bonus (+{underserved_bonus:.1f})"
        )

        input_factors = {
            "population_density_estimate": float(summary.population_density_estimate),
            "estimated_jobs_created": float(scenario.estimated_jobs_created),
            "total_pois": float(summary.total_pois),
            "max_matching_gap_severity": float(max_gap),
        }
        intermediate_values = {
            "population_reach_bonus": round(pop_reach, 2),
            "employment_bonus": round(employ, 2),
            "gap_bonus": round(gap_bonus, 2),
            "underserved_bonus": round(underserved_bonus, 2),
        }

        explanation = ScoreExplanation(
            rule_name=RULE_NAMES["social_utility"],
            formula_description=formula_desc,
            input_factors=input_factors,
            intermediate_values=intermediate_values,
            raw_result=round(raw_result, 2),
            normalised_result=normalised_result,
        )

        dim_score = DimensionScore(
            dimension="social_utility",
            score=normalised_result,
            direction_note=DIRECTION_NOTES["social_utility"],
            explanation=explanation,
        )
        trace_data = explanation.model_dump()
        trace_data["score"] = normalised_result
        trace_data["direction_note"] = DIRECTION_NOTES["social_utility"]
        return dim_score, trace_data

    # -------------------------------------------------------------------------
    # Helper: Normalize Urban Context / ContextSummary
    # -------------------------------------------------------------------------

    def _resolve_summary(
        self,
        context: Optional[Union[UrbanContext, ContextSummary]],
        active_config: AppConfig,
    ) -> ContextSummary:
        """Extract or synthesize ContextSummary defensively."""
        if isinstance(context, UrbanContext):
            return context.summary
        elif isinstance(context, ContextSummary):
            return context

        # Safe fallback with configuration reference baselines
        refs = active_config.scoring.references
        return ContextSummary(
            total_pois=refs.poi_count,
            poi_counts_by_category={},
            poi_density_per_sqkm=8.0,
            road_network_length_m=10000.0,
            road_density_m_per_sqkm=refs.road_density_m_per_sqkm,
            major_road_count=1,
            nearest_major_road_m=500.0,
            dominant_landuse="residential",
            landuse_distribution={"residential": 100.0},
            residential_pct=100.0,
            commercial_pct=0.0,
            green_space_pct=15.0,
            industrial_pct=0.0,
            transit_stop_count=3,
            nearest_transit_m=600.0,
            population_density_estimate=refs.population_density_ref,
            building_density_estimate=0.35,
        )


_impact_simulator_instance: Optional[ImpactSimulator] = None


def get_impact_simulator(
    config: Optional[AppConfig] = None, force_reload: bool = False
) -> ImpactSimulator:
    """Return the singleton ImpactSimulator instance."""
    global _impact_simulator_instance
    if _impact_simulator_instance is None or force_reload or config is not None:
        _impact_simulator_instance = ImpactSimulator(config=config)
    return _impact_simulator_instance
