# 4-Week Implementation Roadmap - Hybrid Approach

**Date:** February 10, 2026
**Approach:** Option C - Hybrid (Progressive Delivery)
**Status:** APPROVED - Ready to Start

---

## Overview

**Goal:** Deliver improved analysis UI, export functionality, and map generation in 4 weeks with functional system available after Week 2.

**Key Milestones:**
- ✅ **Week 1 Complete:** New UI with grouped sections live
- ✅ **Week 2 Complete:** Functional reports with 3 core maps
- ✅ **Week 3 Complete:** Enhanced reports with 6 maps
- ✅ **Week 4 Complete:** Complete system with all 9 maps

---

## Week 1: UI Redesign + Map Foundation

### Goals
- Reorganize Analysis tab with 6 grouped sections
- Implement collapsible card components
- Create map generation service foundation
- Users can see improved UI immediately

### Tasks

#### Days 1-2: Create Reusable UI Components
**Frontend Components:**

1. **MetricCard.tsx** - Key metric display card
   ```tsx
   <MetricCard
     icon="🌲"
     label="Total Area"
     value={145.6}
     unit="ha"
     color="green"
   />
   ```

2. **CollapsibleSection.tsx** - Expandable section container
   ```tsx
   <CollapsibleSection
     title="Forest Characteristics"
     icon="🌲"
     defaultExpanded={false}
   >
     {/* Content */}
   </CollapsibleSection>
   ```

3. **PercentageBar.tsx** - Visual percentage breakdown
   ```tsx
   <PercentageBar
     data={[
       { label: 'Dense', value: 45.2, color: 'green-600' },
       { label: 'Medium', value: 28.1, color: 'green-400' }
     ]}
   />
   ```

4. **EditableMetric.tsx** - Editable metric with inline editing
   (Wrapper around existing EditableCell)

**Deliverables:**
- 4 reusable components created
- Storybook/examples documented
- Unit tests written

#### Days 3-4: Restructure Analysis Tab

**Implement 6 Grouped Sections:**

1. **Key Metrics Dashboard** (Always visible)
   - 6 metric cards in grid
   - Area, Elevation, Carbon, Health, Aspect, Slope

2. **🌲 Forest Characteristics** (Collapsible)
   - Canopy Structure with percentage bar
   - Biomass & Carbon
   - Forest Health with color badges
   - Forest Type & Species (expandable list)

3. **🏔️ Terrain & Climate** (Collapsible)
   - Topography (elevation stats)
   - Slope distribution with percentage bar
   - Aspect distribution
   - Climate data (temperature, precipitation)

4. **📊 Land Cover & Change** (Collapsible)
   - Timeline view (1984 → 2000 → Current)
   - Forest Loss (by year)
   - Forest Gain
   - Fire Loss

5. **🌍 Soil Analysis** (Collapsible)
   - Texture & Composition
   - Fertility with color badges
   - Carbon Content
   - Compaction Status

6. **📍 Location & Context** (Collapsible)
   - Administrative boundaries (2-column grid)
   - Watershed & Hydrology
   - Geographic classifications
   - Directional features

**Deliverables:**
- CalculationDetail.tsx refactored with new structure
- All 30+ parameters reorganized into 6 sections
- Collapsible state management working
- Mobile responsive

#### Day 5: Map Service Foundation

**Backend Setup:**

1. Create `backend/app/services/map_generator.py`
   - MapGenerator class structure
   - Matplotlib configuration
   - Basic map elements (title, north arrow, scale, legend)
   - Helper functions

2. Install dependencies:
   ```bash
   pip install matplotlib>=3.5.0
   pip install geopandas>=0.12.0
   pip install rasterio>=1.3.0
   pip install contextily>=1.3.0
   pip install adjustText>=0.8
   ```

3. Test basic map rendering
   - Simple polygon plot
   - Save as PNG at 300 DPI
   - Verify A5 size (1748 × 2480 pixels)

**Deliverables:**
- Map service scaffolding complete
- Dependencies installed and tested
- Basic map rendering verified

### Week 1 Acceptance Criteria
- [ ] New UI visible on frontend with 6 sections
- [ ] Collapsible sections work correctly
- [ ] All existing data displays in new structure
- [ ] No functionality lost from old UI
- [ ] Map service can generate basic test map

---

## Week 2: Core Maps + Basic Export

### Goals
- Generate 3 essential maps (Boundary, Slope, Land Cover Change)
- Implement Excel export with maps embedded
- Implement Word export with maps embedded
- **System becomes functional for report generation**

### Tasks

#### Days 1-2: Boundary Map + Slope Map

**1. Boundary Map Generator**
- Plot forest boundary polygon
- Add block boundaries with labels
- Show block names and areas
- Coordinate grid overlay
- Professional cartographic styling

**Features:**
- Green fill for forest area
- Blue dashed lines for blocks
- Block labels centered in each block
- Legend showing block breakdown
- Title: "Forest Boundary Map - [Forest Name]"

**2. Slope Map Generator**
- Query `rasters.slope` dataset
- Clip to forest boundary
- Classify into 4 classes:
  - Gentle (0-15°) - Light Green
  - Moderate (15-30°) - Yellow
  - Steep (30-45°) - Orange
  - Very Steep (>45°) - Red
- Create legend with class percentages
- Title: "Slope Classification Map - [Forest Name]"

**Deliverables:**
- `generate_boundary_map()` working
- `generate_slope_map()` working
- Both maps save as high-quality PNG
- Maps tested with real forest data

#### Day 3: Land Cover Change Map

**Land Cover Change Map Generator**
- Query Hansen forest loss/gain datasets
- Show temporal change (2000-2023)
- Color scheme:
  - Dark Green: Stable forest (no change)
  - Red: Forest loss areas
  - Light Green: Forest gain areas
  - Gray: Non-forest areas
- Add timeline annotation showing change period
- Legend with hectare breakdown

**Deliverables:**
- `generate_landcover_change_map()` working
- Temporal data properly visualized
- Map tested with real forest data

#### Days 4-5: Export Functionality with Maps

**Excel Export Enhancement:**

1. Modify `ExcelReportGenerator`:
   - Add "Maps" sheet
   - Embed 3 PNG images in Excel
   - Link to images from Summary sheet
   - Images properly sized (A5 proportions)

2. Test Excel export:
   - Images display correctly
   - File size reasonable (<10MB)
   - Compatible with Excel 2007+

**Word Export Implementation:**

1. Create `WordReportGenerator` class:
   - Cover page
   - Table of contents (auto-generated)
   - Executive summary
   - Forest overview
   - Embed 3 maps in appropriate sections
   - Professional formatting

2. Map embedding:
   - Boundary map in Section 2 (Forest Overview)
   - Slope map in Section 4 (Terrain & Climate)
   - Land Cover Change in Section 5 (Land Cover & Change)
   - Full-page images at high resolution

**API Endpoints:**

```python
@router.get("/calculations/{calculation_id}/export/excel")
async def export_calculation_excel(...)

@router.get("/calculations/{calculation_id}/export/word")
async def export_calculation_word(...)

@router.get("/calculations/{calculation_id}/maps/{map_type}")
async def get_calculation_map(...)  # Single map download
```

**Frontend UI:**

Add export buttons to CalculationDetail header:
```tsx
<div className="flex gap-3">
  <button onClick={handleExportExcel}>
    📊 Export Excel
  </button>
  <button onClick={handleExportWord}>
    📄 Export Word
  </button>
  <button onClick={handleDownloadMaps}>
    🗺️ Download Maps
  </button>
</div>
```

**Deliverables:**
- Excel export working with 3 maps
- Word export working with 3 maps
- Export buttons in UI
- Download functionality tested
- User can generate reports end-to-end

### Week 2 Acceptance Criteria
- [ ] 3 maps generate successfully
- [ ] Excel export includes embedded maps
- [ ] Word export includes embedded maps
- [ ] Reports are functional and usable
- [ ] File sizes reasonable (<15MB)
- [ ] Export completes in <30 seconds

---

## Week 3: Additional Maps (Elevation, Aspect, Health)

### Goals
- Generate 3 more maps (total 6/9)
- Enhance report quality
- Add visualization improvements

### Tasks

#### Days 1-2: Elevation Map + Aspect Map

**1. Elevation/Topographic Map**
- Query `rasters.dem` dataset
- Create hillshade for 3D effect
- Add elevation contours (100m intervals)
- Color gradient from low (green) to high (brown/white)
- Show min/max elevation markers
- Title: "Topographic Map - Elevation Profile"

**Advanced features:**
- Hillshade overlay for terrain relief
- Contour labels at key intervals
- Elevation zones color-coded

**2. Aspect Map**
- Query `rasters.aspect` dataset
- 8-directional classification:
  - N (Blue), NE (Light Blue), E (Green), SE (Light Green)
  - S (Yellow), SW (Orange), W (Red), NW (Purple)
- Compass rose showing dominant direction
- Legend with percentage breakdown
- Title: "Aspect Map - Slope Orientation"

**Deliverables:**
- `generate_elevation_map()` working
- `generate_aspect_map()` working
- Maps visually appealing
- Tested with real data

#### Days 3-4: Forest Health Map

**Forest Health Map Generator**
- Query `rasters.nepal_forest_health` dataset
- 5-class classification:
  - Very Healthy (Dark Green)
  - Healthy (Green)
  - Moderate (Yellow)
  - Poor (Orange)
  - Very Poor (Red)
- Legend with percentage breakdown
- Highlight problem areas
- Title: "Forest Health Assessment Map"

**Deliverables:**
- `generate_forest_health_map()` working
- Color scheme professional
- Problem areas clearly visible

#### Day 5: Update Exports with 6 Maps

**Update Excel Generator:**
- Expand Maps sheet to include 6 images
- Update Summary sheet links
- Test file size and performance

**Update Word Generator:**
- Add 3 new maps to appropriate sections:
  - Elevation map in Section 4 (Terrain & Climate)
  - Aspect map in Section 4 (Terrain & Climate)
  - Forest Health map in Section 3 (Forest Characteristics)
- Update table of contents
- Verify formatting

**Deliverables:**
- Excel exports with 6 maps
- Word exports with 6 maps
- Reports significantly enhanced

### Week 3 Acceptance Criteria
- [ ] 6 maps generate successfully
- [ ] All maps have consistent styling
- [ ] Exports include all 6 maps
- [ ] Reports are comprehensive
- [ ] Map quality is professional

---

## Week 4: Complete Maps + Polish

### Goals
- Generate final 3 maps (total 9/9)
- Polish map styling and quality
- Complete documentation
- User testing and feedback

### Tasks

#### Days 1-2: Soil Map + Canopy Map + Context Map

**1. Soil Map**
- Query `rasters.soilgrids_isric` dataset
- Show soil texture classification
- Color-code fertility classes
- Show erosion risk areas (steep slopes + poor soil)
- Legend with texture types
- Title: "Soil Texture and Fertility Map"

**2. Canopy Cover Map**
- Query `rasters.canopy_height` dataset
- Show canopy height zones:
  - Dense (>15m) - Dark Green
  - Medium (10-15m) - Green
  - Sparse (5-10m) - Light Green
  - Open (<5m) - Yellow
- Height gradient color scheme
- Title: "Canopy Height and Density Map"

**3. Location/Context Map**
- Show forest location in district context
- Display district boundary
- Show adjacent forests (if data available)
- Add nearby settlements, roads, rivers
- Inset map showing district in province
- Basemap with OpenStreetMap or similar
- Title: "Location and Context Map"

**Challenge:** Context map is most complex - needs multiple data sources

**Deliverables:**
- All 9 maps generating successfully
- Context map with basemap integration
- Professional cartographic quality

#### Day 3: Map Styling Improvements

**Polish All Maps:**
- Consistent font sizes and styles
- Professional color schemes
- Better legend placement
- Scale bars on all maps
- Data source citations
- Proper north arrows
- Border styling

**Quality checks:**
- 300 DPI resolution verified
- A5 size correct (148mm × 210mm)
- Text readable when printed
- Colors print-friendly (not just screen-friendly)

**Deliverables:**
- All maps have consistent professional styling
- Print quality verified

#### Days 4-5: Testing, Documentation, User Guide

**Comprehensive Testing:**
- Test with multiple forests (small, medium, large)
- Test with single-block and multi-block forests
- Test edge cases (missing data, extreme values)
- Performance testing (generation time)
- File size testing (ensure <20MB)

**Documentation:**
1. **User Guide** - How to export reports
2. **Map Legend Guide** - What each map shows
3. **Technical Docs** - How maps are generated
4. **Troubleshooting** - Common issues

**User Acceptance Testing:**
- Have actual foresters test the system
- Generate sample reports for review
- Gather feedback on:
  - Map clarity and usefulness
  - Report completeness
  - Export functionality
  - Areas for improvement

**Bug Fixes:**
- Address any issues found during testing
- Optimize slow operations
- Improve error handling

**Deliverables:**
- Complete system tested and verified
- Documentation complete
- User feedback collected
- Bugs fixed

### Week 4 Acceptance Criteria
- [ ] All 9 maps generate successfully
- [ ] Reports are publication-quality
- [ ] System tested with real forests
- [ ] Documentation complete
- [ ] User feedback positive
- [ ] System ready for production use

---

## Technical Stack Summary

### Backend
- **Map Generation:** matplotlib, geopandas, rasterio
- **Excel Export:** openpyxl, xlsxwriter
- **Word Export:** python-docx
- **PDF Export:** reportlab or docx2pdf
- **Data Processing:** numpy, pandas, shapely

### Frontend
- **UI Components:** React, TypeScript, Tailwind CSS
- **Interactive Maps:** Leaflet (existing)
- **State Management:** React hooks
- **File Download:** Fetch API with blob handling

### Data Sources
- **Rasters:** 16 datasets in `rasters` schema
- **Vectors:** Forest boundaries, admin boundaries
- **Basemaps:** OpenStreetMap, contextily

---

## Risk Management

### Risk 1: Map Generation Too Slow
**Mitigation:**
- Cache generated maps (30 days)
- Background job processing for large forests
- Progress indicators during generation
- Optimize raster queries with spatial indexes

### Risk 2: File Sizes Too Large
**Mitigation:**
- Compress PNG images (pillow optimization)
- Limit image resolution where appropriate
- Offer "Quick" vs "High Quality" export options

### Risk 3: Missing Raster Data
**Mitigation:**
- Graceful fallback when data unavailable
- Show "Data Not Available" on map
- Include disclaimer in report

### Risk 4: Complex Basemap Integration
**Mitigation:**
- Use contextily for simple basemaps
- Fallback to plain boundary if basemap fails
- Context map is last priority (Week 4)

### Risk 5: User Adoption Issues
**Mitigation:**
- Provide training materials
- Create video tutorials
- Offer templates for customization
- Support channel for questions

---

## Success Metrics

### Quantitative
- Map generation time: <10 seconds per map
- Export generation time: <30 seconds total
- File sizes: <15MB for typical forest
- User adoption: 80% of users export reports within 2 weeks

### Qualitative
- User satisfaction: 4.5/5 or higher
- Report quality: Accepted by government agencies
- Feature requests: Backlog created from user feedback
- System reliability: <5% error rate

---

## Post-Week 4 Enhancements

### Phase 3 (Future)
1. **Batch Export** - Export multiple forests at once
2. **Custom Templates** - User-defined report sections
3. **Map Customization** - User-controlled colors, labels
4. **3D Visualizations** - Interactive 3D terrain views
5. **Time-Series Analysis** - Multi-year change detection
6. **Mobile App** - Field data collection integration
7. **API for Integration** - External system access
8. **Advanced Analytics** - Machine learning predictions

---

## Daily Standup Format

**What did we complete yesterday?**
**What are we working on today?**
**Any blockers or concerns?**

---

## Weekly Review Format

**Week N Review:**
- ✅ Completed tasks
- ⚠️ In-progress tasks
- ❌ Blocked or delayed tasks
- 📊 Metrics (generation time, file sizes, user feedback)
- 🎯 Next week priorities
- 💡 Learnings and improvements

---

## Communication Plan

### Stakeholders
- **Users (Foresters):** Weekly progress updates, demos
- **Management:** Weekly status reports
- **Development Team:** Daily standups, code reviews

### Channels
- **Slack/Teams:** Daily communication
- **Email:** Weekly summaries
- **Meetings:** Demo every Friday
- **Documentation:** Updated continuously in repo

---

## Rollout Plan

### Week 2: Soft Launch
- Deploy to staging environment
- Invite 5-10 beta testers
- Gather feedback
- Fix critical issues

### Week 3: Extended Beta
- Deploy improvements
- Expand to 20-30 users
- Monitor performance
- Document common issues

### Week 4: General Availability
- Deploy to production
- Announce to all users
- Provide training sessions
- Monitor and support

---

## Backup and Rollback Plan

### Backup Strategy
- Daily database backups
- Version control for all code
- Keep old UI version available (feature flag)
- Document rollback procedure

### Rollback Triggers
- Critical bugs affecting >50% of users
- Data corruption or loss
- Performance degradation >3x slower
- Security vulnerabilities discovered

**Rollback Time:** <1 hour to previous stable version

---

## Conclusion

This 4-week roadmap delivers a complete, professional forest analysis and reporting system using a progressive delivery approach. By Week 2, users have a functional system with improved UI and core reporting capabilities. By Week 4, the system is feature-complete with all 9 maps and publication-quality exports.

The hybrid approach balances speed of delivery with quality of output, allowing for user feedback and iteration throughout the development process.

---

**Status:** APPROVED - Ready to Start Week 1
**Next Action:** Create UI components (MetricCard, CollapsibleSection, PercentageBar)
**Start Date:** February 10, 2026
**Target Completion:** March 7, 2026 (4 weeks)

---

**Document Version:** 1.0
**Last Updated:** February 10, 2026
**Maintained By:** Forest Management System Team
