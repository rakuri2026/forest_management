import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, GeoJSON, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Card, Select, Spin, Empty, Tag, message } from 'antd';
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
      message.error('Failed to load map data');
    } finally {
      setLoading(false);
    }
  };

  // Filter features based on selected filters
  const filteredFeatures = activityGeoData?.features?.filter((feature: any) => {
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
    new Set(activityGeoData?.features?.map((f: any) => f.properties.sub_area_category) || [])
  );
  const uniqueProjects = Array.from(
    new Set(activityGeoData?.features?.map((f: any) => f.properties.project_name) || [])
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
          <div><strong>Project:</strong> ${props.project_name || 'N/A'}</div>
          <div><strong>Program:</strong> ${props.program || 'N/A'}</div>
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
        } as any);

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
            } as any}
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
