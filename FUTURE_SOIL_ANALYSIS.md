# Future Implementation: Enhanced Soil Analysis

**Status**: ⏳ PENDING - Temporarily Disabled (February 9, 2026)
**Priority**: Medium
**Database Impact**: None (uses existing `rasters.soilgrids_isric`)

---

## Why It Was Disabled

### Problem
The enhanced soil analysis feature was implemented on February 9, 2026, but caused **PostgreSQL to crash repeatedly** and enter recovery mode. Even with sequential band processing (8 separate queries), the `soilgrids_isric` raster analysis was too resource-intensive for the current PostgreSQL setup.

### Error Encountered
```
FATAL: the database system is in recovery mode
server closed the connection unexpectedly
```

### Current Workaround
Soil analysis functions (`analyze_soil()` and `analyze_soil_geometry()`) are **temporarily disabled** and return empty/null values. All other 15 analysis parameters work perfectly.

---

## What Was Implemented (But Disabled)

### Phase 1 Enhanced Soil Analysis Features

#### 1. **USDA 12-Class Soil Texture Classification**
**Replaces**: Simple 4-class system (Clay, Sandy, Silty, Loam)

**New 12 Classes**:
- Clay, Silty Clay, Sandy Clay
- Clay Loam, Silty Clay Loam, Sandy Clay Loam
- Loam, Silt Loam, Sandy Loam
- Silt, Loamy Sand, Sand

**Function**: `classify_usda_texture(clay_pct, sand_pct, silt_pct)`
**Location**: `backend/app/services/analysis.py` (line ~1229)

#### 2. **Soil Carbon Stock Calculation**
**Formula**: Carbon Stock (t/ha) = SOC (%) × Bulk Density (g/cm³) × Depth (cm) × 10

**Output**: Tonnes per hectare for topsoil (0-30cm)

**Purpose**:
- Carbon credit programs
- Climate change mitigation tracking
- Baseline for carbon monitoring

**Function**: `calculate_carbon_stock(soc_dg_kg, bulk_density_cg_cm3, depth_cm=30)`
**Location**: `backend/app/services/analysis.py` (line ~1260)

#### 3. **Fertility Assessment**
**Parameters Evaluated**:
- **pH**: Optimal 5.5-7.0 (25 points)
- **Soil Organic Carbon**: >2% optimal (25 points)
- **Nitrogen**: >0.15% optimal (25 points)
- **CEC (Cation Exchange Capacity)**: >150 mmol/kg optimal (25 points)

**Outputs**:
- Fertility class: Very High, High, Medium, Low, Very Low
- Fertility score: 0-100
- Limiting factors identified (e.g., "Low pH limits nutrient availability")

**Function**: `assess_fertility(ph, soc, nitrogen, cec)`
**Location**: `backend/app/services/analysis.py` (line ~1290)

#### 4. **Compaction Status with Alerts**
**Thresholds** (based on bulk density):
- <1.3 g/cm³: Not compacted ✅
- 1.3-1.6: Slight compaction ⚠️ (monitor)
- 1.6-1.8: Moderate compaction 🟠 (limits root growth)
- >1.8: Severe compaction 🔴 (intervention required)

**Function**: `assess_compaction(bulk_density_cg_cm3)`
**Location**: `backend/app/services/analysis.py` (line ~1340)

---

## Technical Details

### Database Schema
**Raster Table**: `rasters.soilgrids_isric`
**Bands** (8 total):
1. **Band 1**: clay_g_kg (Clay content in g/kg)
2. **Band 2**: sand_g_kg (Sand content in g/kg)
3. **Band 3**: silt_g_kg (Silt content in g/kg)
4. **Band 4**: ph_h2o (Soil pH in H2O)
5. **Band 5**: soc_dg_kg (Soil organic carbon in dg/kg)
6. **Band 6**: nitrogen_cg_kg (Nitrogen content in cg/kg)
7. **Band 7**: bdod_cg_cm3 (Bulk density in cg/cm³)
8. **Band 8**: cec_mmol_kg (Cation exchange capacity in mmol/kg)

**Pixel Size**: 250m × 250m
**Data Type**: Float32
**Source**: ISRIC SoilGrids

### Code Location
**Backend**: `backend/app/services/analysis.py`
- Lines ~1229-1370: Helper functions (commented out, ready to re-enable)
- Lines ~1403-1530: `analyze_soil()` function (disabled)
- Lines ~2303-2460: `analyze_soil_geometry()` function (disabled)

**Frontend**: `frontend/src/pages/CalculationDetail.tsx`
- Lines ~714-780: Whole forest soil display
- Lines ~1245-1320: Block-wise soil display
- Color-coded badges and visual indicators already implemented

---

## Future Implementation Options

### **Option 1: Optimize PostgreSQL Settings** (Recommended First)

**Increase Memory Allocation**:

Edit `C:\Program Files\PostgreSQL\18\data\postgresql.conf`:
```ini
# Memory Settings (increase from defaults)
shared_buffers = 512MB          # Default: 128MB
work_mem = 32MB                 # Default: 4MB
maintenance_work_mem = 256MB    # Default: 64MB
effective_cache_size = 2GB      # Default: 4GB

# Query Planning
random_page_cost = 1.1          # For SSD storage (default: 4.0)

# Checkpoint Settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
```

**After editing**, restart PostgreSQL:
```batch
net stop postgresql-x64-18
net start postgresql-x64-18
```

**Then re-enable soil analysis**:
1. Open `backend/app/services/analysis.py`
2. Find the disabled code blocks (marked with `# Original code disabled`)
3. Uncomment the main logic
4. Comment out the "return empty results" section
5. Restart backend server
6. Test with a small boundary file first

**Estimated Performance After Optimization**:
- Per-block analysis time: 8-12 seconds
- Whole forest analysis: 5-7 seconds
- No database crashes

---

### **Option 2: Simplify to Essential Bands Only**

Instead of processing all 8 bands, only analyze the most critical:

**3-Band Minimal Analysis**:
- Band 1: Clay (texture classification)
- Band 2: Sand (texture classification)
- Band 3: Silt (texture classification)

**Result**: USDA texture classification only, no fertility/compaction

**5-Band Moderate Analysis**:
- Bands 1-3: Texture (clay, sand, silt)
- Band 5: SOC (for carbon stock)
- Band 7: Bulk density (for carbon stock + compaction)

**Result**: Texture + carbon stock + compaction, no fertility

**Implementation**: Modify queries to skip unused bands.

---

### **Option 3: Async Background Processing**

**Architecture**:
1. Upload triggers immediate analysis (all except soil)
2. Soil analysis queued as background job
3. User sees "Soil analysis in progress..." message
4. Results update when complete (WebSocket or polling)

**Benefits**:
- No user-facing delays
- Can retry failed analyses
- Can schedule during low-traffic periods

**Technologies**:
- **Celery** (Python task queue)
- **Redis** (message broker)
- **WebSockets** (real-time updates)

**Complexity**: High (requires new infrastructure)

---

### **Option 4: Pre-computed Soil Data**

**Process**:
1. Pre-compute soil metrics for all 3,922 community forests
2. Store in new table: `precomputed_soil_data`
3. Lookup during analysis instead of querying raster

**Benefits**:
- Instant results (no computation)
- No PostgreSQL crashes
- Scalable to unlimited forests

**Drawbacks**:
- One-time heavy computation required
- Won't work for custom uploaded boundaries
- Requires periodic updates if soil data changes

**Hybrid Approach**:
- Use pre-computed for known forests
- Fall back to real-time for custom uploads

---

### **Option 5: External Microservice**

**Architecture**:
1. Create separate soil analysis service (separate server/container)
2. Main API calls soil service via HTTP/gRPC
3. Soil service has dedicated PostgreSQL connection pool
4. Results cached in Redis

**Benefits**:
- Isolates resource-intensive operations
- Can scale independently
- Main API never crashes

**Technologies**:
- **Docker** containers
- **Nginx** reverse proxy
- **Redis** caching layer

**Complexity**: Very High

---

## Recommended Implementation Path

### **Phase 1: Quick Win** (Estimated: 2-4 hours)
1. ✅ Optimize PostgreSQL settings (Option 1)
2. ✅ Test with small boundary file
3. ✅ Monitor PostgreSQL logs for crashes
4. ✅ If stable, re-enable for production

### **Phase 2: Fallback** (If Phase 1 fails, Estimated: 1-2 days)
1. Implement 5-band moderate analysis (Option 2)
2. Skip fertility assessment to reduce load
3. Keep texture + carbon stock + compaction

### **Phase 3: Long-term** (Future enhancement, Estimated: 1-2 weeks)
1. Implement async background processing (Option 3)
2. Better user experience
3. Scalable architecture

---

## Testing Plan

### **Test 1: Small Boundary** (1-5 hectares)
- Expected: Completes in 10-15 seconds
- If fails: PostgreSQL settings insufficient

### **Test 2: Medium Boundary** (20-50 hectares)
- Expected: Completes in 30-60 seconds
- If fails: Need to implement simplified analysis

### **Test 3: Large Boundary** (100+ hectares)
- Expected: Completes in 2-3 minutes
- If fails: Need async processing

### **Test 4: Multiple Concurrent Uploads**
- Expected: All complete without crashes
- If fails: Need connection pool tuning or microservice

---

## Success Metrics

When soil analysis is successfully re-enabled:

✅ **Stability**: No PostgreSQL crashes over 24 hours of testing
✅ **Performance**: Analysis completes in <30 seconds for typical forest (20-50 ha)
✅ **Accuracy**: Results match expected USDA classification
✅ **User Experience**: No noticeable delays or timeouts
✅ **Scalability**: Handles 10+ concurrent analyses without degradation

---

## Files to Modify When Re-enabling

### **Backend**
```
backend/app/services/analysis.py
  - Uncomment lines ~1441-1527 (analyze_soil function)
  - Uncomment lines ~2330-2456 (analyze_soil_geometry function)
  - Comment out "return empty results" sections
```

### **Frontend**
No changes needed - display logic already implemented with color-coded badges.

### **Database**
No schema changes needed - uses existing `rasters.soilgrids_isric`.

---

## Dependencies

**PostgreSQL Extensions**:
- ✅ PostGIS 3.6 (already installed)
- ✅ PostGIS Raster (already installed)

**Python Packages**:
- ✅ SQLAlchemy 2.0.45 (already installed)
- ✅ psycopg2 (already installed)
- ✅ GeoAlchemy2 (already installed)

**No new dependencies required.**

---

## Related Documentation

- `CLAUDE.md` - Full project development log
- `RESTART_GUIDE_2026_02_09.md` - System restart guide with soil analysis disabled
- `backend/app/services/analysis.py` - Source code with disabled functions

---

## Version History

| Date | Version | Status | Notes |
|------|---------|--------|-------|
| 2026-02-09 | 1.0 | Implemented | Phase 1 complete, all 4 features working |
| 2026-02-09 | 1.1 | Disabled | PostgreSQL crashes, temporarily disabled |
| TBD | 2.0 | Planned | Re-enable after PostgreSQL optimization |

---

## Contact & Questions

For questions about re-enabling soil analysis:
1. Read this document thoroughly
2. Test PostgreSQL optimization first (lowest complexity)
3. Monitor logs during testing
4. Document any new errors encountered

---

**Status**: Ready to re-enable when PostgreSQL is optimized
**Risk Level**: Medium (may crash PostgreSQL if settings unchanged)
**Impact**: High (valuable feature for forest management)
**Next Action**: Optimize PostgreSQL settings and test

---

END OF FUTURE SOIL ANALYSIS IMPLEMENTATION GUIDE
