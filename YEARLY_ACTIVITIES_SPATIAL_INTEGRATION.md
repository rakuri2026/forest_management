# Yearly Activities - Spatial Integration Addendum

**Created:** April 5, 2026
**Status:** 📋 Planning Phase - Spatial Features
**Related:** YEARLY_ACTIVITIES_IMPLEMENTATION_PLAN.md

---

## Overview

This document extends the Yearly Activities feature to support **spatial assignment** of activities to forest blocks AND sub-areas, with **map visualization** to show where activities will take place.

### Use Cases

1. **Block-Level Activities**
   - "Thinning Operations" in Block A only
   - "Fire Line Maintenance" in Block B only

2. **Sub-Area-Level Activities**
   - "Tree Planting" in Plantation Area (sub-area)
   - "NTFP Collection Training" in Pro-Poor Income Generation zones
   - "Tourist Trail Maintenance" in Tourist Attraction areas
   - "Biodiversity Monitoring" in Bio-diversity Rich zones

3. **Map Visualization**
   - Show activity locations on map with color-coded markers
   - Click sub-area → see all planned activities for that zone
   - Filter activities by spatial location

---

## Database Schema Updates

### Modified Table: `proposed_yearly_activities`

Add `sub_area_id` column to link activities to specific sub-areas:

```sql
-- Migration: Add sub_area_id to proposed_yearly_activities

ALTER TABLE public.proposed_yearly_activities
ADD COLUMN sub_area_id UUID REFERENCES public.forest_sub_areas(id) ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX idx_proposed_activities_sub_area
ON public.proposed_yearly_activities(sub_area_id);

-- Add constraint: if sub_area_id is set, block_id must also be set
-- (sub-areas belong to blocks)
ALTER TABLE public.proposed_yearly_activities
ADD CONSTRAINT check_sub_area_has_block
CHECK (
  (sub_area_id IS NULL) OR
  (sub_area_id IS NOT NULL AND block_id IS NOT NULL)
);
```

### Spatial Assignment Rules

```
Activity Location Hierarchy:
├── No assignment → Applies to entire forest
├── Block only → Applies to entire block
└── Block + Sub-area → Applies to specific sub-area within block

Examples:
1. Activity without block/sub-area: "Forest Resource Survey" (whole forest)
2. Activity with block only: "Thinning Operations in Block A" (entire Block A)
3. Activity with block + sub-area: "Tree Planting in Plantation Area, Block A" (specific zone)
```

### Updated View: `v_proposed_activities_full`

```sql
CREATE OR REPLACE VIEW public.v_proposed_activities_full AS
SELECT
    pa.id AS proposed_activity_id,
    pa.calculation_id,

    -- Block info
    pa.block_id,
    fb.name AS block_name,

    -- Sub-area info
    pa.sub_area_id,
    fsa.name AS sub_area_name,
    fsa.category AS sub_area_category,
    fsa.area_hectares AS sub_area_area,
    fsa.geometry AS sub_area_geometry,

    -- Activity info
    pot.id AS potential_activity_id,
    pot.project_name,
    pot.program,
    pot.activity,
    pot.unit,

    -- Quantities
    pa.default_quantity,
    pa.default_yearly_budget,
    pa.status,
    pa.notes,

    -- Calculate total budget (10 years)
    pa.default_yearly_budget * 10 AS total_budget_10_years,

    -- Spatial location description
    CASE
        WHEN pa.sub_area_id IS NOT NULL THEN
            fsa.name || ' (' || fsa.category || '), ' || fb.name
        WHEN pa.block_id IS NOT NULL THEN
            fb.name || ' (entire block)'
        ELSE
            'Entire forest'
    END AS location_description,

    pa.created_at,
    pa.updated_at
FROM public.proposed_yearly_activities pa
JOIN public.potential_activities pot ON pa.potential_activity_id = pot.id
LEFT JOIN public.forest_blocks fb ON pa.block_id = fb.id
LEFT JOIN public.forest_sub_areas fsa ON pa.sub_area_id = fsa.id;
```

---

## Backend Implementation Updates

### Step 1: Update Models

**File:** `backend/app/models/yearly_activities.py`

```python
# Add to ProposedYearlyActivity class

class ProposedYearlyActivity(Base):
    """
    Activities selected by a specific community forest.
    Each forest can select multiple activities from the master list.
    """
    __tablename__ = "proposed_yearly_activities"
    __table_args__ = (
        # Add constraint: sub_area requires block
        CheckConstraint(
            '(sub_area_id IS NULL) OR (sub_area_id IS NOT NULL AND block_id IS NOT NULL)',
            name='check_sub_area_has_block'
        ),
        {"schema": "public"}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="CASCADE"), nullable=False)
    potential_activity_id = Column(UUID(as_uuid=True), ForeignKey("public.potential_activities.id", ondelete="CASCADE"), nullable=False)
    block_id = Column(UUID(as_uuid=True), ForeignKey("public.forest_blocks.id", ondelete="SET NULL"), nullable=True)

    # NEW: Sub-area assignment
    sub_area_id = Column(UUID(as_uuid=True), ForeignKey("public.forest_sub_areas.id", ondelete="SET NULL"), nullable=True)

    # ... rest of fields ...

    # Relationships
    calculation = relationship("Calculation", back_populates="proposed_activities")
    potential_activity = relationship("PotentialActivity", back_populates="proposed_activities")
    block = relationship("ForestBlock", foreign_keys=[block_id])

    # NEW: Sub-area relationship
    sub_area = relationship("ForestSubArea", foreign_keys=[sub_area_id])

    year_details = relationship("ActivityYearDetail", back_populates="proposed_activity", cascade="all, delete-orphan")

    def __repr__(self):
        location = "entire forest"
        if self.sub_area:
            location = f"{self.sub_area.name} ({self.sub_area.category})"
        elif self.block:
            location = f"{self.block.name}"
        return f"<ProposedYearlyActivity(id={self.id}, location={location})>"
```

### Step 2: Update Schemas

**File:** `backend/app/schemas/yearly_activities.py`

```python
# Update ProposedActivityBase

class ProposedActivityBase(BaseModel):
    potential_activity_id: UUID
    block_id: Optional[UUID] = None
    sub_area_id: Optional[UUID] = None  # NEW
    default_quantity: Decimal = Field(..., gt=0)
    default_yearly_budget: Decimal = Field(..., gt=0)
    notes: Optional[str] = None
    status: str = 'proposed'

    @validator('sub_area_id')
    def validate_sub_area_requires_block(cls, v, values):
        """Sub-area can only be set if block is also set"""
        if v is not None and values.get('block_id') is None:
            raise ValueError('sub_area_id requires block_id to be set')
        return v


class ProposedActivityResponse(ProposedActivityBase):
    id: UUID
    calculation_id: UUID
    created_at: datetime
    updated_at: datetime

    # Include potential activity details
    potential_activity: PotentialActivityResponse

    # Spatial details
    block_name: Optional[str] = None
    sub_area_name: Optional[str] = None  # NEW
    sub_area_category: Optional[str] = None  # NEW
    location_description: Optional[str] = None  # NEW: "Plantation Area (plantation), Block A"

    class Config:
        from_attributes = True


# NEW: Spatial filter schema

class SpatialActivityFilter(BaseModel):
    """Filter activities by spatial location"""
    block_id: Optional[UUID] = None
    sub_area_id: Optional[UUID] = None
    sub_area_category: Optional[str] = None  # e.g., "plantation", "protected"
    include_whole_forest: bool = True  # Include activities not assigned to specific locations


# NEW: Activity location summary

class ActivityLocationSummary(BaseModel):
    """Summary of activities by spatial location"""
    by_block: dict  # {block_name: count}
    by_sub_area_category: dict  # {category: count}
    by_sub_area: dict  # {sub_area_name: count}
    whole_forest_count: int  # Activities not assigned to specific locations
```

### Step 3: Update API Endpoints

**File:** `backend/app/api/yearly_activities.py`

```python
# Update list endpoint to support spatial filtering

@router.get("/calculations/{calculation_id}/proposed-activities", response_model=List[ProposedActivityWithYears])
async def list_proposed_activities(
    calculation_id: UUID,
    block_id: Optional[UUID] = Query(None),
    sub_area_id: Optional[UUID] = Query(None),  # NEW
    sub_area_category: Optional[str] = Query(None),  # NEW
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all proposed activities for a specific forest.
    Includes spatial filtering by block, sub-area, or sub-area category.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Query with eager loading
    query = db.query(ProposedYearlyActivity).options(
        joinedload(ProposedYearlyActivity.potential_activity),
        joinedload(ProposedYearlyActivity.block),
        joinedload(ProposedYearlyActivity.sub_area),  # NEW
        joinedload(ProposedYearlyActivity.year_details)
    ).filter(ProposedYearlyActivity.calculation_id == calculation_id)

    # Apply filters
    if block_id:
        query = query.filter(ProposedYearlyActivity.block_id == block_id)
    if sub_area_id:
        query = query.filter(ProposedYearlyActivity.sub_area_id == sub_area_id)
    if sub_area_category:
        # Join with ForestSubArea to filter by category
        query = query.join(ForestSubArea).filter(ForestSubArea.category == sub_area_category)
    if status:
        query = query.filter(ProposedYearlyActivity.status == status)

    proposed_activities = query.all()

    # Format response with spatial details
    result = []
    for pa in proposed_activities:
        data = ProposedActivityWithYears.from_orm(pa)

        if pa.block:
            data.block_name = pa.block.name

        # NEW: Add sub-area details
        if pa.sub_area:
            data.sub_area_name = pa.sub_area.name
            data.sub_area_category = pa.sub_area.category
            data.location_description = f"{pa.sub_area.name} ({pa.sub_area.category}), {pa.block.name}"
        elif pa.block:
            data.location_description = f"{pa.block.name} (entire block)"
        else:
            data.location_description = "Entire forest"

        result.append(data)

    return result


# NEW: Get activities with geometry for map visualization

@router.get("/calculations/{calculation_id}/proposed-activities/spatial", response_model=List[dict])
async def get_activities_with_geometry(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all proposed activities with their spatial geometries.
    Used for map visualization.

    Returns GeoJSON-like structure with activity details.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Query activities with spatial data
    from sqlalchemy import func

    query = db.query(
        ProposedYearlyActivity,
        PotentialActivity,
        ForestBlock,
        ForestSubArea,
        func.ST_AsGeoJSON(ForestSubArea.geometry).label('sub_area_geojson')
    ).join(
        PotentialActivity,
        ProposedYearlyActivity.potential_activity_id == PotentialActivity.id
    ).outerjoin(
        ForestBlock,
        ProposedYearlyActivity.block_id == ForestBlock.id
    ).outerjoin(
        ForestSubArea,
        ProposedYearlyActivity.sub_area_id == ForestSubArea.id
    ).filter(
        ProposedYearlyActivity.calculation_id == calculation_id
    )

    results = query.all()

    # Format for map display
    features = []
    for pa, pot, block, sub_area, geojson in results:
        if not sub_area:
            continue  # Skip activities without spatial geometry

        import json
        geometry = json.loads(geojson) if geojson else None

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "activity_id": str(pa.id),
                "activity_name": pot.activity,
                "project_name": pot.project_name,
                "program": pot.program,
                "sub_area_name": sub_area.name,
                "sub_area_category": sub_area.category,
                "block_name": block.name if block else None,
                "quantity": float(pa.default_quantity),
                "unit": pot.unit,
                "yearly_budget": float(pa.default_yearly_budget),
                "total_budget_10_years": float(pa.default_yearly_budget * 10),
                "status": pa.status,
                "location_description": f"{pot.activity} in {sub_area.name} ({sub_area.category})"
            }
        })

    return {
        "type": "FeatureCollection",
        "features": features
    }


# NEW: Get location summary

@router.get("/calculations/{calculation_id}/location-summary", response_model=ActivityLocationSummary)
async def get_activity_location_summary(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get summary of activities by spatial location.
    """
    # Verify ownership
    calculation = db.query(Calculation).filter(
        Calculation.id == calculation_id,
        Calculation.user_id == current_user.id
    ).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Get all proposed activities with relationships
    proposed_activities = db.query(ProposedYearlyActivity).options(
        joinedload(ProposedYearlyActivity.block),
        joinedload(ProposedYearlyActivity.sub_area)
    ).filter(ProposedYearlyActivity.calculation_id == calculation_id).all()

    # Initialize counters
    by_block = {}
    by_sub_area_category = {}
    by_sub_area = {}
    whole_forest_count = 0

    for pa in proposed_activities:
        # Count by block
        if pa.block:
            block_name = pa.block.name
            by_block[block_name] = by_block.get(block_name, 0) + 1
        else:
            whole_forest_count += 1

        # Count by sub-area
        if pa.sub_area:
            sub_area_name = pa.sub_area.name
            category = pa.sub_area.category

            by_sub_area[sub_area_name] = by_sub_area.get(sub_area_name, 0) + 1
            by_sub_area_category[category] = by_sub_area_category.get(category, 0) + 1

    return ActivityLocationSummary(
        by_block=by_block,
        by_sub_area_category=by_sub_area_category,
        by_sub_area=by_sub_area,
        whole_forest_count=whole_forest_count
    )
```

---

## Frontend Implementation Updates

### Step 1: Update API Client

**File:** `frontend/src/services/api.ts`

```typescript
// Update yearlyActivitiesApi object

export const yearlyActivitiesApi = {
  // ... existing methods ...

  // Updated: Add sub_area_id to filters
  listProposedActivities: async (
    calculationId: string,
    filters?: {
      block_id?: string;
      sub_area_id?: string;  // NEW
      sub_area_category?: string;  // NEW
      status?: string;
    }
  ): Promise<any[]> => {
    const params = filters || {};
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/proposed-activities`,
      { params }
    );
    return response.data;
  },

  // Updated: Add sub_area_id to create
  createProposedActivity: async (
    calculationId: string,
    data: {
      potential_activity_id: string;
      block_id?: string;
      sub_area_id?: string;  // NEW
      default_quantity: number;
      default_yearly_budget: number;
      notes?: string;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/yearly-activities/calculations/${calculationId}/proposed-activities`,
      data
    );
    return response.data;
  },

  // Updated: Add sub_area_id to update
  updateProposedActivity: async (
    proposedActivityId: string,
    data: {
      block_id?: string;
      sub_area_id?: string;  // NEW
      default_quantity?: number;
      default_yearly_budget?: number;
      notes?: string;
      status?: string;
    }
  ): Promise<any> => {
    const response = await api.patch(
      `/api/yearly-activities/proposed-activities/${proposedActivityId}`,
      data
    );
    return response.data;
  },

  // NEW: Get activities with geometry for map
  getActivitiesWithGeometry: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/proposed-activities/spatial`
    );
    return response.data;
  },

  // NEW: Get location summary
  getLocationSummary: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/location-summary`
    );
    return response.data;
  }
};
```

### Step 2: Update Activity Table Component

**File:** `frontend/src/components/YearlyActivities/ActivitySelectionTable.tsx`

```typescript
// Add to imports
import { forestsApi } from '../../services/api';  // To fetch sub-areas

// Add state for sub-areas
const [subAreas, setSubAreas] = useState<any[]>([]);
const [filteredSubAreas, setFilteredSubAreas] = useState<any[]>([]);

// Load blocks and sub-areas
useEffect(() => {
  loadSpatialData();
}, [calculationId]);

const loadSpatialData = async () => {
  try {
    // Fetch calculation to get blocks
    const calc = await forestsApi.getCalculation(calculationId);
    setBlocks(calc.blocks || []);

    // Fetch sub-areas
    const subAreasData = await forestsApi.getSubAreas(calculationId);
    setSubAreas(subAreasData || []);
  } catch (error: any) {
    console.error('Failed to load spatial data', error);
  }
};

// Filter sub-areas when block changes
const handleBlockChange = (blockId: string | undefined, record: any) => {
  // Update filtered sub-areas based on selected block
  if (blockId) {
    const filtered = subAreas.filter(sa => sa.block_id === blockId);
    setFilteredSubAreas(filtered);
  } else {
    setFilteredSubAreas([]);
  }

  // Clear sub-area if block changes
  form.setFieldValue('sub_area_id', undefined);
};

// Add columns for Block and Sub-Area

const columns: ColumnsType<any> = [
  // ... existing columns ...

  {
    title: 'Block',
    dataIndex: 'block_name',
    key: 'block_name',
    width: 150,
    render: (value, record) => {
      if (!record.is_selected) return '-';

      const editable = isEditing(record);
      return editable ? (
        <Form.Item name="block_id" style={{ margin: 0 }}>
          <Select
            placeholder="Select block"
            allowClear
            options={blocks.map(b => ({ label: b.name, value: b.id }))}
            onChange={(blockId) => handleBlockChange(blockId, record)}
          />
        </Form.Item>
      ) : (
        <span>{value || 'All blocks'}</span>
      );
    }
  },
  {
    title: 'Sub-Area',
    dataIndex: 'sub_area_name',
    key: 'sub_area_name',
    width: 180,
    render: (value, record) => {
      if (!record.is_selected) return '-';

      const editable = isEditing(record);
      const blockId = form.getFieldValue('block_id');

      return editable ? (
        <Form.Item
          name="sub_area_id"
          style={{ margin: 0 }}
          dependencies={['block_id']}
        >
          <Select
            placeholder={blockId ? "Select sub-area" : "Select block first"}
            allowClear
            disabled={!blockId}
            options={filteredSubAreas.map(sa => ({
              label: `${sa.name} (${sa.category})`,
              value: sa.id
            }))}
            showSearch
            optionFilterProp="label"
          />
        </Form.Item>
      ) : (
        <span>
          {value ? (
            <>
              {value}
              {record.sub_area_category && (
                <span style={{ marginLeft: 4, color: '#888', fontSize: '0.9em' }}>
                  ({record.sub_area_category})
                </span>
              )}
            </>
          ) : (
            'All sub-areas'
          )}
        </span>
      );
    }
  },

  // ... rest of columns ...
];
```

### Step 3: Create Map Visualization Component

**File:** `frontend/src/components/YearlyActivities/ActivityMapView.tsx` (NEW)

```typescript
import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Card, Select, Spin, Empty, Tag } from 'antd';
import { yearlyActivitiesApi } from '../../services/api';

interface ActivityMapViewProps {
  calculationId: string;
}

// Sub-area category colors (match your existing SUB_AREA_CATEGORIES)
const CATEGORY_COLORS: Record<string, string> = {
  'protected': '#ef4444',
  'plantation': '#10b981',
  'pro-poor': '#f59e0b',
  'religious': '#8b5cf6',
  'biodiversity': '#06b6d4',
  'tourist': '#ec4899',
  'office': '#6b7280',
  'private_land': '#dc2626'
};

const ActivityMapView: React.FC<ActivityMapViewProps> = ({ calculationId }) => {
  const [loading, setLoading] = useState(false);
  const [activityGeoData, setActivityGeoData] = useState<any>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | undefined>();
  const [selectedProject, setSelectedProject] = useState<string | undefined>();

  useEffect(() => {
    loadActivityGeoData();
  }, [calculationId]);

  const loadActivityGeoData = async () => {
    setLoading(true);
    try {
      const data = await yearlyActivitiesApi.getActivitiesWithGeometry(calculationId);
      setActivityGeoData(data);
    } catch (error: any) {
      console.error('Failed to load activity geometry', error);
    } finally {
      setLoading(false);
    }
  };

  // Filter features based on selected filters
  const filteredFeatures = activityGeoData?.features.filter((feature: any) => {
    const props = feature.properties;

    if (selectedCategory && props.sub_area_category !== selectedCategory) {
      return false;
    }

    if (selectedProject && props.project_name !== selectedProject) {
      return false;
    }

    return true;
  }) || [];

  // Get unique values for filters
  const uniqueCategories = Array.from(
    new Set(activityGeoData?.features.map((f: any) => f.properties.sub_area_category) || [])
  );
  const uniqueProjects = Array.from(
    new Set(activityGeoData?.features.map((f: any) => f.properties.project_name) || [])
  );

  // Style function based on sub-area category
  const styleFeature = (feature: any) => {
    const category = feature.properties.sub_area_category;
    const color = CATEGORY_COLORS[category] || '#3b82f6';

    return {
      fillColor: color,
      weight: 2,
      opacity: 0.8,
      color: color,
      fillOpacity: 0.4
    };
  };

  // Popup content
  const onEachFeature = (feature: any, layer: L.Layer) => {
    const props = feature.properties;

    const popupContent = `
      <div style="min-width: 250px;">
        <h3 style="margin: 0 0 8px 0; font-size: 14px; font-weight: bold;">
          ${props.activity_name}
        </h3>
        <div style="font-size: 12px; line-height: 1.6;">
          <div><strong>Location:</strong> ${props.sub_area_name} (${props.sub_area_category})</div>
          <div><strong>Block:</strong> ${props.block_name || 'N/A'}</div>
          <div><strong>Project:</strong> ${props.project_name}</div>
          <div><strong>Program:</strong> ${props.program}</div>
          <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #ddd;">
            <strong>Quantity:</strong> ${Number(props.quantity).toLocaleString()} ${props.unit}/year
          </div>
          <div><strong>Budget:</strong> NPR ${Number(props.yearly_budget).toLocaleString()}/year</div>
          <div><strong>Total (10 years):</strong> NPR ${Number(props.total_budget_10_years).toLocaleString()}</div>
          <div style="margin-top: 8px;">
            <span style="display: inline-block; padding: 2px 8px; background: #1890ff; color: white; border-radius: 4px; font-size: 11px;">
              ${props.status}
            </span>
          </div>
        </div>
      </div>
    `;

    layer.bindPopup(popupContent);
  };

  // Auto-fit map to show all features
  const MapBoundsUpdater: React.FC = () => {
    const map = useMap();

    useEffect(() => {
      if (filteredFeatures.length > 0) {
        const geojsonLayer = L.geoJSON({
          type: 'FeatureCollection',
          features: filteredFeatures
        });

        map.fitBounds(geojsonLayer.getBounds(), { padding: [50, 50] });
      }
    }, [filteredFeatures, map]);

    return null;
  };

  if (loading) {
    return <Spin tip="Loading activity map..." />;
  }

  if (!activityGeoData || filteredFeatures.length === 0) {
    return (
      <Empty
        description="No activities with spatial locations found. Assign activities to sub-areas to see them on the map."
      />
    );
  }

  return (
    <div>
      {/* Filter Controls */}
      <div style={{ marginBottom: '16px', display: 'flex', gap: '16px' }}>
        <Select
          placeholder="Filter by sub-area category"
          allowClear
          style={{ width: 250 }}
          value={selectedCategory}
          onChange={setSelectedCategory}
          options={uniqueCategories.map(cat => ({
            label: cat,
            value: cat
          }))}
        />
        <Select
          placeholder="Filter by project"
          allowClear
          style={{ width: 250 }}
          value={selectedProject}
          onChange={setSelectedProject}
          options={uniqueProjects.map(proj => ({
            label: proj,
            value: proj
          }))}
        />
        <div style={{ flex: 1, textAlign: 'right' }}>
          <Tag color="blue">{filteredFeatures.length} activities shown</Tag>
        </div>
      </div>

      {/* Map */}
      <div style={{ height: '600px', border: '1px solid #ddd', borderRadius: '4px', overflow: 'hidden' }}>
        <MapContainer
          center={[28.3949, 84.1240]}  // Nepal center
          zoom={10}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <GeoJSON
            key={JSON.stringify(filteredFeatures)}  // Force re-render on filter change
            data={{
              type: 'FeatureCollection',
              features: filteredFeatures
            }}
            style={styleFeature}
            onEachFeature={onEachFeature}
          />

          <MapBoundsUpdater />
        </MapContainer>
      </div>

      {/* Legend */}
      <Card size="small" style={{ marginTop: '16px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
          <strong style={{ width: '100%' }}>Sub-Area Categories:</strong>
          {Object.entries(CATEGORY_COLORS).map(([category, color]) => (
            <div key={category} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{
                width: '16px',
                height: '16px',
                backgroundColor: color,
                border: '1px solid #ddd',
                borderRadius: '2px'
              }} />
              <span style={{ fontSize: '12px', textTransform: 'capitalize' }}>
                {category.replace('_', ' ')}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default ActivityMapView;
```

### Step 4: Update Main Tab Component

**File:** `frontend/src/components/YearlyActivitiesTab.tsx`

```typescript
// Add import
import ActivityMapView from './YearlyActivities/ActivityMapView';

// Update tabItems
const tabItems: TabsProps['items'] = [
  {
    key: '1',
    label: 'Activity Selection',
    children: (
      <ActivitySelectionTable
        calculationId={calculationId}
        potentialActivities={potentialActivities}
        proposedActivities={proposedActivities}
        onUpdate={() => setRefreshKey(prev => prev + 1)}
      />
    )
  },
  {
    key: '2',
    label: 'Map View',  // NEW
    children: (
      <ActivityMapView calculationId={calculationId} />
    )
  },
  {
    key: '3',
    label: 'Summary & Reports',
    children: (
      <ActivitySummary
        calculationId={calculationId}
        summary={summary}
        onRefresh={() => setRefreshKey(prev => prev + 1)}
      />
    )
  }
];
```

---

## User Workflow with Spatial Assignment

### Example 1: Tree Planting in Plantation Area

```
1. Navigate to Yearly Activities tab
   ↓
2. Select "Tree Planting" activity (check box)
   ↓
3. Click "Edit" button
   ↓
4. Select Block: "Block A"
   ↓
5. Select Sub-Area: "Plantation Zone 1 (plantation)"
   ↓
6. Enter quantity: 5000 trees/year
   ↓
7. Enter budget: NPR 200,000/year
   ↓
8. Click "Save"
   ↓
9. Switch to "Map View" tab → See tree planting activity highlighted on Plantation Zone 1
```

### Example 2: Different Activities in Different Sub-Areas

```
Block A has 3 sub-areas:
├── Plantation Area → "Tree Planting" (5000 trees, NPR 200k)
├── Protected Zone → "Biodiversity Monitoring" (50 plots, NPR 80k)
└── Tourist Area → "Trail Maintenance" (5 km, NPR 50k)

All three activities show on map with different colors:
- Green area (plantation) = Tree planting marker
- Red area (protected) = Monitoring marker
- Pink area (tourist) = Trail maintenance marker
```

---

## Migration Script

**File:** `backend/alembic/versions/XXX_add_sub_area_to_activities.py`

```python
"""Add sub_area_id to proposed_yearly_activities

Revision ID: XXX
Revises: YYY
Create Date: 2026-04-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'XXX'
down_revision = 'YYY'  # Previous migration
branch_labels = None
depends_on = None


def upgrade():
    # Add sub_area_id column
    op.add_column(
        'proposed_yearly_activities',
        sa.Column('sub_area_id', postgresql.UUID(as_uuid=True), nullable=True),
        schema='public'
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_proposed_activities_sub_area',
        'proposed_yearly_activities', 'forest_sub_areas',
        ['sub_area_id'], ['id'],
        source_schema='public', referent_schema='public',
        ondelete='SET NULL'
    )

    # Add index
    op.create_index(
        'idx_proposed_activities_sub_area',
        'proposed_yearly_activities',
        ['sub_area_id'],
        schema='public'
    )

    # Add check constraint: sub_area requires block
    op.create_check_constraint(
        'check_sub_area_has_block',
        'proposed_yearly_activities',
        '(sub_area_id IS NULL) OR (sub_area_id IS NOT NULL AND block_id IS NOT NULL)',
        schema='public'
    )


def downgrade():
    # Remove check constraint
    op.drop_constraint(
        'check_sub_area_has_block',
        'proposed_yearly_activities',
        schema='public',
        type_='check'
    )

    # Remove index
    op.drop_index(
        'idx_proposed_activities_sub_area',
        table_name='proposed_yearly_activities',
        schema='public'
    )

    # Remove foreign key
    op.drop_constraint(
        'fk_proposed_activities_sub_area',
        'proposed_yearly_activities',
        schema='public',
        type_='foreignkey'
    )

    # Remove column
    op.drop_column('proposed_yearly_activities', 'sub_area_id', schema='public')
```

---

## Testing Checklist

### Spatial Assignment Tests

- [ ] Assign activity to block only (no sub-area)
- [ ] Assign activity to block + sub-area
- [ ] Verify sub-area dropdown is disabled until block is selected
- [ ] Verify sub-area dropdown only shows sub-areas from selected block
- [ ] Assign same activity to different blocks
- [ ] Assign same activity to different sub-areas in same block
- [ ] Verify validation: sub-area requires block

### Map Visualization Tests

- [ ] Load map with activities assigned to sub-areas
- [ ] Verify sub-areas are colored correctly by category
- [ ] Click sub-area → verify popup shows activity details
- [ ] Filter by sub-area category
- [ ] Filter by project name
- [ ] Verify map auto-fits to show all activities
- [ ] Verify activities without sub-areas don't appear on map

### Integration Tests

- [ ] Create activity → assign to plantation area → verify on map
- [ ] Edit activity → change sub-area → verify map updates
- [ ] Delete activity → verify removed from map
- [ ] Create sub-area → assign activity → verify appears on map

---

## Summary

This spatial integration provides:

✅ **Hierarchical Location Assignment**: Forest → Block → Sub-Area
✅ **Map Visualization**: See exactly where activities will happen
✅ **Category-Based Planning**: Different activities in different zones (plantation, protected, tourist, etc.)
✅ **Spatial Filtering**: Filter activities by location on map and in table
✅ **Click-to-View**: Click sub-area on map to see all planned activities
✅ **Budget by Location**: See budget breakdown by block and sub-area category

This makes yearly activity planning **spatially aware** and helps community forests visualize their 10-year management plan on a map!
