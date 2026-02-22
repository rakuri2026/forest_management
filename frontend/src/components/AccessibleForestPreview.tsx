import { useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import { LatLngBounds } from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface AccessibleForestPreviewProps {
  previewData: any;
}

function FitBounds({ bounds }: { bounds: LatLngBounds }) {
  const map = useMap();
  map.fitBounds(bounds);
  return null;
}

export function AccessibleForestPreview({ previewData }: AccessibleForestPreviewProps) {
  const [showStats, setShowStats] = useState(true);

  if (!previewData) {
    return null;
  }

  const { boundary, accessible_forest, protected_forest, area_statistics } = previewData;

  // Calculate bounds from boundary
  const boundaryCoords = boundary?.geometry?.coordinates || [];
  let bounds: LatLngBounds | null = null;

  if (boundaryCoords.length > 0) {
    const allCoords: [number, number][] = [];

    const extractCoords = (coords: any) => {
      if (Array.isArray(coords)) {
        if (typeof coords[0] === 'number') {
          allCoords.push([coords[1], coords[0]]);
        } else {
          coords.forEach(extractCoords);
        }
      }
    };

    extractCoords(boundaryCoords);

    if (allCoords.length > 0) {
      bounds = new LatLngBounds(allCoords);
    }
  }

  const stats = area_statistics || {};

  return (
    <div className="space-y-4">
      {/* Statistics Panel */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex justify-between items-center mb-3">
          <h4 className="text-md font-semibold text-gray-900">
            Forest Area Classification
          </h4>
          <button
            onClick={() => setShowStats(!showStats)}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            {showStats ? 'Hide' : 'Show'} Details
          </button>
        </div>

        {showStats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-50 rounded p-3">
              <div className="text-xs text-gray-600 mb-1">Total Boundary Area</div>
              <div className="text-lg font-bold text-gray-900">
                {stats.total_boundary_area_ha?.toFixed(2) || 0} ha
              </div>
            </div>

            {stats.accessible_forest_area_ha !== undefined && (
              <div className="bg-green-50 rounded p-3 border border-green-200">
                <div className="text-xs text-green-700 mb-1">
                  ✓ Accessible Forest (GREEN)
                </div>
                <div className="text-lg font-bold text-green-900">
                  {stats.accessible_forest_area_ha.toFixed(2)} ha
                </div>
                <div className="text-xs text-green-600 mt-1">
                  {stats.accessible_forest_percentage?.toFixed(1)}% of total
                </div>
              </div>
            )}

            {stats.inaccessible_steep_forest_ha !== undefined && stats.inaccessible_steep_forest_ha > 0 && (
              <div className="bg-red-50 rounded p-3 border border-red-200">
                <div className="text-xs text-red-700 mb-1">
                  ⚠ Protected Forest (RED)
                </div>
                <div className="text-lg font-bold text-red-900">
                  {stats.inaccessible_steep_forest_ha.toFixed(2)} ha
                </div>
                <div className="text-xs text-red-600 mt-1">
                  {stats.inaccessible_steep_percentage?.toFixed(1)}% of total
                </div>
              </div>
            )}

            {stats.non_forest_area_ha !== undefined && stats.non_forest_area_ha > 0 && (
              <div className="bg-gray-50 rounded p-3">
                <div className="text-xs text-gray-600 mb-1">Non-Forest Area</div>
                <div className="text-lg font-bold text-gray-900">
                  {stats.non_forest_area_ha.toFixed(2)} ha
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {stats.non_forest_percentage?.toFixed(1)}% of total
                </div>
              </div>
            )}
          </div>
        )}

        {/* Legend */}
        <div className="mt-4 pt-3 border-t border-gray-200">
          <div className="text-xs font-semibold text-gray-700 mb-2">Map Legend:</div>
          <div className="flex flex-wrap gap-4 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 border-2 border-blue-600 bg-transparent"></div>
              <span className="text-gray-700">Boundary</span>
            </div>
            {accessible_forest && (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-green-500 opacity-40"></div>
                <span className="text-gray-700">Accessible Forest (Resource Effective Area)</span>
              </div>
            )}
            {protected_forest && (
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-500 opacity-40"></div>
                <span className="text-gray-700">Protected Forest (Steep Slopes)</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Map */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div style={{ height: '500px', width: '100%' }}>
          <MapContainer
            style={{ height: '100%', width: '100%' }}
            center={[28.3949, 84.124]}
            zoom={13}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {/* Accessible Forest Layer (GREEN) */}
            {accessible_forest?.geometry && (
              <GeoJSON
                key="accessible-forest"
                data={accessible_forest}
                style={{
                  fillColor: '#22c55e',
                  fillOpacity: 0.4,
                  color: '#16a34a',
                  weight: 1,
                }}
              />
            )}

            {/* Protected Forest Layer (RED) */}
            {protected_forest?.geometry && (
              <GeoJSON
                key="protected-forest"
                data={protected_forest}
                style={{
                  fillColor: '#ef4444',
                  fillOpacity: 0.4,
                  color: '#dc2626',
                  weight: 1,
                }}
              />
            )}

            {/* Boundary Layer (BLUE outline) */}
            {boundary?.geometry && (
              <GeoJSON
                key="boundary"
                data={boundary}
                style={{
                  fillColor: 'transparent',
                  fillOpacity: 0,
                  color: '#2563eb',
                  weight: 3,
                }}
              />
            )}

            {bounds && <FitBounds bounds={bounds} />}
          </MapContainer>
        </div>
      </div>

      {/* Slope Filter Note */}
      {area_statistics?.preview_note && (
        <div className="bg-orange-50 border border-orange-300 rounded-lg p-4 mb-4">
          <h5 className="text-sm font-semibold text-orange-900 mb-2">
            ⚠️ Slope Filtering Note:
          </h5>
          <p className="text-sm text-orange-800">
            {area_statistics.preview_note}
          </p>
          <p className="text-xs text-orange-700 mt-2">
            The preview map shows ALL tree cover areas. When you create the sampling design with slope filtering enabled,
            steep slopes will be automatically excluded from sample plot placement.
          </p>
        </div>
      )}

      {/* Explanation */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h5 className="text-sm font-semibold text-blue-900 mb-2">
          Understanding Forest Classification:
        </h5>
        <div className="text-sm text-blue-800 space-y-1">
          <p>
            <span className="font-semibold text-green-700">• Green Areas (Accessible Forest):</span>{' '}
            These are tree-covered areas. {area_statistics?.preview_note ? 'Slope filtering will be applied when you create the sampling design.' : 'Sample plots will be placed here for forest inventory.'}
          </p>
          {protected_forest && (
            <p>
              <span className="font-semibold text-red-700">• Red Areas (Protected Forest):</span>{' '}
              These are tree-covered areas with steep slopes that should be preserved for soil conservation and watershed protection.
            </p>
          )}
          <p className="mt-2 text-xs text-blue-600">
            💡 This visualization helps you understand which areas will be sampled before generating the sampling design.
          </p>
        </div>
      </div>

      {/* Technical Note about Raster vs Vector Area */}
      {stats.total_boundary_area_ha > 0 && (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-3">
          <h6 className="text-xs font-semibold text-yellow-900 mb-1">
            📊 Note on Area Calculations:
          </h6>
          <div className="text-xs text-yellow-800">
            <p>
              Raster-based area (from satellite pixels) may differ from vector-based boundary area by 10-15%.
              This is normal and expected due to pixel grid resolution (10m×10m). The raster analysis is accurate
              for forest classification purposes.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
