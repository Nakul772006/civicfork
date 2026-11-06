"""OpenStreetMap data access service and caching layer for CivicFork.

Provides abstract service interface (OSMServiceBase) and concrete implementation
(CachedOSMService) backed by bundled Mysuru GeoJSON datasets using GeoPandas
and Shapely for spatial indexing, radius queries, and nearest-feature operations.
"""

from abc import ABC, abstractmethod
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point

from app.exceptions import OSMDataError
from app.models.domain import LandUseZone, POI, RoadSegment, TransportStop, WardData, WaterBody
from app.settings import settings

logger = logging.getLogger("civicfork.osm")

# Mysuru is in UTM Zone 43N (covering 72°E - 78°E)
PROJECTION_CRS = "EPSG:32643"
GEOGRAPHIC_CRS = "EPSG:4326"

MAJOR_HIGHWAYS = ("motorway", "trunk", "primary", "secondary")

# Tag and subcategory sets for canonical normalization
HEALTHCARE_TAGS = {"hospital", "clinic", "doctors", "pharmacy", "medical_centre", "medical_center", "health_post", "dispensary"}


def normalize_poi_category(
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    """Map raw OSM tags, category, and subcategory to CivicFork's canonical categories."""
    raw_cat = (category or "").lower().strip()
    subcat = (subcategory or "").lower().strip()
    tag_dict = tags if isinstance(tags, dict) else {}
    amenity = str(tag_dict.get("amenity", "")).lower().strip()
    healthcare_tag = str(tag_dict.get("healthcare", "")).lower().strip()

    # 1. Canonical healthcare normalization (checks category, subcategory, amenity, and healthcare tags)
    if (
        raw_cat in ("healthcare", "hospital", "clinic", "pharmacy", "doctors", "medical_centre", "medical_center")
        or subcat in HEALTHCARE_TAGS
        or amenity in ("hospital", "clinic", "pharmacy", "doctors")
        or bool(healthcare_tag)
    ):
        return "healthcare"

    # 2. Preserve known canonical categories
    if raw_cat in ("education", "parks", "transport", "parking", "commercial", "community", "government", "other"):
        return raw_cat

    # 3. Tag / subcategory inference for unclassified raw OSM entries
    if subcat in ("school", "college", "university", "kindergarten") or amenity in ("school", "college", "university", "kindergarten"):
        return "education"
    if subcat in ("park", "pitch", "garden", "playground") or str(tag_dict.get("leisure", "")).lower() in ("park", "garden", "playground", "pitch"):
        return "parks"
    if subcat in ("bus_station", "railway_station", "bus_stop") or str(tag_dict.get("highway", "")).lower() == "bus_stop":
        return "transport"
    if subcat in ("parking", "parking_space") or amenity in ("parking", "bicycle_parking"):
        return "parking"
    if subcat in ("supermarket", "marketplace", "market", "mall", "shop", "retail") or bool(tag_dict.get("shop")):
        return "commercial"
    if subcat in ("community_centre", "social_facility") or amenity in ("community_centre", "social_facility"):
        return "community"

    return raw_cat if raw_cat else "other"


class OSMServiceBase(ABC):
    """Abstract interface defining the contract for OSM data access.

    Allows replacing the cached static GeoJSON implementation with a live
    Overpass API or PostGIS service in future iterations.
    """

    @abstractmethod
    def is_loaded(self) -> bool:
        """Return True if OSM data sources are loaded and available."""
        pass

    @abstractmethod
    def get_pois(
        self, lat: float, lng: float, radius_m: int, category: Optional[str] = None
    ) -> List[POI]:
        """Retrieve POIs within a radius, optionally filtered by category."""
        pass

    @abstractmethod
    def get_nearest_poi(
        self, lat: float, lng: float, category: str, max_distance_m: Optional[float] = None
    ) -> Optional[POI]:
        """Find the nearest POI matching a category."""
        pass

    @abstractmethod
    def get_poi_counts(self, lat: float, lng: float, radius_m: int) -> Dict[str, int]:
        """Count POIs within radius grouped by normalized category."""
        pass

    @abstractmethod
    def get_roads(self, lat: float, lng: float, radius_m: int) -> List[RoadSegment]:
        """Retrieve road segments within radius."""
        pass

    @abstractmethod
    def get_nearest_major_road(
        self, lat: float, lng: float
    ) -> Optional[Tuple[RoadSegment, float]]:
        """Find the nearest major road (trunk, primary, secondary) and its distance."""
        pass

    @abstractmethod
    def get_landuse(self, lat: float, lng: float, radius_m: int) -> List[LandUseZone]:
        """Retrieve land-use zones intersecting radius buffer."""
        pass

    @abstractmethod
    def get_transport_stops(
        self, lat: float, lng: float, radius_m: int
    ) -> List[TransportStop]:
        """Retrieve public transport stops within radius."""
        pass

    @abstractmethod
    def get_nearest_transport_stop(
        self, lat: float, lng: float, max_distance_m: Optional[float] = None
    ) -> Optional[TransportStop]:
        """Find the nearest public transit stop."""
        pass

    @abstractmethod
    def get_ward(self, lat: float, lng: float) -> Optional[WardData]:
        """Find the MCC ward containing the given latitude and longitude, if covered."""
        pass

    @abstractmethod
    def get_water_bodies(
        self, lat: float, lng: float, radius_m: int
    ) -> List[WaterBody]:
        """Retrieve water bodies intersecting the circular radius buffer around (lat, lng)."""
        pass

    @abstractmethod
    def get_nearest_water_body(
        self, lat: float, lng: float, max_distance_m: Optional[float] = None
    ) -> Optional[Tuple[WaterBody, float]]:
        """Find the nearest water body to (lat, lng) and its distance in metres."""
        pass

    @abstractmethod
    def get_water_body_overlap(
        self, lat: float, lng: float, radius_m: int
    ) -> Dict[str, float]:
        """Calculate aggregate water body metrics within radius."""
        pass

    @abstractmethod
    def get_geojson(
        self, lat: float, lng: float, radius_m: int, layer: str
    ) -> Dict[str, Any]:
        """Return GeoJSON FeatureCollection within radius for frontend map rendering."""
        pass


class CachedOSMService(OSMServiceBase):
    """GeoPandas/Shapely implementation of OSM data access backed by cached GeoJSON."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or settings.osm_data_dir
        self._transformer_to_utm = Transformer.from_crs(
            GEOGRAPHIC_CRS, PROJECTION_CRS, always_xy=True
        )

        self._pois_gdf: Optional[gpd.GeoDataFrame] = None
        self._pois_utm: Optional[gpd.GeoDataFrame] = None

        self._roads_gdf: Optional[gpd.GeoDataFrame] = None
        self._roads_utm: Optional[gpd.GeoDataFrame] = None

        self._landuse_gdf: Optional[gpd.GeoDataFrame] = None
        self._landuse_utm: Optional[gpd.GeoDataFrame] = None

        self._transport_gdf: Optional[gpd.GeoDataFrame] = None
        self._transport_utm: Optional[gpd.GeoDataFrame] = None

        self._buildings_gdf: Optional[gpd.GeoDataFrame] = None
        self._buildings_utm: Optional[gpd.GeoDataFrame] = None

        self._wards_gdf: Optional[gpd.GeoDataFrame] = None
        self._wards_utm: Optional[gpd.GeoDataFrame] = None

        self._water_bodies_gdf: Optional[gpd.GeoDataFrame] = None
        self._water_bodies_utm: Optional[gpd.GeoDataFrame] = None

        self._loaded = False
        self._load_datasets()

    def is_loaded(self) -> bool:
        """Return True if all core GeoJSON datasets were loaded."""
        return self._loaded

    def _load_single_dataset(self, filename: str, required: bool = True) -> Optional[gpd.GeoDataFrame]:
        file_path = self.data_dir / filename
        if not file_path.exists():
            if required:
                raise OSMDataError(f"Required OSM dataset missing: {file_path}")
            return None
        try:
            gdf = gpd.read_file(file_path)
            if gdf.crs is None:
                gdf = gdf.set_crs(GEOGRAPHIC_CRS)
            elif gdf.crs != GEOGRAPHIC_CRS:
                gdf = gdf.to_crs(GEOGRAPHIC_CRS)
            return gdf
        except Exception as e:
            raise OSMDataError(f"Failed to read or parse GeoJSON dataset {filename}: {e}") from e

    def _load_datasets(self) -> None:
        """Load and spatially index all available Mysuru GeoJSON layers."""
        if not self.data_dir.exists():
            raise OSMDataError(f"OSM data directory not found: {self.data_dir}")

        logger.info("Loading cached Mysuru OSM datasets from %s", self.data_dir)

        # 1. POIs
        self._pois_gdf = self._load_single_dataset("pois.geojson", required=True)
        # Apply canonical category normalization across all features
        canonical_categories = []
        for _, row in self._pois_gdf.iterrows():
            c_cat = normalize_poi_category(
                category=row.get("category"),
                subcategory=row.get("subcategory"),
                tags=row.get("tags") if isinstance(row.get("tags"), dict) else {},
            )
            canonical_categories.append(c_cat)
        self._pois_gdf["category"] = canonical_categories
        self._pois_utm = self._pois_gdf.to_crs(PROJECTION_CRS)

        # 2. Roads
        self._roads_gdf = self._load_single_dataset("roads.geojson", required=True)
        self._roads_utm = self._roads_gdf.to_crs(PROJECTION_CRS)

        # 3. Land Use
        self._landuse_gdf = self._load_single_dataset("landuse.geojson", required=True)
        self._landuse_utm = self._landuse_gdf.to_crs(PROJECTION_CRS)

        # 4. Transport Stops
        self._transport_gdf = self._load_single_dataset("transport.geojson", required=True)
        self._transport_utm = self._transport_gdf.to_crs(PROJECTION_CRS)

        # 5. Buildings (Optional)
        self._buildings_gdf = self._load_single_dataset("buildings.geojson", required=False)
        if self._buildings_gdf is not None:
            self._buildings_utm = self._buildings_gdf.to_crs(PROJECTION_CRS)

        # 6. Wards (Optional / administrative context)
        self._wards_gdf = self._load_single_dataset("wards.geojson", required=False)
        if self._wards_gdf is not None:
            self._wards_utm = self._wards_gdf.to_crs(PROJECTION_CRS)

        # 7. Water Bodies (Optional / environmental context)
        self._water_bodies_gdf = self._load_single_dataset("water_bodies.geojson", required=False)
        if self._water_bodies_gdf is not None:
            self._water_bodies_utm = self._water_bodies_gdf.to_crs(PROJECTION_CRS)

        self._loaded = True
        logger.info(
            "OSM datasets loaded: %d POIs, %d roads, %d landuse zones, %d transit stops",
            len(self._pois_gdf),
            len(self._roads_gdf),
            len(self._landuse_gdf),
            len(self._transport_gdf),
        )

    def _create_buffer_utm(self, lat: float, lng: float, radius_m: int) -> Tuple[Point, Any]:
        """Project (lat, lng) to UTM and generate circular buffer of radius_m."""
        x, y = self._transformer_to_utm.transform(lng, lat)
        center_utm = Point(x, y)
        buffer_utm = center_utm.buffer(radius_m)
        return center_utm, buffer_utm

    def get_pois(
        self, lat: float, lng: float, radius_m: int, category: Optional[str] = None
    ) -> List[POI]:
        """Retrieve normalized POIs within radius_m of (lat, lng)."""
        if self._pois_utm is None or len(self._pois_utm) == 0:
            return []

        center_utm, buffer_utm = self._create_buffer_utm(lat, lng, radius_m)

        # Spatial filter using intersects with buffer
        mask = self._pois_utm.intersects(buffer_utm)
        if not mask.any():
            return []

        matched_utm = self._pois_utm[mask].copy()
        matched_4326 = self._pois_gdf.loc[matched_utm.index]

        if category:
            cat_mask = matched_utm["category"] == category
            if not cat_mask.any():
                return []
            matched_utm = matched_utm[cat_mask]
            matched_4326 = matched_4326.loc[matched_utm.index]

        # Compute Euclidean distance in metres
        distances = matched_utm.geometry.distance(center_utm)

        results: List[POI] = []
        for idx, row in matched_utm.iterrows():
            geo_row = matched_4326.loc[idx]
            dist_m = float(distances.loc[idx])
            geom = geo_row.geometry

            tags_dict = geo_row.get("tags")
            if not isinstance(tags_dict, dict):
                tags_dict = {}

            results.append(
                POI(
                    osm_id=str(geo_row.get("osm_id", f"poi/{idx}")),
                    name=geo_row.get("name"),
                    category=str(geo_row.get("category", "other")),
                    subcategory=geo_row.get("subcategory"),
                    lat=float(geom.y),
                    lng=float(geom.x),
                    distance_m=round(dist_m, 1),
                    tags=tags_dict,
                )
            )

        # Sort closest first
        results.sort(key=lambda p: p.distance_m)
        return results

    def get_nearest_poi(
        self, lat: float, lng: float, category: str, max_distance_m: Optional[float] = None
    ) -> Optional[POI]:
        """Find the single nearest POI of category across the dataset."""
        if self._pois_utm is None or len(self._pois_utm) == 0:
            return None

        center_utm, _ = self._create_buffer_utm(lat, lng, radius_m=10)
        cat_matches = self._pois_utm[self._pois_utm["category"] == category]
        if cat_matches.empty:
            return None

        distances = cat_matches.geometry.distance(center_utm)
        min_idx = distances.idxmin()
        min_dist = float(distances.loc[min_idx])

        if max_distance_m is not None and min_dist > max_distance_m:
            return None

        geo_row = self._pois_gdf.loc[min_idx]
        geom = geo_row.geometry

        tags_dict = geo_row.get("tags")
        if not isinstance(tags_dict, dict):
            tags_dict = {}

        return POI(
            osm_id=str(geo_row.get("osm_id", f"poi/{min_idx}")),
            name=geo_row.get("name"),
            category=str(geo_row.get("category", category)),
            subcategory=geo_row.get("subcategory"),
            lat=float(geom.y),
            lng=float(geom.x),
            distance_m=round(min_dist, 1),
            tags=tags_dict,
        )

    def get_poi_counts(self, lat: float, lng: float, radius_m: int) -> Dict[str, int]:
        """Return counts of POIs within radius_m grouped by category."""
        pois = self.get_pois(lat, lng, radius_m)
        counts: Dict[str, int] = {}
        for p in pois:
            counts[p.category] = counts.get(p.category, 0) + 1
        return counts

    def get_roads(self, lat: float, lng: float, radius_m: int) -> List[RoadSegment]:
        """Retrieve road segments within radius_m of (lat, lng)."""
        if self._roads_utm is None or len(self._roads_utm) == 0:
            return []

        center_utm, buffer_utm = self._create_buffer_utm(lat, lng, radius_m)
        mask = self._roads_utm.intersects(buffer_utm)
        if not mask.any():
            return []

        matched_utm = self._roads_utm[mask].copy()
        matched_4326 = self._roads_gdf.loc[matched_utm.index]

        distances = matched_utm.geometry.distance(center_utm)

        results: List[RoadSegment] = []
        for idx, row in matched_utm.iterrows():
            geo_row = matched_4326.loc[idx]
            dist_m = float(distances.loc[idx])
            geom_4326 = geo_row.geometry

            # Segment length in metres from UTM geometry
            length_m = float(row.geometry.length)

            # Coordinates in [[lng, lat], ...]
            coords: List[List[float]] = []
            if hasattr(geom_4326, "coords"):
                coords = [[round(coord[0], 6), round(coord[1], 6)] for coord in geom_4326.coords]
            elif hasattr(geom_4326, "geoms"):
                for line in geom_4326.geoms:
                    coords.extend([[round(coord[0], 6), round(coord[1], 6)] for coord in line.coords])

            results.append(
                RoadSegment(
                    osm_id=str(geo_row.get("osm_id", f"way/{idx}")),
                    name=geo_row.get("name"),
                    highway_type=str(geo_row.get("highway", "residential")),
                    length_m=round(length_m, 1),
                    distance_m=round(dist_m, 1),
                    geometry_coords=coords,
                )
            )

        results.sort(key=lambda r: r.distance_m)
        return results

    def get_nearest_major_road(
        self, lat: float, lng: float
    ) -> Optional[Tuple[RoadSegment, float]]:
        """Find the nearest primary, secondary, or trunk road and its distance in metres."""
        if self._roads_utm is None or len(self._roads_utm) == 0:
            return None

        center_utm, _ = self._create_buffer_utm(lat, lng, radius_m=10)
        major_mask = self._roads_utm["highway"].isin(MAJOR_HIGHWAYS)
        if not major_mask.any():
            return None

        matched_utm = self._roads_utm[major_mask]
        distances = matched_utm.geometry.distance(center_utm)
        min_idx = distances.idxmin()
        min_dist = float(distances.loc[min_idx])

        geo_row = self._roads_gdf.loc[min_idx]
        geom_4326 = geo_row.geometry
        length_m = float(matched_utm.loc[min_idx].geometry.length)

        coords = []
        if hasattr(geom_4326, "coords"):
            coords = [[round(c[0], 6), round(c[1], 6)] for c in geom_4326.coords]

        road = RoadSegment(
            osm_id=str(geo_row.get("osm_id", f"way/{min_idx}")),
            name=geo_row.get("name"),
            highway_type=str(geo_row.get("highway", "primary")),
            length_m=round(length_m, 1),
            distance_m=round(min_dist, 1),
            geometry_coords=coords,
        )
        return road, round(min_dist, 1)

    def get_landuse(self, lat: float, lng: float, radius_m: int) -> List[LandUseZone]:
        """Retrieve land-use zones intersecting radius_m buffer."""
        if self._landuse_utm is None or len(self._landuse_utm) == 0:
            return []

        center_utm, buffer_utm = self._create_buffer_utm(lat, lng, radius_m)
        mask = self._landuse_utm.intersects(buffer_utm)
        if not mask.any():
            return []

        matched_utm = self._landuse_utm[mask].copy()
        matched_4326 = self._landuse_gdf.loc[matched_utm.index]

        results: List[LandUseZone] = []
        for idx, row in matched_utm.iterrows():
            geo_row = matched_4326.loc[idx]
            zone_geom_utm = row.geometry
            zone_area = float(zone_geom_utm.area)

            # Distance to zone centroid in metres
            dist_m = float(zone_geom_utm.centroid.distance(center_utm))

            # Overlap percentage of this zone inside buffer
            overlap_pct = 0.0
            if zone_area > 0:
                intersection = zone_geom_utm.intersection(buffer_utm)
                overlap_pct = min(100.0, max(0.0, (intersection.area / zone_area) * 100.0))

            results.append(
                LandUseZone(
                    osm_id=str(geo_row.get("osm_id", f"relation/{idx}")),
                    landuse_type=str(geo_row.get("landuse", "residential")),
                    area_sqm=round(zone_area, 1),
                    distance_m=round(dist_m, 1),
                    overlap_pct=round(overlap_pct, 1),
                )
            )

        results.sort(key=lambda z: z.distance_m)
        return results

    def get_transport_stops(
        self, lat: float, lng: float, radius_m: int
    ) -> List[TransportStop]:
        """Retrieve public transport stops within radius_m of (lat, lng)."""
        if self._transport_utm is None or len(self._transport_utm) == 0:
            return []

        center_utm, buffer_utm = self._create_buffer_utm(lat, lng, radius_m)
        mask = self._transport_utm.intersects(buffer_utm)
        if not mask.any():
            return []

        matched_utm = self._transport_utm[mask].copy()
        matched_4326 = self._transport_gdf.loc[matched_utm.index]

        distances = matched_utm.geometry.distance(center_utm)

        results: List[TransportStop] = []
        for idx, row in matched_utm.iterrows():
            geo_row = matched_4326.loc[idx]
            dist_m = float(distances.loc[idx])
            geom = geo_row.geometry

            results.append(
                TransportStop(
                    osm_id=str(geo_row.get("osm_id", f"stop/{idx}")),
                    name=geo_row.get("name"),
                    transport_type=str(geo_row.get("transport_type", "bus_stop")),
                    lat=float(geom.y),
                    lng=float(geom.x),
                    distance_m=round(dist_m, 1),
                )
            )

        results.sort(key=lambda s: s.distance_m)
        return results

    def get_nearest_transport_stop(
        self, lat: float, lng: float, max_distance_m: Optional[float] = None
    ) -> Optional[TransportStop]:
        """Find the nearest public transit stop across the transport layer."""
        if self._transport_utm is None or len(self._transport_utm) == 0:
            return None

        center_utm, _ = self._create_buffer_utm(lat, lng, radius_m=10)
        distances = self._transport_utm.geometry.distance(center_utm)
        min_idx = distances.idxmin()
        min_dist = float(distances.loc[min_idx])

        if max_distance_m is not None and min_dist > max_distance_m:
            return None

        geo_row = self._transport_gdf.loc[min_idx]
        geom = geo_row.geometry

        return TransportStop(
            osm_id=str(geo_row.get("osm_id", f"stop/{min_idx}")),
            name=geo_row.get("name"),
            transport_type=str(geo_row.get("transport_type", "bus_stop")),
            lat=float(geom.y),
            lng=float(geom.x),
            distance_m=round(min_dist, 1),
        )

    def get_ward(self, lat: float, lng: float) -> Optional[WardData]:
        """Find the MCC ward containing the given latitude and longitude.

        Expected behavior:
        - point inside ward -> return WardData
        - point outside ward dataset -> return None
        - invalid geometry or coordinates -> handled safely (return None)
        - boundary cases -> deterministic (sort by ward_id)
        - repeated calls -> identical results
        """
        if self._wards_gdf is None or len(self._wards_gdf) == 0:
            return None

        try:
            pt = Point(lng, lat)
            if not pt.is_valid or pt.is_empty:
                return None

            # Spatial candidate search via covers (interior + boundary)
            matches = self._wards_gdf[self._wards_gdf.geometry.covers(pt)]
            if len(matches) == 0:
                matches = self._wards_gdf[self._wards_gdf.geometry.intersects(pt)]

            if len(matches) == 0:
                return None

            # Ensure determinism on boundary cases by sorting by ward_id
            if len(matches) > 1:
                matches = matches.sort_values(
                    by="ward_id",
                    key=lambda col: pd.to_numeric(col, errors="coerce").fillna(9999),
                )

            row = matches.iloc[0]

            def _clean_val(val, target_type):
                if val is None or pd.isna(val):
                    return None
                try:
                    return target_type(val)
                except (ValueError, TypeError):
                    return None

            return WardData(
                ward_id=str(row.get("ward_id")),
                ward_name=str(row["ward_name"]) if row.get("ward_name") is not None and not pd.isna(row.get("ward_name")) else None,
                zone_id=str(row["zone_id"]) if row.get("zone_id") is not None and not pd.isna(row.get("zone_id")) else None,
                population=_clean_val(row.get("population"), int),
                population_year=_clean_val(row.get("population_year"), int),
                area_sq_km=_clean_val(row.get("area_sq_km"), float),
                population_density_per_sq_km=_clean_val(row.get("population_density_per_sq_km"), float),
                lgd_ward_code=_clean_val(row.get("lgd_ward_code"), int),
            )
        except Exception as e:
            logger.warning("Error during ward lookup for (lat=%.4f, lng=%.4f): %s", lat, lng, e)
            return None

    def get_water_bodies(
        self, lat: float, lng: float, radius_m: int
    ) -> List[WaterBody]:
        """Retrieve water bodies intersecting the circular radius buffer around (lat, lng)."""
        if (
            self._water_bodies_gdf is None
            or self._water_bodies_utm is None
            or len(self._water_bodies_utm) == 0
        ):
            return []

        try:
            center_utm, buffer_utm = self._create_buffer_utm(lat, lng, radius_m)
            mask = self._water_bodies_utm.geometry.intersects(buffer_utm)
            if not mask.any():
                return []

            subset_utm = self._water_bodies_utm[mask]
            results: List[WaterBody] = []

            for idx, row in subset_utm.iterrows():
                geom_utm = row.geometry
                dist_m = round(float(geom_utm.distance(center_utm)), 1)
                intersection = geom_utm.intersection(buffer_utm)
                inter_area = round(float(intersection.area), 1)
                total_area = round(float(geom_utm.area), 1)
                overlap_pct = round((inter_area / total_area) * 100.0, 2) if total_area > 0 else 0.0

                wb = WaterBody(
                    osm_id=str(row.get("osm_id", f"water/{idx}")),
                    name=str(row.get("name", "Unnamed Water Body")),
                    local_name=str(row["local_name"]) if row.get("local_name") and not pd.isna(row.get("local_name")) else None,
                    water_type=str(row.get("water_type", "lake")),
                    area_sqm=total_area,
                    distance_m=dist_m,
                    overlap_pct=overlap_pct,
                    intersecting_area_sqm=inter_area,
                )
                results.append(wb)

            # Sort deterministically by distance_m, then osm_id
            results.sort(key=lambda w: (w.distance_m, w.osm_id))
            return results
        except Exception as e:
            logger.warning("Error querying water bodies for (lat=%.4f, lng=%.4f): %s", lat, lng, e)
            return []

    def get_nearest_water_body(
        self, lat: float, lng: float, max_distance_m: Optional[float] = None
    ) -> Optional[Tuple[WaterBody, float]]:
        """Find the nearest water body to (lat, lng) and its distance in metres."""
        if (
            self._water_bodies_gdf is None
            or self._water_bodies_utm is None
            or len(self._water_bodies_utm) == 0
        ):
            return None

        try:
            center_utm, _ = self._create_buffer_utm(lat, lng, radius_m=10)
            distances = self._water_bodies_utm.geometry.distance(center_utm)
            min_idx = distances.idxmin()
            min_dist = round(float(distances.loc[min_idx]), 1)

            if max_distance_m is not None and min_dist > max_distance_m:
                return None

            row = self._water_bodies_utm.loc[min_idx]
            geom_utm = row.geometry
            total_area = round(float(geom_utm.area), 1)

            wb = WaterBody(
                osm_id=str(row.get("osm_id", f"water/{min_idx}")),
                name=str(row.get("name", "Unnamed Water Body")),
                local_name=str(row["local_name"]) if row.get("local_name") and not pd.isna(row.get("local_name")) else None,
                water_type=str(row.get("water_type", "lake")),
                area_sqm=total_area,
                distance_m=min_dist,
                overlap_pct=0.0,
                intersecting_area_sqm=0.0,
            )
            return wb, min_dist
        except Exception as e:
            logger.warning("Error finding nearest water body for (lat=%.4f, lng=%.4f): %s", lat, lng, e)
            return None

    def get_water_body_overlap(
        self, lat: float, lng: float, radius_m: int
    ) -> Dict[str, float]:
        """Calculate aggregate water body metrics within radius."""
        try:
            water_bodies = self.get_water_bodies(lat, lng, radius_m)
            total_inter_area = sum(w.intersecting_area_sqm for w in water_bodies)
            import math
            buffer_area = math.pi * (radius_m ** 2)
            overlap_pct = round((total_inter_area / buffer_area) * 100.0, 2) if buffer_area > 0 else 0.0

            return {
                "count": float(len(water_bodies)),
                "intersecting_area_sqm": round(total_inter_area, 1),
                "buffer_overlap_pct": overlap_pct,
            }
        except Exception as e:
            logger.warning("Error calculating water body overlap for (lat=%.4f, lng=%.4f): %s", lat, lng, e)
            return {"count": 0.0, "intersecting_area_sqm": 0.0, "buffer_overlap_pct": 0.0}

    def get_geojson(
        self, lat: float, lng: float, radius_m: int, layer: str
    ) -> Dict[str, Any]:
        """Extract a GeoJSON FeatureCollection in EPSG:4326 within radius for frontend map layers."""
        gdf_map = {
            "pois": (self._pois_gdf, self._pois_utm),
            "roads": (self._roads_gdf, self._roads_utm),
            "landuse": (self._landuse_gdf, self._landuse_utm),
            "transport": (self._transport_gdf, self._transport_utm),
            "buildings": (self._buildings_gdf, self._buildings_utm),
            "wards": (self._wards_gdf, self._wards_utm),
            "water_bodies": (self._water_bodies_gdf, self._water_bodies_utm),
        }

        if layer not in gdf_map:
            raise OSMDataError(f"Unknown layer requested: {layer}. Must be one of {list(gdf_map.keys())}")

        gdf_4326, gdf_utm = gdf_map[layer]
        if gdf_4326 is None or gdf_utm is None or len(gdf_utm) == 0:
            return {"type": "FeatureCollection", "features": []}

        _, buffer_utm = self._create_buffer_utm(lat, lng, radius_m)
        mask = gdf_utm.intersects(buffer_utm)
        if not mask.any():
            return {"type": "FeatureCollection", "features": []}

        subset_4326 = gdf_4326[mask]
        return json.loads(subset_4326.to_json())


# -----------------------------------------------------------------------------
# Singleton Management
# -----------------------------------------------------------------------------

_osm_service_instance: Optional[OSMServiceBase] = None


def get_osm_service(data_dir: Optional[Path] = None, force_reload: bool = False) -> OSMServiceBase:
    """Return the global cached OSM service instance."""
    global _osm_service_instance
    if _osm_service_instance is None or force_reload:
        _osm_service_instance = CachedOSMService(data_dir=data_dir)
    return _osm_service_instance


def reset_osm_service() -> None:
    """Reset the singleton instance (primarily for tests)."""
    global _osm_service_instance
    _osm_service_instance = None
