# Map Generation - Implementation Timing Decision

**Date:** February 10, 2026
**Context:** Deciding whether to implement map generation now or later

---

## Current Status

### What We Have ✅
- Interactive Leaflet map in frontend (Analysis tab)
- Boundary visualization working
- GeoJSON geometry available
- Block polygons can be displayed

### What We Need 📋
From requirements (CLAUDE.md Phase 2):
- **9 A5 PNG maps** (static images for reports)
- Various thematic maps
- Cartographic styling
- Suitable for printing and embedding in Word/Excel/PDF reports

---

## Map Requirements Analysis

### Required Maps (Government Submission Standard)

Based on Nepal's Community Forest Operational Plan (CFOP) requirements:

1. **Location/Context Map**
   - Shows forest location within district/province
   - Inset map showing position in Nepal
   - Roads, settlements, rivers
   - Scale bar, north arrow, legend

2. **Forest Boundary Map**
   - Detailed boundary with blocks labeled
   - Coordinate grid
   - Boundary vertices marked
   - Adjacent land use

3. **Topographic Map (Elevation)**
   - Elevation contours or hillshade
   - Color-coded elevation zones
   - 3D terrain visualization (optional)

4. **Slope Map**
   - Color-coded slope classes (Gentle/Moderate/Steep/Very Steep)
   - Percentage breakdown
   - Management implications zones

5. **Aspect Map**
   - 8-directional aspect classes with compass rose
   - Color scheme matching cardinal directions
   - Percentage distribution

6. **Forest Cover Map**
   - Current forest cover classification
   - Canopy density zones
   - Non-forest areas

7. **Land Cover Change Map**
   - Forest loss areas (red)
   - Forest gain areas (green)
   - Stable forest (green)
   - Timeline: 2000-2023

8. **Soil Map**
   - Soil texture classes
   - Fertility zones
   - Erosion risk areas

9. **Forest Health Map**
   - Color-coded health classes
   - Problem areas highlighted
   - Management priority zones

### Map Specifications

**Format:** PNG (high resolution)
**Size:** A5 (148mm × 210mm) at 300 DPI = 1748 × 2480 pixels
**Color:** Full color for digital, grayscale compatible
**Elements:** Title, legend, scale bar, north arrow, data sources, date
**Style:** Professional cartographic standard

---

## Implementation Options

### Option 1: Implement Maps NOW (Before Export)

**Sequence:**
1. Build map generation service (Week 1-2)
2. Implement UI redesign (Week 2-3)
3. Build export functionality with maps (Week 3-4)

**Pros:**
- ✅ Export functionality gets complete feature set immediately
- ✅ Maps can be tested independently
- ✅ Deliverable matches government requirements fully
- ✅ No need to revisit export code later
- ✅ Core Phase 2 requirement addressed

**Cons:**
- ❌ Users wait longer for improved UI
- ❌ Complex implementation (2+ weeks)
- ❌ Export delayed until maps complete
- ❌ Can't get feedback on exports until maps done

**Timeline:**
- Week 1-2: Map generation service
- Week 3: UI redesign
- Week 4: Export with maps
- **Total: 4 weeks**

---

### Option 2: Implement Maps LATER (After Export)

**Sequence:**
1. Implement UI redesign (Week 1)
2. Build export functionality (data only, simple maps) (Week 2)
3. Build comprehensive map generation (Week 3-4)
4. Enhance exports with full maps (Week 4)

**Pros:**
- ✅ Quick wins with improved UI
- ✅ Exports available sooner (even without fancy maps)
- ✅ Can get user feedback early
- ✅ Progressive enhancement approach
- ✅ Leaflet interactive maps already work

**Cons:**
- ❌ Exports incomplete initially
- ❌ Need to modify export code twice
- ❌ Users might submit incomplete reports
- ❌ Rework required to add maps later

**Timeline:**
- Week 1: UI redesign
- Week 2: Export (basic)
- Week 3-4: Map generation + export enhancement
- **Total: 4 weeks**

---

### Option 3: HYBRID Approach (Recommended) ⭐

**Sequence:**
1. **Week 1:** UI redesign with collapsible sections
2. **Week 1-2:** Basic map generation (3 essential maps)
3. **Week 2:** Export functionality with basic maps
4. **Week 3-4:** Complete remaining 6 maps + enhancements

**Phase 1 Maps (Essential):**
- Forest Boundary Map (with blocks)
- Slope Map (most important for management)
- Land Cover Change Map (shows forest loss/gain)

**Phase 2 Maps (Comprehensive):**
- Location/Context Map
- Elevation/Topographic Map
- Aspect Map
- Forest Health Map
- Soil Map
- Canopy Cover Map

**Pros:**
- ✅ Balanced approach
- ✅ UI improvements immediate
- ✅ Exports functional quickly with core maps
- ✅ Progressive delivery
- ✅ Users can start using system sooner
- ✅ Feedback guides remaining map development

**Cons:**
- ⚠️ Reports initially have only 3 maps instead of 9
- ⚠️ Need to clearly label as "Phase 1" to manage expectations

**Timeline:**
- Week 1: UI redesign + Map service foundation
- Week 2: 3 basic maps + Export with basic maps
- Week 3: 3 more maps (elevation, aspect, health)
- Week 4: Final 3 maps (soil, context, canopy) + polish
- **Total: 4 weeks, but functional after Week 2**

---

## Technical Implementation Requirements

### Backend Map Service

```python
# backend/app/services/map_generator.py

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
import numpy as np
from PIL import Image
import io
import geopandas as gpd
from shapely import wkt
import rasterio
from rasterio.mask import mask

class MapGenerator:
    """Generate static PNG maps for reports"""

    def __init__(self, calculation_data):
        self.data = calculation_data
        self.boundary_geom = wkt.loads(calculation_data['boundary_wkt'])
        self.blocks = calculation_data.get('blocks', [])

    def generate_boundary_map(self, output_path=None):
        """Generate forest boundary map with blocks"""
        fig, ax = plt.subplots(figsize=(5.83, 8.27))  # A5 size in inches

        # Plot boundary
        gdf = gpd.GeoDataFrame({'geometry': [self.boundary_geom]}, crs='EPSG:4326')
        gdf.plot(ax=ax, facecolor='lightgreen', edgecolor='darkgreen', linewidth=2)

        # Plot blocks
        for idx, block in enumerate(self.blocks):
            block_geom = wkt.loads(block['geometry_wkt'])
            block_gdf = gpd.GeoDataFrame({'geometry': [block_geom]}, crs='EPSG:4326')
            block_gdf.plot(ax=ax, facecolor='none', edgecolor='blue', linewidth=1.5, linestyle='--')

            # Add block label
            centroid = block_geom.centroid
            ax.text(centroid.x, centroid.y, f"Block {idx+1}\n{block['block_name']}",
                   ha='center', va='center', fontsize=10, weight='bold',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        # Add map elements
        self._add_map_elements(ax, "Forest Boundary Map", f"{self.data['forest_name']}")

        # Save or return
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close()
            return output_path
        else:
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
            buffer.seek(0)
            plt.close()
            return buffer

    def generate_slope_map(self, output_path=None):
        """Generate slope classification map"""
        # Query slope raster, clip to boundary, classify, render
        # Color scheme: Green (gentle) → Yellow (moderate) → Orange (steep) → Red (very steep)
        pass

    def generate_landcover_change_map(self, output_path=None):
        """Generate forest loss/gain map (2000-2023)"""
        # Red = Loss, Green = Gain, Dark Green = Stable
        pass

    def generate_elevation_map(self, output_path=None):
        """Generate elevation/topographic map with contours"""
        pass

    def generate_aspect_map(self, output_path=None):
        """Generate aspect map with compass colors"""
        pass

    def generate_forest_health_map(self, output_path=None):
        """Generate forest health classification map"""
        pass

    def generate_soil_map(self, output_path=None):
        """Generate soil texture/fertility map"""
        pass

    def generate_canopy_map(self, output_path=None):
        """Generate canopy height/density map"""
        pass

    def generate_context_map(self, output_path=None):
        """Generate location context map (forest in district)"""
        pass

    def generate_all_maps(self, output_dir):
        """Generate all 9 maps and return paths"""
        maps = {
            'boundary': self.generate_boundary_map(f"{output_dir}/01_boundary.png"),
            'slope': self.generate_slope_map(f"{output_dir}/02_slope.png"),
            'landcover_change': self.generate_landcover_change_map(f"{output_dir}/03_landcover_change.png"),
            'elevation': self.generate_elevation_map(f"{output_dir}/04_elevation.png"),
            'aspect': self.generate_aspect_map(f"{output_dir}/05_aspect.png"),
            'forest_health': self.generate_forest_health_map(f"{output_dir}/06_forest_health.png"),
            'soil': self.generate_soil_map(f"{output_dir}/07_soil.png"),
            'canopy': self.generate_canopy_map(f"{output_dir}/08_canopy.png"),
            'context': self.generate_context_map(f"{output_dir}/09_context.png"),
        }
        return maps

    def _add_map_elements(self, ax, title, subtitle):
        """Add standard map elements (title, scale, north arrow, legend)"""
        # Title
        ax.set_title(f"{title}\n{subtitle}", fontsize=14, weight='bold', pad=20)

        # North arrow (simple)
        ax.annotate('N', xy=(0.95, 0.95), xycoords='axes fraction',
                   fontsize=16, weight='bold', ha='center',
                   bbox=dict(boxstyle='round', facecolor='white', edgecolor='black'))
        ax.arrow(0.95, 0.90, 0, 0.03, transform=ax.transAxes,
                head_width=0.02, head_length=0.02, fc='black', ec='black')

        # Scale bar (approximate)
        # TODO: Calculate proper scale based on bounds

        # Remove axis ticks for cleaner look
        ax.set_xticks([])
        ax.set_yticks([])

        # Add coordinate labels
        ax.set_xlabel('Longitude', fontsize=8)
        ax.set_ylabel('Latitude', fontsize=8)

        # Add footer with source and date
        plt.figtext(0.5, 0.02, f"Generated: {self.data.get('created_at', 'N/A')} | Source: Forest Management System",
                   ha='center', fontsize=7, style='italic', color='gray')
```

### API Endpoint

```python
# backend/app/api/forests.py

@router.get("/calculations/{calculation_id}/maps")
async def get_calculation_maps(
    calculation_id: str,
    map_type: str = "all",  # all, boundary, slope, landcover_change, etc.
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate and return map images for a calculation

    Args:
        map_type: Which map(s) to generate (all, boundary, slope, etc.)

    Returns:
        If single map: PNG image
        If all: ZIP file with all 9 maps
    """
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    generator = MapGenerator(calculation.to_dict())

    if map_type == "all":
        # Generate all maps, zip them
        temp_dir = tempfile.mkdtemp()
        maps = generator.generate_all_maps(temp_dir)

        # Create zip
        zip_path = f"{temp_dir}/maps.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for name, path in maps.items():
                zipf.write(path, f"{name}.png")

        return FileResponse(zip_path, filename=f"{calculation.forest_name}_maps.zip")

    else:
        # Generate single map
        map_method = getattr(generator, f"generate_{map_type}_map", None)
        if not map_method:
            raise HTTPException(status_code=400, detail=f"Unknown map type: {map_type}")

        buffer = map_method()
        return Response(content=buffer.getvalue(), media_type="image/png")
```

### Required Libraries

```bash
# Additional dependencies for map generation
pip install matplotlib>=3.5.0
pip install geopandas>=0.12.0
pip install rasterio>=1.3.0
pip install contextily>=1.3.0  # For basemaps
pip install adjustText>=0.8  # For better label placement
```

---

## Recommendation: HYBRID APPROACH ⭐

### Why Hybrid is Best

1. **Immediate Value** - Users get UI improvements in Week 1
2. **Functional Reports** - 3 essential maps by Week 2 make reports usable
3. **Risk Mitigation** - Test map generation with core maps before building all 9
4. **User Feedback** - Learn what map styles/features users want most
5. **Progressive Enhancement** - Each week adds more capability
6. **Realistic Timeline** - 2 weeks to useful, 4 weeks to complete

### Implementation Schedule

**Week 1: Foundation + UI**
- Days 1-2: Create collapsible card UI components
- Days 3-4: Implement grouped sections (6 sections)
- Day 5: Map service foundation + basic matplotlib setup

**Week 2: Core Maps + Export**
- Days 1-2: Boundary map + Slope map
- Day 3: Land Cover Change map
- Days 4-5: Excel/Word export with 3 maps embedded

**Week 3: Additional Maps**
- Days 1-2: Elevation map + Aspect map
- Days 3-4: Forest Health map
- Day 5: Update exports with 6 maps

**Week 4: Complete Maps + Polish**
- Days 1-2: Soil map + Canopy map + Context map
- Day 3: Map styling improvements
- Days 4-5: Testing, documentation, user guide

### Deliverables Timeline

- **End of Week 1:** ✅ New UI live, better organization
- **End of Week 2:** ✅ Basic reports exportable with 3 maps
- **End of Week 3:** ✅ Enhanced reports with 6 maps
- **End of Week 4:** ✅ Complete system with all 9 maps

---

## Decision Criteria

### Choose NOW if:
- ❗ Government submission deadline is soon
- ❗ Complete reports are required immediately
- ❗ Users explicitly requesting map exports
- ❗ Have 4+ weeks of development time available

### Choose LATER if:
- ❗ Users need UI improvements urgently
- ❗ Interactive maps (Leaflet) are sufficient for now
- ❗ Data exports are higher priority than visualizations
- ❗ Want to validate approach before full investment

### Choose HYBRID if: ⭐
- ✅ Want balanced progress on all fronts
- ✅ Need something functional quickly
- ✅ Can iterate based on user feedback
- ✅ Have 2-4 weeks available
- ✅ **This is the recommended approach**

---

## Map Complexity Assessment

### Easy (1-2 days each)
- ✅ Boundary map (vector only)
- ✅ Slope map (single raster, 4 classes)
- ✅ Aspect map (single raster, 8 classes)

### Medium (2-3 days each)
- ⚠️ Land Cover Change map (multiple rasters, temporal comparison)
- ⚠️ Forest Health map (raster + classification)
- ⚠️ Canopy map (raster + height visualization)

### Hard (3-5 days each)
- ❌ Elevation/Topographic map (hillshade + contours + styling)
- ❌ Context/Location map (multiple data sources, administrative boundaries, basemap)
- ❌ Soil map (complex classification, fertility zones)

**Strategy:** Start with Easy maps, get them working, then tackle Medium and Hard

---

## Next Steps

1. **Get User Input** - Ask: "Do you need reports urgently, or can we do progressive delivery?"

2. **If Hybrid Approach Approved:**
   - Week 1: UI redesign (as planned)
   - Week 1-2: Implement 3 basic maps (boundary, slope, landcover change)
   - Week 2: Basic export functionality
   - Week 3-4: Complete remaining 6 maps

3. **Start with Map Service Foundation:**
   - Create `MapGenerator` class
   - Setup matplotlib configuration
   - Test boundary map generation
   - Verify raster data access

---

## Question for User

**"For the map generation, I recommend a HYBRID approach:**
- **Week 1:** UI improvements (you'll see better organization immediately)
- **Week 2:** 3 essential maps (Boundary, Slope, Forest Loss/Gain) + Basic exports
- **Week 3-4:** Remaining 6 maps (Elevation, Aspect, Health, Soil, Canopy, Context)

**This way:**
- ✅ You get UI improvements right away
- ✅ Reports are functional with core maps by Week 2
- ✅ Complete system with all 9 maps by Week 4

**Alternatively:**
- **Option A:** Do all 9 maps first (2-3 weeks), then UI + export
- **Option B:** Do UI + export first (2 weeks), then all 9 maps (2-3 weeks)

**Which approach works best for your needs?"**

---

**Document Version:** 1.0
**Last Updated:** February 10, 2026
**Recommendation:** HYBRID Approach (3 maps Week 2, 9 maps Week 4)
