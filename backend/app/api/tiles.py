"""
API endpoints for raster tile generation
Provides XYZ tile service for map visualization
"""
import math
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional

from ..core.database import get_db
from ..services.tile_service import get_tile_service


router = APIRouter(prefix="/api", tags=["tiles"])


@router.get("/calculations/{calculation_id}/tiles/{layer_name}/{z}/{x}/{y}.png")
async def get_raster_tile(
    calculation_id: str,
    layer_name: str,
    z: int,
    x: int,
    y: int,
    alpha: int = Query(default=128, ge=0, le=255, description="Transparency (0=transparent, 255=opaque)"),
    filter_classes: str = Query(default=None, description="Comma-separated class codes to filter (e.g., '1,2,3' for slope classes)"),
    db: Session = Depends(get_db)
):
    """
    Get a single raster tile for map visualization

    **Tile Coordinates (XYZ format):**
    - **z**: Zoom level (10-16 recommended for Nepal forests)
    - **x**: Tile X coordinate (longitude index)
    - **y**: Tile Y coordinate (latitude index)

    **Available Layers:**
    - `slope` - Terrain slope (Forest Regulation 2079: Class 1-4)
    - `aspect` - Slope direction (N, NE, E, SE, S, SW, W, NW, Flat)
    - `dem` - Elevation (Digital Elevation Model)
    - `canopy` - Canopy height (meters)
    - `biomass` - Above-ground biomass (Mg/ha, ESA CCI AGB V6)
    - `nasa_forest_2020` - Forest quality (Primary/Secondary, NASA IPCC Tier 1)
    - `forest_type` - Forest classification (FRTC)
    - `landcover` - Land cover classes (ESA WorldCover)
    - `forest_loss` - Forest loss year (Hansen GFC)
    - `forest_gain` - Forest gain (Hansen GFC, binary)
    - `temperature` - Mean annual temperature (WorldClim)
    - `precipitation` - Annual precipitation (WorldClim)
    - `min_temp_coldest` - Min temperature coldest month (WorldClim)
    - `soil_ph` - Soil pH/acidity (SoilGrids ISRIC)
    - `soil_texture` - Soil texture classification (SoilGrids ISRIC)
    - `soil_carbon` - Soil organic carbon (SoilGrids ISRIC)
    - `soil_fertility` - Soil fertility index (SoilGrids ISRIC)
    - `soil_density` - Bulk density/compaction (SoilGrids ISRIC)
    - `fire` - Fire damage areas (Hansen GFC)
    - `forest_health` - Forest health index (NDVI)

    **Parameters:**
    - **alpha**: Transparency level (default 128 = 50%)
    - **filter_classes**: Comma-separated class codes to show (e.g., '1,2' shows only classes 1 and 2)

    **Returns:**
    - PNG image (256×256 pixels) with color-coded raster data
    - HTTP 404 if calculation not found
    - HTTP 400 if invalid layer name
    - HTTP 500 if tile generation fails

    **Example:**
    ```
    GET /api/calculations/{calc_id}/tiles/slope/14/12345/6789.png?alpha=128
    GET /api/calculations/{calc_id}/tiles/slope/14/12345/6789.png?filter_classes=1,2
    ```

    **Caching:**
    - Tiles are cached for 24 hours
    - Cache-Control header set to public
    """
    try:
        tile_service = get_tile_service(db)
        
        # Parse filter_classes parameter
        filter_list = None
        if filter_classes and layer_name == 'slope':
            try:
                filter_list = [int(c.strip()) for c in filter_classes.split(',')]
            except ValueError:
                pass  # Invalid format, ignore filter

        png_bytes = tile_service.get_tile_cached(
            calculation_id=calculation_id,
            layer_name=layer_name,
            z=z,
            x=x,
            y=y,
            alpha=alpha,
            filter_classes=filter_list
        )

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400",
                "Content-Type": "image/png",
                "Access-Control-Allow-Origin": "*"
            }
        )

    except ValueError as e:
        # Invalid calculation_id or layer_name
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Tile generation failed
        print(f"Tile generation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tile generation failed: {str(e)}")


@router.get("/calculations/{calculation_id}/user-group-tiles/{layer_name}/{z}/{x}/{y}.png")
async def get_user_group_tile(
    calculation_id: str,
    layer_name: str,
    z: int,
    x: int,
    y: int,
    exclude_forest: bool = Query(default=True, description="Exclude forest overlap from visualization"),
    alpha: int = Query(default=180, ge=0, le=255, description="Transparency (0=transparent, 255=opaque)"),
    db: Session = Depends(get_db)
):
    """
    Get raster tiles for user group extent with optional forest overlap exclusion

    **Available Layers:**
    - `landcover` - ESA World Cover land use classification (11 classes)
    - `biomass` - Above-ground biomass (Mg/ha, ESA CCI AGB 2022 Nepal)

    **Parameters:**
    - **exclude_forest**: Exclude community forest overlap (default: True)
    - **alpha**: Transparency level (default 180 = 70%)

    **Returns:**
    - PNG image (256×256 pixels) clipped to user group extent

    **Example:**
    ```
    GET /api/calculations/{calc_id}/user-group-tiles/landcover/14/12345/6789.png?exclude_forest=true&alpha=180
    ```

    **Prerequisites:**
    - User group extent must be created for this calculation
    - If exclude_forest=True, community forest boundary must exist

    **Caching:**
    - Tiles are cached for 1 hour
    - Cache varies by exclude_forest parameter
    """
    try:
        tile_service = get_tile_service(db)

        png_bytes = tile_service.get_user_group_tile(
            calculation_id=calculation_id,
            layer_name=layer_name,
            z=z,
            x=x,
            y=y,
            exclude_forest_overlap=exclude_forest,
            alpha=alpha
        )

        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Content-Type": "image/png",
                "Access-Control-Allow-Origin": "*"
            }
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print(f"User group tile generation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tile generation failed: {str(e)}")


@router.get("/calculations/{calculation_id}/user-group/query")
async def query_user_group_point(
    calculation_id: str,
    lat: float = Query(..., description="Latitude (WGS84)", ge=-90, le=90),
    lon: float = Query(..., description="Longitude (WGS84)", ge=-180, le=180),
    db: Session = Depends(get_db)
):
    """
    Get land cover and biomass values at a specific point within user group extent

    **Parameters:**
    - **lat**: Latitude in decimal degrees (WGS84)
    - **lon**: Longitude in decimal degrees (WGS84)

    **Returns:**
    - JSON object with land cover class and biomass value
    - Only returns data if point is within effective area (user group - forest overlap)

    **Example:**
    ```
    GET /api/calculations/{calc_id}/user-group/query?lat=27.7172&lon=85.3240
    ```

    **Response:**
    ```json
    {
      "location": {"lat": 27.7172, "lon": 85.3240},
      "in_effective_area": true,
      "land_cover": {
        "class_code": 10,
        "class_name": "Tree cover"
      },
      "biomass": {
        "value_mg_ha": 150.5,
        "volume_m3_ha": 100.8
      }
    }
    ```
    """
    try:
        from sqlalchemy import text

        point_wkt = f"POINT({lon} {lat})"

        # Land cover class names
        landcover_names = {
            10: "Tree cover",
            20: "Shrubland",
            30: "Grassland",
            40: "Cropland",
            50: "Built-up",
            60: "Bare / sparse vegetation",
            70: "Snow and ice",
            80: "Permanent water bodies",
            90: "Herbaceous wetland",
            95: "Mangroves",
            100: "Moss and lichen"
        }

        # First check if point is within effective area (user group - forest overlap)
        validation_query = text("""
            WITH user_extent AS (
                SELECT extent_geometry
                FROM public.user_group_extents
                WHERE calculation_id = :calc_id
                ORDER BY created_at DESC
                LIMIT 1
            ),
            forest_boundary AS (
                SELECT boundary_geom
                FROM public.calculations
                WHERE id = :calc_id
            ),
            net_geometry AS (
                SELECT
                    CASE
                        WHEN ST_Intersects(ue.extent_geometry, fb.boundary_geom) THEN
                            ST_Difference(ue.extent_geometry, fb.boundary_geom)
                        ELSE
                            ue.extent_geometry
                    END as net_geom
                FROM user_extent ue, forest_boundary fb
            )
            SELECT ST_Contains(net_geom, ST_GeomFromText(:point, 4326)) as in_effective_area
            FROM net_geometry
        """)

        validation_result = db.execute(
            validation_query,
            {"calc_id": calculation_id, "point": point_wkt}
        ).first()

        if not validation_result or not validation_result.in_effective_area:
            raise HTTPException(
                status_code=400,
                detail="Point is outside effective area (user group extent minus forest overlap)"
            )

        # Query land cover and biomass
        query = text("""
            SELECT
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326))
                 FROM rasters.esa_world_cover
                 WHERE ST_Intersects(rast, ST_GeomFromText(:point, 4326))
                 LIMIT 1) as landcover_class,
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326))
                 FROM rasters.agb_2022_nepal
                 WHERE ST_Intersects(rast, ST_GeomFromText(:point, 4326))
                 LIMIT 1) as biomass_mg_ha
        """)

        result = db.execute(query, {"point": point_wkt}).first()

        # Process land cover (may be None)
        landcover_class = int(result.landcover_class) if result and result.landcover_class is not None else None
        landcover_name = landcover_names.get(landcover_class, "Unknown") if landcover_class else None

        # Process biomass (may be None)
        biomass_mg_ha = float(result.biomass_mg_ha) if result and result.biomass_mg_ha is not None else None
        volume_m3_ha = round(biomass_mg_ha * 0.67, 2) if biomass_mg_ha and biomass_mg_ha > 0 else None

        return {
            "location": {
                "lat": lat,
                "lon": lon
            },
            "in_effective_area": True,
            "land_cover": {
                "class_code": landcover_class,
                "class_name": landcover_name
            } if landcover_class else None,
            "biomass": {
                "value_mg_ha": round(biomass_mg_ha, 2) if biomass_mg_ha and biomass_mg_ha > 0 else None,
                "volume_m3_ha": volume_m3_ha
            } if biomass_mg_ha and biomass_mg_ha > 0 else None
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"User group point query error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/calculations/{calculation_id}/query")
async def query_point(
    calculation_id: str,
    lat: float = Query(..., description="Latitude (WGS84)", ge=-90, le=90),
    lon: float = Query(..., description="Longitude (WGS84)", ge=-180, le=180),
    db: Session = Depends(get_db)
):
    """
    Get all raster values at a specific point

    **Parameters:**
    - **lat**: Latitude in decimal degrees (WGS84)
    - **lon**: Longitude in decimal degrees (WGS84)

    **Returns:**
    - JSON object with all 16 parameter values at the clicked location

    **Example:**
    ```
    GET /api/calculations/{calc_id}/query?lat=27.7172&lon=85.3240
    ```

    **Response:**
    ```json
    {
      "elevation_m": 1350.5,
      "slope_degrees": 15.3,
      "aspect_direction": "SE",
      "canopy_height_m": 12.5,
      "biomass_mg_ha": 150.2,
      "temperature_c": 18.5,
      "precipitation_mm": 1500,
      ...
    }
    ```
    """
    try:
        from sqlalchemy import text

        point_wkt = f"POINT({lon} {lat})"

        # Query only existing rasters at this point
        query = text("""
            SELECT
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326)) FROM rasters.dem LIMIT 1) as elevation_m,
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326)) FROM rasters.slope LIMIT 1) as slope_degrees,
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326)) FROM rasters.aspect LIMIT 1) as aspect_class,
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326)) FROM rasters.canopy_height LIMIT 1) as canopy_height_m,
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326)) FROM rasters.agb_2022_nepal LIMIT 1) as biomass_mg_ha,
                (SELECT ST_Value(rast, ST_GeomFromText(:point, 4326)) FROM rasters.forest_type LIMIT 1) as forest_type_class
        """)

        result = db.execute(query, {"point": point_wkt}).first()

        if not result:
            raise HTTPException(status_code=404, detail="No data at this location")

        # Convert aspect class to direction name
        aspect_names = ['Flat', 'N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        aspect_class = int(result.aspect_class) if result.aspect_class is not None else 0

        return {
            "location": {
                "lat": lat,
                "lon": lon
            },
            "elevation_m": round(result.elevation_m, 1) if result.elevation_m is not None else None,
            "slope_degrees": round(result.slope_degrees, 1) if result.slope_degrees is not None else None,
            "aspect_direction": aspect_names[aspect_class] if 0 <= aspect_class < len(aspect_names) else None,
            "canopy_height_m": round(result.canopy_height_m, 1) if result.canopy_height_m is not None else None,
            "biomass_mg_ha": round(result.biomass_mg_ha, 1) if result.biomass_mg_ha is not None else None,
            "forest_type_class": int(result.forest_type_class) if result.forest_type_class is not None else None
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"Point query error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.get("/calculations/{calculation_id}/steep-slope-mask/{z}/{x}/{y}.png")
async def get_steep_slope_mask_tile(
    calculation_id: str,
    z: int,
    x: int,
    y: int,
    threshold: int = Query(default=4, ge=2, le=4, description="Slope class threshold (deprecated, use filter_classes)"),
    alpha: int = Query(default=180, ge=0, le=255, description="Transparency (0=transparent, 255=opaque)"),
    filter_classes: str = Query(default=None, description="Comma-separated class codes to show (e.g., '1,2,3' or '3,4')"),
    db: Session = Depends(get_db)
):
    """
    Get steep slope mask tile - shows selected slope classes with different colors
    
    **Purpose:**
    - Helps users visually identify slope classes for defining protected zones
    - Shows selected classes with different colors:
      - Class 1 (Gentle 0-19°): Green
      - Class 2 (Moderate 19-30°): Yellow
      - Class 3 (Sensitive 30-45°): Orange
      - Class 4 (Extreme >45°): Red
    
    **Parameters:**
    - **filter_classes**: Comma-separated class codes to show (e.g., '1,2' or '3,4'). If not provided, uses threshold.
    - **alpha**: Transparency level (default 180 = 70%)
    
    **Returns:**
    - PNG image (256×256 pixels) with selected slope classes in different colors
    - HTTP 404 if calculation not found
    - HTTP 500 if tile generation fails
    
    **Example:**
    ```
    GET /api/calculations/{calc_id}/steep-slope-mask/14/12345/6789.png?filter_classes=3,4
    ```
    """
    try:
        from sqlalchemy import text
        import io
        from PIL import Image, ImageDraw
        
        print(f"[SteepSlope] ===== Tile request: calc={calculation_id}, z={z}, x={x}, y={y}, threshold={threshold} =====")
        
        # Get boundary WKT
        boundary_query = text("""
            SELECT ST_AsText(boundary_geom) as wkt
            FROM calculations
            WHERE id = :calc_id
        """)
        
        boundary_result = db.execute(boundary_query, {"calc_id": calculation_id}).first()
        
        if not boundary_result or not boundary_result.wkt:
            raise HTTPException(status_code=404, detail="Calculation not found")
        
        boundary_wkt = boundary_result.wkt
        print(f"[SteepSlope] Boundary WKT length: {len(boundary_wkt)}")
        print(f"[SteepSlope] Boundary WKT sample: {boundary_wkt[:100]}...")
        
        # Convert XYZ to bounds
        n = 2.0 ** z
        lon_min = x / n * 360.0 - 180.0
        lon_max = (x + 1) / n * 360.0 - 180.0
        
        lat_max_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
        lat_max = math.degrees(lat_max_rad)
        
        lat_min_rad = math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n)))
        lat_min = math.degrees(lat_min_rad)
        
        print(f"[SteepSlope] Tile bounds: lon=[{lon_min:.4f}, {lon_max:.4f}], lat=[{lat_min:.4f}, {lat_max:.4f}]")

        # Parse filter_classes parameter (new method) or use threshold (legacy)
        show_classes = None
        if filter_classes:
            try:
                show_classes = [int(c.strip()) for c in filter_classes.split(',')]
                print(f"[SteepSlope] Filter classes: {show_classes}")
            except ValueError:
                pass
        
        # Fallback to threshold-based logic
        if show_classes is None:
            if threshold == 4:
                show_classes = [4]
            elif threshold == 3:
                show_classes = [3, 4]
            else:
                show_classes = [2, 3, 4]
            print(f"[SteepSlope] Using threshold-based classes: {show_classes}")
        
        try:
            # Use the exact same grid sampling approach as tile_service
            sample_size = 32
            lon_step = (lon_max - lon_min) / sample_size
            lat_step = (lat_max - lat_min) / sample_size
            
            # Same query as tile_service uses
            query = text("""
                WITH forest_boundary AS (
                    SELECT ST_GeomFromText(:boundary_wkt, 4326) as geom
                ),
                relevant_rasters AS (
                    SELECT r.rast
                    FROM rasters.slope_regulation r, forest_boundary f
                    WHERE ST_Intersects(r.rast, f.geom)
                ),
                grid AS (
                    SELECT
                        i.i as i,
                        j.j as j,
                        :min_lon + (i.i * :lon_step) + (:lon_step / 2.0) as lon,
                        :min_lat + (j.j * :lat_step) + (:lat_step / 2.0) as lat
                    FROM
                        generate_series(0, :sample_size - 1) as i(i),
                        generate_series(0, :sample_size - 1) as j(j)
                )
                SELECT
                    g.i,
                    g.j,
                    ST_Value(r.rast, ST_SetSRID(ST_MakePoint(g.lon, g.lat), 4326)) as val
                FROM grid g
                CROSS JOIN relevant_rasters r
                CROSS JOIN forest_boundary f
                WHERE
                    ST_Contains(f.geom, ST_SetSRID(ST_MakePoint(g.lon, g.lat), 4326))
                    AND ST_Value(r.rast, ST_SetSRID(ST_MakePoint(g.lon, g.lat), 4326)) IS NOT NULL
                LIMIT 2000
            """)
            
            result = db.execute(query, {
                "boundary_wkt": boundary_wkt,
                "min_lon": lon_min,
                "min_lat": lat_min,
                "lon_step": lon_step,
                "lat_step": lat_step,
                "sample_size": sample_size
            }).fetchall()
            
            print(f"[SteepSlope] Grid samples: {len(result)}")
            
            if not result or len(result) == 0:
                print(f"[SteepSlope] No grid data - returning fallback")
                raise ValueError("No grid data found")
            
            # Count by class
            class_counts = {}
            for row in result:
                c = int(row.val) if row.val else 0
                class_counts[c] = class_counts.get(c, 0) + 1
            print(f"[SteepSlope] Class distribution: {class_counts}")
            
            # Convert to list of dicts for the drawing loop
            raster_data = [{'i': row.i, 'j': row.j, 'val': row.val} for row in result]
            
            # Class colors (Forest Regulation 2079)
            class_colors = {
                1: (46, 204, 113, alpha),   # Green - Gentle
                2: (241, 196, 15, alpha),   # Yellow - Moderate
                3: (230, 126, 34, alpha),   # Orange - Sensitive
                4: (220, 38, 38, alpha)    # Red - Extreme
            }
            
            # Create 256x256 image using same approach as tile_service
            cell_size = 256 // sample_size  # 8
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Draw each grid cell with class-based colors
            for sample in raster_data:
                i = sample['i']
                j = sample['j']
                val = sample['val']
                
                if val is None:
                    continue
                
                class_code = int(val)
                
                # Only show cells in the selected classes
                if class_code not in show_classes:
                    continue  # Skip - transparent
                
                color = class_colors.get(class_code, (220, 38, 38, alpha))
                
                x1 = i * cell_size
                y1 = (sample_size - 1 - j) * cell_size  # Flip Y axis like tile_service
                x2 = x1 + cell_size
                y2 = y1 + cell_size
                
                draw.rectangle([x1, y1, x2, y2], fill=color)
            
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            print(f"[SteepSlope] Generated PNG with {len(raster_data)} data points, size={len(img_bytes.getvalue())} bytes")
            return Response(
                content=img_bytes.getvalue(),
                media_type="image/png",
                headers={
                    "Cache-Control": "public, max-age=3600",
                    "Content-Type": "image/png",
                    "Access-Control-Allow-Origin": "*"
                }
            )
             
        except Exception as e:
            print(f"[SteepSlope] Query failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback: return empty transparent tile
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return Response(
            content=img_bytes.getvalue(),
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Type": "image/png",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except HTTPException:
        raise
        
    except Exception as e:
        print(f"Steep slope tile error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Tile generation failed: {str(e)}")
