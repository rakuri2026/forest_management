# Analysis Page Structure Improvement Proposal

**Date:** February 10, 2026
**Status:** Draft Proposal
**Purpose:** Reorganize the Analysis tab for better information hierarchy and user experience

---

## Executive Summary

The current analysis page displays 30+ parameters in a single long table format, making it difficult for users to scan, understand, and extract insights. This proposal reorganizes the content into **6 logical groups** using a **card-based layout** with **collapsible sections** and **visual indicators**.

---

## Current Structure Analysis

### Current Layout
- Single massive table with 30+ rows
- Parameters listed sequentially without grouping
- Uniform visual treatment for all data types
- No summary or quick insights section
- Block-wise analysis duplicates the same long format

### Content Categories (Current Order)
1. Area, Extent, Elevation
2. Slope, Aspect, Canopy Height
3. Above Ground Biomass, Carbon Stock
4. Forest Health, Forest Type, Potential Species
5. Land Cover (1984, 2000, Current)
6. Forest Loss/Gain/Fire Loss
7. Temperature, Precipitation
8. Soil Texture, Carbon Stock, Fertility, Compaction
9. Province, District, Municipality, Ward, Watershed, River Basin
10. Geology, Physiography, Ecoregion, NASA Forest 2020
11. Natural Features (N/E/S/W)

---

## Proposed Structure

### Layout Philosophy
**"Progressive Disclosure + Visual Hierarchy"**
- Show key metrics prominently at top
- Group related information into themed cards
- Allow users to expand/collapse sections
- Use visual indicators (charts, badges, colors) for quick understanding
- Maintain detailed data access without overwhelming users

---

## Proposed 6-Section Layout

### **Section 1: Key Metrics Dashboard (Always Visible)**
**Purpose:** Quick overview of most important metrics
**Layout:** 4-column grid of metric cards with icons

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Total Area  │ Elevation   │ Carbon Stock│ Forest Health│
│ 145.6 ha    │ 1,234 m     │ 12,450 Mg   │ Healthy ✓   │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

**Metrics:**
- Total Area (hectares)
- Elevation Range (min-max with mean)
- Total Carbon Stock
- Forest Health Status (with color badge)
- Dominant Aspect (with compass icon)
- Dominant Slope Class

---

### **Section 2: Forest Characteristics (Collapsible)**
**Purpose:** Biophysical forest properties
**Icon:** 🌲 Tree icon
**Default:** Collapsed

**Content:**
- **Canopy Structure**
  - Dominant class with percentage breakdown
  - Mean height with visual bar chart
  - Class distribution (dense, medium, sparse, open)

- **Above Ground Biomass**
  - Total biomass (Mg)
  - Mean per hectare (Mg/ha)
  - Carbon stock derived (50% of AGB)

- **Forest Health**
  - Dominant health class
  - Percentage distribution with color-coded badges
  - 5-class breakdown (Very Healthy → Very Poor)

- **Forest Type & Species**
  - Dominant forest type
  - Type percentage distribution
  - **Potential Species Section** (Expandable)
    - Species cards with local/scientific names
    - Economic value badges (High/Medium/Low)
    - Role labels (Primary, Secondary, etc.)
    - "Show all X species" button

---

### **Section 3: Terrain & Climate (Collapsible)**
**Purpose:** Physical environmental conditions
**Icon:** 🏔️ Mountain icon
**Default:** Collapsed

**Content:**
- **Topography**
  - Elevation statistics (min/max/mean) with elevation profile mini-chart
  - Slope class distribution with visual pie/donut chart
  - Aspect distribution with compass rose visualization

- **Climate**
  - Annual mean temperature (°C)
  - Min temperature (coldest month)
  - Annual precipitation (mm/year)
  - Optional: Climate suitability indicator

---

### **Section 4: Land Cover & Change (Collapsible)**
**Purpose:** Historical and current land cover analysis
**Icon:** 📊 Timeline icon
**Default:** Collapsed

**Content:**
- **Temporal Land Cover Timeline**
  ```
  1984 ──────► 2000 ──────► Current
  [Dominant]   [Dominant]    [Dominant]
  ```
  - Visual timeline showing dominant land cover at each period
  - Percentage breakdowns for each year

- **Forest Change Detection (2001-2023)**
  - **Forest Loss**
    - Total loss (hectares)
    - Year-by-year bar chart
    - Peak loss years highlighted

  - **Forest Gain (2000-2012)**
    - Total gain (hectares)
    - Net change indicator

  - **Fire Loss**
    - Total fire-related loss
    - Year-by-year breakdown
    - Fire risk indicator if significant loss detected

---

### **Section 5: Soil Analysis (Collapsible)**
**Purpose:** Soil properties and fertility
**Icon:** 🌍 Soil layers icon
**Default:** Collapsed

**Content:**
- **Soil Texture**
  - Texture class with system (USDA/FAO)
  - Soil properties breakdown (Sand/Silt/Clay %)

- **Fertility Assessment**
  - Fertility class with color-coded badge
    - Very High (dark green), High (green), Medium (yellow), Low (orange), Very Low (red)
  - Fertility score (0-100)
  - Limiting factors (if any)

- **Carbon Content**
  - Organic carbon stock (t/ha)
  - Topsoil (0-30cm) specification

- **Compaction Status**
  - Compaction level with badge
  - Alert message if action needed

---

### **Section 6: Location & Context (Collapsible)**
**Purpose:** Administrative and geographic context
**Icon:** 📍 Location pin icon
**Default:** Collapsed

**Content:**
- **Administrative Boundaries** (2-column grid)
  - Province
  - District
  - Municipality
  - Ward

- **Watershed & Hydrology**
  - Watershed name
  - Major River Basin

- **Geographic Classifications**
  - Geology (percentage distribution)
  - Physiography (zone percentages)
  - Ecoregion (percentages)
  - NASA Forest 2020 classification

- **Directional Features (Within 100m)**
  - Compass grid showing features in each direction
  ```
  ┌─────┬───────┬─────┐
  │ NW  │ North │ NE  │
  ├─────┼───────┼─────┤
  │West │Forest │East │
  ├─────┼───────┼─────┤
  │ SW  │ South │ SE  │
  └─────┴───────┴─────┘
  ```

---

## Visual Design Mockup

### Overall Page Layout

```
┌─────────────────────────────────────────────────────────┐
│ [Analysis Tab] [Fieldbook] [Sampling] [Tree] [Bio]      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ ◄ KEY METRICS DASHBOARD (Always Visible) ►              │
│ ┌──────┬──────┬──────┬──────┬──────┬──────┐           │
│ │Area  │Elev  │Carbon│Health│Aspect│Slope │           │
│ │145 ha│1234m │12450 │  ✓   │  N   │Steep │           │
│ └──────┴──────┴──────┴──────┴──────┴──────┘           │
│                                                          │
│ ┌────────────────────────────────────────────┐          │
│ │ 🌲 Forest Characteristics            [▼]   │          │
│ └────────────────────────────────────────────┘          │
│                                                          │
│ ┌────────────────────────────────────────────┐          │
│ │ 🏔️ Terrain & Climate                 [▶]   │          │
│ └────────────────────────────────────────────┘          │
│                                                          │
│ ┌────────────────────────────────────────────┐          │
│ │ 📊 Land Cover & Change               [▶]   │          │
│ └────────────────────────────────────────────┘          │
│                                                          │
│ ┌────────────────────────────────────────────┐          │
│ │ 🌍 Soil Analysis                     [▶]   │          │
│ └────────────────────────────────────────────┘          │
│                                                          │
│ ┌────────────────────────────────────────────┐          │
│ │ 📍 Location & Context                [▶]   │          │
│ └────────────────────────────────────────────┘          │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Individual Card Design (Expanded State)

```
┌──────────────────────────────────────────────────┐
│ 🌲 Forest Characteristics              [▲]      │
├──────────────────────────────────────────────────┤
│                                                   │
│  Canopy Structure                                │
│  ┌─────────────────────────────────────┐        │
│  │ Dominant: Dense Forest (45.2%)      │        │
│  │ Mean Height: 18.5m                   │        │
│  │                                       │        │
│  │ ████████ Dense (45.2%)              │        │
│  │ █████ Medium (28.1%)                │        │
│  │ ██ Sparse (15.3%)                   │        │
│  │ █ Open (11.4%)                      │        │
│  └─────────────────────────────────────┘        │
│                                                   │
│  Above Ground Biomass                            │
│  • Total: 12,450 Mg                              │
│  • Mean: 85.5 Mg/ha                              │
│  • Carbon Stock: 6,225 Mg (50% of AGB)          │
│                                                   │
│  Forest Health                                   │
│  [Very Healthy] 60.2% | [Healthy] 30.1% | ...   │
│                                                   │
│  Forest Type & Species                           │
│  Dominant: Sal Forest (65.3%)                   │
│  [Show Potential Species ▼]                     │
│                                                   │
└──────────────────────────────────────────────────┘
```

---

## Implementation Details

### Technical Components

1. **MetricCard Component**
   ```tsx
   <MetricCard
     icon="🌲"
     label="Total Area"
     value="145.6"
     unit="ha"
     color="green"
   />
   ```

2. **CollapsibleSection Component**
   ```tsx
   <CollapsibleSection
     title="Forest Characteristics"
     icon="🌲"
     defaultExpanded={false}
   >
     {/* Content */}
   </CollapsibleSection>
   ```

3. **PercentageBar Component**
   ```tsx
   <PercentageBar
     data={[
       { label: 'Dense', value: 45.2, color: 'green-600' },
       { label: 'Medium', value: 28.1, color: 'green-400' },
       // ...
     ]}
   />
   ```

4. **CompassRose Component** (for Aspect visualization)
   ```tsx
   <CompassRose
     distribution={{
       N: 15.2, NE: 12.5, E: 18.3, SE: 10.1,
       S: 20.4, SW: 8.7, W: 9.6, NW: 5.2
     }}
     dominant="S"
   />
   ```

5. **TimelineChart Component** (for Land Cover changes)
   ```tsx
   <TimelineChart
     periods={[
       { year: 1984, dominant: 'Forest', percentage: 70 },
       { year: 2000, dominant: 'Dense Forest', percentage: 75 },
       { year: 2023, dominant: 'Dense Forest', percentage: 78 }
     ]}
   />
   ```

---

## Block-wise Analysis Improvements

### Current Issue
Each block repeats the entire long table format

### Proposed Solution
**Compact Card View with Expandable Details**

```
┌──────────────────────────────────────────────────┐
│ 📊 Detailed Block-wise Analysis                  │
├──────────────────────────────────────────────────┤
│                                                   │
│ ┌─────────────────────────────────────────┐     │
│ │ Block #1: Kathe  [Expand All ▼]        │     │
│ │ Area: 45.2 ha                            │     │
│ │                                           │     │
│ │ ┌──────┬──────┬──────┬──────┬──────┐   │     │
│ │ │Elev  │Slope │Aspect│Canopy│Health│   │     │
│ │ │1234m │Steep │ North│Dense │  ✓   │   │     │
│ │ └──────┴──────┴──────┴──────┴──────┘   │     │
│ │                                           │     │
│ │ [View Full Analysis ▼]                   │     │
│ └─────────────────────────────────────────┘     │
│                                                   │
│ ┌─────────────────────────────────────────┐     │
│ │ Block #2: Gairibas                       │     │
│ │ Area: 38.7 ha                            │     │
│ │ ...                                       │     │
│ └─────────────────────────────────────────┘     │
│                                                   │
└──────────────────────────────────────────────────┘
```

**Benefits:**
- Compact overview shows key metrics for each block
- "View Full Analysis" button expands to show grouped sections (same 6-section layout)
- Compare blocks easily with compact view
- Drill down when needed without overwhelming information

---

## User Benefits

### 1. **Faster Information Retrieval**
- Users find relevant information 3-5x faster with grouped sections
- Key metrics visible at a glance without scrolling

### 2. **Reduced Cognitive Load**
- Only see details when needed (progressive disclosure)
- Visual hierarchy guides attention to important metrics
- Related information grouped together

### 3. **Better Decision Making**
- Visual charts and indicators provide instant insights
- Temporal changes visible at a glance (timeline view)
- Comparisons easier with consistent formatting

### 4. **Improved Mobile Experience**
- Collapsible sections work better on small screens
- Metric cards stack vertically on mobile
- Less scrolling required

### 5. **Professional Presentation**
- Modern card-based layout
- Color-coded health indicators
- Visual charts and graphics
- Better for presentations and reports

---

## Implementation Priority

### Phase 1: Foundation (Week 1)
1. Create reusable components:
   - MetricCard
   - CollapsibleSection
   - PercentageBar
2. Implement Key Metrics Dashboard
3. Migrate existing table to grouped sections (no visuals yet)

### Phase 2: Visualization (Week 2)
1. Add CompassRose for Aspect
2. Add TimelineChart for Land Cover
3. Add bar charts for Forest Loss/Gain
4. Add color-coded badges and indicators

### Phase 3: Block-wise Enhancement (Week 3)
1. Implement compact block cards
2. Add expand/collapse functionality
3. Add "Compare Blocks" feature (optional)

### Phase 4: Polish & Testing (Week 4)
1. Mobile responsiveness
2. Accessibility improvements
3. Loading states and animations
4. User testing and feedback

---

## Risks & Mitigation

### Risk 1: Information Hidden Behind Clicks
**Mitigation:**
- Key metrics always visible at top
- Smart defaults (expand most important sections)
- "Expand All" / "Collapse All" buttons
- Remember user's expanded state in session

### Risk 2: Development Complexity
**Mitigation:**
- Build reusable components first
- Incremental migration (keep old view as fallback)
- Thorough testing before full rollout

### Risk 3: User Resistance to Change
**Mitigation:**
- Provide toggle to switch between old/new view
- Gradual rollout with feedback collection
- User documentation and tooltips
- Highlight benefits in release notes

---

## Success Metrics

### Quantitative
- 50% reduction in time to find specific information
- 70% reduction in scrolling distance
- Increased user engagement (time on page)

### Qualitative
- Positive user feedback on organization
- Reduced support requests about finding data
- Increased feature adoption (users exploring more sections)

---

## Alternative Approaches Considered

### 1. Tabbed Layout (Rejected)
**Pros:** Clear separation, no scrolling
**Cons:** Hides information, requires many clicks, poor for comparison

### 2. Accordion + Single Table (Rejected)
**Pros:** Simple to implement
**Cons:** Maintains long table problem, no visual improvements

### 3. Dashboard with Widgets (Rejected)
**Pros:** Very visual, customizable
**Cons:** Too complex, difficult to maintain, overkill for use case

### 4. Grouped Cards with Collapsible Sections (SELECTED) ✓
**Pros:** Progressive disclosure, visual hierarchy, mobile-friendly, professional
**Cons:** More development effort (mitigated by reusable components)

---

## Conclusion

The proposed grouped card-based layout with collapsible sections addresses all identified issues with the current structure:

✅ **Better Organization** - 6 logical groups instead of flat list
✅ **Progressive Disclosure** - Show details on demand
✅ **Visual Hierarchy** - Key metrics prominent, details collapsible
✅ **Improved Scannability** - Icons, colors, charts aid quick understanding
✅ **Mobile Friendly** - Collapsible sections work well on small screens
✅ **Professional** - Modern design patterns, better for presentations

**Recommendation:** Proceed with phased implementation starting with Phase 1 (Foundation) to validate approach with real users before investing in full visualization suite.

---

**Next Steps:**
1. Review and approve this proposal
2. Create detailed component specifications
3. Design visual mockups in Figma/design tool
4. Begin Phase 1 implementation
5. Gather user feedback after Phase 1
6. Iterate based on feedback before Phase 2

---

**Document Version:** 1.0
**Last Updated:** February 10, 2026
**Author:** Forest Management System Team
**Status:** Awaiting Review & Approval
