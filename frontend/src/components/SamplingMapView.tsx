import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap, LayersControl } from 'react-leaflet';
import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { samplingApi } from '../services/api';

// Fix Leaflet default marker icon
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Component to handle auto-zoom and scale
function MapController({ geometry }: { geometry: any }) {
  const map = useMap();

  useEffect(() => {
    // Add scale control
    const scaleControl = L.control.scale({
      position: 'bottomleft',
      metric: true,
      imperial: false,
      maxWidth: 150
    });
    scaleControl.addTo(map);

    // Auto-zoom to geometry
    if (geometry) {
      const geoJsonLayer = L.geoJSON(geometry);
      const bounds = geoJsonLayer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [50, 50] });
      }
    }

    return () => {
      map.removeControl(scaleControl);
    };
  }, [geometry, map]);

  return null;
}

// North Arrow Component
function NorthArrow() {
  return (
    <div className="absolute top-4 right-4 z-[1000] bg-white rounded-lg shadow-lg p-2 border border-gray-300">
      <div className="flex flex-col items-center">
        <div className="text-sm font-bold text-gray-800 mb-1">N</div>
        <svg width="30" height="50" viewBox="0 0 30 60">
          <line x1="15" y1="10" x2="15" y2="50" stroke="#333" strokeWidth="2"/>
          <polygon points="15,5 10,20 15,18 20,20" fill="#1a1a1a" stroke="#000" strokeWidth="1"/>
          <polygon points="15,18 10,20 15,50 20,20" fill="#ffffff" stroke="#000" strokeWidth="1"/>
        </svg>
      </div>
    </div>
  );
}

interface SamplingMapViewProps {
  designId: string;
}

export function SamplingMapView({ designId }: SamplingMapViewProps) {
  const [mapLayers, setMapLayers] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMapLayers();
  }, [designId]);

  const loadMapLayers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await samplingApi.getMapLayers(designId);
      setMapLayers(response);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load map layers');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96 bg-gray-50 rounded-lg">
        <div className="text-gray-600">Loading map...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="text-red-700">{error}</div>
      </div>
    );
  }

  if (!mapLayers) {
    return null;
  }

  // Styles for different layers
  const boundaryStyle = {
    color: '#2563eb',
    weight: 3,
    opacity: 1,
    fillOpacity: 0
  };

  const accessibleForestStyle = {
    color: '#10b981',
    weight: 1,
    opacity: 0.8,
    fillColor: '#10b981',
    fillOpacity: 0.3
  };

  // Function to create numbered marker icons for sampling points
  const createNumberedIcon = (plotNumber: number) => {
    return new L.DivIcon({
      className: 'custom-numbered-marker',
      html: `
        <div style="
          background-color: transparent;
          width: 16px;
          height: 16px;
          border-radius: 50%;
          border: 2px solid #fbbf24;
          box-shadow: 0 1px 3px rgba(0,0,0,0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          color: white;
          font-size: 9px;
          font-family: Arial, sans-serif;
          text-shadow: 1px 1px 2px rgba(0,0,0,0.9), -1px -1px 2px rgba(0,0,0,0.9);
        ">
          ${plotNumber}
        </div>
      `,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
      popupAnchor: [0, -8],
    });
  };

  // Function to create block name labels
  const createBlockLabel = (blockName: string) => {
    return new L.DivIcon({
      className: 'custom-block-label',
      html: `
        <div style="
          background-color: transparent;
          padding: 4px 8px;
          font-weight: bold;
          color: white;
          font-size: 14px;
          font-family: Arial, sans-serif;
          text-shadow: 2px 2px 4px rgba(0,0,0,0.9), -1px -1px 3px rgba(0,0,0,0.9);
          white-space: nowrap;
          pointer-events: none;
        ">
          ${blockName}
        </div>
      `,
      iconSize: [0, 0],
      iconAnchor: [0, 0],
    });
  };

  // Function to calculate polygon centroid
  const getPolygonCentroid = (coordinates: any): [number, number] | null => {
    try {
      // Handle different GeoJSON geometry types
      let coords = coordinates;
      if (coordinates[0] && Array.isArray(coordinates[0][0])) {
        // Polygon or MultiPolygon - use first ring
        coords = coordinates[0];
      }

      let sumLat = 0;
      let sumLon = 0;
      let count = 0;

      coords.forEach((coord: number[]) => {
        sumLon += coord[0];
        sumLat += coord[1];
        count++;
      });

      if (count === 0) return null;
      return [sumLat / count, sumLon / count];
    } catch (error) {
      console.error('Error calculating centroid:', error);
      return null;
    }
  };

  return (
    <div className="relative">
      {/* Map Legend */}
      <div className="absolute top-4 left-4 z-[1000] bg-white rounded-lg shadow-lg p-3 border border-gray-300 max-w-xs">
        <h3 className="text-sm font-bold text-gray-800 mb-2">Map Legend</h3>
        <div className="space-y-1 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-blue-600 rounded"></div>
            <span>Forest Boundary</span>
          </div>
          {mapLayers.accessible_forest && (
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-green-500 opacity-50 border border-green-600 rounded"></div>
              <span>Accessible Forest Area</span>
            </div>
          )}
          <div className="flex items-center gap-2">
            <div style={{
              width: '16px',
              height: '16px',
              backgroundColor: 'transparent',
              border: '2px solid #fbbf24',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '9px',
              fontWeight: 'bold',
              color: 'white',
              textShadow: '1px 1px 2px rgba(0,0,0,0.9)'
            }}>1</div>
            <span>Sample Plot Locations (numbered)</span>
          </div>
        </div>

        {/* Filter Info */}
        {mapLayers.filter_settings && (
          <div className="mt-3 pt-3 border-t border-gray-200">
            <div className="text-xs text-gray-600">
              <div className="font-semibold mb-1">Active Filters:</div>
              {mapLayers.filter_settings.filter_tree_cover && (
                <div>✓ Tree Cover Only</div>
              )}
              {mapLayers.filter_settings.filter_slope && (
                <div>✓ Slope ≤ {mapLayers.filter_settings.max_slope_degrees}°</div>
              )}
              {!mapLayers.filter_settings.filter_tree_cover && !mapLayers.filter_settings.filter_slope && (
                <div className="text-gray-500">No filters applied</div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* North Arrow */}
      <NorthArrow />

      {/* Map Container */}
      <MapContainer
        style={{ height: '600px', width: '100%' }}
        className="rounded-lg shadow-lg"
        zoom={13}
        zoomControl={true}
        attributionControl={true}
      >
        {/* Basemap Layer Control */}
        <LayersControl position="topright">
          {/* OpenStreetMap */}
          <LayersControl.BaseLayer name="Street Map">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>

          {/* Satellite Basemap - Esri World Imagery */}
          <LayersControl.BaseLayer checked name="Satellite">
            <TileLayer
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={19}
            />
          </LayersControl.BaseLayer>

          {/* Satellite with Labels */}
          <LayersControl.BaseLayer name="Satellite + Labels">
            <TileLayer
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={19}
            />
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              opacity={0.3}
            />
          </LayersControl.BaseLayer>

          {/* Terrain Basemap */}
          <LayersControl.BaseLayer name="Terrain">
            <TileLayer
              attribution='&copy; <a href="https://www.opentopomap.org/">OpenTopoMap</a>'
              url="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png"
              maxZoom={17}
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        {/* Forest Boundary Layer */}
        {mapLayers.boundary && (
          <GeoJSON
            data={mapLayers.boundary}
            style={boundaryStyle}
            onEachFeature={(feature, layer) => {
              layer.bindPopup(`
                <div class="text-sm">
                  <strong>${feature.properties.name || 'Forest Boundary'}</strong>
                </div>
              `);
            }}
          />
        )}

        {/* Block Name Labels */}
        {mapLayers.boundary && mapLayers.boundary.features && (
          mapLayers.boundary.features.map((feature: any, index: number) => {
            const blockName = feature.properties.name || feature.properties.block_name || `Block ${index + 1}`;
            const centroid = getPolygonCentroid(feature.geometry.coordinates);

            if (!centroid) return null;

            return (
              <Marker
                key={`label-${index}`}
                position={centroid}
                icon={createBlockLabel(blockName)}
                interactive={false}
              />
            );
          })
        )}

        {/* Accessible Forest Area Layer */}
        {mapLayers.accessible_forest && (
          <GeoJSON
            data={mapLayers.accessible_forest}
            style={accessibleForestStyle}
            onEachFeature={(feature, layer) => {
              layer.bindPopup(`
                <div class="text-sm">
                  <strong>Accessible Forest Area</strong><br/>
                  <span class="text-xs text-gray-600">
                    Tree cover with slope ≤ ${mapLayers.filter_settings?.max_slope_degrees || 45}°
                  </span>
                </div>
              `);
            }}
          />
        )}

        {/* Sampling Points Layer - Numbered Markers */}
        {mapLayers.sampling_points && mapLayers.sampling_points.features && (
          mapLayers.sampling_points.features.map((feature: any, index: number) => {
            const coords = feature.geometry.coordinates;
            const plotNumber = feature.properties.plot_number || (index + 1);

            return (
              <Marker
                key={index}
                position={[coords[1], coords[0]]}
                icon={createNumberedIcon(plotNumber)}
              >
                <Popup>
                  <div className="text-sm">
                    <strong className="text-red-600">Plot #{plotNumber}</strong><br/>
                    <span className="text-gray-700">Block: {feature.properties.block_name}</span><br/>
                    <span className="text-xs text-gray-500">
                      GPS: {coords[1].toFixed(6)}°N, {coords[0].toFixed(6)}°E
                    </span>
                  </div>
                </Popup>
              </Marker>
            );
          })
        )}

        {/* Map Controller */}
        <MapController geometry={mapLayers.boundary?.geometry} />
      </MapContainer>

      {/* Map Info Footer */}
      <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2">
        <div className="flex justify-between items-center">
          <div>
            <span className="font-semibold">Total Sampling Points:</span>{' '}
            {mapLayers.sampling_points?.features?.length || 0}
          </div>
          <div>
            <span className="font-semibold">Basemap:</span> Switch using layer control (top-right)
          </div>
        </div>
      </div>
    </div>
  );
}
