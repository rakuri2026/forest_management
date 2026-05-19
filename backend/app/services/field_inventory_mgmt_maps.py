"""
Management Plan Map Generator
Generates A5 map PNGs with OSM basemap + boundary polygon / raster overlay for DOCX embedding.
Uses matplotlib + contextily for basemap, tile_service for raster layers.
"""
import io
import math
import logging
from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager as fm
import numpy as np
from PIL import Image as PILImage

from .tile_service import get_tile_service

logger = logging.getLogger(__name__)

# ── Devanagari font fallback ──
_DEVANAGARI_FONT_PATHS = [
    "C:/Windows/Fonts/Nirmala.ttc",
    "C:/Windows/Fonts/mangal.ttf",
    "C:/Windows/Fonts/ARIALUNI.TTF",
    "C:/Windows/Fonts/arial.ttf",
]
_DEVANAGARI_FONT = None
_DEVANAGARI_FONT_NAME = None
for _fp in _DEVANAGARI_FONT_PATHS:
    try:
        _prop = fm.FontProperties(fname=_fp)
        if _prop.get_name():
            fm.fontManager.addfont(_fp)
            _DEVANAGARI_FONT = _fp
            _DEVANAGARI_FONT_NAME = _prop.get_name()
            break
    except Exception:
        continue
if _DEVANAGARI_FONT_NAME:
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = [_DEVANAGARI_FONT_NAME] + plt.rcParams.get('font.sans-serif', [])
else:
    logger.warning("No Devanagari font found - Nepali labels may not render")

def _get_dev_fontprop(size: int = 14):
    """Get FontProperties for Devanagari text."""
    if _DEVANAGARI_FONT:
        return fm.FontProperties(fname=_DEVANAGARI_FONT, size=size)
    return fm.FontProperties(size=size)

MAP_FIGURE_MM = 150
MAP_FIGURE_INCHES = (MAP_FIGURE_MM / 25.4, MAP_FIGURE_MM / 25.4)
TILE_SIZE = 256

LAYER_INFO = {
    "boundary": {"label": "सिमाना नक्सा", "en_label": "Boundary Map"},
    "forest_type": {"label": "वन प्रकार", "en_label": "Forest Type"},
    "forest_health": {"label": "वन स्वास्थ्य", "en_label": "Forest Health"},
    "slope": {"label": "भिरालो", "en_label": "Slope"},
    "biomass": {"label": "बायोमास", "en_label": "Biomass (AGB)"},
    "landcover": {"label": "भू-आवरण", "en_label": "Land Cover"},
    "soil_texture": {"label": "माटो बनावट", "en_label": "Soil Texture"},
    "dem": {"label": "उचाइ", "en_label": "Elevation (DEM)"},
}


def _get_forest_bbox(db: Session, calculation_id: UUID) -> Optional[Tuple[float, float, float, float]]:
    from ..models.calculation import Calculation
    from geoalchemy2.shape import to_shape
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.boundary_geom:
        return None
    geom = to_shape(calc.boundary_geom)
    return geom.bounds


def _get_forest_geometry(db: Session, calculation_id: UUID):
    from ..models.calculation import Calculation
    from geoalchemy2.shape import to_shape
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.boundary_geom:
        return None
    return to_shape(calc.boundary_geom)


def _add_basemap(ax, crs='EPSG:4326', alpha=0.6):
    """Add OpenStreetMap basemap. Falls back to gray background on failure."""
    import contextily as cx
    try:
        cx.add_basemap(ax, crs=crs, source=cx.providers.OpenStreetMap.Mapnik, alpha=alpha, zorder=1)
        return True
    except Exception as e:
        logger.warning(f"Basemap unavailable: {e}")
        ax.set_facecolor('#f0f0f0')
        return False


def generate_map_image(
    db: Session,
    calculation_id: UUID,
    layer_name: str,
    dpi: int = 100,
    forest_name: str = "",
) -> io.BytesIO:
    """
    Generate 150×150mm square map PNG with OSM basemap + boundary/raster overlay.

    Args:
        db: Database session
        calculation_id: Forest calculation UUID
        layer_name: Layer identifier (boundary, forest_type, slope, etc.)
        dpi: Output DPI
        forest_name: Forest name for title

    Returns:
        BytesIO containing PNG image
    """
    bbox = _get_forest_bbox(db, calculation_id)
    if not bbox:
        buf = io.BytesIO()
        px = int(MAP_FIGURE_INCHES[0] * dpi)
        PILImage.new("RGB", (px, px), "white").save(buf, format="PNG")
        buf.seek(0)
        return buf

    min_lon, min_lat, max_lon, max_lat = bbox
    lon_width = max_lon - min_lon
    lat_height = max_lat - min_lat

    fig, ax = plt.subplots(figsize=MAP_FIGURE_INCHES, dpi=dpi)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.05)

    boundary_geom = _get_forest_geometry(db, calculation_id)

    # Set axis limits for correct basemap extent
    pad_x = lon_width * 0.05
    pad_y = lat_height * 0.05
    ax.set_xlim(min_lon - pad_x, max_lon + pad_x)
    ax.set_ylim(min_lat - pad_y, max_lat + pad_y)

    # OSM basemap (uses the axis limits from above)
    _add_basemap(ax, crs='EPSG:4326')

    if layer_name == "boundary":
        if boundary_geom is not None:
            from shapely.geometry import Polygon, MultiPolygon
            polys = [boundary_geom] if isinstance(boundary_geom, Polygon) else list(boundary_geom.geoms)
            for poly in polys:
                xs, ys = poly.exterior.xy
                ax.fill(xs, ys, color='#2e7d32', alpha=0.30, edgecolor='#1b5e20', linewidth=2, zorder=3)
                for ring in poly.interiors:
                    rx, ry = ring.xy
                    ax.fill(rx, ry, color='white', alpha=0.85, edgecolor='#888888', linewidth=1, zorder=4)
    else:
        try:
            tile_service = get_tile_service(db)
            calc_id_str = str(calculation_id)
            zoom = _calc_zoom(lon_width, MAP_FIGURE_INCHES[0], dpi=dpi)

            center_lat = (min_lat + max_lat) / 2.0
            x_min, _ = _latlon_to_tile(center_lat, min_lon, zoom)
            x_max, _ = _latlon_to_tile(center_lat, max_lon, zoom)
            _, y_min_t = _latlon_to_tile(max_lat, min_lon, zoom)
            _, y_max_t = _latlon_to_tile(min_lat, min_lon, zoom)

            x_start = min(x_min, x_max)
            x_end = max(x_min, x_max)
            y_start = min(y_min_t, y_max_t)
            y_end = max(y_min_t, y_max_t)

            n = 2.0 ** zoom
            comp_min_lon = x_start / n * 360.0 - 180.0
            comp_max_lon = (x_end + 1) / n * 360.0 - 180.0
            comp_max_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y_start / n))))
            comp_min_lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y_end + 1) / n))))

            rows = []
            for ty in range(y_start, y_end + 1):
                row_tiles = []
                for tx in range(x_start, x_end + 1):
                    try:
                        tb = tile_service.get_tile(calculation_id=calc_id_str, layer_name=layer_name,
                                                    z=zoom, x=tx, y=ty, alpha=255)
                        row_tiles.append(np.array(PILImage.open(io.BytesIO(tb)).convert("RGBA")))
                    except Exception:
                        row_tiles.append(np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8))
                rows.append(np.hstack(row_tiles))
            raster_img = np.vstack(rows) if len(rows) > 1 else rows[0]

            extent = [comp_min_lon, comp_max_lon, comp_min_lat, comp_max_lat]
            ax.imshow(raster_img, extent=extent, alpha=0.80, zorder=2)

            if boundary_geom is not None:
                from shapely.geometry import Polygon, MultiPolygon
                polys = [boundary_geom] if isinstance(boundary_geom, Polygon) else list(boundary_geom.geoms)
                for poly in polys:
                    xs, ys = poly.exterior.xy
                    ax.plot(xs, ys, color='#1b5e20', linewidth=2, zorder=5)
        except Exception as e:
            logger.error(f"Raster overlay failed for {layer_name}: {e}")

    _add_grid_5x5(ax, min_lon, max_lon, min_lat, max_lat)
    ax.axis('off')

    # Title
    info = LAYER_INFO.get(layer_name, {})
    title = f"{forest_name} — {info.get('label', layer_name)}" if forest_name else info.get('label', layer_name)
    ax.set_title(title, fontsize=18, fontweight='bold', pad=12, color='#1b5e20',
                 fontproperties=_get_dev_fontprop(18))

    # North arrow
    na_x = 0.93
    na_y = 0.88
    ax.annotate('N', xy=(na_x, na_y), xytext=(na_x, na_y - 0.05),
                xycoords='axes fraction', fontsize=14, fontweight='bold', ha='center', va='center',
                arrowprops=dict(arrowstyle='->', color='#222222', lw=3),
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#cccccc', alpha=0.85))

    # Scale bar (approximate)
    _add_scale_bar(ax, center_lat=(min_lat + max_lat) / 2, min_lon=min_lon, max_lon=max_lon, fig_width=MAP_FIGURE_INCHES[0])

    # Legend for raster layers
    if layer_name != "boundary":
        _add_legend(ax, layer_name)

    # Footer
    fig.text(0.02, 0.02, f"{dpi} DPI | {info.get('en_label', layer_name)}", fontsize=8, color='#888888')

    buf = io.BytesIO()
    fig.savefig(buf, format='PNG', dpi=dpi, facecolor='white')
    plt.close(fig)
    buf.seek(0)
    return buf


def _latlon_to_tile(lat: float, lon: float, z: int) -> Tuple[int, int]:
    n = 2.0 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n)
    return (x, y)


def _calc_zoom(lon_width_deg: float, target_inches: float, dpi: int = 200) -> int:
    target_pixels = target_inches * dpi
    target_pixels_80 = target_pixels * 0.80
    for z in range(5, 19):
        tw = 360.0 / (2.0 ** z)
        pw = TILE_SIZE * (lon_width_deg / tw)
        if pw >= target_pixels_80:
            return z
    return 15


def _add_grid_5x5(ax, min_lon: float, max_lon: float, min_lat: float, max_lat: float):
    """5×5 thin grid lines with coordinate labels at 5 positions."""
    lon_step = (max_lon - min_lon) / 5
    lat_step = (max_lat - min_lat) / 5
    lon_vals = [min_lon + i * lon_step for i in range(6)]
    lat_vals = [min_lat + i * lat_step for i in range(6)]

    for lon in lon_vals:
        ax.axvline(lon, color='#888888', linewidth=0.3, linestyle='-', alpha=0.5, zorder=0)
    for lat in lat_vals:
        ax.axhline(lat, color='#888888', linewidth=0.3, linestyle='-', alpha=0.5, zorder=0)

    kw = dict(fontsize=7, color='#444444', alpha=0.7)
    for lon in lon_vals:
        ax.text(lon, min_lat, f'{lon:.3f}°', ha='center', va='top', **kw)
    for lat in lat_vals:
        ax.text(min_lon, lat, f'{lat:.4f}°', ha='right', va='center', **kw)


def _add_scale_bar(ax, center_lat: float, min_lon: float, max_lon: float, fig_width: float):
    """Add prominent scale bar with white background."""
    lon_range = max_lon - min_lon
    scale_km_options = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50]
    m_per_deg = 111320 * math.cos(math.radians(center_lat))
    available_width = fig_width * 0.3
    best = scale_km_options[0]
    for skm in scale_km_options:
        px_needed = (skm * 1000 / m_per_deg) / lon_range * fig_width
        if px_needed <= available_width * 100:
            best = skm
    km = best
    deg_km = (km * 1000) / m_per_deg
    frac = deg_km / lon_range
    sb_x = 0.05
    sb_y = 0.06

    # White background box
    bbox_props = dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='#555555', alpha=0.85)
    ax.text(sb_x + frac / 2, sb_y + 0.03, f'{km} km', transform=ax.transAxes,
            fontsize=10, ha='center', va='bottom', color='#222222', fontweight='bold',
            bbox=bbox_props)

    # Thick scale bar line
    ax.annotate('', xy=(sb_x + frac, sb_y + 0.01), xytext=(sb_x, sb_y + 0.01),
                xycoords='axes fraction', fontsize=0,
                arrowprops=dict(arrowstyle='-', color='#222222', lw=4))


def _add_legend(ax, layer_name: str):
    """Add legend for raster map layers."""
    if layer_name == "forest_type":
        elements = [
            mpatches.Patch(color=(0/255, 100/255, 0/255, 0.85), label="Shorea robusta"),
            mpatches.Patch(color=(154/255, 205/255, 50/255, 0.85), label="Pinus wallichiana-Tsuga"),
            mpatches.Patch(color=(46/255, 139/255, 87/255, 0.85), label="Abies spectabilis"),
            mpatches.Patch(color=(106/255, 90/255, 205/255, 0.85), label="Rhododendron"),
            mpatches.Patch(color=(139/255, 69/255, 19/255, 0.85), label="Tropical Riverine"),
            mpatches.Patch(color=(189/255, 189/255, 189/255, 0.85), label="Other / No Data"),
        ]
    elif layer_name == "forest_health":
        elements = [
            mpatches.Patch(color=(220/255, 20/255, 60/255, 0.85), label="Stressed"),
            mpatches.Patch(color=(255/255, 140/255, 0/255, 0.85), label="Poor"),
            mpatches.Patch(color=(255/255, 215/255, 0/255, 0.85), label="Moderate"),
            mpatches.Patch(color=(144/255, 238/255, 144/255, 0.85), label="Healthy"),
            mpatches.Patch(color=(34/255, 139/255, 34/255, 0.85), label="Excellent"),
        ]
    elif layer_name == "slope":
        elements = [
            mpatches.Patch(color=(46/255, 204/255, 113/255, 0.85), label="Gentle (<10°)"),
            mpatches.Patch(color=(241/255, 196/255, 15/255, 0.85), label="Moderate (10-20°)"),
            mpatches.Patch(color=(230/255, 126/255, 34/255, 0.85), label="Steep (20-30°)"),
            mpatches.Patch(color=(231/255, 76/255, 60/255, 0.85), label="Very Steep (>30°)"),
        ]
    elif layer_name == "biomass":
        elements = [
            mpatches.Patch(color=(220/255, 20/255, 60/255, 0.85), label="Very Low (<50 Mg/ha)"),
            mpatches.Patch(color=(255/255, 215/255, 0/255, 0.85), label="Low (50-100 Mg/ha)"),
            mpatches.Patch(color=(144/255, 238/255, 144/255, 0.85), label="Medium (100-200 Mg/ha)"),
            mpatches.Patch(color=(34/255, 139/255, 34/255, 0.85), label="High (200-300 Mg/ha)"),
            mpatches.Patch(color=(30/255, 144/255, 255/255, 0.85), label="Very High (>300 Mg/ha)"),
        ]
    elif layer_name == "landcover":
        elements = [
            mpatches.Patch(color=(0/255, 100/255, 0/255, 0.85), label="Tree Cover"),
            mpatches.Patch(color=(255/255, 187/255, 34/255, 0.85), label="Shrubland"),
            mpatches.Patch(color=(255/255, 255/255, 76/255, 0.85), label="Grassland"),
            mpatches.Patch(color=(240/255, 150/255, 255/255, 0.85), label="Cropland"),
            mpatches.Patch(color=(250/255, 0/255, 0/255, 0.85), label="Built-up"),
            mpatches.Patch(color=(0/255, 100/255, 200/255, 0.85), label="Water"),
        ]
    elif layer_name == "dem":
        elements = [
            mpatches.Patch(color=(139/255, 69/255, 19/255, 0.85), label="Low"),
            mpatches.Patch(color=(255/255, 165/255, 0/255, 0.85), label="Medium-Low"),
            mpatches.Patch(color=(127/255, 255/255, 0/255, 0.85), label="Medium-High"),
            mpatches.Patch(color=(135/255, 206/255, 235/255, 0.85), label="High"),
        ]
    else:
        return

    ax.legend(
        handles=elements,
        loc='lower right',
        fontsize=7,
        title_fontsize=8,
        framealpha=0.90,
        edgecolor='#555555',
        fancybox=True,
    )
