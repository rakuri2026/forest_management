"""
Map Generation Service for Forest Management System

Generates A5-sized PNG maps for forest analysis reports.
- A5 dimensions: 148mm × 210mm (portrait) or 210mm × 148mm (landscape)
- Target DPI: 300 (high quality for printing)
- Output format: PNG with transparency support
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server-side generation

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import numpy as np
from typing import Optional, Tuple, Dict, Any, List
from pathlib import Path
import io
from PIL import Image
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import contextily as cx
from shapely.geometry import shape, mapping
from shapely import wkt
from sqlalchemy import text
import matplotlib.colors as mcolors

# A5 dimensions in inches at 300 DPI
A5_PORTRAIT_INCHES = (5.83, 8.27)   # 148mm × 210mm
A5_LANDSCAPE_INCHES = (8.27, 5.83)  # 210mm × 148mm
DEFAULT_DPI = 300


class MapGenerator:
    """
    Service for generating forest analysis maps.

    Features:
    - A5-sized maps (portrait/landscape)
    - High-quality 300 DPI output
    - Customizable colors and styles
    - North arrow and scale bar
    - Legend support
    """

    def __init__(self, dpi: int = DEFAULT_DPI):
        """
        Initialize the map generator.

        Args:
            dpi: Dots per inch for output images (default: 300)
        """
        self.dpi = dpi

        # Configure matplotlib for better map aesthetics
        plt.style.use('seaborn-v0_8-darkgrid')
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.size'] = 8
        plt.rcParams['axes.labelsize'] = 9
        plt.rcParams['axes.titlesize'] = 11
        plt.rcParams['legend.fontsize'] = 7
        plt.rcParams['figure.dpi'] = dpi

        # Configure requests session with timeout for basemap tiles
        self.session = requests.Session()
        retry_strategy = Retry(
            total=2,  # Only 2 retries (fast fail)
            backoff_factor=0.5,  # Short backoff
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def add_basemap_with_timeout(self, ax, crs='EPSG:4326', timeout=5, alpha=0.7, zorder=1):
        """
        Add basemap with timeout to prevent hanging.

        Args:
            ax: Matplotlib axes
            crs: Coordinate reference system
            timeout: Timeout in seconds (default: 5)
            alpha: Transparency (default: 0.7)
            zorder: Layer order (default: 1)

        Returns:
            bool: True if basemap added successfully, False otherwise
        """
        try:
            # Configure contextily to use our session with timeout
            import contextily.tile as ctx_tile

            # Store original session
            original_session = getattr(ctx_tile, '_session', None)

            # Create a new session with timeout
            session_with_timeout = requests.Session()
            session_with_timeout.request = lambda *args, **kwargs: requests.Session.request(
                session_with_timeout, *args, timeout=timeout, **kwargs
            )

            # Temporarily replace contextily's session
            ctx_tile._session = session_with_timeout

            # Add basemap with timeout
            cx.add_basemap(
                ax,
                crs=crs,
                source=cx.providers.OpenStreetMap.Mapnik,
                alpha=alpha,
                zorder=zorder
            )

            # Restore original session
            if original_session is not None:
                ctx_tile._session = original_session

            return True

        except Exception as e:
            print(f"Warning: Could not add basemap (timeout or connection error): {e}")
            return False

    def create_figure(
        self,
        orientation: str = 'portrait',
        title: str = '',
        add_border: bool = True
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        Create a new figure with A5 dimensions.

        Args:
            orientation: 'portrait' or 'landscape'
            title: Map title
            add_border: Whether to add border around map

        Returns:
            Tuple of (figure, axes)
        """
        # Set figure size based on orientation
        figsize = A5_PORTRAIT_INCHES if orientation == 'portrait' else A5_LANDSCAPE_INCHES

        # Create figure with adjusted layout for external elements
        # Leave space for title at top and legend/scale at bottom
        fig = plt.figure(figsize=figsize, dpi=self.dpi)

        # Create axes with margins for map elements
        # [left, bottom, width, height] in figure coordinates
        ax = fig.add_axes([0.12, 0.15, 0.76, 0.75])  # Leave margins for elements

        # Add title if provided (outside the axes)
        if title:
            fig.suptitle(title, fontsize=12, fontweight='bold', y=0.96)

        # Add border if requested
        if add_border:
            ax.spines['top'].set_visible(True)
            ax.spines['right'].set_visible(True)
            ax.spines['bottom'].set_visible(True)
            ax.spines['left'].set_visible(True)
            ax.spines['top'].set_linewidth(2)
            ax.spines['right'].set_linewidth(2)
            ax.spines['bottom'].set_linewidth(2)
            ax.spines['left'].set_linewidth(2)

        return fig, ax

    def add_north_arrow(
        self,
        fig: plt.Figure,
        ax: plt.Axes,
        x: float = 0.92,
        y: float = 0.92,
        size: float = 0.04
    ) -> None:
        """
        Add a north arrow outside the map area.

        Args:
            fig: Matplotlib figure
            ax: Matplotlib axes
            x: X position (0-1, figure coordinates)
            y: Y position (0-1, figure coordinates)
            size: Arrow size relative to figure
        """
        # Draw north arrow in figure coordinates (outside axes)
        arrow = mpatches.FancyArrow(
            x, y - size, 0, size,
            width=size/3,
            head_width=size,
            head_length=size/2,
            fc='black',
            ec='black',
            transform=fig.transFigure,
            zorder=1000,
            clip_on=False
        )
        fig.patches.append(arrow)

        # Add "N" label
        fig.text(
            x, y + size/4, 'N',
            ha='center',
            va='bottom',
            fontsize=10,
            fontweight='bold',
            zorder=1001
        )

    def add_scale_bar(
        self,
        fig: plt.Figure,
        ax: plt.Axes,
        length_km: float = 1.0,
        x: float = 0.15,
        y: float = 0.08,
        bar_width: float = 0.12
    ) -> None:
        """
        Add a scale bar outside the map area.

        Args:
            fig: Matplotlib figure
            ax: Matplotlib axes
            length_km: Scale bar length in kilometers
            x: X position (0-1, figure coordinates)
            y: Y position (0-1, figure coordinates)
            bar_width: Bar width relative to figure
        """
        # Draw scale bar in figure coordinates (outside axes)
        bar = mpatches.Rectangle(
            (x, y), bar_width, 0.008,
            transform=fig.transFigure,
            fc='black',
            ec='black',
            zorder=1000,
            clip_on=False
        )
        fig.patches.append(bar)

        # Add scale label
        fig.text(
            x + bar_width/2, y + 0.015,
            f'{length_km} km',
            ha='center',
            va='bottom',
            fontsize=8,
            zorder=1001
        )

    def save_to_buffer(self, fig: plt.Figure) -> io.BytesIO:
        """
        Save figure to BytesIO buffer as PNG.

        Args:
            fig: Matplotlib figure

        Returns:
            BytesIO buffer containing PNG data
        """
        buffer = io.BytesIO()
        fig.savefig(
            buffer,
            format='png',
            dpi=self.dpi,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none',
            pad_inches=0.1
        )
        buffer.seek(0)
        return buffer

    def save_to_file(self, fig: plt.Figure, filepath: str) -> Path:
        """
        Save figure to file as PNG.

        Args:
            fig: Matplotlib figure
            filepath: Output file path

        Returns:
            Path object of saved file
        """
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig.savefig(
            output_path,
            format='png',
            dpi=self.dpi,
            bbox_inches='tight',
            facecolor='white',
            edgecolor='none',
            pad_inches=0.1
        )

        return output_path

    def close_figure(self, fig: plt.Figure) -> None:
        """
        Close figure to free memory.

        Args:
            fig: Matplotlib figure to close
        """
        plt.close(fig)

    def query_schools_within_buffer(
        self,
        db_session,
        geometry: Dict[str, Any],
        buffer_meters: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Query schools within buffer distance of geometry.

        Args:
            db_session: SQLAlchemy database session
            geometry: GeoJSON geometry dict
            buffer_meters: Buffer distance in meters (default: 100m)

        Returns:
            List of school dicts with name, lon, lat, distance
        """
        try:
            # Convert geometry to WKT
            geom_shape = shape(geometry)
            geom_wkt = geom_shape.wkt

            # Query schools within buffer
            query = text("""
                SELECT
                    COALESCE(e.name, e.name_en, 'School') as name,
                    e.amenity,
                    ST_X(ST_Centroid(e.geom)) as lon,
                    ST_Y(ST_Centroid(e.geom)) as lat,
                    ST_Distance(
                        e.geom::geography,
                        ST_GeomFromText(:geom_wkt, 4326)::geography
                    ) as distance_m
                FROM infrastructure.education_facilities e
                WHERE ST_DWithin(
                    e.geom::geography,
                    ST_GeomFromText(:geom_wkt, 4326)::geography,
                    :buffer_m
                )
                ORDER BY distance_m
                LIMIT 50
            """)

            result = db_session.execute(
                query,
                {"geom_wkt": geom_wkt, "buffer_m": buffer_meters}
            )

            schools = []
            for row in result:
                schools.append({
                    "name": row[0],
                    "amenity": row[1],
                    "lon": float(row[2]),
                    "lat": float(row[3]),
                    "distance_m": float(row[4])
                })

            return schools

        except Exception as e:
            print(f"Warning: Could not query schools: {e}")
            return []

    def query_poi_within_buffer(
        self,
        db_session,
        geometry: Dict[str, Any],
        buffer_meters: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Query POI within buffer distance of geometry.

        Args:
            db_session: SQLAlchemy database session
            geometry: GeoJSON geometry dict
            buffer_meters: Buffer distance in meters (default: 100m)

        Returns:
            List of POI dicts with name, amenity, lon, lat, distance
        """
        try:
            geom_shape = shape(geometry)
            geom_wkt = geom_shape.wkt

            query = text("""
                SELECT
                    COALESCE(p.name, p.name_en, p.amenity, 'POI') as name,
                    COALESCE(p.amenity, p.shop, p.tourism, 'poi') as type,
                    ST_X(ST_Centroid(p.geom)) as lon,
                    ST_Y(ST_Centroid(p.geom)) as lat,
                    ST_Distance(
                        p.geom::geography,
                        ST_GeomFromText(:geom_wkt, 4326)::geography
                    ) as distance_m
                FROM infrastructure.poi p
                WHERE ST_DWithin(
                    p.geom::geography,
                    ST_GeomFromText(:geom_wkt, 4326)::geography,
                    :buffer_m
                )
                AND (p.amenity IS NOT NULL OR p.shop IS NOT NULL OR p.tourism IS NOT NULL)
                ORDER BY distance_m
                LIMIT 30
            """)

            result = db_session.execute(
                query,
                {"geom_wkt": geom_wkt, "buffer_m": buffer_meters}
            )

            poi_list = []
            for row in result:
                poi_list.append({
                    "name": row[0],
                    "type": row[1],
                    "lon": float(row[2]),
                    "lat": float(row[3]),
                    "distance_m": float(row[4])
                })

            return poi_list

        except Exception as e:
            print(f"Warning: Could not query POI: {e}")
            return []

    def query_roads_within_buffer(
        self,
        db_session,
        geometry: Dict[str, Any],
        buffer_meters: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Query roads within buffer distance of geometry.

        Args:
            db_session: SQLAlchemy database session
            geometry: GeoJSON geometry dict
            buffer_meters: Buffer distance in meters (default: 100m)

        Returns:
            List of road dicts with highway type and geometry WKT
        """
        try:
            geom_shape = shape(geometry)
            geom_wkt = geom_shape.wkt

            query = text("""
                SELECT
                    r.highway,
                    ST_AsText(r.geom) as geom_wkt
                FROM infrastructure.road r
                WHERE ST_DWithin(
                    r.geom::geography,
                    ST_GeomFromText(:geom_wkt, 4326)::geography,
                    :buffer_m
                )
                AND r.highway IS NOT NULL
                LIMIT 100
            """)

            result = db_session.execute(
                query,
                {"geom_wkt": geom_wkt, "buffer_m": buffer_meters}
            )

            roads = []
            for row in result:
                roads.append({
                    "highway": row[0],
                    "geom_wkt": row[1]
                })

            return roads

        except Exception as e:
            print(f"Warning: Could not query roads: {e}")
            return []

    def query_rivers_within_buffer(
        self,
        db_session,
        geometry: Dict[str, Any],
        buffer_meters: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Query rivers within buffer distance of geometry.

        Args:
            db_session: SQLAlchemy database session
            geometry: GeoJSON geometry dict
            buffer_meters: Buffer distance in meters (default: 100m)

        Returns:
            List of river dicts with name and geometry WKT
        """
        try:
            geom_shape = shape(geometry)
            geom_wkt = geom_shape.wkt

            query = text("""
                SELECT
                    COALESCE(NULLIF(TRIM(r.river_name), ''), 'River') as name,
                    ST_AsText(r.geom) as geom_wkt,
                    ST_X(ST_Centroid(r.geom)) as center_lon,
                    ST_Y(ST_Centroid(r.geom)) as center_lat
                FROM river.river_line r
                WHERE ST_DWithin(
                    r.geom::geography,
                    ST_GeomFromText(:geom_wkt, 4326)::geography,
                    :buffer_m
                )
                ORDER BY ST_Distance(
                    r.geom::geography,
                    ST_GeomFromText(:geom_wkt, 4326)::geography
                )
                LIMIT 20
            """)

            result = db_session.execute(
                query,
                {"geom_wkt": geom_wkt, "buffer_m": buffer_meters}
            )

            rivers = []
            for row in result:
                rivers.append({
                    "name": row[0],
                    "geom_wkt": row[1],
                    "center_lon": float(row[2]),
                    "center_lat": float(row[3])
                })

            return rivers

        except Exception as e:
            print(f"Warning: Could not query rivers: {e}")
            return []

    def query_ridges_within_buffer(
        self,
        db_session,
        geometry: Dict[str, Any],
        buffer_meters: float = 100.0
    ) -> List[Dict[str, Any]]:
        """
        Query ridges within buffer distance of geometry.

        Args:
            db_session: SQLAlchemy database session
            geometry: GeoJSON geometry dict
            buffer_meters: Buffer distance in meters (default: 100m)

        Returns:
            List of ridge dicts with name and geometry WKT
        """
        try:
            geom_shape = shape(geometry)
            geom_wkt = geom_shape.wkt

            query = text("""
                SELECT
                    COALESCE(NULLIF(TRIM(r.ridge_name), ''), 'Ridge') as name,
                    ST_AsText(r.geom) as geom_wkt,
                    ST_X(ST_Centroid(r.geom)) as center_lon,
                    ST_Y(ST_Centroid(r.geom)) as center_lat
                FROM river.ridge r
                WHERE ST_DWithin(
                    r.geom::geography,
                    ST_GeomFromText(:geom_wkt, 4326)::geography,
                    :buffer_m
                )
                ORDER BY ST_Distance(
                    r.geom::geography,
                    ST_GeomFromText(:geom_wkt, 4326)::geography
                )
                LIMIT 20
            """)

            result = db_session.execute(
                query,
                {"geom_wkt": geom_wkt, "buffer_m": buffer_meters}
            )

            ridges = []
            for row in result:
                ridges.append({
                    "name": row[0],
                    "geom_wkt": row[1],
                    "center_lon": float(row[2]),
                    "center_lat": float(row[3])
                })

            return ridges

        except Exception as e:
            print(f"Warning: Could not query ridges: {e}")
            return []

    def query_esa_boundary_intersecting(
        self,
        db_session,
        geometry: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Query ESA forest boundary intersecting with geometry.

        Args:
            db_session: SQLAlchemy database session
            geometry: GeoJSON geometry dict

        Returns:
            List of ESA boundary dicts with geometry WKT
        """
        try:
            geom_shape = shape(geometry)
            geom_wkt = geom_shape.wkt

            query = text("""
                SELECT
                    ST_AsText(e.geom) as geom_wkt
                FROM admin."esa_forest_Boundary" e
                WHERE ST_Intersects(
                    e.geom,
                    ST_GeomFromText(:geom_wkt, 4326)
                )
                LIMIT 10
            """)

            result = db_session.execute(
                query,
                {"geom_wkt": geom_wkt}
            )

            boundaries = []
            for row in result:
                boundaries.append({
                    "geom_wkt": row[0]
                })

            return boundaries

        except Exception as e:
            print(f"Warning: Could not query ESA boundary: {e}")
            return []

    def generate_boundary_map(
        self,
        geometry: Dict[str, Any],
        forest_name: str = 'Forest Boundary',
        orientation: str = 'auto',
        output_path: Optional[str] = None,
        db_session = None,
        show_schools: bool = True,
        show_poi: bool = True,
        show_roads: bool = True,
        show_rivers: bool = True,
        show_ridges: bool = True,
        show_esa_boundary: bool = True,
        buffer_m: float = 100.0
    ) -> io.BytesIO:
        """
        Generate a boundary map from GeoJSON geometry with OSM basemap.

        Args:
            geometry: GeoJSON dict with type and coordinates
            forest_name: Name of the forest for title
            orientation: 'auto' (recommended), 'portrait', or 'landscape'
                        'auto' determines orientation based on extent proportions
            output_path: Optional file path to save

        Returns:
            BytesIO buffer with PNG data
        """
        # Auto-detect orientation based on extent proportions
        if orientation == 'auto':
            geom_shape = shape(geometry)
            bounds = geom_shape.bounds  # (minx, miny, maxx, maxy)
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            aspect_ratio = width / height if height > 0 else 1.0

            # Determine orientation based on aspect ratio
            if 0.85 <= aspect_ratio <= 1.15:
                # Nearly square - use portrait (more paper-efficient)
                orientation = 'portrait'
            elif aspect_ratio > 1.15:
                # Wider than tall - use landscape
                orientation = 'landscape'
            else:
                # Taller than wide - use portrait
                orientation = 'portrait'

        # Create figure
        fig, ax = self.create_figure(
            orientation=orientation,
            title=f'{forest_name} - Boundary Map',
            add_border=True
        )

        # Convert GeoJSON to Shapely geometry (stay in WGS84)
        geom_shape = shape(geometry)

        # Extract coordinates from GeoJSON
        geom_type = geometry.get('type', '')
        coords = geometry.get('coordinates', [])

        # Handle different geometry types
        if geom_type == 'Polygon':
            polygons = [coords]
        elif geom_type == 'MultiPolygon':
            polygons = coords
        else:
            raise ValueError(f"Unsupported geometry type: {geom_type}")

        # Get WGS84 bounds
        bounds = geom_shape.bounds  # (minx, miny, maxx, maxy)
        min_x, min_y, max_x, max_y = bounds
        min_x_wgs, min_y_wgs, max_x_wgs, max_y_wgs = min_x, min_y, max_x, max_y

        # Plot boundary in WGS84 coordinates
        if geom_shape.geom_type == 'Polygon':
            polys_to_plot = [geom_shape]
        else:  # MultiPolygon
            polys_to_plot = list(geom_shape.geoms)

        for poly in polys_to_plot:
            # Exterior ring
            x, y = poly.exterior.xy
            ax.plot(x, y, color='#059669', linewidth=3, label='Forest Boundary', zorder=10)
            ax.fill(x, y, color='#34d399', alpha=0.4, zorder=9)

            # Interior rings (holes)
            for interior in poly.interiors:
                x, y = interior.xy
                ax.plot(x, y, 'r-', linewidth=1.5, zorder=10)
                ax.fill(x, y, color='white', alpha=0.8, zorder=9)

        # Set axis limits with padding (in WGS84)
        x_range = max_x - min_x
        y_range = max_y - min_y
        padding = max(x_range, y_range) * 0.15  # Increased padding for context

        ax.set_xlim(min_x - padding, max_x + padding)
        ax.set_ylim(min_y - padding, max_y + padding)

        # Add OpenStreetMap basemap with timeout (5 seconds)
        basemap_success = self.add_basemap_with_timeout(
            ax,
            crs='EPSG:4326',  # Our data is in WGS84
            timeout=5,  # 5 second timeout for fast failure
            alpha=0.7,  # Semi-transparent to see our boundary clearly
            zorder=1  # Behind our boundary
        )

        if not basemap_success:
            # Add a simple background color if basemap fails
            ax.set_facecolor('#f0f0f0')
            print("Basemap failed - using plain background")

        # Query and plot schools within buffer
        schools = []
        if show_schools and db_session is not None:
            schools = self.query_schools_within_buffer(db_session, geometry, buffer_m)
            if schools:
                school_lons = [s['lon'] for s in schools]
                school_lats = [s['lat'] for s in schools]

                # Plot school markers (red triangles)
                ax.scatter(
                    school_lons, school_lats,
                    marker='^',
                    s=100,
                    c='red',
                    edgecolors='darkred',
                    linewidths=1.5,
                    zorder=20,
                    label='Schools'
                )

                # Add school labels (offset slightly to avoid overlap with markers)
                for school in schools:
                    # Only label schools with names (not "School")
                    if school['name'] and school['name'] != 'School':
                        ax.annotate(
                            school['name'],
                            xy=(school['lon'], school['lat']),
                            xytext=(5, 5),  # Offset 5 points right and up
                            textcoords='offset points',
                            fontsize=7,
                            color='darkred',
                            fontweight='bold',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='darkred'),
                            zorder=21
                        )

        # Query and plot POI within buffer
        if show_poi and db_session is not None:
            poi_list = self.query_poi_within_buffer(db_session, geometry, buffer_m)
            if poi_list:
                poi_lons = [p['lon'] for p in poi_list]
                poi_lats = [p['lat'] for p in poi_list]

                # Plot POI markers (orange diamonds)
                ax.scatter(
                    poi_lons, poi_lats,
                    marker='D',
                    s=60,
                    c='orange',
                    edgecolors='darkorange',
                    linewidths=1,
                    zorder=19,
                    label='POI'
                )

                # Add POI labels (only for named POI)
                for poi in poi_list:
                    if poi['name'] and poi['name'] not in ['POI', 'poi']:
                        ax.annotate(
                            poi['name'],
                            xy=(poi['lon'], poi['lat']),
                            xytext=(5, -5),  # Offset differently from schools
                            textcoords='offset points',
                            fontsize=6,
                            color='darkorange',
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='darkorange'),
                            zorder=19
                        )

        # Query and plot roads within buffer (NO LABELS per user requirement)
        if show_roads and db_session is not None:
            roads = self.query_roads_within_buffer(db_session, geometry, buffer_m)
            if roads:
                for road in roads:
                    try:
                        from shapely import wkt
                        road_geom = wkt.loads(road['geom_wkt'])

                        # Different colors by highway type
                        if road['highway'] in ['primary', 'secondary', 'tertiary']:
                            color = '#FF6B6B'  # Red for major roads
                            width = 2
                        elif road['highway'] in ['residential', 'living_street']:
                            color = '#95A5A6'  # Gray for residential
                            width = 1
                        else:
                            color = '#BDC3C7'  # Light gray for paths
                            width = 0.8

                        if road_geom.geom_type == 'LineString':
                            x, y = road_geom.xy
                            ax.plot(x, y, color=color, linewidth=width, alpha=0.6, zorder=5)
                        elif road_geom.geom_type == 'MultiLineString':
                            for line in road_geom.geoms:
                                x, y = line.xy
                                ax.plot(x, y, color=color, linewidth=width, alpha=0.6, zorder=5)
                    except Exception as e:
                        continue  # Skip problematic geometries

                # Add roads to legend (single entry, no individual labels)
                ax.plot([], [], color='#FF6B6B', linewidth=2, alpha=0.6, label='Roads')

        # Query and plot rivers within buffer (WITH LABELS - user said "crucial")
        if show_rivers and db_session is not None:
            rivers = self.query_rivers_within_buffer(db_session, geometry, buffer_m)
            if rivers:
                for river in rivers:
                    try:
                        from shapely import wkt
                        river_geom = wkt.loads(river['geom_wkt'])

                        # Blue lines for rivers
                        if river_geom.geom_type == 'LineString':
                            x, y = river_geom.xy
                            ax.plot(x, y, color='#3498DB', linewidth=1.5, alpha=0.8, zorder=6)
                        elif river_geom.geom_type == 'MultiLineString':
                            for line in river_geom.geoms:
                                x, y = line.xy
                                ax.plot(x, y, color='#3498DB', linewidth=1.5, alpha=0.8, zorder=6)

                        # Label rivers (user requirement: "crucial")
                        if river['name'] and river['name'] != 'River':
                            ax.annotate(
                                river['name'],
                                xy=(river['center_lon'], river['center_lat']),
                                xytext=(0, -8),
                                textcoords='offset points',
                                fontsize=6,
                                color='#2874A6',
                                fontweight='bold',
                                style='italic',
                                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='#2874A6'),
                                zorder=18
                            )
                    except Exception as e:
                        continue

                # Add rivers to legend
                ax.plot([], [], color='#3498DB', linewidth=1.5, alpha=0.8, label='Rivers')

        # Query and plot ridges within buffer (WITH LABELS - user said "crucial")
        if show_ridges and db_session is not None:
            ridges = self.query_ridges_within_buffer(db_session, geometry, buffer_m)
            if ridges:
                for ridge in ridges:
                    try:
                        from shapely import wkt
                        ridge_geom = wkt.loads(ridge['geom_wkt'])

                        # Brown lines for ridges
                        if ridge_geom.geom_type == 'LineString':
                            x, y = ridge_geom.xy
                            ax.plot(x, y, color='#8B4513', linewidth=1.2, alpha=0.7, linestyle='--', zorder=6)
                        elif ridge_geom.geom_type == 'MultiLineString':
                            for line in ridge_geom.geoms:
                                x, y = line.xy
                                ax.plot(x, y, color='#8B4513', linewidth=1.2, alpha=0.7, linestyle='--', zorder=6)

                        # Label ridges (user requirement: "crucial")
                        if ridge['name'] and ridge['name'] != 'Ridge':
                            ax.annotate(
                                ridge['name'],
                                xy=(ridge['center_lon'], ridge['center_lat']),
                                xytext=(0, 8),
                                textcoords='offset points',
                                fontsize=6,
                                color='#654321',
                                fontweight='bold',
                                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7, edgecolor='#654321'),
                                zorder=18
                            )
                    except Exception as e:
                        continue

                # Add ridges to legend
                ax.plot([], [], color='#8B4513', linewidth=1.2, alpha=0.7, linestyle='--', label='Ridges')

        # Query and plot ESA forest boundary (reference boundary)
        if show_esa_boundary and db_session is not None:
            esa_boundaries = self.query_esa_boundary_intersecting(db_session, geometry)
            if esa_boundaries:
                for esa_bound in esa_boundaries:
                    try:
                        from shapely import wkt
                        esa_geom = wkt.loads(esa_bound['geom_wkt'])

                        # Dashed purple line for ESA boundary
                        if esa_geom.geom_type == 'LineString':
                            x, y = esa_geom.xy
                            ax.plot(x, y, color='#9B59B6', linewidth=2, alpha=0.7, linestyle=':', zorder=7)
                        elif esa_geom.geom_type == 'MultiLineString':
                            for line in esa_geom.geoms:
                                x, y = line.xy
                                ax.plot(x, y, color='#9B59B6', linewidth=2, alpha=0.7, linestyle=':', zorder=7)
                    except Exception as e:
                        continue

                # Add ESA boundary to legend
                ax.plot([], [], color='#9B59B6', linewidth=2, alpha=0.7, linestyle=':', label='ESA Boundary')

        # Add grid (on top of basemap, white for visibility)
        ax.grid(True, alpha=0.4, linestyle='--', linewidth=0.5, zorder=8, color='white')

        # Equal aspect ratio
        ax.set_aspect('equal', adjustable='box')

        # Format axis tick labels
        ax.tick_params(axis='both', labelsize=8)

        # Add north arrow (outside map area, top-right)
        self.add_north_arrow(fig, ax)

        # Calculate approximate scale (1 degree ≈ 111 km at equator)
        # Use WGS84 coordinates for scale calculation
        x_range_wgs = max_x_wgs - min_x_wgs
        y_range_wgs = max_y_wgs - min_y_wgs
        avg_lat = (min_y_wgs + max_y_wgs) / 2
        km_per_degree = 111.0 * np.cos(np.radians(avg_lat))
        scale_km = round(x_range_wgs * km_per_degree / 5, 1)  # 1/5 of width
        self.add_scale_bar(fig, ax, length_km=scale_km if scale_km > 0 else 1.0)

        # Add metadata (bottom center, outside map)
        fig.text(
            0.5, 0.03,
            f'A5 {orientation.capitalize()} | 300 DPI | WGS84 (EPSG:4326)',
            ha='center',
            va='bottom',
            fontsize=6,
            style='italic',
            color='gray'
        )

        # Remove duplicate legend entries and place outside map (bottom-right)
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        # Use figure.legend to place outside axes
        fig.legend(
            by_label.values(),
            by_label.keys(),
            loc='lower right',
            bbox_to_anchor=(0.90, 0.12),
            fontsize=8,
            frameon=True,
            fancybox=True,
            shadow=True
        )

        # Save to file if path provided
        if output_path:
            self.save_to_file(fig, output_path)

        # Save to buffer
        buffer = self.save_to_buffer(fig)

        # Close figure
        self.close_figure(fig)

        return buffer

    def generate_slope_map(
        self,
        geometry: Dict[str, Any],
        db_session,
        forest_name: str = 'Forest Boundary',
        orientation: str = 'auto',
        output_path: Optional[str] = None
    ) -> io.BytesIO:
        """
        Generate a slope map from raster data with color-coded slope classes.

        Slope Classes:
        - 0-5°: Flat (green)
        - 5-15°: Gentle (yellow-green)
        - 15-30°: Moderate (yellow)
        - 30-45°: Steep (orange)
        - >45°: Very Steep (red)

        Args:
            geometry: GeoJSON dict with type and coordinates
            db_session: SQLAlchemy database session for raster queries
            forest_name: Name of the forest for title
            orientation: 'auto', 'portrait', or 'landscape'
            output_path: Optional file path to save

        Returns:
            BytesIO buffer with PNG data
        """
        # Auto-detect orientation based on extent proportions
        if orientation == 'auto':
            geom_shape = shape(geometry)
            bounds = geom_shape.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            aspect_ratio = width / height if height > 0 else 1.0

            if 0.85 <= aspect_ratio <= 1.15:
                orientation = 'portrait'
            elif aspect_ratio > 1.15:
                orientation = 'landscape'
            else:
                orientation = 'portrait'

        # Create figure
        fig, ax = self.create_figure(
            orientation=orientation,
            title=f'{forest_name} - Slope Map',
            add_border=True
        )

        # Convert geometry to WKT and Shapely
        geom_shape = shape(geometry)
        geom_wkt = geom_shape.wkt
        bounds = geom_shape.bounds
        min_x, min_y, max_x, max_y = bounds

        # Query slope raster data within boundary
        # Uses pre-computed slope raster for speed and consistency with Analysis tab
        try:
            query = text("""
                WITH slope_pixels AS (
                    SELECT
                        (ST_PixelAsPolygons(ST_Clip(rast, 1, ST_GeomFromText(:geom_wkt, 4326)))).val as slope_degrees,
                        (ST_PixelAsPolygons(ST_Clip(rast, 1, ST_GeomFromText(:geom_wkt, 4326)))).geom as geom
                    FROM rasters.slope
                    WHERE ST_Intersects(rast, ST_GeomFromText(:geom_wkt, 4326))
                )
                SELECT
                    slope_degrees,
                    ST_AsText(geom) as geom_wkt
                FROM slope_pixels
                WHERE slope_degrees IS NOT NULL AND slope_degrees >= 0
            """)

            result = db_session.execute(query, {"geom_wkt": geom_wkt})

            # Collect pixels and classify
            pixels = []
            for row in result:
                slope_val = float(row[0])
                pixel_geom_wkt = row[1]

                # Classify slope
                if slope_val < 5:
                    slope_class = 'Flat (0-5°)'
                    color = '#2ECC71'  # Green
                elif slope_val < 15:
                    slope_class = 'Gentle (5-15°)'
                    color = '#F1C40F'  # Yellow
                elif slope_val < 30:
                    slope_class = 'Moderate (15-30°)'
                    color = '#E67E22'  # Orange
                elif slope_val < 45:
                    slope_class = 'Steep (30-45°)'
                    color = '#E74C3C'  # Red-Orange
                else:
                    slope_class = 'Very Steep (>45°)'
                    color = '#C0392B'  # Dark Red

                pixels.append({
                    'slope': slope_val,
                    'class': slope_class,
                    'color': color,
                    'geom_wkt': pixel_geom_wkt
                })

            print(f"Loaded {len(pixels)} slope pixels")

            # Plot pixels
            if pixels:
                for pixel in pixels:
                    try:
                        pixel_geom = wkt.loads(pixel['geom_wkt'])
                        if pixel_geom.geom_type == 'Polygon':
                            x, y = pixel_geom.exterior.xy
                            ax.fill(x, y, color=pixel['color'], edgecolor='none', alpha=0.8, zorder=5)
                    except:
                        continue

        except Exception as e:
            print(f"Warning: Could not load slope raster: {e}")
            # Draw empty map with boundary
            pass

        # Plot forest boundary outline on top
        if geom_shape.geom_type == 'Polygon':
            polys_to_plot = [geom_shape]
        else:
            polys_to_plot = list(geom_shape.geoms)

        for poly in polys_to_plot:
            x, y = poly.exterior.xy
            ax.plot(x, y, color='black', linewidth=2, label='Forest Boundary', zorder=10)

        # Set axis limits with padding
        x_range = max_x - min_x
        y_range = max_y - min_y
        padding = max(x_range, y_range) * 0.05
        ax.set_xlim(min_x - padding, max_x + padding)
        ax.set_ylim(min_y - padding, max_y + padding)

        # Add grid
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, zorder=8)

        # Equal aspect ratio
        ax.set_aspect('equal', adjustable='box')

        # Format axis tick labels
        ax.tick_params(axis='both', labelsize=8)

        # Add north arrow
        self.add_north_arrow(fig, ax)

        # Add scale bar
        x_range_wgs = max_x - min_x
        avg_lat = (min_y + max_y) / 2
        km_per_degree = 111.0 * np.cos(np.radians(avg_lat))
        scale_km = round(x_range_wgs * km_per_degree / 5, 1)
        self.add_scale_bar(fig, ax, length_km=scale_km if scale_km > 0 else 1.0)

        # Add metadata
        fig.text(
            0.5, 0.03,
            f'A5 {orientation.capitalize()} | 300 DPI | WGS84 (EPSG:4326)',
            ha='center',
            va='bottom',
            fontsize=6,
            style='italic',
            color='gray'
        )

        # Add slope class legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#2ECC71', edgecolor='black', label='Flat (0-5°)'),
            Patch(facecolor='#F1C40F', edgecolor='black', label='Gentle (5-15°)'),
            Patch(facecolor='#E67E22', edgecolor='black', label='Moderate (15-30°)'),
            Patch(facecolor='#E74C3C', edgecolor='black', label='Steep (30-45°)'),
            Patch(facecolor='#C0392B', edgecolor='black', label='Very Steep (>45°)'),
        ]
        fig.legend(
            handles=legend_elements,
            loc='lower right',
            bbox_to_anchor=(0.90, 0.12),
            fontsize=7,
            frameon=True,
            fancybox=True,
            shadow=True,
            title='Slope Classes'
        )

        # Save to file if path provided
        if output_path:
            self.save_to_file(fig, output_path)

        # Save to buffer
        buffer = self.save_to_buffer(fig)

        # Close figure
        self.close_figure(fig)

        return buffer

    def generate_landcover_map(
        self,
        geometry: Dict[str, Any],
        db_session,
        forest_name: str = 'Forest Boundary',
        orientation: str = 'auto',
        output_path: Optional[str] = None
    ) -> io.BytesIO:
        """
        Generate a land cover map from ESA WorldCover raster data.

        Land Cover Classes (ESA WorldCover v100):
        - 10: Tree cover (dark green)
        - 20: Shrubland (olive)
        - 30: Grassland (light green)
        - 40: Cropland (yellow)
        - 50: Built-up (red)
        - 60: Bare/sparse vegetation (tan)
        - 70: Snow and ice (white)
        - 80: Permanent water bodies (blue)
        - 90: Herbaceous wetland (cyan)
        - 100: Mangroves (teal)

        Args:
            geometry: GeoJSON dict with type and coordinates
            db_session: SQLAlchemy database session for raster queries
            forest_name: Name of the forest for title
            orientation: 'auto', 'portrait', or 'landscape'
            output_path: Optional file path to save

        Returns:
            BytesIO buffer with PNG data
        """
        # Auto-detect orientation
        if orientation == 'auto':
            geom_shape = shape(geometry)
            bounds = geom_shape.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            aspect_ratio = width / height if height > 0 else 1.0

            if 0.85 <= aspect_ratio <= 1.15:
                orientation = 'portrait'
            elif aspect_ratio > 1.15:
                orientation = 'landscape'
            else:
                orientation = 'portrait'

        # Create figure
        fig, ax = self.create_figure(
            orientation=orientation,
            title=f'{forest_name} - Land Cover Map',
            add_border=True
        )

        # Convert geometry
        geom_shape = shape(geometry)
        geom_wkt = geom_shape.wkt
        bounds = geom_shape.bounds
        min_x, min_y, max_x, max_y = bounds

        # Define ESA WorldCover classification
        landcover_classes = {
            10: {'name': 'Tree cover', 'color': '#006400'},  # Dark green
            20: {'name': 'Shrubland', 'color': '#FFBB22'},   # Olive/gold
            30: {'name': 'Grassland', 'color': '#FFFF4C'},   # Light yellow
            40: {'name': 'Cropland', 'color': '#F096FF'},    # Pink
            50: {'name': 'Built-up', 'color': '#FA0000'},    # Red
            60: {'name': 'Bare/sparse vegetation', 'color': '#B4B4B4'},  # Gray
            70: {'name': 'Snow and ice', 'color': '#F0F0F0'},  # White
            80: {'name': 'Water', 'color': '#0064C8'},       # Blue
            90: {'name': 'Herbaceous wetland', 'color': '#0096A0'},  # Cyan
            100: {'name': 'Mangroves', 'color': '#00CF75'},  # Teal
        }

        # Query land cover raster data
        try:
            query = text("""
                WITH landcover_pixels AS (
                    SELECT
                        (ST_PixelAsPolygons(ST_Clip(rast, 1, ST_GeomFromText(:geom_wkt, 4326)))).val as lc_class,
                        (ST_PixelAsPolygons(ST_Clip(rast, 1, ST_GeomFromText(:geom_wkt, 4326)))).geom as geom
                    FROM rasters.esa_world_cover
                    WHERE ST_Intersects(rast, ST_GeomFromText(:geom_wkt, 4326))
                )
                SELECT
                    lc_class,
                    ST_AsText(geom) as geom_wkt
                FROM landcover_pixels
                WHERE lc_class IS NOT NULL AND lc_class > 0
            """)

            result = db_session.execute(query, {"geom_wkt": geom_wkt})

            # Collect pixels and classify
            pixels = []
            class_counts = {}

            for row in result:
                lc_value = int(row[0])
                pixel_geom_wkt = row[1]

                if lc_value in landcover_classes:
                    lc_info = landcover_classes[lc_value]
                    pixels.append({
                        'class': lc_value,
                        'name': lc_info['name'],
                        'color': lc_info['color'],
                        'geom_wkt': pixel_geom_wkt
                    })
                    class_counts[lc_value] = class_counts.get(lc_value, 0) + 1

            print(f"Loaded {len(pixels)} land cover pixels")
            print(f"Classes found: {list(class_counts.keys())}")

            # Plot pixels
            if pixels:
                for pixel in pixels:
                    try:
                        pixel_geom = wkt.loads(pixel['geom_wkt'])
                        if pixel_geom.geom_type == 'Polygon':
                            x, y = pixel_geom.exterior.xy
                            ax.fill(x, y, color=pixel['color'], edgecolor='none', alpha=0.9, zorder=5)
                    except:
                        continue

        except Exception as e:
            print(f"Warning: Could not load land cover raster: {e}")
            import traceback
            traceback.print_exc()

        # Plot forest boundary outline
        if geom_shape.geom_type == 'Polygon':
            polys_to_plot = [geom_shape]
        else:
            polys_to_plot = list(geom_shape.geoms)

        for poly in polys_to_plot:
            x, y = poly.exterior.xy
            ax.plot(x, y, color='black', linewidth=2, label='Forest Boundary', zorder=10)

        # Set axis limits
        x_range = max_x - min_x
        y_range = max_y - min_y
        padding = max(x_range, y_range) * 0.05
        ax.set_xlim(min_x - padding, max_x + padding)
        ax.set_ylim(min_y - padding, max_y + padding)

        # Add grid
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, zorder=8)
        ax.set_aspect('equal', adjustable='box')
        ax.tick_params(axis='both', labelsize=8)

        # Add north arrow
        self.add_north_arrow(fig, ax)

        # Add scale bar
        x_range_wgs = max_x - min_x
        avg_lat = (min_y + max_y) / 2
        km_per_degree = 111.0 * np.cos(np.radians(avg_lat))
        scale_km = round(x_range_wgs * km_per_degree / 5, 1)
        self.add_scale_bar(fig, ax, length_km=scale_km if scale_km > 0 else 1.0)

        # Add metadata
        fig.text(
            0.5, 0.03,
            f'A5 {orientation.capitalize()} | 300 DPI | ESA WorldCover v100',
            ha='center',
            va='bottom',
            fontsize=6,
            style='italic',
            color='gray'
        )

        # Add land cover legend (only classes present in data)
        from matplotlib.patches import Patch
        legend_elements = []
        if pixels:
            # Get unique classes present
            present_classes = sorted(set(p['class'] for p in pixels))
            for lc_class in present_classes:
                if lc_class in landcover_classes:
                    info = landcover_classes[lc_class]
                    legend_elements.append(
                        Patch(facecolor=info['color'], edgecolor='black', label=info['name'])
                    )

        if legend_elements:
            fig.legend(
                handles=legend_elements,
                loc='lower right',
                bbox_to_anchor=(0.90, 0.12),
                fontsize=7,
                frameon=True,
                fancybox=True,
                shadow=True,
                title='Land Cover'
            )

        # Save to file
        if output_path:
            self.save_to_file(fig, output_path)

        # Save to buffer
        buffer = self.save_to_buffer(fig)

        # Close figure
        self.close_figure(fig)

        return buffer

    def generate_aspect_map(
        self,
        geometry: Dict[str, Any],
        db_session,
        forest_name: str = 'Forest Boundary',
        orientation: str = 'auto',
        output_path: Optional[str] = None
    ) -> io.BytesIO:
        """
        Generate an aspect map from raster data with pre-classified aspect directions.

        Aspect Classes (temperature-based colors - N=cold, S=warm):
        - 0: Flat (slope < 2°) - Gray (neutral)
        - 1: N (337.5° - 22.5°) - Dark Blue (coldest - least sunlight)
        - 2: NE (22.5° - 67.5°) - Blue (cool - morning sun)
        - 3: E (67.5° - 112.5°) - Cyan (cool-moderate - morning sun)
        - 4: SE (112.5° - 157.5°) - Yellow (warm-moderate - morning-midday sun)
        - 5: S (157.5° - 202.5°) - Red (warmest - maximum sunlight)
        - 6: SW (202.5° - 247.5°) - Orange (warm - afternoon sun)
        - 7: W (247.5° - 292.5°) - Light Orange (warm-moderate - afternoon sun)
        - 8: NW (292.5° - 337.5°) - Purple (cool - evening)

        Args:
            geometry: GeoJSON dict with type and coordinates
            db_session: SQLAlchemy database session for raster queries
            forest_name: Name of the forest for title
            orientation: 'auto', 'portrait', or 'landscape'
            output_path: Optional file path to save

        Returns:
            BytesIO buffer with PNG data
        """
        # Auto-detect orientation based on extent proportions
        if orientation == 'auto':
            geom_shape = shape(geometry)
            bounds = geom_shape.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            aspect_ratio = width / height if height > 0 else 1.0

            if 0.85 <= aspect_ratio <= 1.15:
                orientation = 'portrait'
            elif aspect_ratio > 1.15:
                orientation = 'landscape'
            else:
                orientation = 'portrait'

        # Create figure
        fig, ax = self.create_figure(
            orientation=orientation,
            title=f'{forest_name} - Aspect Map',
            add_border=True
        )

        # Convert geometry to WKT and Shapely
        geom_shape = shape(geometry)
        geom_wkt = geom_shape.wkt
        bounds = geom_shape.bounds
        min_x, min_y, max_x, max_y = bounds

        # Define aspect classes with colors (temperature-based: N=cold/blue, S=warm/red)
        aspect_classes = {
            0: {'name': 'Flat', 'color': '#CCCCCC'},        # Gray (neutral)
            1: {'name': 'N', 'color': '#1A5490'},           # Dark Blue (coldest - least sun)
            2: {'name': 'NE', 'color': '#3498DB'},          # Blue (cool - morning sun)
            3: {'name': 'E', 'color': '#1ABC9C'},           # Cyan (cool-moderate - morning sun)
            4: {'name': 'SE', 'color': '#F1C40F'},          # Yellow (warm-moderate - morning-midday sun)
            5: {'name': 'S', 'color': '#E74C3C'},           # Red (warmest - most sun)
            6: {'name': 'SW', 'color': '#E67E22'},          # Orange (warm - afternoon sun)
            7: {'name': 'W', 'color': '#F39C12'},           # Light Orange (warm-moderate - afternoon sun)
            8: {'name': 'NW', 'color': '#9B59B6'},          # Purple (cool - evening)
        }

        # Query aspect raster data within boundary
        # The aspect raster is already classified (0-8), just display it
        try:
            query = text("""
                WITH aspect_pixels AS (
                    SELECT
                        (ST_PixelAsPolygons(ST_Clip(rast, 1, ST_GeomFromText(:geom_wkt, 4326)))).val as aspect_class,
                        (ST_PixelAsPolygons(ST_Clip(rast, 1, ST_GeomFromText(:geom_wkt, 4326)))).geom as geom
                    FROM rasters.aspect
                    WHERE ST_Intersects(rast, ST_GeomFromText(:geom_wkt, 4326))
                )
                SELECT
                    aspect_class,
                    ST_AsText(geom) as geom_wkt
                FROM aspect_pixels
                WHERE aspect_class IS NOT NULL AND aspect_class >= 0 AND aspect_class <= 8
            """)

            result = db_session.execute(query, {"geom_wkt": geom_wkt})

            # Collect pixels
            pixels = []
            class_counts = {}

            for row in result:
                aspect_val = int(row[0])
                pixel_geom_wkt = row[1]

                if aspect_val in aspect_classes:
                    aspect_info = aspect_classes[aspect_val]
                    pixels.append({
                        'class': aspect_val,
                        'name': aspect_info['name'],
                        'color': aspect_info['color'],
                        'geom_wkt': pixel_geom_wkt
                    })
                    class_counts[aspect_val] = class_counts.get(aspect_val, 0) + 1

            print(f"Loaded {len(pixels)} aspect pixels")
            print(f"Classes found: {list(class_counts.keys())}")

            # Plot pixels
            if pixels:
                for pixel in pixels:
                    try:
                        pixel_geom = wkt.loads(pixel['geom_wkt'])
                        if pixel_geom.geom_type == 'Polygon':
                            x, y = pixel_geom.exterior.xy
                            ax.fill(x, y, color=pixel['color'], edgecolor='none', alpha=0.85, zorder=5)
                    except:
                        continue

        except Exception as e:
            print(f"Warning: Could not load aspect raster: {e}")
            import traceback
            traceback.print_exc()

        # Plot forest boundary outline on top
        if geom_shape.geom_type == 'Polygon':
            polys_to_plot = [geom_shape]
        else:
            polys_to_plot = list(geom_shape.geoms)

        for poly in polys_to_plot:
            x, y = poly.exterior.xy
            ax.plot(x, y, color='black', linewidth=2, label='Forest Boundary', zorder=10)

        # Set axis limits with padding
        x_range = max_x - min_x
        y_range = max_y - min_y
        padding = max(x_range, y_range) * 0.05
        ax.set_xlim(min_x - padding, max_x + padding)
        ax.set_ylim(min_y - padding, max_y + padding)

        # Add grid
        ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, zorder=8)

        # Equal aspect ratio
        ax.set_aspect('equal', adjustable='box')

        # Format axis tick labels
        ax.tick_params(axis='both', labelsize=8)

        # Add north arrow
        self.add_north_arrow(fig, ax)

        # Add scale bar
        x_range_wgs = max_x - min_x
        avg_lat = (min_y + max_y) / 2
        km_per_degree = 111.0 * np.cos(np.radians(avg_lat))
        scale_km = round(x_range_wgs * km_per_degree / 5, 1)
        self.add_scale_bar(fig, ax, length_km=scale_km if scale_km > 0 else 1.0)

        # Add metadata
        fig.text(
            0.5, 0.03,
            f'A5 {orientation.capitalize()} | 300 DPI | WGS84 (EPSG:4326)',
            ha='center',
            va='bottom',
            fontsize=6,
            style='italic',
            color='gray'
        )

        # Add aspect legend (only classes present in data)
        from matplotlib.patches import Patch
        legend_elements = []
        if pixels:
            # Get unique classes present
            present_classes = sorted(set(p['class'] for p in pixels))
            for aspect_class in present_classes:
                if aspect_class in aspect_classes:
                    info = aspect_classes[aspect_class]
                    legend_elements.append(
                        Patch(facecolor=info['color'], edgecolor='black', label=info['name'])
                    )

        if legend_elements:
            fig.legend(
                handles=legend_elements,
                loc='lower right',
                bbox_to_anchor=(0.90, 0.12),
                fontsize=7,
                frameon=True,
                fancybox=True,
                shadow=True,
                title='Aspect Classes'
            )

        # Save to file if path provided
        if output_path:
            self.save_to_file(fig, output_path)

        # Save to buffer
        buffer = self.save_to_buffer(fig)

        # Close figure
        self.close_figure(fig)

        return buffer

    def generate_test_map(
        self,
        orientation: str = 'portrait',
        output_path: Optional[str] = None
    ) -> io.BytesIO:
        """
        Generate a test map to verify the system is working.

        Args:
            orientation: 'portrait' or 'landscape'
            output_path: Optional file path to save (if None, returns buffer)

        Returns:
            BytesIO buffer with PNG data
        """
        # Create figure
        fig, ax = self.create_figure(
            orientation=orientation,
            title='Test Map - Forest Management System',
            add_border=True
        )

        # Draw a simple test pattern
        x = np.linspace(0, 2*np.pi, 100)
        y = np.sin(x)

        ax.plot(x, y, 'g-', linewidth=2, label='Test Pattern')
        ax.fill_between(x, 0, y, alpha=0.3, color='green')

        # Remove axis labels
        ax.tick_params(axis='both', labelsize=8)
        ax.grid(True, alpha=0.3)

        # Add north arrow and scale bar (outside map area)
        self.add_north_arrow(fig, ax)
        self.add_scale_bar(fig, ax, length_km=1.0)

        # Add legend outside map area
        fig.legend(
            loc='lower right',
            bbox_to_anchor=(0.90, 0.12),
            fontsize=8,
            frameon=True,
            fancybox=True,
            shadow=True
        )

        # Add metadata text
        fig.text(
            0.5, 0.03,
            f'A5 {orientation.capitalize()} | {self.dpi} DPI | Generated by MapGenerator',
            ha='center',
            va='bottom',
            fontsize=6,
            style='italic',
            color='gray'
        )

        # Save to file if path provided
        if output_path:
            self.save_to_file(fig, output_path)

        # Save to buffer
        buffer = self.save_to_buffer(fig)

        # Close figure
        self.close_figure(fig)

        return buffer


# Singleton instance
_map_generator: Optional[MapGenerator] = None


def get_map_generator() -> MapGenerator:
    """
    Get the singleton MapGenerator instance.

    Returns:
        MapGenerator instance
    """
    global _map_generator
    if _map_generator is None:
        _map_generator = MapGenerator()
    return _map_generator


# Convenience functions
def generate_test_map(
    orientation: str = 'portrait',
    output_path: Optional[str] = None
) -> io.BytesIO:
    """
    Generate a test map using the default generator.

    Args:
        orientation: 'portrait' or 'landscape'
        output_path: Optional file path to save

    Returns:
        BytesIO buffer with PNG data
    """
    generator = get_map_generator()
    return generator.generate_test_map(orientation, output_path)
