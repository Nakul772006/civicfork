"""Scenario Generator service for CivicFork.

Deterministically synthesises the seven canonical CivicFork urban development
policy scenarios from configuration templates, tailored to the selected plot,
urban context, and identified municipal infrastructure gaps.

Canonical Scenarios:
1. park (Parks / Recreational Space)
2. healthcare (Healthcare Facility)
3. education (Educational Facility)
4. parking (Multi-level Parking / Transit Hub)
5. commercial (Commercial / Mixed-Use Development)
6. community_centre (Community / Cultural Centre)
7. public_transport (Public Transport Terminal)

Preserves strict data-integrity boundaries between:
- Configured scenario assumptions (scenarios.yaml, feasibility.yaml)
- Observed contextual indicators (OSM observations via UrbanContext)
- Modelled approximations (deterministic visitor, job, traffic, surface estimates)
- Downstream impact evaluations (no scoring or ranking performed here)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from app.config_loader import AppConfig, ScenarioTemplate, get_app_config
from app.models.domain import (
    ContextSummary,
    GapCategory,
    InfrastructureGap,
    PlotLocation,
    SCENARIO_IDS,
    Scenario,
    ScenarioId,
    UrbanContext,
)

logger = logging.getLogger("civicfork.scenario_generator")

# Canonical scenario ordering matching approved documentation and configurations
ORDERED_SCENARIO_IDS: Tuple[ScenarioId, ...] = (
    "park",
    "healthcare",
    "education",
    "parking",
    "commercial",
    "community_centre",
    "public_transport",
)

# 1-to-1 primary mapping from scenario ID to corresponding infrastructure gap category
SCENARIO_PRIMARY_GAP: Dict[ScenarioId, GapCategory] = {
    "park": "parks",
    "healthcare": "healthcare",
    "education": "education",
    "parking": "parking",
    "commercial": "commercial",
    "community_centre": "community",
    "public_transport": "transport",
}


class ScenarioGenerator:
    """Service generating the seven canonical CivicFork development scenarios.

    Consumes plot dimensions, urban context summary, infrastructure gaps, and
    application configuration to populate Scenario domain models deterministically.
    """

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
        """Return a copy of calculation and provenance traces from the latest generation."""
        return dict(self._last_traces)

    def generate(
        self,
        plot_or_context: Union[PlotLocation, UrbanContext],
        context: Optional[Union[UrbanContext, ContextSummary, List[InfrastructureGap]]] = None,
        gaps: Optional[List[InfrastructureGap]] = None,
        config: Optional[AppConfig] = None,
    ) -> List[Scenario]:
        """Generate all seven canonical development alternatives.

        Args:
            plot_or_context: Either a validated PlotLocation or a full UrbanContext.
            context: If plot_or_context is PlotLocation, the accompanying UrbanContext
                     or ContextSummary. If plot_or_context is UrbanContext, this parameter
                     can optionally supply the gaps list if passed positionally.
            gaps: Optional list of InfrastructureGap models from Phase 2.3.
            config: Optional AppConfig override.

        Returns:
            List of 7 populated Scenario domain models in canonical order.
        """
        active_config = config or self._config or self.config

        # 1. Resolve plot, summary, and gaps inputs flexibly
        plot, summary, resolved_gaps = self._resolve_inputs(
            plot_or_context=plot_or_context,
            context=context,
            gaps=gaps,
        )

        logger.info(
            "Generating 7 canonical scenarios for plot (lat=%.4f, lng=%.4f, area=%s)",
            plot.lat,
            plot.lng,
            f"{plot.area_sqm}m²" if plot.area_sqm else "default",
        )

        # 2. Extract context indicators (observed / modelled)
        ref_pop_density = active_config.scoring.references.population_density_ref
        if summary is not None:
            pop_density_est = summary.population_density_estimate
        else:
            pop_density_est = ref_pop_density

        # Population density factor: min(pop_density_est / 5000.0, 2.0)
        safe_ref_pop = max(1.0, ref_pop_density)
        pop_density_factor = min(pop_density_est / safe_ref_pop, 2.0) if pop_density_est > 0 else 0.0

        # Map gaps by category for rapid association
        gaps_by_category: Dict[str, InfrastructureGap] = {}
        if resolved_gaps:
            for g in resolved_gaps:
                gaps_by_category[g.category] = g

        scenarios: List[Scenario] = []
        new_traces: Dict[str, Dict[str, Any]] = {}

        templates = active_config.scenarios.scenarios
        feasibility_scenarios = active_config.feasibility.scenarios

        # 3. Deterministically construct each canonical scenario
        for sid in ORDERED_SCENARIO_IDS:
            if sid not in templates:
                raise ValueError(f"Required scenario '{sid}' missing from scenarios configuration.")

            template: ScenarioTemplate = templates[sid]

            # Minimum required area from feasibility rules (or template ref_area fallback)
            if sid in feasibility_scenarios:
                required_area_sqm = feasibility_scenarios[sid].min_area_sqm
            else:
                required_area_sqm = template.ref_area_sqm

            # Proposed area: uses plot.area_sqm if provided; otherwise template default
            if plot.area_sqm is not None and plot.area_sqm > 0:
                proposed_area_sqm = float(plot.area_sqm)
            else:
                proposed_area_sqm = float(template.default_area_sqm)

            # Modelled estimations from scoring model specifications §4
            # A. Capital & Operating Costs
            estimated_cost_inr = round(proposed_area_sqm * template.cost_per_sqm, 2)
            estimated_annual_operating_cost_inr = round(
                estimated_cost_inr * template.operating_ratio, 2
            )

            # B. Daily Visitors
            ref_area = max(1.0, template.ref_area_sqm)
            raw_visitors = template.base_visitors * (proposed_area_sqm / ref_area) * pop_density_factor
            estimated_daily_visitors = int(round(raw_visitors))

            # C. Direct Jobs Created
            raw_jobs = template.jobs_per_1000sqm * (proposed_area_sqm / 1000.0)
            estimated_jobs_created = int(round(raw_jobs))

            # D. Traffic Volume Change (%)
            estimated_traffic_change_pct = round(template.base_traffic_pct * pop_density_factor, 1)

            # E. Green Space & Impervious Surface Deltas (m²)
            green_space_delta_sqm = round(template.green_ratio * proposed_area_sqm, 1)
            impervious_surface_delta_sqm = round(template.impervious_ratio * proposed_area_sqm, 1)

            # Gap association
            primary_gap_cat = SCENARIO_PRIMARY_GAP.get(sid)
            associated_gap = gaps_by_category.get(primary_gap_cat) if primary_gap_cat else None

            # Attributes assembly: preserve configured attributes, modelling parameters, and gap link
            scenario_attributes = dict(template.attributes)
            scenario_attributes["trip_rate"] = template.trip_rate
            scenario_attributes["ref_area_sqm"] = template.ref_area_sqm
            scenario_attributes["cost_per_sqm"] = template.cost_per_sqm
            scenario_attributes["operating_ratio"] = template.operating_ratio
            scenario_attributes["revenue_generating"] = template.revenue_generating
            scenario_attributes["associated_gap_category"] = primary_gap_cat

            if associated_gap is not None:
                scenario_attributes["primary_gap_severity"] = associated_gap.gap_severity
                scenario_attributes["primary_gap_type"] = associated_gap.gap_type
                scenario_attributes["gap_facilities_in_radius"] = associated_gap.facilities_in_radius
                scenario_attributes["gap_coverage_threshold_m"] = associated_gap.coverage_threshold_m
            else:
                scenario_attributes["primary_gap_severity"] = None
                scenario_attributes["primary_gap_type"] = None

            scenario = Scenario(
                id=sid,
                name=template.name,
                description=template.description,
                category=template.category,
                required_area_sqm=required_area_sqm,
                proposed_area_sqm=proposed_area_sqm,
                estimated_cost_inr=estimated_cost_inr,
                estimated_annual_operating_cost_inr=estimated_annual_operating_cost_inr,
                estimated_daily_visitors=estimated_daily_visitors,
                estimated_jobs_created=estimated_jobs_created,
                estimated_traffic_change_pct=estimated_traffic_change_pct,
                green_space_delta_sqm=green_space_delta_sqm,
                impervious_surface_delta_sqm=impervious_surface_delta_sqm,
                addresses_gaps=list(template.addresses_gaps),
                attributes=scenario_attributes,
            )
            scenarios.append(scenario)

            # Record provenance and explainability trace
            new_traces[sid] = {
                "scenario_id": sid,
                "scenario_name": template.name,
                "template_source": "scenarios.yaml",
                "configured_params": {
                    "cost_per_sqm": template.cost_per_sqm,
                    "operating_ratio": template.operating_ratio,
                    "base_visitors": template.base_visitors,
                    "ref_area_sqm": template.ref_area_sqm,
                    "default_area_sqm": template.default_area_sqm,
                    "jobs_per_1000sqm": template.jobs_per_1000sqm,
                    "base_traffic_pct": template.base_traffic_pct,
                    "trip_rate": template.trip_rate,
                    "green_ratio": template.green_ratio,
                    "impervious_ratio": template.impervious_ratio,
                    "revenue_generating": template.revenue_generating,
                    "addresses_gaps": list(template.addresses_gaps),
                },
                "observed_context": {
                    "plot_lat": plot.lat,
                    "plot_lng": plot.lng,
                    "plot_radius_m": plot.radius_m,
                    "plot_area_sqm": plot.area_sqm,
                    "population_density_estimate": pop_density_est,
                },
                "modelled_estimations": {
                    "pop_density_factor": pop_density_factor,
                    "proposed_area_sqm": proposed_area_sqm,
                    "required_area_sqm": required_area_sqm,
                    "estimated_cost_inr": estimated_cost_inr,
                    "estimated_annual_operating_cost_inr": estimated_annual_operating_cost_inr,
                    "estimated_daily_visitors": estimated_daily_visitors,
                    "estimated_jobs_created": estimated_jobs_created,
                    "estimated_traffic_change_pct": estimated_traffic_change_pct,
                    "green_space_delta_sqm": green_space_delta_sqm,
                    "impervious_surface_delta_sqm": impervious_surface_delta_sqm,
                },
                "associated_gap": (
                    {
                        "category": associated_gap.category,
                        "gap_type": associated_gap.gap_type,
                        "gap_severity": associated_gap.gap_severity,
                        "facilities_in_radius": associated_gap.facilities_in_radius,
                        "expected_facilities": associated_gap.expected_facilities,
                        "coverage_threshold_m": associated_gap.coverage_threshold_m,
                        "nearest_facility_distance_m": associated_gap.nearest_facility_distance_m,
                    }
                    if associated_gap
                    else None
                ),
                "data_integrity_notes": {
                    "configured": "Base unit costs, ratios, visitor baselines, job densities, and surface ratios are policy parameters from scenarios.yaml.",
                    "observed": "Plot coordinates, radius, and context metrics (e.g. population density estimate) derive from cached OSM observations.",
                    "modelled": "Visitor numbers, cost totals, job creation, traffic changes, and surface area deltas are rule-based model estimates, not real-world empirical measurements.",
                    "calculated_impacts": "Final impact scores across 6 dimensions are not computed at scenario generation time; they are evaluated downstream by the Impact Simulator.",
                },
            }

        self._last_traces = new_traces
        return scenarios

    def get_scenario_trace(self, scenario_or_id: Union[Scenario, str]) -> Dict[str, Any]:
        """Retrieve calculation, configuration, and provenance trace for a scenario.

        Args:
            scenario_or_id: Either a Scenario model or string scenario ID.

        Returns:
            Dictionary containing configuration assumptions, observed context, and modelled estimations.
        """
        sid = scenario_or_id.id if isinstance(scenario_or_id, Scenario) else str(scenario_or_id)
        if sid in self._last_traces:
            return dict(self._last_traces[sid])

        raise KeyError(f"No generation trace available for scenario '{sid}'.")

    def _resolve_inputs(
        self,
        plot_or_context: Union[PlotLocation, UrbanContext],
        context: Optional[Union[UrbanContext, ContextSummary, List[InfrastructureGap]]],
        gaps: Optional[List[InfrastructureGap]],
    ) -> Tuple[PlotLocation, Optional[ContextSummary], Optional[List[InfrastructureGap]]]:
        """Normalize varied calling conventions into (plot, summary, gaps)."""
        resolved_gaps = gaps

        if isinstance(plot_or_context, UrbanContext):
            plot = plot_or_context.plot
            summary: Optional[ContextSummary] = plot_or_context.summary
            if isinstance(context, list) and resolved_gaps is None:
                # Caller invoked generate(urban_context, gaps)
                resolved_gaps = context
        elif isinstance(plot_or_context, PlotLocation):
            plot = plot_or_context
            if isinstance(context, UrbanContext):
                summary = context.summary
            elif isinstance(context, ContextSummary):
                summary = context
            else:
                summary = None
        else:
            raise TypeError("Expected PlotLocation or UrbanContext as first argument.")

        return plot, summary, resolved_gaps


_scenario_generator_instance: Optional[ScenarioGenerator] = None


def get_scenario_generator(
    config: Optional[AppConfig] = None, force_reload: bool = False
) -> ScenarioGenerator:
    """Return the singleton ScenarioGenerator instance."""
    global _scenario_generator_instance
    if _scenario_generator_instance is None or force_reload or config is not None:
        _scenario_generator_instance = ScenarioGenerator(config=config)
    return _scenario_generator_instance
