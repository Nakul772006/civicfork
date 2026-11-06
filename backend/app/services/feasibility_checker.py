"""Deterministic feasibility evaluation service for CivicFork.

Evaluates scenarios against municipal constraints loaded from feasibility.yaml:
1. minimum_area (blocker): Proposed plot area meets or exceeds minimum required area.
2. proximity_conflict (warning): No facility of the same type within conflict radius.
3. service_saturation (warning): Existing facilities do not exceed saturation limit.
4. zoning_compatibility (warning): Dominant land-use zone is compatible.

Feasibility is independent of weighted ranking:
- Ranking evaluates performance against municipal priorities.
- Feasibility evaluates compliance with physical and planning constraints.
"""

from typing import Dict, List, Optional
from app.config_loader import AppConfig, get_app_config
from app.models.domain import (
    FeasibilityCheck,
    FeasibilityVerdict,
    InfrastructureGap,
    PlotLocation,
    Scenario,
    ScenarioId,
    UrbanContext,
)

SCENARIO_TO_GAP_CATEGORY: Dict[str, str] = {
    "park": "parks",
    "healthcare": "healthcare",
    "education": "education",
    "parking": "parking",
    "commercial": "commercial",
    "community_centre": "community",
    "public_transport": "transport",
}


class FeasibilityChecker:
    """Service evaluating physical and regulatory feasibility constraints."""

    def __init__(self, config: Optional[AppConfig] = None):
        self._config = config or get_app_config()

    def evaluate(
        self,
        scenario: Scenario,
        plot: PlotLocation,
        context: UrbanContext,
        gaps: Optional[List[InfrastructureGap]] = None,
    ) -> FeasibilityVerdict:
        """Evaluate feasibility checks for a single scenario."""
        feasibility_cfg = self._config.feasibility
        scenario_id = scenario.id

        if scenario_id not in feasibility_cfg.scenarios:
            raise ValueError(f"No feasibility configuration for scenario '{scenario_id}'")

        cfg = feasibility_cfg.scenarios[scenario_id]
        category = SCENARIO_TO_GAP_CATEGORY.get(scenario_id, scenario_id)

        # Gap info for proximity & saturation
        gap_info = next((g for g in (gaps or []) if g.category == category), None)
        facilities_count = gap_info.facilities_in_radius if gap_info else 0
        nearest_distance = gap_info.nearest_facility_distance_m if gap_info else None

        checks: List[FeasibilityCheck] = []

        # -------------------------------------------------------------
        # Rule 1: minimum_area (blocker)
        # -------------------------------------------------------------
        actual_area = plot.area_sqm if plot.area_sqm is not None else scenario.proposed_area_sqm
        req_area = cfg.min_area_sqm
        area_passed = actual_area >= req_area
        checks.append(
            FeasibilityCheck(
                check_name="minimum_area",
                passed=area_passed,
                severity="blocker",
                message=(
                    f"Plot area ({actual_area:,.0f} m²) meets minimum required area ({req_area:,.0f} m²)"
                    if area_passed
                    else f"Plot area ({actual_area:,.0f} m²) is below minimum required area ({req_area:,.0f} m²)"
                ),
                details={"required_min_sqm": req_area, "available_sqm": actual_area, "unit": "sqm"},
            )
        )

        # -------------------------------------------------------------
        # Rule 2: proximity_conflict (warning)
        # -------------------------------------------------------------
        conflict_radius = cfg.conflict_radius_m
        has_conflict = nearest_distance is not None and nearest_distance < conflict_radius
        prox_passed = not has_conflict
        checks.append(
            FeasibilityCheck(
                check_name="proximity_conflict",
                passed=prox_passed,
                severity="warning",
                message=(
                    f"No proximity conflict within {conflict_radius:,.0f} m buffer"
                    if prox_passed
                    else f"Nearby existing facility located {nearest_distance:,.0f} m away (buffer threshold {conflict_radius:,.0f} m)"
                ),
                details={
                    "conflict_buffer_m": conflict_radius,
                    "nearest_facility_distance_m": nearest_distance,
                    "unit": "meters",
                },
            )
        )

        # -------------------------------------------------------------
        # Rule 3: service_saturation (warning)
        # -------------------------------------------------------------
        sat_limit = cfg.saturation_limit
        sat_passed = facilities_count <= sat_limit
        checks.append(
            FeasibilityCheck(
                check_name="service_saturation",
                passed=sat_passed,
                severity="warning",
                message=(
                    f"Facility count ({facilities_count}) is within saturation limit ({sat_limit})"
                    if sat_passed
                    else f"Area contains {facilities_count} existing facilities, exceeding saturation limit of {sat_limit}"
                ),
                details={"saturation_limit": sat_limit, "existing_facilities_count": facilities_count},
            )
        )

        # -------------------------------------------------------------
        # Rule 4: zoning_compatibility (warning)
        # -------------------------------------------------------------
        incompat_zones = [z.lower() for z in cfg.incompatible_zones]
        dominant_zone = (context.summary.dominant_landuse or "residential").lower()
        zoning_passed = dominant_zone not in incompat_zones
        checks.append(
            FeasibilityCheck(
                check_name="zoning_compatibility",
                passed=zoning_passed,
                severity="warning",
                message=(
                    f"Dominant zoning '{dominant_zone}' is compatible with {scenario.name}"
                    if zoning_passed
                    else f"Zoning conflict: dominant zone '{dominant_zone}' is incompatible with {scenario.name}"
                ),
                details={"dominant_landuse": dominant_zone, "incompatible_zones": cfg.incompatible_zones},
            )
        )

        blockers = [c.message for c in checks if not c.passed and c.severity == "blocker"]
        warnings = [c.message for c in checks if not c.passed and c.severity == "warning"]

        return FeasibilityVerdict(
            scenario_id=scenario_id,
            feasible=len(blockers) == 0,
            blocker_count=len(blockers),
            warning_count=len(warnings),
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )

    def evaluate_all(
        self,
        scenarios: List[Scenario],
        plot: PlotLocation,
        context: UrbanContext,
        gaps: Optional[List[InfrastructureGap]] = None,
    ) -> List[FeasibilityVerdict]:
        """Evaluate feasibility checks across all provided scenarios."""
        return [self.evaluate(sc, plot, context, gaps) for sc in scenarios]


_feasibility_checker: Optional[FeasibilityChecker] = None


def get_feasibility_checker() -> FeasibilityChecker:
    """Singleton getter for FeasibilityChecker."""
    global _feasibility_checker
    if _feasibility_checker is None:
        _feasibility_checker = FeasibilityChecker()
    return _feasibility_checker
