import io
import math
import os
import hashlib
import logging
from typing import Optional, Tuple, List, Dict
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import text
from shapely.geometry import Polygon as ShapelyPolygon, MultiPolygon, shape
from geoalchemy2.shape import to_shape

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager as fm
import numpy as np
from PIL import Image as PILImage

import contextily as cx

from ..tile_service import get_tile_service

logger = logging.getLogger(__name__)

MAP_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "maps_cache")


def _map_cache_path(calculation_id: UUID, layer_name: str, dpi: int = None) -> str:
    if dpi is None:
        import sys
        dpi = sys.modules[__name__].DPI
    cid = str(calculation_id)
    sub = os.path.join(MAP_CACHE_DIR, cid)
    os.makedirs(sub, exist_ok=True)
    return os.path.join(sub, f"{layer_name}_dpi{dpi}.png")


def _map_cache_get(calculation_id: UUID, layer_name: str, dpi: int = None) -> Optional[io.BytesIO]:
    if dpi is None:
        import sys
        dpi = sys.modules[__name__].DPI
    path = _map_cache_path(calculation_id, layer_name, dpi)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                buf = io.BytesIO(f.read())
            logger.info(f"Map cache HIT: {layer_name} for {calculation_id} dpi={dpi}")
            return buf
        except Exception as e:
            logger.warning(f"Map cache read failed: {e}")
    return None


def _map_cache_set(calculation_id: UUID, layer_name: str, buf: io.BytesIO, dpi: int = None):
    if dpi is None:
        import sys
        dpi = sys.modules[__name__].DPI
    path = _map_cache_path(calculation_id, layer_name, dpi)
    try:
        with open(path, "wb") as f:
            f.write(buf.getvalue())
        logger.info(f"Map cache SAVED: {layer_name} -> {path} dpi={dpi}")
    except Exception as e:
        logger.warning(f"Map cache write failed: {e}")


def clear_map_cache(calculation_id: Optional[UUID] = None, layer_name: Optional[str] = None):
    if calculation_id:
        sub = os.path.join(MAP_CACHE_DIR, str(calculation_id))
        if layer_name:
            path = os.path.join(sub, f"{layer_name}.png")
            if os.path.exists(path):
                os.remove(path)
                logger.info(f"Map cache CLEARED: {layer_name}")
        elif os.path.isdir(sub):
            import shutil
            shutil.rmtree(sub)
            logger.info(f"Map cache CLEARED all for {calculation_id}")
    elif os.path.isdir(MAP_CACHE_DIR):
        import shutil
        for entry in os.listdir(MAP_CACHE_DIR):
            shutil.rmtree(os.path.join(MAP_CACHE_DIR, entry))
        logger.info("Map cache CLEARED all")

_DEVANAGARI_FONT_PATHS = [
    "C:/Windows/Fonts/Nirmala.ttc",
    "C:/Windows/Fonts/mangal.ttf",
    "C:/Windows/Fonts/ARIALUNI.TTF",
    "C:/Windows/Fonts/Kokila.ttf",
    "C:/Windows/Fonts/Shivaji01.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_DEVANAGARI_FONT = None
for _fp in _DEVANAGARI_FONT_PATHS:
    if os.path.exists(_fp):
        try:
            _prop = fm.FontProperties(fname=_fp)
            if _prop.get_name():
                fm.fontManager.addfont(_fp)
                _DEVANAGARI_FONT = _fp
                break
        except Exception:
            continue

if _DEVANAGARI_FONT:
    _font_name = fm.FontProperties(fname=_DEVANAGARI_FONT).get_name()
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = [_font_name] + plt.rcParams.get('font.sans-serif', [])
else:
    logger.warning("No Devanagari font found - map labels will use English fallback")

def _dev_fontprop(size: int = 14):
    if _DEVANAGARI_FONT:
        return fm.FontProperties(fname=_DEVANAGARI_FONT, size=size)
    return fm.FontProperties(size=size)

FIG_SIZE_MM = 150
FIG_SIZE_INCHES = (FIG_SIZE_MM / 25.4, FIG_SIZE_MM / 25.4)
TILE_SIZE = 256
DPI = 150
RASTER_ALPHA = 0.55
BOUNDARY_FILL_ALPHA = 0.25
BLOCK_FILL_ALPHA = 0.20

BASEMAP_SOURCES = {
    "boundary":      cx.providers.OpenStreetMap.Mapnik,
    "slope":         cx.providers.OpenTopoMap,
    "aspect":        cx.providers.OpenTopoMap,
    "dem":           cx.providers.OpenTopoMap,
    "forest_type":   cx.providers.OpenStreetMap.Mapnik,
    "landcover":     cx.providers.OpenStreetMap.Mapnik,
    "forest_health": cx.providers.OpenStreetMap.Mapnik,
    "canopy":        cx.providers.OpenStreetMap.Mapnik,
    "biomass":       cx.providers.OpenStreetMap.Mapnik,
    "soil_texture":  cx.providers.OpenStreetMap.Mapnik,
    "sampling_plot":         cx.providers.OpenStreetMap.Mapnik,
    "sampling_plot_topo":    cx.providers.OpenTopoMap,
    "sampling_plot_satellite": cx.providers.Esri.WorldImagery,
    "fieldbook":               cx.providers.OpenTopoMap,
}

LAYER_LABELS = {
    "boundary":                {"ne": "सिमाना नक्सा",                   "en": "Boundary Map"},
    "forest_type":             {"ne": "वन प्रकार नक्सा",                "en": "Forest Type Map"},
    "forest_health":           {"ne": "वन स्वास्थ्य नक्सा",             "en": "Forest Health Map"},
    "slope":                   {"ne": "भिरालो नक्सा",                   "en": "Slope Map"},
    "biomass":                 {"ne": "बायोमास नक्सा",                  "en": "Biomass Map"},
    "landcover":               {"ne": "भू-आवरण नक्सा",                   "en": "Land Cover Map"},
    "soil_texture":            {"ne": "माटो बनावट नक्सा",               "en": "Soil Texture Map"},
    "dem":                     {"ne": "उचाइ नक्सा",                      "en": "Elevation Map"},
    "aspect":                  {"ne": "दिशा नक्सा",                      "en": "Aspect Map"},
    "canopy":                  {"ne": "वन छाना नक्सा",                   "en": "Canopy Cover Map"},
    "sampling_plot":           {"ne": "नमुना प्लट नक्सा",                "en": "Sample Plot Map"},
    "sampling_plot_topo":      {"ne": "स्थलाकृतिक नमुना प्लट नक्सा",     "en": "Sample Plot Map (Topo)"},
    "sampling_plot_satellite": {"ne": "उपग्रह नमुना प्लट नक्सा",         "en": "Sample Plot Map (Satellite)"},
    "fieldbook":               {"ne": "फिल्डबुक बाटो नक्सा",              "en": "Fieldbook Path Map"},
}

_SAMPLING_PLOT_LAYERS = {"sampling_plot", "sampling_plot_topo", "sampling_plot_satellite"}

BLOCK_COLORS = [
    '#2e7d32', '#1565c0', '#795548', '#f9a825',
    '#6a1b9a', '#00838f', '#e65100', '#c62828',
]


def _get_forest_bbox(db: Session, calculation_id: UUID) -> Optional[Tuple[float, float, float, float]]:
    from ...models.calculation import Calculation
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.boundary_geom:
        return None
    geom = to_shape(calc.boundary_geom)
    return geom.bounds


def _get_forest_geometry(db: Session, calculation_id: UUID):
    from ...models.calculation import Calculation
    from geoalchemy2.shape import to_shape
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc or not calc.boundary_geom:
        return None
    return to_shape(calc.boundary_geom)


def _get_blocks_with_geometry(db: Session, calculation_id: UUID) -> List[Dict]:
    from ...models.forest_block import ForestBlock
    blocks = db.query(ForestBlock).filter(
        ForestBlock.calculation_id == calculation_id,
        ForestBlock.division_level == 0,
    ).order_by(ForestBlock.index).all()

    result = []
    for b in blocks:
        try:
            geom = to_shape(b.geometry)
            centroid = geom.centroid
            result.append({
                "name": b.name,
                "geometry": geom,
                "centroid": centroid,
                "area_ha": b.area_hectares,
            })
        except Exception as e:
            logger.warning(f"Could not parse geometry for block {b.name}: {e}")
    return result


def _get_sample_plots(db: Session, calculation_id: UUID) -> List[Dict]:
    from ...models.sampling import SamplingDesign
    from shapely import wkt as shapely_wkt

    designs = db.query(SamplingDesign).filter(
        SamplingDesign.calculation_id == calculation_id,
        SamplingDesign.points_geometry.isnot(None),
    ).order_by(SamplingDesign.created_at).all()
    if not designs:
        return []

    design = designs[0]

    # Prefer cached points_data (has lon/lat, point_index, block_name)
    cached = design.points_data or {}
    cached_points = cached.get("points") if isinstance(cached, dict) else None
    if cached_points:
        plots = []
        for pt in cached_points:
            lon = pt.get("longitude") or pt.get("lon")
            lat = pt.get("latitude") or pt.get("lat")
            if lon is None or lat is None:
                continue
            plots.append({
                "lon": float(lon),
                "lat": float(lat),
                "label": str(pt.get("plot_number", pt.get("point_index", ""))),
                "block_name": pt.get("block_name", ""),
            })
        return plots

    # Fallback: extract from points_geometry MULTIPOINT
    block_assignment = design.points_block_assignment or []
    result = db.execute(
        text("SELECT ST_AsText(points_geometry) FROM public.sampling_designs WHERE id = :id"),
        {"id": str(design.id)},
    ).first()
    if not result or not result[0]:
        return []

    multipoint = shapely_wkt.loads(result[0])
    plots = []
    for i, point in enumerate(multipoint.geoms):
        block_info = next((b for b in block_assignment if b.get("point_index") == i), None)
        plots.append({
            "lon": point.x,
            "lat": point.y,
            "label": str(i + 1),
            "block_name": (block_info or {}).get("block_name", ""),
        })
    return plots


def _add_basemap(ax, layer_name: str, alpha: float = 0.6):
    source = BASEMAP_SOURCES.get(layer_name, cx.providers.OpenStreetMap.Mapnik)
    try:
        cx.add_basemap(ax, crs='EPSG:4326', source=source, alpha=alpha, zorder=1)
        return True
    except Exception as e:
        logger.warning(f"Basemap unavailable for {layer_name}: {e}")
        ax.set_facecolor('#f0f0f0')
        return False


def _add_raster_overlay(ax, db: Session, calculation_id: UUID, layer_name: str, bbox, dpi: int):
    from shapely.geometry import Polygon, MultiPolygon
    min_lon, min_lat, max_lon, max_lat = bbox
    lon_width = max_lon - min_lon

    try:
        tile_service = get_tile_service(db)
        calc_id_str = str(calculation_id)
        zoom = _calc_zoom(lon_width, FIG_SIZE_INCHES[0], dpi=dpi)

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

        from concurrent.futures import ThreadPoolExecutor, as_completed
        tile_coords = [(tx, ty) for ty in range(y_start, y_end + 1) for tx in range(x_start, x_end + 1)]
        tile_results = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_map = {}
            for tx, ty in tile_coords:
                future = executor.submit(tile_service.get_tile,
                                         calculation_id=calc_id_str, layer_name=layer_name,
                                         z=zoom, x=tx, y=ty, alpha=255)
                future_map[future] = (tx, ty)
            for future in as_completed(future_map):
                tx, ty = future_map[future]
                try:
                    tb = future.result()
                    tile_results[(tx, ty)] = np.array(PILImage.open(io.BytesIO(tb)).convert("RGBA"))
                except Exception:
                    tile_results[(tx, ty)] = np.zeros((TILE_SIZE, TILE_SIZE, 4), dtype=np.uint8)
        rows = []
        for ty in range(y_start, y_end + 1):
            row_tiles = [tile_results[(tx, ty)] for tx in range(x_start, x_end + 1)]
            rows.append(np.hstack(row_tiles))
        raster_img = np.vstack(rows) if len(rows) > 1 else rows[0]

        extent = [comp_min_lon, comp_max_lon, comp_min_lat, comp_max_lat]
        ax.imshow(raster_img, extent=extent, alpha=RASTER_ALPHA, zorder=2)
        return True

    except Exception as e:
        logger.error(f"Raster overlay failed for {layer_name}: {e}")
        return False


def _add_block_polygons_with_labels(ax, blocks: List[Dict]):
    for i, blk in enumerate(blocks):
        color = BLOCK_COLORS[i % len(BLOCK_COLORS)]

        geom = blk["geometry"]
        centroid = blk["centroid"]

        if isinstance(geom, ShapelyPolygon):
            xs, ys = geom.exterior.xy
            ax.plot(xs, ys, color=color, linewidth=2.0, zorder=3)
            for ring in geom.interiors:
                rx, ry = ring.xy
                ax.plot(rx, ry, color='#888', linewidth=0.8, linestyle='--', zorder=3)
        elif isinstance(geom, MultiPolygon):
            for part in geom.geoms:
                xs, ys = part.exterior.xy
                ax.plot(xs, ys, color=color, linewidth=2.0, zorder=3)
                for ring in part.interiors:
                    rx, ry = ring.xy
                    ax.plot(rx, ry, color='#888', linewidth=0.8, linestyle='--', zorder=3)

        ax.annotate(
            blk["name"],
            xy=(centroid.x, centroid.y),
            fontsize=10,
            fontweight='bold',
            ha='center',
            va='center',
            color='#1b5e20',
            fontproperties=_dev_fontprop(10),
            bbox=dict(
                boxstyle='round,pad=0.25',
                facecolor='white',
                edgecolor='#1b5e20',
                alpha=0.85,
                linewidth=0.5,
            ),
            zorder=6,
        )


def _add_sample_plots(ax, plots: List[Dict]):
    for pt in plots:
        ax.scatter(
            pt["lon"], pt["lat"],
            s=160, marker='o', facecolors='none', edgecolors='#ffd600',
            linewidth=2.0, zorder=7
        )
        ax.annotate(
            pt["label"],
            xy=(pt["lon"], pt["lat"]),
            fontsize=8, fontweight='bold', color='#000000',
            ha='center', va='center',
            zorder=8,
        )


def _add_fieldbook_features(ax, db: Session, calculation_id: UUID):
    from ...models.fieldbook import Fieldbook
    from shapely import wkt as shapely_wkt

    points = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).order_by(Fieldbook.point_number).all()
    if not points:
        return

    # Distinct colors per forest block
    block_names = sorted(set(p.block_name or "Unknown" for p in points))
    palette = ['#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
               '#911eb4', '#42d4f4', '#f032e6', '#bfef45', '#fabed4',
               '#469990', '#dcbeff', '#9A6324', '#800000', '#aaffc3']
    block_color = {bn: palette[i % len(palette)] for i, bn in enumerate(block_names)}

    # Plot points per block with block-specific colors
    for bn in block_names:
        blk = [p for p in points if (p.block_name or "Unknown") == bn]
        c = block_color[bn]
        # Vertex points: filled circles
        vv = [p for p in blk if p.point_type == "vertex"]
        if vv:
            ax.scatter([float(p.longitude) for p in vv],
                       [float(p.latitude) for p in vv],
                       s=40, marker='o', color=c,
                       edgecolors='#000000', linewidth=1.0, zorder=7, label=bn)
        # Interpolated points: hollow circles
        ii = [p for p in blk if p.point_type == "interpolated"]
        if ii:
            ax.scatter([float(p.longitude) for p in ii],
                       [float(p.latitude) for p in ii],
                       s=25, marker='o', facecolors='none',
                       edgecolors=c, linewidth=1.5, zorder=7)

    # Vertex-only labels with 8-direction collision avoidance
    _label_offsets = [
        (0, 6, 'center', 'bottom'),    # above (default)
        (6, 0, 'left', 'center'),       # right
        (-6, 0, 'right', 'center'),     # left
        (0, -6, 'center', 'top'),       # below
        (6, 6, 'left', 'bottom'),       # top-right
        (-6, 6, 'right', 'bottom'),     # top-left
        (6, -6, 'left', 'top'),         # bottom-right
        (-6, -6, 'right', 'top'),       # bottom-left
    ]
    fs_pt = 6
    cw_pt = 3.5
    lh_pt = fs_pt + 2
    pad_pt = 1.5
    dpi = ax.figure.dpi if hasattr(ax, 'figure') else 100
    placed_bboxes = []
    for p in points:
        if p.point_type != "vertex":
            continue
        label = str(p.point_number)
        lon, lat = float(p.longitude), float(p.latitude)
        lw_pt = len(label) * cw_pt + pad_pt * 2
        anchor = ax.transData.transform((lon, lat))
        placed = False
        for dx_pt, dy_pt, ha, va in _label_offsets:
            ox = anchor[0] + dx_pt * dpi / 72
            oy = anchor[1] + dy_pt * dpi / 72
            w = lw_pt * dpi / 72
            h = lh_pt * dpi / 72
            if ha == 'center':
                x0, x1 = ox - w / 2, ox + w / 2
            elif ha == 'left':
                x0, x1 = ox, ox + w
            else:
                x0, x1 = ox - w, ox
            if va == 'bottom':
                y0, y1 = oy, oy + h
            elif va == 'center':
                y0, y1 = oy - h / 2, oy + h / 2
            else:
                y0, y1 = oy - h, oy
            collision = any(
                not (x1 <= bx0 or x0 >= bx1 or y1 <= by0 or y0 >= by1)
                for bx0, bx1, by0, by1 in placed_bboxes
            )
            if not collision:
                ax.annotate(label, xy=(lon, lat),
                            xytext=(dx_pt, dy_pt), textcoords='offset points',
                            fontsize=fs_pt, fontweight='bold', color='#000000',
                            ha=ha, va=va, zorder=8)
                placed_bboxes.append((x0, x1, y0, y1))
                placed = True
                break

    # Legend for block colors
    handles = [mpatches.Patch(facecolor=block_color[bn], edgecolor='black', label=bn)
               for bn in block_names]
    if handles:
        ax.legend(handles=handles, loc='lower right', fontsize=7,
                  title='Forest Block', title_fontsize=8)


def _add_boundary_outline(ax, boundary_geom):
    if boundary_geom is None:
        return
    from shapely.geometry import Polygon, MultiPolygon
    polys = [boundary_geom] if isinstance(boundary_geom, Polygon) else list(boundary_geom.geoms)
    for poly in polys:
        xs, ys = poly.exterior.xy
        ax.plot(xs, ys, color='#1b5e20', linewidth=2.5, zorder=5)
        for ring in poly.interiors:
            rx, ry = ring.xy
            ax.plot(rx, ry, color='#888', linewidth=1, linestyle='--', zorder=5)


def _add_grid(ax, min_lon, max_lon, min_lat, max_lat):
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


def _add_north_arrow(ax):
    na_x = 0.93
    na_y = 0.85
    ax.annotate('N', xy=(na_x, na_y), xytext=(na_x, na_y - 0.05),
                xycoords='axes fraction', fontsize=14, fontweight='bold',
                ha='center', va='center',
                arrowprops=dict(arrowstyle='->', color='#222222', lw=3),
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                          edgecolor='#cccccc', alpha=0.85))


def _add_legend(ax, layer_name: str):
    legend_map = {
        "forest_type": [
            ( (0/255, 100/255, 0/255, 0.85), "Shorea robusta"),
            ((154/255, 205/255, 50/255, 0.85), "Pinus wallichiana"),
            ( (46/255, 139/255, 87/255, 0.85), "Abies spectabilis"),
            ((106/255, 90/255, 205/255, 0.85), "Rhododendron"),
            ((139/255, 69/255, 19/255, 0.85), "Tropical Riverine"),
            ((189/255, 189/255, 189/255, 0.85), "Other"),
        ],
        "forest_health": [
            ((220/255, 20/255, 60/255, 0.85), "Stressed"),
            ((255/255, 140/255, 0/255, 0.85), "Poor"),
            ((255/255, 215/255, 0/255, 0.85), "Moderate"),
            ((144/255, 238/255, 144/255, 0.85), "Healthy"),
            ( (34/255, 139/255, 34/255, 0.85), "Excellent"),
        ],
        "slope": [
            ( (46/255, 204/255, 113/255, 0.85), "Gentle (<10°)"),
            ((241/255, 196/255, 15/255, 0.85), "Moderate (10-20°)"),
            ((230/255, 126/255, 34/255, 0.85), "Steep (20-30°)"),
            ((231/255, 76/255, 60/255, 0.85), "Very Steep (>30°)"),
        ],
        "biomass": [
            ((220/255, 20/255, 60/255, 0.85), "Very Low (<50 Mg/ha)"),
            ((255/255, 215/255, 0/255, 0.85), "Low (50-100)"),
            ((144/255, 238/255, 144/255, 0.85), "Medium (100-200)"),
            ( (34/255, 139/255, 34/255, 0.85), "High (200-300)"),
            ( (30/255, 144/255, 255/255, 0.85), "Very High (>300)"),
        ],
        "landcover": [
            ( (0/255, 100/255, 0/255, 0.85), "Tree Cover"),
            ((255/255, 187/255, 34/255, 0.85), "Shrubland"),
            ((255/255, 255/255, 76/255, 0.85), "Grassland"),
            ((240/255, 150/255, 255/255, 0.85), "Cropland"),
            ((250/255, 0/255, 0/255, 0.85), "Built-up"),
            ( (0/255, 100/255, 200/255, 0.85), "Water"),
        ],
        "dem": [
            ((139/255, 69/255, 19/255, 0.85), "Low"),
            ((255/255, 165/255, 0/255, 0.85), "Medium-Low"),
            ((127/255, 255/255, 0/255, 0.85), "Medium-High"),
            ((135/255, 206/255, 235/255, 0.85), "High"),
        ],
        "aspect": [
            ((200/255, 200/255, 200/255, 0.85), "N"),
            ((150/255, 150/255, 150/255, 0.85), "E"),
            ((100/255, 100/255, 100/255, 0.85), "S"),
            ((50/255, 50/255, 50/255, 0.85), "W"),
        ],
        "soil_texture": [
            ((139/255, 69/255, 19/255, 0.85), "Loam"),
            ((205/255, 133/255, 63/255, 0.85), "Sandy Loam"),
            ((244/255, 164/255, 96/255, 0.85), "Silt Loam"),
            ((160/255, 82/255, 45/255, 0.85), "Clay Loam"),
        ],
        "sampling_plot": [
            ((46/255, 125/255, 50/255, 0.85), "Forest Block"),
            ((255/255, 87/255, 34/255, 0.85), "Sample Plot"),
        ],
    }

    items = legend_map.get(layer_name)
    if not items:
        return

    elements = [mpatches.Patch(color=c, label=l) for c, l in items]
    ax.legend(
        handles=elements, loc='lower right', fontsize=7,
        title_fontsize=8, framealpha=0.90, edgecolor='#555555',
        fancybox=True,
    )


def generate_standard_map(
    db: Session,
    calculation_id: UUID,
    layer_name: str,
    forest_name: str = "",
    dpi: int = DPI,
    use_cache: bool = True,
) -> io.BytesIO:
    """
    Generate a standardized map following the protocol:
    - Basemap (OSM or Topo per layer)
    - Raster overlay at alpha=0.55
    - Block polygons with distinct colors + name labels on ALL maps
    - Boundary outline
    - Coordinate grid (5x5), NO scale bar
    - North arrow, legend, title
    - Devanagari font with fallback verification

    Uses a persistent file cache — generated maps are saved once and reused.
    Call clear_map_cache() to force regeneration.

    Args:
        db: Database session
        calculation_id: Forest calculation UUID
        layer_name: One of BASEMAP_SOURCES keys
        forest_name: Forest name for title
        dpi: Output DPI (200 default)
        use_cache: If True, check/save persistent cache (default True)

    Returns:
        BytesIO containing PNG image
    """
    if use_cache:
        cached = _map_cache_get(calculation_id, layer_name, dpi)
        if cached:
            return cached

    try:
        buf = _generate_map_inner(db, calculation_id, layer_name, forest_name, dpi)
    except Exception as e:
        logger.error(f"Map generation failed for {layer_name}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        buf = io.BytesIO()
        px = int(FIG_SIZE_INCHES[0] * dpi)
        PILImage.new("RGB", (px, px), "white").save(buf, format="PNG")
        buf.seek(0)

    if use_cache:
        buf.seek(0)
        _map_cache_set(calculation_id, layer_name, buf, dpi)
    buf.seek(0)
    return buf


def _generate_map_inner(
    db: Session, calculation_id: UUID, layer_name: str,
    forest_name: str = "", dpi: int = DPI,
) -> io.BytesIO:
    bbox = _get_forest_bbox(db, calculation_id)
    if not bbox:
        buf = io.BytesIO()
        px = int(FIG_SIZE_INCHES[0] * dpi)
        PILImage.new("RGB", (px, px), "white").save(buf, format="PNG")
        buf.seek(0)
        return buf

    min_lon, min_lat, max_lon, max_lat = bbox
    lon_width = max_lon - min_lon
    lat_height = max_lat - min_lat

    # Compute figure size preserving data aspect ratio
    base_width_inches = FIG_SIZE_MM / 25.4
    aspect = lon_width / lat_height if lat_height > 0 else 1.0
    fig_width = base_width_inches
    fig_height = base_width_inches / aspect
    # Clamp to reasonable range so very elongated shapes don't break layout
    fig_height = max(base_width_inches * 0.5, min(fig_height, base_width_inches * 2.0))

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.92, bottom=0.06)

    boundary_geom = _get_forest_geometry(db, calculation_id)

    pad_x = lon_width * 0.05
    pad_y = lat_height * 0.05
    ax.set_xlim(min_lon - pad_x, max_lon + pad_x)
    ax.set_ylim(min_lat - pad_y, max_lat + pad_y)
    ax.set_aspect('equal')

    # 1. Basemap
    _add_basemap(ax, layer_name, alpha=0.6)

    _NO_RASTER_LAYERS = {"boundary", "fieldbook"} | _SAMPLING_PLOT_LAYERS
    # 2. Raster overlay (skip for boundary, fieldbook, and sampling_plot layers)
    if layer_name not in _NO_RASTER_LAYERS:
        _add_raster_overlay(ax, db, calculation_id, layer_name, bbox, dpi)

    # 3. Block polygons with name labels — on EVERY map
    blocks = _get_blocks_with_geometry(db, calculation_id)
    if blocks:
        _add_block_polygons_with_labels(ax, blocks)

    # 4. Sample plot points (for all sampling_plot layer variants)
    if layer_name in _SAMPLING_PLOT_LAYERS:
        plots = _get_sample_plots(db, calculation_id)
        if plots:
            _add_sample_plots(ax, plots)

    # 4b. Fieldbook features (fieldbook layer only)
    if layer_name == "fieldbook":
        _add_fieldbook_features(ax, db, calculation_id)

    # 5. Boundary outline
    _add_boundary_outline(ax, boundary_geom)

    # 6. Coordinate grid (5x5 lines + labels)
    _add_grid(ax, min_lon, max_lon, min_lat, max_lat)

    # 7. Hide axis ticks
    ax.axis('off')

    # 8. Title (Nepali main + English sub — single block, no overlap)
    label_info = LAYER_LABELS.get(layer_name, {})
    title_ne = label_info.get("ne", layer_name)
    title_en = label_info.get("en", layer_name)
    prefix = f"{forest_name} — " if forest_name else ""
    title = f"{prefix}{title_ne}\n{title_en}"
    ax.set_title(title, fontsize=16, fontweight='bold', pad=10, color='#1b5e20',
                 fontproperties=_dev_fontprop(16), linespacing=1.4)

    # 9. North arrow (NO scale bar — grid provides scale)
    _add_north_arrow(ax)

    # 10. Legend
    if layer_name != "boundary":
        _add_legend(ax, layer_name)

    # Footer
    fig.text(0.02, 0.02, f"{dpi} DPI | {title_en}", fontsize=8, color='#888888')

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
