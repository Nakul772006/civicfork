"""Urban Context Analyser for CivicFork.

Extracts geospatial evidence (POIs, road network, land-use zones, transit stops)
from the OSM service for a given plot and computes the structured analytical
UrbanContext and compact ContextSummary domain models.
"""

import logging
import math
from typing import Dict, List, Optional

from app.models.domain import (
    ContextSummary,
    LandUseZone,
    PlotLocation,
    POI,
    RoadSegment,
    TransportStop,
    UrbanContext,
    WardData,
    WaterBody,
)
from app.services.osm_service import MAJOR_HIGHWAYS, OSMServiceBase, get_osm_service

logger = logging.getLogger("civicfork.context_analyzer")

# Green space land-use tags
GREEN_SPACE_LANDUSE_TYPES = ("forest", "recreation_ground", "park", "nature_reserve", "grass", "meadow")

# Commercial land-use tags
COMMERCIAL_LANDUSE_TYPES = ("commercial", "retail")


class ContextAnalyzer:
    """Produces structured UrbanContext and ContextSummary from cached OSM data."""

    def __init__(self, osm_service: Optional[OSMServiceBase] = None):
        self._osm_service = osm_service

    @property
    def osm_service(self) -> OSMServiceBase:
        if self._osm_service is None:
            self._osm_service = get_osm_service()
        return self._osm_service

    def analyze(self, plot: PlotLocation, radius_m: Optional[int] = None) -> UrbanContext:
        """Produce authoritative UrbanContext and ContextSummary for a plot location.

        Args:
            plot: The validated plot location.
            radius_m: Optional override for analysis radius; defaults to plot.radius_m.

        Returns:
            UrbanContext containing all raw features and the aggregated ContextSummary.
        """
        target_radius = radius_m if radius_m is not None else plot.radius_m

        logger.info(
            "Analyzing urban context for plot (lat=%.4f, lng=%.4f, radius=%dm)",
            plot.lat,
            plot.lng,
            target_radius,
        )

        # 1. Query spatial features within radius from OSM service
        pois = self.osm_service.get_pois(plot.lat, plot.lng, target_radius)
        roads = self.osm_service.get_roads(plot.lat, plot.lng, target_radius)
        landuse_zones = self.osm_service.get_landuse(plot.lat, plot.lng, target_radius)
        transport_stops = self.osm_service.get_transport_stops(plot.lat, plot.lng, target_radius)
        
        raw_ward = self.osm_service.get_ward(plot.lat, plot.lng)
        if isinstance(raw_ward, WardData):
            ward = raw_ward
        elif isinstance(raw_ward, dict):
            try:
                ward = WardData.model_validate(raw_ward)
            except Exception:
                ward = None
        else:
            ward = None

        raw_water_bodies = self.osm_service.get_water_bodies(plot.lat, plot.lng, target_radius)
        if isinstance(raw_water_bodies, list):
            water_bodies = [w for w in raw_water_bodies if isinstance(w, WaterBody)]
        else:
            water_bodies = []

        # 2. Compute aggregated ContextSummary
        summary = self._compute_summary(
            plot=plot,
            radius_m=target_radius,
            pois=pois,
            roads=roads,
            landuse_zones=landuse_zones,
            transport_stops=transport_stops,
            ward=ward,
            water_bodies=water_bodies,
        )

        # 3. Assemble and return authoritative UrbanContext
        return UrbanContext(
            plot=plot,
            pois=pois,
            roads=roads,
            landuse_zones=landuse_zones,
            transport_stops=transport_stops,
            ward=ward,
            water_bodies=water_bodies,
            summary=summary,
        )

    def _compute_summary(
        self,
        plot: PlotLocation,
        radius_m: int,
        pois: List[POI],
        roads: List[RoadSegment],
        landuse_zones: List[LandUseZone],
        transport_stops: List[TransportStop],
        ward: Optional[WardData] = None,
        water_bodies: Optional[List[WaterBody]] = None,
    ) -> ContextSummary:
        """Calculate observed and modelled urban contextual indicators."""
        radius_km = radius_m / 1000.0
        radius_area_sqkm = math.pi * (radius_km ** 2)

        # --- A. POI Metrics [Observed / Calculated] ---
        total_pois = len(pois)
        poi_counts_by_category = self.osm_service.get_poi_counts(plot.lat, plot.lng, radius_m)
        poi_density_per_sqkm = round(total_pois / radius_area_sqkm, 2) if radius_area_sqkm > 0 else 0.0

        # --- B. Road Network & Access Metrics [Observed / Calculated] ---
        road_network_length_m = round(sum(r.length_m for r in roads), 1)
        road_density_m_per_sqkm = (
            round(road_network_length_m / radius_area_sqkm, 1) if radius_area_sqkm > 0 else 0.0
        )
        major_roads = [r for r in roads if r.highway_type in MAJOR_HIGHWAYS]
        major_road_count = len(major_roads)

        # Nearest major road distance in metres
        nearest_major = self.osm_service.get_nearest_major_road(plot.lat, plot.lng)
        if nearest_major is not None:
            nearest_major_road_m = nearest_major[1]
        else:
            nearest_major_road_m = float(radius_m)

        # --- C. Land Use Composition [Observed / Calculated] ---
        type_effective_areas: Dict[str, float] = {}
        for zone in landuse_zones:
            effective_area = zone.area_sqm * (zone.overlap_pct / 100.0)
            type_effective_areas[zone.landuse_type] = (
                type_effective_areas.get(zone.landuse_type, 0.0) + effective_area
            )

        total_effective_area = sum(type_effective_areas.values())

        if total_effective_area > 0:
            dominant_landuse = max(type_effective_areas, key=type_effective_areas.get)
            landuse_distribution = {
                k: round((v / total_effective_area) * 100.0, 1)
                for k, v in type_effective_areas.items()
            }
        else:
            dominant_landuse = "residential"
            landuse_distribution = {}

        residential_pct = landuse_distribution.get("residential", 0.0)
        commercial_pct = round(
            sum(landuse_distribution.get(t, 0.0) for t in COMMERCIAL_LANDUSE_TYPES), 1
        )
        green_space_pct = round(
            sum(landuse_distribution.get(t, 0.0) for t in GREEN_SPACE_LANDUSE_TYPES), 1
        )
        industrial_pct = landuse_distribution.get("industrial", 0.0)

        # Ensure percentages stay clamped in [0.0, 100.0]
        residential_pct = min(100.0, max(0.0, residential_pct))
        commercial_pct = min(100.0, max(0.0, commercial_pct))
        green_space_pct = min(100.0, max(0.0, green_space_pct))
        industrial_pct = min(100.0, max(0.0, industrial_pct))

        # --- D. Transit Metrics [Observed / Calculated] ---
        transit_stop_count = len(transport_stops)
        if transport_stops:
            nearest_transit_m = min(s.distance_m for s in transport_stops)
        else:
            nearest_stop = self.osm_service.get_nearest_transport_stop(plot.lat, plot.lng)
            nearest_transit_m = nearest_stop.distance_m if nearest_stop else float(radius_m)

        # --- E. Modelled Indicators [Derived / Modelled] ---
        # 1. Building density estimate: ratio of built-up footprint coverage (0.0 - 1.0)
        # Derived from built-up land use shares with typical ground-space index (GSI)
        building_density_estimate = round(
            min(
                1.0,
                max(
                    0.0,
                    (residential_pct * 0.35 + commercial_pct * 0.50 + industrial_pct * 0.40) / 100.0,
                ),
            ),
            2,
        )

        # 2. Population density estimate: people/km²
        # Modelled proxy based on residential land fraction and building density
        if residential_pct > 0:
            raw_pop_est = (residential_pct / 100.0) * 10500.0 + (building_density_estimate * 2000.0)
            population_density_estimate = round(max(0.0, raw_pop_est), 1)
        else:
            population_density_estimate = 0.0

        # --- F. Environmental / Water-body Context [Observed / Calculated] ---
        active_water_bodies = water_bodies if water_bodies is not None else []
        water_body_count = len(active_water_bodies)
        nearest_wb_tuple = self.osm_service.get_nearest_water_body(plot.lat, plot.lng)
        if (
            nearest_wb_tuple is not None
            and isinstance(nearest_wb_tuple, (tuple, list))
            and len(nearest_wb_tuple) == 2
        ):
            nearest_wb, nearest_water_body_m = nearest_wb_tuple
            nearest_water_body_name = getattr(nearest_wb, "name", None)
            nearest_water_body_m = (
                float(nearest_water_body_m) if nearest_water_body_m is not None else None
            )
        else:
            nearest_water_body_m = None
            nearest_water_body_name = None

        water_body_area_within_radius_sqm = round(
            sum(w.intersecting_area_sqm for w in active_water_bodies), 1
        )

        if nearest_water_body_name is not None and nearest_water_body_m is not None:
            if nearest_water_body_m < 1000:
                dist_desc = f"{int(nearest_water_body_m)}m"
            else:
                dist_desc = f"{(nearest_water_body_m / 1000.0):.1f}km"
            water_body_proximity_context = (
                f"Selected plot is {dist_desc} from {nearest_water_body_name}."
            )
        else:
            water_body_proximity_context = None

        return ContextSummary(
            total_pois=total_pois,
            poi_counts_by_category=poi_counts_by_category,
            poi_density_per_sqkm=poi_density_per_sqkm,
            road_network_length_m=road_network_length_m,
            road_density_m_per_sqkm=road_density_m_per_sqkm,
            major_road_count=major_road_count,
            nearest_major_road_m=nearest_major_road_m,
            dominant_landuse=dominant_landuse,
            landuse_distribution=landuse_distribution,
            residential_pct=residential_pct,
            commercial_pct=commercial_pct,
            green_space_pct=green_space_pct,
            industrial_pct=industrial_pct,
            transit_stop_count=transit_stop_count,
            nearest_transit_m=nearest_transit_m,
            population_density_estimate=population_density_estimate,
            building_density_estimate=building_density_estimate,
            ward=ward,
            water_body_count=water_body_count,
            nearest_water_body_m=nearest_water_body_m,
            nearest_water_body_name=nearest_water_body_name,
            water_body_area_within_radius_sqm=water_body_area_within_radius_sqm,
            water_body_proximity_context=water_body_proximity_context,
        )


_context_analyzer_instance: Optional[ContextAnalyzer] = None


def get_context_analyzer(
    osm_service: Optional[OSMServiceBase] = None, force_reload: bool = False
) -> ContextAnalyzer:
    """Return the global ContextAnalyzer instance."""
    global _context_analyzer_instance
    if _context_analyzer_instance is None or force_reload:
        _context_analyzer_instance = ContextAnalyzer(osm_service=osm_service)
    return _context_analyzer_instance
