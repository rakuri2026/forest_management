from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.user_group import UserGroupExtent, UserGroupBuilding
from app.models.calculation import Calculation
from fastapi import UploadFile
import tempfile
import os
import json
from typing import List, Dict, Any, Optional
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class UserGroupAnalysisService:
    """
    Service for User Group Map analysis
    Handles extent creation, spatial analysis, and data export
    """

    def __init__(self, db: Session):
        self.db = db

    def _delete_existing_extents(self, calculation_id: str) -> int:
        """
        Delete all existing extents for this calculation
        CASCADE will automatically delete related user_group_buildings
        Returns: number of extents deleted
        """
        try:
            deleted_count = self.db.query(UserGroupExtent).filter(
                UserGroupExtent.calculation_id == UUID(calculation_id)
            ).delete()
            self.db.commit()
            logger.info(f"Deleted {deleted_count} existing extents for calculation {calculation_id}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting existing extents: {e}")
            self.db.rollback()
            return 0

    async def process_uploaded_boundary(
        self,
        calculation_id: str,
        file: UploadFile,
        user_id: UUID
    ) -> UserGroupExtent:
        """
        Process uploaded boundary file and create extent
        Supports: KML, KMZ, Shapefile, GPX, GeoJSON, CSV
        """
        # Check if extent already exists
        existing = self.db.query(UserGroupExtent).filter(
            UserGroupExtent.calculation_id == UUID(calculation_id)
        ).first()
        if existing:
            raise ValueError("User Group extent already exists. Please delete it first before uploading a new one.")

        # Save uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        file_ext = file.filename.lower().split('.')[-1]
        file_path = os.path.join(temp_dir, file.filename)

        try:
            # Save file
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)

            # Process based on file type
            if file_ext in ['kml', 'kmz']:
                geometry_wkt = self._process_kml(file_path)
            elif file_ext == 'zip':  # Shapefile
                geometry_wkt = self._process_shapefile(file_path)
            elif file_ext == 'gpx':
                geometry_wkt = self._process_gpx(file_path)
            elif file_ext in ['geojson', 'json']:
                geometry_wkt = self._process_geojson(file_path)
            elif file_ext == 'csv':
                geometry_wkt = self._process_csv(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            # Create extent record
            extent = UserGroupExtent(
                calculation_id=UUID(calculation_id),
                user_id=user_id,
                extent_geometry=geometry_wkt,
                source_type='uploaded'
            )
            self.db.add(extent)
            self.db.commit()
            self.db.refresh(extent)

            return extent

        finally:
            # Cleanup temp files
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    def _process_kml(self, file_path: str) -> str:
        """Process KML/KMZ file and return WKT"""
        try:
            import geopandas as gpd
            from shapely.geometry import MultiPolygon
            from shapely import force_2d

            # Try reading KML with geopandas
            # geopandas can use fiona or pyogrio backend
            try:
                gdf = gpd.read_file(file_path, driver='KML')
            except:
                # If KML driver fails, try without specifying driver
                gdf = gpd.read_file(file_path)

            gdf = gdf.to_crs('EPSG:4326')

            # Combine all geometries
            geometry = gdf.geometry.unary_union

            # Force 2D (remove Z dimension if present)
            geometry = force_2d(geometry)

            # Ensure MultiPolygon
            if geometry.geom_type == 'Polygon':
                geometry = MultiPolygon([geometry])

            return geometry.wkt

        except Exception as e:
            logger.error(f"Error processing KML: {e}")
            raise ValueError(f"Failed to process KML file: {str(e)}")

    def _process_shapefile(self, zip_path: str) -> str:
        """Process Shapefile (ZIP) and return WKT"""
        try:
            import zipfile
            import geopandas as gpd
            from shapely.geometry import MultiPolygon
            from shapely import force_2d

            temp_dir = tempfile.mkdtemp()

            # Extract ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)

            # Find .shp file
            shp_files = [f for f in os.listdir(temp_dir) if f.endswith('.shp')]
            if not shp_files:
                raise ValueError("No .shp file found in ZIP")

            shp_path = os.path.join(temp_dir, shp_files[0])

            # Read shapefile
            gdf = gpd.read_file(shp_path)
            gdf = gdf.to_crs('EPSG:4326')

            # Combine geometries
            geometry = gdf.geometry.unary_union

            # Force 2D (remove Z dimension if present)
            geometry = force_2d(geometry)

            if geometry.geom_type == 'Polygon':
                geometry = MultiPolygon([geometry])

            return geometry.wkt

        except Exception as e:
            logger.error(f"Error processing Shapefile: {e}")
            raise ValueError(f"Failed to process Shapefile: {str(e)}")

    def _process_gpx(self, file_path: str) -> str:
        """Process GPX track file - convert to polygon"""
        try:
            import geopandas as gpd
            from shapely.geometry import MultiPolygon
            from shapely import force_2d

            # Read GPX tracks
            gdf = gpd.read_file(file_path, layer='tracks')
            gdf = gdf.to_crs('EPSG:4326')

            # Convert LineString to Polygon using convex hull
            geometry = gdf.geometry.unary_union.convex_hull

            # Force 2D (remove Z dimension if present)
            geometry = force_2d(geometry)

            if geometry.geom_type == 'Polygon':
                geometry = MultiPolygon([geometry])

            return geometry.wkt

        except Exception as e:
            logger.error(f"Error processing GPX: {e}")
            raise ValueError(f"Failed to process GPX file: {str(e)}")

    def _process_geojson(self, file_path: str) -> str:
        """Process GeoJSON file"""
        try:
            import geopandas as gpd
            from shapely.geometry import MultiPolygon
            from shapely import force_2d

            gdf = gpd.read_file(file_path)
            gdf = gdf.to_crs('EPSG:4326')

            geometry = gdf.geometry.unary_union

            # Force 2D (remove Z dimension if present)
            geometry = force_2d(geometry)

            if geometry.geom_type == 'Polygon':
                geometry = MultiPolygon([geometry])

            return geometry.wkt

        except Exception as e:
            logger.error(f"Error processing GeoJSON: {e}")
            raise ValueError(f"Failed to process GeoJSON file: {str(e)}")

    def _process_csv(self, file_path: str) -> str:
        """Process CSV with coordinates - convert to polygon"""
        try:
            import pandas as pd
            from shapely.geometry import Polygon, MultiPolygon, Point
            from shapely import force_2d

            df = pd.read_csv(file_path)

            # Detect column names
            lat_col = None
            lon_col = None

            for col in df.columns:
                col_lower = col.lower()
                if col_lower in ['lat', 'latitude', 'y']:
                    lat_col = col
                if col_lower in ['lon', 'long', 'longitude', 'x']:
                    lon_col = col

            if not lat_col or not lon_col:
                raise ValueError("CSV must have lat/lon columns")

            # Create polygon from points
            points = [(row[lon_col], row[lat_col]) for _, row in df.iterrows()]

            if len(points) < 3:
                raise ValueError("Need at least 3 points to create a polygon")

            polygon = Polygon(points)

            # Force 2D (should already be 2D, but just in case)
            polygon = force_2d(polygon)

            geometry = MultiPolygon([polygon])

            return geometry.wkt

        except Exception as e:
            logger.error(f"Error processing CSV: {e}")
            raise ValueError(f"Failed to process CSV file: {str(e)}")

    async def create_manual_extent(
        self,
        calculation_id: str,
        geometry: Dict[str, Any],
        user_id: UUID
    ) -> UserGroupExtent:
        """Create extent from manually digitized geometry"""
        try:
            from shapely.geometry import shape, MultiPolygon
            from shapely import force_2d

            # Convert GeoJSON to shapely geometry
            geom = shape(geometry)

            # Force 2D (remove Z dimension if present)
            geom = force_2d(geom)

            if geom.geom_type == 'Polygon':
                geom = MultiPolygon([geom])

            extent = UserGroupExtent(
                calculation_id=UUID(calculation_id),
                user_id=user_id,
                extent_geometry=geom.wkt,
                source_type='manual'
            )
            self.db.add(extent)
            self.db.commit()
            self.db.refresh(extent)

            return extent

        except Exception as e:
            logger.error(f"Error creating manual extent: {e}")
            raise

    async def create_auto_buffer(
        self,
        calculation_id: str,
        buffer_distance_m: int,
        user_id: UUID
    ) -> UserGroupExtent:
        """Create auto-buffer extent from forest boundary"""
        try:
            # Check if extent already exists
            existing = self.db.query(UserGroupExtent).filter(
                UserGroupExtent.calculation_id == UUID(calculation_id)
            ).first()
            if existing:
                raise ValueError("User Group extent already exists. Please delete it first before creating a new one.")

            # Get forest boundary
            calc = self.db.query(Calculation).filter(
                Calculation.id == UUID(calculation_id)
            ).first()

            if not calc:
                raise ValueError("Calculation not found")

            # Create buffer using PostGIS (in meters using UTM)
            # Convert boundary_geom to GeoJSON
            boundary_geojson_query = text("""
                SELECT ST_AsGeoJSON(boundary_geom)
                FROM public.calculations
                WHERE id = :calc_id
            """)
            boundary_geojson = self.db.execute(
                boundary_geojson_query,
                {'calc_id': str(calc.id)}
            ).first()[0]

            query = text("""
                SELECT ST_AsText(
                    ST_Transform(
                        ST_Buffer(
                            ST_Transform(ST_GeomFromGeoJSON(:geom), 32645),  -- UTM 45N for Nepal
                            :distance
                        ),
                        4326  -- Convert back to WGS84
                    )
                ) as buffered_geom
            """)

            result = self.db.execute(query, {
                'geom': boundary_geojson,
                'distance': buffer_distance_m
            }).first()

            buffered_geom_wkt = result[0]

            extent = UserGroupExtent(
                calculation_id=UUID(calculation_id),
                user_id=user_id,
                extent_geometry=buffered_geom_wkt,
                source_type='auto_buffer',
                buffer_distance_m=buffer_distance_m
            )
            self.db.add(extent)
            self.db.commit()
            self.db.refresh(extent)

            return extent

        except Exception as e:
            logger.error(f"Error creating auto-buffer: {e}")
            raise

    async def analyze_user_group(
        self,
        calculation_id: str,
        extent_id: int
    ) -> List[Dict[str, Any]]:
        """
        Main analysis:
        1. Clip buildings and settlements
        2. Assign buildings to nearest settlement
        3. Calculate statistics
        4. Calculate direction from forest centroid
        """
        import time
        analysis_start = time.time()

        try:
            logger.info(f"🔍 Starting User Group analysis for extent_id={extent_id}")

            # Get extent
            step_start = time.time()
            extent = self.db.query(UserGroupExtent).filter(
                UserGroupExtent.id == extent_id
            ).first()

            if not extent:
                raise ValueError("Extent not found")
            logger.info(f"  ✓ Get extent: {time.time() - step_start:.3f}s")

            # Get forest centroid
            step_start = time.time()
            calc = self.db.query(Calculation).filter(
                Calculation.id == UUID(calculation_id)
            ).first()

            # Convert boundary_geom to use directly in ST_Centroid
            forest_centroid_query = text("""
                SELECT ST_AsText(ST_Centroid(boundary_geom)) as centroid
                FROM public.calculations
                WHERE id = :calc_id
            """)
            forest_centroid = self.db.execute(
                forest_centroid_query,
                {'calc_id': str(calc.id)}
            ).first()[0]
            logger.info(f"  ✓ Get forest centroid: {time.time() - step_start:.3f}s")

            # Get extent geometry as WKT text for spatial queries
            step_start = time.time()
            extent_wkt_query = text("""
                SELECT ST_AsText(extent_geometry)
                FROM public.user_group_extents
                WHERE id = :extent_id
            """)
            extent_wkt = self.db.execute(
                extent_wkt_query,
                {'extent_id': extent.id}
            ).first()[0]
            logger.info(f"  ✓ Get extent WKT: {time.time() - step_start:.3f}s")

            # Clip buildings and settlements
            step_start = time.time()
            buildings = self._clip_buildings(extent_wkt)
            logger.info(f"  ✓ Clip buildings: {time.time() - step_start:.3f}s (found {len(buildings)} buildings)")

            step_start = time.time()
            settlements = self._clip_settlements(extent_wkt)
            logger.info(f"  ✓ Clip settlements: {time.time() - step_start:.3f}s (found {len(settlements)} settlements)")

            # If no buildings found at all, return early
            if not buildings:
                logger.warning("No buildings found within extent")
                return []

            # If no settlements found, create a virtual settlement for all buildings
            if not settlements:
                logger.info("No settlements found within extent - creating virtual 'User Group Area' settlement")
                # Calculate centroid of all buildings as virtual settlement location
                avg_lon = sum(b['centroid_lon'] for b in buildings) / len(buildings)
                avg_lat = sum(b['centroid_lat'] for b in buildings) / len(buildings)

                settlements = [{
                    'id': -1,  # Virtual settlement ID
                    'name': 'User Group Area',
                    'geometry': json.dumps({
                        'type': 'Point',
                        'coordinates': [avg_lon, avg_lat]
                    }),
                    'lon': avg_lon,
                    'lat': avg_lat
                }]

            # Assign buildings to settlements
            step_start = time.time()
            building_settlement_map = self._assign_buildings_to_settlements(
                buildings, settlements
            )
            logger.info(f"  ✓ Assign buildings to settlements: {time.time() - step_start:.3f}s ({len(buildings)} × {len(settlements)} calculations)")

            # Calculate statistics per settlement
            step_start = time.time()
            results = []

            # Clear existing analysis results for this extent
            self.db.query(UserGroupBuilding).filter(
                UserGroupBuilding.extent_id == extent_id
            ).delete()

            for settlement in settlements:
                settlement_buildings = [
                    b for b in buildings
                    if building_settlement_map.get(b['id']) == settlement['id']
                ]

                building_count = len(settlement_buildings)
                total_area = sum(b['area_m2'] for b in settlement_buildings)

                # Categorize buildings by size
                # Small: < 50 m², Medium: 50-150 m², Large: > 150 m²
                small_count = sum(1 for b in settlement_buildings if b['area_m2'] < 50)
                medium_count = sum(1 for b in settlement_buildings if 50 <= b['area_m2'] <= 150)
                large_count = sum(1 for b in settlement_buildings if b['area_m2'] > 150)
                avg_building_size = total_area / building_count if building_count > 0 else 0

                # Calculate direction from forest centroid
                direction = self._calculate_direction(
                    forest_centroid,
                    settlement['geometry']
                )

                # Convert building polygons to points (centroids)
                building_points = [
                    {
                        'lat': b['centroid_lat'],
                        'lon': b['centroid_lon'],
                        'area': b['area_m2']
                    }
                    for b in settlement_buildings
                ]

                # Create settlement location point
                settlement_point = f"POINT({settlement['lon']} {settlement['lat']})"

                # Save to database
                user_group_building = UserGroupBuilding(
                    extent_id=extent_id,
                    settlement_id=settlement['id'],
                    settlement_name=settlement['name'],
                    building_count=building_count,
                    total_building_area_m2=total_area,
                    direction_from_forest=direction,
                    buildings_geojson=building_points,
                    settlement_location=settlement_point
                )
                self.db.add(user_group_building)

                results.append({
                    'settlement_name': settlement['name'],
                    'building_count': building_count,
                    'total_area_m2': total_area,
                    'small_buildings': small_count,
                    'medium_buildings': medium_count,
                    'large_buildings': large_count,
                    'avg_building_size_m2': avg_building_size,
                    'direction': direction
                })

            logger.info(f"  ✓ Calculate statistics: {time.time() - step_start:.3f}s")

            step_start = time.time()
            self.db.commit()
            logger.info(f"  ✓ Save to database: {time.time() - step_start:.3f}s")

            total_time = time.time() - analysis_start
            logger.info(f"✅ User Group analysis completed in {total_time:.2f}s")

            return results

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Error analyzing user group: {e}")
            raise

    def _clip_buildings(self, extent_geom: str) -> List[Dict[str, Any]]:
        """Query buildings within extent"""
        try:
            query = text("""
                SELECT
                    b.objectid,
                    ST_AsGeoJSON(b.shape) as geometry,
                    ST_Area(b.shape::geography) as area_m2,
                    ST_X(ST_Centroid(b.shape)) as centroid_lon,
                    ST_Y(ST_Centroid(b.shape)) as centroid_lat
                FROM buildings.building b
                WHERE ST_Intersects(b.shape, ST_GeomFromText(:extent, 4326))
                LIMIT 10000
            """)

            results = self.db.execute(query, {'extent': extent_geom}).fetchall()

            return [
                {
                    'id': r[0],
                    'geometry': r[1],
                    'area_m2': float(r[2]) if r[2] else 0.0,
                    'centroid_lon': float(r[3]),
                    'centroid_lat': float(r[4])
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Error clipping buildings: {e}")
            return []

    def _clip_settlements(self, extent_geom: str) -> List[Dict[str, Any]]:
        """Query settlements within extent"""
        try:
            query = text("""
                SELECT
                    s.objectid,
                    s.vil_name,
                    ST_AsGeoJSON(s.shape) as geometry,
                    s.x as lon,
                    s.y as lat
                FROM admin.settlement s
                WHERE ST_Intersects(s.shape, ST_GeomFromText(:extent, 4326))
                LIMIT 1000
            """)

            results = self.db.execute(query, {'extent': extent_geom}).fetchall()

            return [
                {
                    'id': r[0],
                    'name': r[1] or f'Settlement {r[0]}',
                    'geometry': r[2],
                    'lon': float(r[3]) if r[3] else 0.0,
                    'lat': float(r[4]) if r[4] else 0.0
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Error clipping settlements: {e}")
            return []

    def _assign_buildings_to_settlements(
        self,
        buildings: List[Dict],
        settlements: List[Dict]
    ) -> Dict[int, int]:
        """Assign each building to nearest settlement"""
        if not buildings or not settlements:
            return {}

        try:
            # Use PostGIS for efficient nearest neighbor
            building_ids = [str(b['id']) for b in buildings]
            building_geoms = [b['geometry'] for b in buildings]
            settlement_ids = [str(s['id']) for s in settlements]
            settlement_geoms = [s['geometry'] for s in settlements]

            # For simplicity, use a lateral join approach
            mapping = {}
            for building in buildings:
                min_distance = float('inf')
                nearest_settlement = None

                for settlement in settlements:
                    # Simple distance calculation (could be optimized)
                    from math import sqrt
                    dx = building['centroid_lon'] - settlement['lon']
                    dy = building['centroid_lat'] - settlement['lat']
                    distance = sqrt(dx*dx + dy*dy)

                    if distance < min_distance:
                        min_distance = distance
                        nearest_settlement = settlement['id']

                if nearest_settlement:
                    mapping[building['id']] = nearest_settlement

            return mapping

        except Exception as e:
            logger.error(f"Error assigning buildings to settlements: {e}")
            return {}

    def _calculate_direction(
        self,
        forest_centroid_wkt: str,
        settlement_geom_json: str
    ) -> str:
        """Calculate compass direction from forest to settlement"""
        try:
            query = text("""
                SELECT
                    CASE
                        WHEN degrees(ST_Azimuth(
                            ST_GeomFromText(:forest_centroid, 4326),
                            ST_GeomFromGeoJSON(:settlement_geom)
                        )) BETWEEN 337.5 AND 360
                            OR degrees(ST_Azimuth(
                                ST_GeomFromText(:forest_centroid, 4326),
                                ST_GeomFromGeoJSON(:settlement_geom)
                            )) BETWEEN 0 AND 22.5 THEN 'N'
                        WHEN degrees(ST_Azimuth(
                            ST_GeomFromText(:forest_centroid, 4326),
                            ST_GeomFromGeoJSON(:settlement_geom)
                        )) BETWEEN 22.5 AND 67.5 THEN 'NE'
                        WHEN degrees(ST_Azimuth(
                            ST_GeomFromText(:forest_centroid, 4326),
                            ST_GeomFromGeoJSON(:settlement_geom)
                        )) BETWEEN 67.5 AND 112.5 THEN 'E'
                        WHEN degrees(ST_Azimuth(
                            ST_GeomFromText(:forest_centroid, 4326),
                            ST_GeomFromGeoJSON(:settlement_geom)
                        )) BETWEEN 112.5 AND 157.5 THEN 'SE'
                        WHEN degrees(ST_Azimuth(
                            ST_GeomFromText(:forest_centroid, 4326),
                            ST_GeomFromGeoJSON(:settlement_geom)
                        )) BETWEEN 157.5 AND 202.5 THEN 'S'
                        WHEN degrees(ST_Azimuth(
                            ST_GeomFromText(:forest_centroid, 4326),
                            ST_GeomFromGeoJSON(:settlement_geom)
                        )) BETWEEN 202.5 AND 247.5 THEN 'SW'
                        WHEN degrees(ST_Azimuth(
                            ST_GeomFromText(:forest_centroid, 4326),
                            ST_GeomFromGeoJSON(:settlement_geom)
                        )) BETWEEN 247.5 AND 292.5 THEN 'W'
                        ELSE 'NW'
                    END as direction
            """)

            result = self.db.execute(query, {
                'forest_centroid': forest_centroid_wkt,
                'settlement_geom': settlement_geom_json
            }).first()

            return result[0] if result else 'Unknown'

        except Exception as e:
            logger.error(f"Error calculating direction: {e}")
            return 'Unknown'

    async def get_results(self, calculation_id: str) -> Optional[Dict[str, Any]]:
        """Get all analysis results for visualization"""
        try:
            # Get extent
            extent = self.db.query(UserGroupExtent).filter(
                UserGroupExtent.calculation_id == UUID(calculation_id)
            ).order_by(UserGroupExtent.created_at.desc()).first()

            if not extent:
                return None

            # Get building statistics
            buildings = self.db.query(UserGroupBuilding).filter(
                UserGroupBuilding.extent_id == extent.id
            ).all()

            # Get forest boundary
            calc = self.db.query(Calculation).filter(
                Calculation.id == UUID(calculation_id)
            ).first()

            # Convert extent geometry to GeoJSON - query directly from table
            extent_geojson_query = text("""
                SELECT ST_AsGeoJSON(extent_geometry)
                FROM public.user_group_extents
                WHERE id = :extent_id
            """)
            extent_geojson = self.db.execute(
                extent_geojson_query,
                {'extent_id': extent.id}
            ).first()[0]

            # Convert forest boundary_geom to GeoJSON
            forest_boundary_query = text("""
                SELECT ST_AsGeoJSON(boundary_geom)
                FROM public.calculations
                WHERE id = :calc_id
            """)
            forest_boundary_geojson = self.db.execute(
                forest_boundary_query,
                {'calc_id': str(calc.id)}
            ).first()[0]

            return {
                'extent_id': extent.id,
                'extent_geometry': json.loads(extent_geojson),
                'forest_boundary': json.loads(forest_boundary_geojson),
                'settlements': [
                    self._enrich_settlement_with_categories(b)
                    for b in buildings
                ],
                'buildings': [
                    building_point
                    for b in buildings
                    if b.buildings_geojson
                    for building_point in b.buildings_geojson
                ]
            }

        except Exception as e:
            logger.error(f"Error getting results: {e}")
            return None

    def _enrich_settlement_with_categories(self, building_record: UserGroupBuilding) -> Dict[str, Any]:
        """Calculate building size categories from the buildings_geojson field"""
        # Extract building areas from the geojson
        building_areas = []
        if building_record.buildings_geojson:
            building_areas = [b.get('area', 0) for b in building_record.buildings_geojson]

        # Categorize: Small < 50 m², Medium 50-150 m², Large > 150 m²
        small_count = sum(1 for area in building_areas if area < 50)
        medium_count = sum(1 for area in building_areas if 50 <= area <= 150)
        large_count = sum(1 for area in building_areas if area > 150)

        total_area = float(building_record.total_building_area_m2) if building_record.total_building_area_m2 else 0
        avg_size = total_area / building_record.building_count if building_record.building_count > 0 else 0

        return {
            'settlement_id': building_record.settlement_id,
            'settlement_name': building_record.settlement_name,
            'building_count': building_record.building_count,
            'total_area_m2': total_area,
            'small_buildings': small_count,
            'medium_buildings': medium_count,
            'large_buildings': large_count,
            'avg_building_size_m2': round(avg_size, 2),
            'direction_from_forest': building_record.direction_from_forest,
            'lat': self._get_point_lat(building_record.settlement_location),
            'lon': self._get_point_lon(building_record.settlement_location)
        }

    def _get_point_lat(self, point_geom) -> Optional[float]:
        """Extract latitude from point geometry (handles both WKT and WKBElement)"""
        if not point_geom:
            return None
        try:
            from geoalchemy2.shape import to_shape
            point = to_shape(point_geom)
            return float(point.y)
        except:
            return None

    def _get_point_lon(self, point_geom) -> Optional[float]:
        """Extract longitude from point geometry (handles both WKT and WKBElement)"""
        if not point_geom:
            return None
        try:
            from geoalchemy2.shape import to_shape
            point = to_shape(point_geom)
            return float(point.x)
        except:
            return None

    async def get_poi_layers(
        self,
        calculation_id: str,
        layer_type: str = "all"
    ) -> Dict[str, List]:
        """Get POI layers for visualization"""
        try:
            # Get extent to query within
            extent = self.db.query(UserGroupExtent).filter(
                UserGroupExtent.calculation_id == UUID(calculation_id)
            ).order_by(UserGroupExtent.created_at.desc()).first()

            if not extent:
                return {}

            # Get extent geometry as WKT text
            extent_wkt_query = text("""
                SELECT ST_AsText(extent_geometry)
                FROM public.user_group_extents
                WHERE id = :extent_id
            """)
            extent_wkt = self.db.execute(
                extent_wkt_query,
                {'extent_id': extent.id}
            ).first()[0]

            poi_data = {}

            # POI layer
            if layer_type in ['all', 'poi']:
                poi_query = text("""
                    SELECT
                        COALESCE(name, name_en) as name,
                        amenity,
                        ST_X(geom) as lon,
                        ST_Y(geom) as lat
                    FROM infrastructure.poi
                    WHERE ST_Intersects(geom, ST_GeomFromText(:extent, 4326))
                    LIMIT 500
                """)
                poi_results = self.db.execute(
                    poi_query,
                    {'extent': extent_wkt}
                ).fetchall()
                poi_data['poi'] = [
                    {
                        'name': r[0] or 'Unknown',
                        'type': r[1],
                        'lon': float(r[2]),
                        'lat': float(r[3])
                    }
                    for r in poi_results
                ]

            # Education facilities
            if layer_type in ['all', 'education']:
                edu_query = text("""
                    SELECT
                        name,
                        ST_X(geom) as lon,
                        ST_Y(geom) as lat
                    FROM infrastructure.education_facilities
                    WHERE ST_Intersects(geom, ST_GeomFromText(:extent, 4326))
                    LIMIT 200
                """)
                try:
                    edu_results = self.db.execute(
                        edu_query,
                        {'extent': extent_wkt}
                    ).fetchall()
                    poi_data['education'] = [
                        {
                            'name': r[0] or 'School',
                            'lon': float(r[1]),
                            'lat': float(r[2])
                        }
                        for r in edu_results
                    ]
                except:
                    poi_data['education'] = []

            # Health facilities
            if layer_type in ['all', 'health']:
                health_query = text("""
                    SELECT
                        hf_type,
                        ST_X(geom) as lon,
                        ST_Y(geom) as lat
                    FROM infrastructure.health_facilities
                    WHERE ST_Intersects(geom, ST_GeomFromText(:extent, 4326))
                    LIMIT 200
                """)
                try:
                    health_results = self.db.execute(
                        health_query,
                        {'extent': extent_wkt}
                    ).fetchall()
                    poi_data['health'] = [
                        {
                            'name': r[0] or 'Health Facility',
                            'lon': float(r[1]),
                            'lat': float(r[2])
                        }
                        for r in health_results
                    ]
                except:
                    poi_data['health'] = []

            # Rivers
            if layer_type in ['all', 'rivers']:
                river_query = text("""
                    SELECT
                        river_name,
                        ST_AsGeoJSON(geom) as geometry
                    FROM river.river84
                    WHERE ST_Intersects(geom, ST_GeomFromText(:extent, 4326))
                    LIMIT 100
                """)
                try:
                    river_results = self.db.execute(
                        river_query,
                        {'extent': extent_wkt}
                    ).fetchall()
                    poi_data['rivers'] = [
                        {
                            'name': r[0] or 'River',
                            'geometry': json.loads(r[1])
                        }
                        for r in river_results
                    ]
                except:
                    poi_data['rivers'] = []

            return poi_data

        except Exception as e:
            logger.error(f"Error getting POI layers: {e}")
            return {}

    # Export functions (placeholders for now)
    async def generate_pdf_report(self, extent_id: int) -> str:
        """Generate PDF report - placeholder"""
        raise NotImplementedError("PDF export not yet implemented")

    async def export_to_gpkg(self, extent_id: int) -> str:
        """Export to GeoPackage - placeholder"""
        raise NotImplementedError("GeoPackage export not yet implemented")

    async def export_to_geojson(self, extent_id: int) -> str:
        """Export extent, settlements, and buildings to GeoJSON"""
        import tempfile

        try:
            # Get extent
            extent = self.db.query(UserGroupExtent).filter(
                UserGroupExtent.id == extent_id
            ).first()

            if not extent:
                raise ValueError("Extent not found")

            # Get settlement statistics
            buildings = self.db.query(UserGroupBuilding).filter(
                UserGroupBuilding.extent_id == extent_id
            ).all()

            # Get extent geometry as GeoJSON
            extent_geom_query = text("""
                SELECT ST_AsGeoJSON(extent_geometry)
                FROM public.user_group_extents
                WHERE id = :extent_id
            """)
            extent_geojson = self.db.execute(
                extent_geom_query,
                {'extent_id': extent_id}
            ).first()[0]

            # Build GeoJSON FeatureCollection
            features = []

            # Add extent boundary as a feature
            features.append({
                'type': 'Feature',
                'properties': {
                    'type': 'extent_boundary',
                    'source_type': extent.source_type,
                    'buffer_distance_m': extent.buffer_distance_m
                },
                'geometry': json.loads(extent_geojson)
            })

            # Add settlements as point features
            for b in buildings:
                if b.settlement_location:
                    # Calculate building size categories from buildings_geojson
                    building_areas = [building.get('area', 0) for building in b.buildings_geojson] if b.buildings_geojson else []
                    small_count = sum(1 for area in building_areas if area < 50)
                    medium_count = sum(1 for area in building_areas if 50 <= area <= 150)
                    large_count = sum(1 for area in building_areas if area > 150)
                    total_area = float(b.total_building_area_m2) if b.total_building_area_m2 else 0
                    avg_size = total_area / b.building_count if b.building_count and b.building_count > 0 else 0

                    features.append({
                        'type': 'Feature',
                        'properties': {
                            'type': 'settlement',
                            'settlement_name': b.settlement_name,
                            'building_count': b.building_count,
                            'total_area_m2': total_area,
                            'small_buildings': small_count,
                            'medium_buildings': medium_count,
                            'large_buildings': large_count,
                            'avg_building_size_m2': round(avg_size, 2),
                            'direction_from_forest': b.direction_from_forest
                        },
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [
                                self._get_point_lon(b.settlement_location),
                                self._get_point_lat(b.settlement_location)
                            ]
                        }
                    })

                # Add individual buildings if available
                if b.buildings_geojson:
                    for building in b.buildings_geojson:
                        features.append({
                            'type': 'Feature',
                            'properties': {
                                'type': 'building',
                                'settlement_name': b.settlement_name,
                                'area_m2': building.get('area', 0)
                            },
                            'geometry': {
                                'type': 'Point',
                                'coordinates': [building['lon'], building['lat']]
                            }
                        })

            geojson_data = {
                'type': 'FeatureCollection',
                'features': features
            }

            # Create temporary GeoJSON file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                suffix='.geojson',
                encoding='utf-8'
            )
            json.dump(geojson_data, temp_file, indent=2)
            temp_file.close()

            return temp_file.name

        except Exception as e:
            logger.error(f"Error exporting to GeoJSON: {e}")
            raise

    async def export_to_csv(self, extent_id: int) -> str:
        """Export settlement statistics to CSV"""
        import csv
        import tempfile

        try:
            # Get settlement statistics
            buildings = self.db.query(UserGroupBuilding).filter(
                UserGroupBuilding.extent_id == extent_id
            ).order_by(UserGroupBuilding.settlement_name).all()

            if not buildings:
                raise ValueError("No analysis data found for this extent")

            # Create temporary CSV file
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                delete=False,
                suffix='.csv',
                newline='',
                encoding='utf-8'
            )

            writer = csv.writer(temp_file)

            # Write header
            writer.writerow([
                'Settlement Name',
                'Number of Buildings',
                'Total Building Area (m²)',
                'Small Buildings (<50m²)',
                'Medium Buildings (50-150m²)',
                'Large Buildings (>150m²)',
                'Average Building Size (m²)',
                'Direction from Forest',
                'Latitude',
                'Longitude'
            ])

            # Write data rows
            for b in buildings:
                # Calculate building size categories from buildings_geojson
                building_areas = [building.get('area', 0) for building in b.buildings_geojson] if b.buildings_geojson else []
                small_count = sum(1 for area in building_areas if area < 50)
                medium_count = sum(1 for area in building_areas if 50 <= area <= 150)
                large_count = sum(1 for area in building_areas if area > 150)
                total_area = float(b.total_building_area_m2) if b.total_building_area_m2 else 0
                avg_size = total_area / b.building_count if b.building_count and b.building_count > 0 else 0

                writer.writerow([
                    b.settlement_name or 'Unknown',
                    b.building_count or 0,
                    round(total_area, 2),
                    small_count,
                    medium_count,
                    large_count,
                    round(avg_size, 2),
                    b.direction_from_forest or 'Unknown',
                    self._get_point_lat(b.settlement_location) if b.settlement_location else '',
                    self._get_point_lon(b.settlement_location) if b.settlement_location else ''
                ])

            temp_file.close()
            return temp_file.name

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            raise

    # ============================================================================
    # Land Cover Analysis
    # ============================================================================

    async def analyze_land_cover(self, calculation_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive land cover and biomass analysis for user group map

        This analysis:
        1. Gets user group extent geometry
        2. Gets community forest boundary geometry
        3. Calculates overlap and net analysis area
        4. Performs land cover classification (ESA World Cover)
        5. Calculates biomass and timber volume (AGB 2022 Nepal)

        Args:
            calculation_id: The calculation (community forest) ID

        Returns:
            Dictionary with land cover classes, biomass, and area statistics

        Raises:
            ValueError: If community forest boundary or user group extent not found
        """
        from datetime import datetime

        try:
            logger.info(f"Starting land cover analysis for calculation {calculation_id}")

            # Step 1: Get community forest boundary
            calc = self.db.query(Calculation).filter(
                Calculation.id == UUID(calculation_id)
            ).first()

            if not calc:
                raise ValueError(
                    "Community Forest boundary not found. "
                    "Please upload a forest boundary in the Analysis tab first."
                )

            # Step 2: Get user group extent
            extent = self.db.query(UserGroupExtent).filter(
                UserGroupExtent.calculation_id == UUID(calculation_id)
            ).order_by(UserGroupExtent.created_at.desc()).first()

            if not extent:
                raise ValueError(
                    "User Group extent not found. "
                    "Please upload or create a user group boundary in the Forest User Map tab first."
                )

            logger.info(f"Found extent ID: {extent.id}, calculation ID: {calc.id}")

            # Step 3: Call PostgreSQL function to perform per-class biomass analysis
            # This ensures biomass is only counted for tree cover (and partially for shrubland/grassland)
            query = text("""
                SELECT
                    user_group_area_ha,
                    forest_overlap_area_ha,
                    net_analysis_area_ha,
                    land_cover_class,
                    land_cover_name,
                    land_cover_area_ha,
                    land_cover_percentage,
                    avg_biomass_mg_per_ha,
                    min_biomass_mg_per_ha,
                    max_biomass_mg_per_ha,
                    total_biomass_mg,
                    avg_volume_m3_per_ha,
                    total_volume_m3,
                    pixel_count
                FROM analyze_land_cover_and_biomass_per_class(
                    (SELECT extent_geometry FROM public.user_group_extents WHERE id = :extent_id),
                    (SELECT boundary_geom FROM public.calculations WHERE id = :calc_id)
                )
            """)

            results = self.db.execute(
                query,
                {'extent_id': extent.id, 'calc_id': str(calc.id)}
            ).fetchall()

            if not results:
                raise ValueError("No land cover data found. Please ensure raster datasets are available.")

            # Step 4: Process results
            land_cover_classes = []
            total_biomass = 0
            total_volume = 0
            user_group_area = 0
            forest_overlap_area = 0
            net_area = 0

            for row in results:
                # Extract area summary (same for all rows)
                if not land_cover_classes:
                    user_group_area = float(row[0])
                    forest_overlap_area = float(row[1])
                    net_area = float(row[2])

                # Extract land cover class data
                land_cover_classes.append({
                    'class_code': int(row[3]),
                    'class_name': row[4],
                    'area_ha': float(row[5]),
                    'percentage': float(row[6]),
                    'avg_biomass_mg_per_ha': float(row[7]),
                    'min_biomass_mg_per_ha': float(row[8]),
                    'max_biomass_mg_per_ha': float(row[9]),
                    'total_biomass_mg': float(row[10]),
                    'avg_volume_m3_per_ha': float(row[11]),
                    'total_volume_m3': float(row[12]),
                    'pixel_count': int(row[13])
                })

                total_biomass += float(row[10])
                total_volume += float(row[12])

            # Calculate overall averages
            avg_biomass = total_biomass / net_area if net_area > 0 else 0
            avg_volume = total_volume / net_area if net_area > 0 else 0

            logger.info(f"Land cover analysis completed: {len(land_cover_classes)} classes found")
            logger.info(f"Total biomass: {total_biomass:.2f} Mg, Total volume: {total_volume:.2f} m³")

            return {
                'user_group_area_ha': round(user_group_area, 4),
                'forest_overlap_area_ha': round(forest_overlap_area, 4),
                'net_analysis_area_ha': round(net_area, 4),
                'land_cover_classes': land_cover_classes,
                'total_biomass_mg': round(total_biomass, 2),
                'total_volume_m3': round(total_volume, 2),
                'avg_biomass_mg_per_ha': round(avg_biomass, 2),
                'avg_volume_m3_per_ha': round(avg_volume, 2),
                'analysis_date': datetime.utcnow(),
                'has_forest_overlap': forest_overlap_area > 0
            }

        except ValueError:
            # Re-raise ValueError with original message
            raise
        except Exception as e:
            logger.error(f"Error performing land cover analysis: {e}")
            raise ValueError(f"Land cover analysis failed: {str(e)}")
