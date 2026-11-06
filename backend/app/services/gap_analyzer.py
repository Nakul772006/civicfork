"""Infrastructure Gap Analyser for CivicFork.

Consumes the authoritative UrbanContext / ContextSummary produced by the
Urban Context Analyser and deterministically identifies municipal infrastructure
and service gaps across the seven approved CivicFork categories:
- healthcare
- education
- parks
- transport
- parking
- commercial
- community

Adheres strictly to the scoring model specification:
- coverage_score_c = min(facilities_in_radius_c / expected_facilities_c, 1.0)
- proximity_score_c = max(1.0 - nearest_distance_c / coverage_threshold_c, 0.0) if facilities > 0 else 0.0
- G_c = 1.0 - (0.6 * coverage_score_c + 0.4 * proximity_score_c)
- Classification:
    * 0.0 <= G_c <= 0.2: adequate
    * 0.2 <  G_c <= 0.5: distant
    * 0.5 <  G_c <= 0.8: insufficient
    * 0.8 <  G_c <= 1.0: absent
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from app.config_loader import AppConfig, get_app_config
from app.models.domain import (
    ContextSummary,
    GapCategory,
    GapType,
    InfrastructureGap,
    PlotLocation,
    POI,
    TransportStop,
    UrbanContext,
)

logger = logging.getLogger("civicfork.gap_analyzer")

# The 7 canonical infrastructure categories assessed by CivicFork
ORDERED_CATEGORIES: Tuple[GapCategory, ...] = (
    "healthcare",
    "education",
    "parks",
    "transport",
    "parking",
    "commercial",
    "community",
)

# Tag and category aliases mapping OSM features to the 7 canonical gap categories
CATEGORY_ALIASES: Dict[GapCategory, Set[str]] = {
    "healthcare": {"healthcare", "hospital", "clinic", "doctors", "pharmacy"},
    "education": {"education", "school", "college", "university", "kindergarten"},
    "parks": {"parks", "park"},
    "transport": {"transport", "bus_station", "railway_station", "transit_station"},
    "parking": {"parking"},
    "commercial": {"commercial", "retail", "supermarket", "marketplace"},
    "community": {"community", "community_centre", "social_facility"},
}

# Formula weights
COVERAGE_WEIGHT = 0.6
PROXIMITY_WEIGHT = 0.4


def classify_gap(severity: float) -> GapType:
    """Classify gap severity G_c into approved gap_type categories.

    Boundaries:
        0.0 <= G_c <= 0.2 -> adequate
        0.2 <  G_c <= 0.5 -> distant
        0.5 <  G_c <= 0.8 -> insufficient
        0.8 <  G_c <= 1.0 -> absent
    """
    if severity <= 0.2:
        return "adequate"
    elif severity <= 0.5:
        return "distant"
    elif severity <= 0.8:
        return "insufficient"
    else:
        return "absent"


def generate_cautious_description(
    category: GapCategory,
    gap_type: GapType,
    facilities_in_radius: int,
    expected_facilities: int,
    coverage_threshold_m: float,
    nearest_facility_name: Optional[str],
    nearest_facility_distance_m: Optional[float],
    radius_m: int,
) -> str:
    """Generate human-readable, cautious semantic description for an infrastructure gap.

    Enforces data integrity principles:
    - Distinguishes observed lack in cached OSM from absolute real-world absence.
    - Explicitly attributes gaps to OSM / context observation.
    - Never factually claims non-existence in reality when data is missing.
    """
    category_display = category.replace("_", " ")

    if gap_type == "adequate":
        if nearest_facility_name and nearest_facility_distance_m is not None:
            return (
                f"OSM-observed coverage is adequate for {category_display}: "
                f"{facilities_in_radius} facility/facilities recorded within {radius_m}m "
                f"(expected ~{expected_facilities}), with nearest '{nearest_facility_name}' "
                f"at {nearest_facility_distance_m:.0f}m (threshold {coverage_threshold_m:.0f}m)."
            )
        elif nearest_facility_distance_m is not None:
            return (
                f"OSM-observed coverage is adequate for {category_display}: "
                f"{facilities_in_radius} facility/facilities recorded within {radius_m}m "
                f"(expected ~{expected_facilities}), with nearest at {nearest_facility_distance_m:.0f}m "
                f"(threshold {coverage_threshold_m:.0f}m)."
            )
        else:
            return (
                f"OSM-observed coverage is adequate for {category_display}: "
                f"{facilities_in_radius} facility/facilities recorded within {radius_m}m "
                f"(expected ~{expected_facilities})."
            )

    elif gap_type == "distant":
        dist_str = (
            f"'{nearest_facility_name}' at {nearest_facility_distance_m:.0f}m"
            if nearest_facility_name and nearest_facility_distance_m is not None
            else (
                f"at {nearest_facility_distance_m:.0f}m"
                if nearest_facility_distance_m is not None
                else "beyond immediate reach"
            )
        )
        return (
            f"Context-indicated service lag for {category_display}: "
            f"facilities are recorded in OSM ({facilities_in_radius} within {radius_m}m, "
            f"expected ~{expected_facilities}), but nearest facility is {dist_str} "
            f"against a {coverage_threshold_m:.0f}m coverage threshold."
        )

    elif gap_type == "insufficient":
        dist_str = (
            f", nearest '{nearest_facility_name}' at {nearest_facility_distance_m:.0f}m"
            if nearest_facility_name and nearest_facility_distance_m is not None
            else (
                f", nearest at {nearest_facility_distance_m:.0f}m"
                if nearest_facility_distance_m is not None
                else ""
            )
        )
        return (
            f"OSM-observed deficit for {category_display}: "
            f"only {facilities_in_radius} facility/facilities recorded within {radius_m}m "
            f"(expected ~{expected_facilities}){dist_str} (service threshold {coverage_threshold_m:.0f}m)."
        )

    else:  # absent
        return (
            f"No {category_display} facilities recorded in cached OSM data within {radius_m}m "
            f"(expected ~{expected_facilities}, threshold {coverage_threshold_m:.0f}m). "
            f"Unmapped real-world facilities may exist outside cached open records, "
            f"indicating a potential municipal service gap."
        )


class GapAnalyzer:
    """Infrastructure Gap Analyser service for CivicFork.

    Evaluates municipal service coverage and deficits using authoritative
    urban context and validated scoring configuration thresholds.
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
        """Return a copy of the calculation traces from the most recent analysis."""
        return dict(self._last_traces)

    def analyze(
        self,
        plot_or_context: Union[PlotLocation, UrbanContext],
        context: Optional[Union[UrbanContext, ContextSummary]] = None,
        config: Optional[AppConfig] = None,
    ) -> List[InfrastructureGap]:
        """Evaluate infrastructure gaps across all seven canonical categories.

        Args:
            plot_or_context: Either a validated PlotLocation or a full UrbanContext.
            context: If plot_or_context is PlotLocation, the accompanying UrbanContext
                     or ContextSummary. Ignored if plot_or_context is UrbanContext.
            config: Optional AppConfig override.

        Returns:
            List of 7 InfrastructureGap domain models in canonical order.
        """
        active_config = config or self._config or self.config

        # Resolve plot and urban context / summary inputs
        if isinstance(plot_or_context, UrbanContext):
            plot = plot_or_context.plot
            urban_ctx: Optional[UrbanContext] = plot_or_context
            ctx_summary: ContextSummary = plot_or_context.summary
        elif isinstance(plot_or_context, PlotLocation):
            plot = plot_or_context
            if isinstance(context, UrbanContext):
                urban_ctx = context
                ctx_summary = context.summary
            elif isinstance(context, ContextSummary):
                urban_ctx = None
                ctx_summary = context
            else:
                raise ValueError("An UrbanContext or ContextSummary must be provided with PlotLocation.")
        else:
            raise TypeError("Expected PlotLocation or UrbanContext as first argument.")

        logger.info(
            "Evaluating infrastructure gaps for plot (lat=%.4f, lng=%.4f, radius=%dm)",
            plot.lat,
            plot.lng,
            plot.radius_m,
        )

        thresholds = active_config.scoring.gap_thresholds
        gaps: List[InfrastructureGap] = []
        new_traces: Dict[str, Dict[str, Any]] = {}

        for category in ORDERED_CATEGORIES:
            cat_thresh = thresholds.get(category)
            if cat_thresh is not None:
                coverage_threshold_m = cat_thresh.coverage_threshold_m
                expected_facilities = cat_thresh.expected_facilities
            else:
                # Safe fallback if configuration entry is missing
                coverage_threshold_m = 2000.0
                expected_facilities = 3

            # Ensure expected_facilities is non-zero to avoid division by zero
            safe_expected = max(1, expected_facilities)

            # 1. Feature extraction from urban context
            fac_count, nearest_name, nearest_dist = self._extract_category_features(
                category=category,
                urban_ctx=urban_ctx,
                summary=ctx_summary,
            )

            # 2. Compute coverage score [0.0, 1.0]
            coverage_score = min(fac_count / safe_expected, 1.0)

            # 3. Compute proximity score [0.0, 1.0]
            if fac_count > 0 and nearest_dist is not None:
                safe_thresh = max(1.0, coverage_threshold_m)
                proximity_score = max(1.0 - (nearest_dist / safe_thresh), 0.0)
            else:
                proximity_score = 0.0

            # Clamp intermediate metrics
            coverage_score = min(1.0, max(0.0, coverage_score))
            proximity_score = min(1.0, max(0.0, proximity_score))

            # 4. Compute gap severity G_c in [0.0, 1.0]
            raw_severity = 1.0 - (
                COVERAGE_WEIGHT * coverage_score + PROXIMITY_WEIGHT * proximity_score
            )
            clamped_severity = min(1.0, max(0.0, raw_severity))
            gap_severity = round(clamped_severity, 2)

            # 5. Classify gap type
            gap_type = classify_gap(gap_severity)

            # 6. Generate cautious semantic description
            description = generate_cautious_description(
                category=category,
                gap_type=gap_type,
                facilities_in_radius=fac_count,
                expected_facilities=expected_facilities,
                coverage_threshold_m=coverage_threshold_m,
                nearest_facility_name=nearest_name,
                nearest_facility_distance_m=nearest_dist,
                radius_m=plot.radius_m,
            )

            # 7. Construct InfrastructureGap model
            gap_model = InfrastructureGap(
                category=category,
                gap_type=gap_type,
                nearest_facility_name=nearest_name,
                nearest_facility_distance_m=round(nearest_dist, 1) if nearest_dist is not None else None,
                coverage_threshold_m=coverage_threshold_m,
                facilities_in_radius=fac_count,
                expected_facilities=expected_facilities,
                gap_severity=gap_severity,
                description=description,
            )
            gaps.append(gap_model)

            # 8. Record explainability / calculation trace
            total_pois_count = len(urban_ctx.pois) if urban_ctx is not None else ctx_summary.total_pois
            diag_chain = (
                f"Plot ({plot.lat:.4f}, {plot.lng:.4f}) -> Radius: {plot.radius_m}m -> "
                f"Total POIs in radius: {total_pois_count} -> {category} POIs: {fac_count} -> "
                f"Nearest: '{nearest_name or 'None'}' "
                f"({f'{round(nearest_dist, 1)}m' if nearest_dist is not None else 'None'}) -> "
                f"Gap severity: {gap_severity} ({gap_type})"
            )
            new_traces[category] = {
                "plot_lat": plot.lat,
                "plot_lng": plot.lng,
                "radius_m": plot.radius_m,
                "total_pois_in_radius": total_pois_count,
                "category_pois_in_radius": fac_count,
                "diagnostic_chain": diag_chain,
                "category": category,
                "facilities_in_radius": fac_count,
                "expected_facilities": expected_facilities,
                "coverage_score": round(coverage_score, 4),
                "coverage_threshold_m": coverage_threshold_m,
                "nearest_facility_name": nearest_name,
                "nearest_facility_distance_m": round(nearest_dist, 1) if nearest_dist is not None else None,
                "proximity_score": round(proximity_score, 4),
                "coverage_weight": COVERAGE_WEIGHT,
                "proximity_weight": PROXIMITY_WEIGHT,
                "raw_severity": round(raw_severity, 4),
                "gap_severity": gap_severity,
                "gap_type": gap_type,
                "formula": "1.0 - (0.6 * coverage_score + 0.4 * proximity_score)",
                "data_source_caveat": (
                    "Based on cached OpenStreetMap observations; unmapped real-world facilities may exist."
                ),
            }

        self._last_traces = new_traces
        return gaps

    def get_calculation_trace(
        self,
        gap_or_category: Union[InfrastructureGap, str],
    ) -> Dict[str, Any]:
        """Retrieve calculation trace and intermediate values for a gap.

        Args:
            gap_or_category: Either an InfrastructureGap instance or category name.

        Returns:
            Dictionary containing intermediate variables, weights, and formulas.
        """
        if isinstance(gap_or_category, InfrastructureGap):
            category = gap_or_category.category
            # If already cached from most recent analysis, return it
            if category in self._last_traces:
                return dict(self._last_traces[category])

            # Reconstruct trace deterministically from the gap model
            safe_exp = max(1, gap_or_category.expected_facilities)
            cov = min(gap_or_category.facilities_in_radius / safe_exp, 1.0)
            if (
                gap_or_category.facilities_in_radius > 0
                and gap_or_category.nearest_facility_distance_m is not None
            ):
                safe_thresh = max(1.0, gap_or_category.coverage_threshold_m)
                prox = max(1.0 - (gap_or_category.nearest_facility_distance_m / safe_thresh), 0.0)
            else:
                prox = 0.0

            raw = 1.0 - (COVERAGE_WEIGHT * cov + PROXIMITY_WEIGHT * prox)
            diag_chain = (
                f"Reconstructed trace -> {category} POIs: {gap_or_category.facilities_in_radius} -> "
                f"Nearest: '{gap_or_category.nearest_facility_name or 'None'}' "
                f"({f'{round(gap_or_category.nearest_facility_distance_m, 1)}m' if gap_or_category.nearest_facility_distance_m is not None else 'None'}) -> "
                f"Gap severity: {gap_or_category.gap_severity} ({gap_or_category.gap_type})"
            )
            return {
                "total_pois_in_radius": gap_or_category.facilities_in_radius,
                "category_pois_in_radius": gap_or_category.facilities_in_radius,
                "diagnostic_chain": diag_chain,
                "category": category,
                "facilities_in_radius": gap_or_category.facilities_in_radius,
                "expected_facilities": gap_or_category.expected_facilities,
                "coverage_score": round(cov, 4),
                "coverage_threshold_m": gap_or_category.coverage_threshold_m,
                "nearest_facility_name": gap_or_category.nearest_facility_name,
                "nearest_facility_distance_m": gap_or_category.nearest_facility_distance_m,
                "proximity_score": round(prox, 4),
                "coverage_weight": COVERAGE_WEIGHT,
                "proximity_weight": PROXIMITY_WEIGHT,
                "raw_severity": round(raw, 4),
                "gap_severity": gap_or_category.gap_severity,
                "gap_type": gap_or_category.gap_type,
                "formula": "1.0 - (0.6 * coverage_score + 0.4 * proximity_score)",
                "data_source_caveat": (
                    "Based on cached OpenStreetMap observations; unmapped real-world facilities may exist."
                ),
            }

        category_str = str(gap_or_category)
        if category_str in self._last_traces:
            return dict(self._last_traces[category_str])

        raise KeyError(f"No calculation trace available for category '{category_str}'.")

    def _extract_category_features(
        self,
        category: GapCategory,
        urban_ctx: Optional[UrbanContext],
        summary: ContextSummary,
    ) -> Tuple[int, Optional[str], Optional[float]]:
        """Extract matching facilities count, nearest name, and nearest distance.

        Returns:
            Tuple of (facilities_in_radius, nearest_name, nearest_distance_m).
        """
        aliases = CATEGORY_ALIASES.get(category, {category})

        # Scenario 1: Full UrbanContext available with raw POIs
        if urban_ctx is not None and urban_ctx.pois:
            def _poi_matches(p: POI) -> bool:
                # 1. Canonical or alias category match
                if p.category == category or p.category in aliases:
                    return True
                # 2. Subcategory match
                if p.subcategory and (p.subcategory == category or p.subcategory in aliases):
                    return True
                # 3. OSM raw tag match
                if isinstance(p.tags, dict):
                    amenity = p.tags.get("amenity")
                    if amenity and (amenity == category or amenity in aliases):
                        return True
                    if category == "healthcare" and "healthcare" in p.tags:
                        return True
                    if category == "parks" and p.tags.get("leisure") in ("park", "garden", "playground", "pitch"):
                        return True
                    if category == "transport" and p.tags.get("highway") == "bus_stop":
                        return True
                return False

            matching_pois = [p for p in urban_ctx.pois if _poi_matches(p)]

            # Special case for transport: also consider transport_stops
            if category == "transport":
                stops = urban_ctx.transport_stops
                nearest_poi: Optional[POI] = (
                    min(matching_pois, key=lambda p: p.distance_m) if matching_pois else None
                )
                nearest_stop: Optional[TransportStop] = (
                    min(stops, key=lambda s: s.distance_m) if stops else None
                )

                fac_count = max(len(matching_pois), len(stops))
                if nearest_poi and nearest_stop:
                    if nearest_stop.distance_m <= nearest_poi.distance_m:
                        return fac_count, nearest_stop.name, nearest_stop.distance_m
                    else:
                        return fac_count, nearest_poi.name, nearest_poi.distance_m
                elif nearest_stop:
                    return fac_count, nearest_stop.name, nearest_stop.distance_m
                elif nearest_poi:
                    return fac_count, nearest_poi.name, nearest_poi.distance_m
                else:
                    return 0, None, None

            # Special case for parks: if no POIs exist, fallback to park landuse zones
            if category == "parks" and not matching_pois and urban_ctx.landuse_zones:
                park_zones = [
                    z
                    for z in urban_ctx.landuse_zones
                    if z.landuse_type in ("park", "recreation_ground", "nature_reserve")
                ]
                if park_zones:
                    nearest_zone = min(park_zones, key=lambda z: z.distance_m)
                    name = f"Open space ({nearest_zone.landuse_type})"
                    return len(park_zones), name, nearest_zone.distance_m

            # Standard POI category extraction
            if matching_pois:
                nearest = min(matching_pois, key=lambda p: p.distance_m)
                return len(matching_pois), nearest.name, nearest.distance_m
            else:
                return 0, None, None

        # Scenario 2: Only ContextSummary or empty raw lists available
        count_from_summary = summary.poi_counts_by_category.get(category, 0)
        if category == "transport":
            total_transit = max(count_from_summary, summary.transit_stop_count)
            nearest_m = summary.nearest_transit_m if total_transit > 0 else None
            return total_transit, None, nearest_m

        if count_from_summary > 0:
            return count_from_summary, None, None

        return 0, None, None


_gap_analyzer_instance: Optional[GapAnalyzer] = None


def get_gap_analyzer(
    config: Optional[AppConfig] = None, force_reload: bool = False
) -> GapAnalyzer:
    """Return the singleton GapAnalyzer instance."""
    global _gap_analyzer_instance
    if _gap_analyzer_instance is None or force_reload or config is not None:
        _gap_analyzer_instance = GapAnalyzer(config=config)
    return _gap_analyzer_instance
