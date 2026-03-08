import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import { GPSPoint, gpsPointsToPolygon } from '../../utils/gpsUtils';
import {
  validatePolygonGeometry,
  calculateAreaHectares,
  simplifyPolygon,
  formatArea,
} from '../../utils/geometryValidation';
import BaseMapSelector from './BaseMapSelector';

interface PolygonCreatorProps {
  gpsPoints?: GPSPoint[];
  onPolygonChange: (polygon: any) => void;
  initialPolygon?: any;
}

export interface PolygonCreatorHandle {
  zoomToBounds: (bounds: [number, number, number, number]) => void;
  setWardBoundary: (geometry: any) => void;
}

// Component to capture map reference
const MapRefCapture: React.FC<{ onMapReady: (map: L.Map) => void }> = ({ onMapReady }) => {
  const map = useMap();

  useEffect(() => {
    if (map) {
      onMapReady(map);
    }
  }, [map, onMapReady]);

  return null;
};

// Map component with Leaflet-Geoman drawing controls
const DrawingControls: React.FC<{
  mode: 'auto' | 'manual';
  onPolygonCreated: (polygon: any) => void;
  initialPolygon?: any;
}> = ({ mode, onPolygonCreated, initialPolygon }) => {
  const map = useMap();
  const layerRef = useRef<L.Layer | null>(null);

  useEffect(() => {
    if (mode === 'manual') {
      // Enable Leaflet-Geoman controls
      map.pm.addControls({
        position: 'topleft',
        drawPolygon: true,
        drawMarker: false,
        drawCircle: false,
        drawCircleMarker: false,
        drawPolyline: false,
        drawRectangle: true,
        editMode: true,
        dragMode: false,
        cutPolygon: false,
        removalMode: true,
      });

      // Listen for polygon creation
      const handleCreate = (e: any) => {
        const layer = e.layer;
        const geoJSON = layer.toGeoJSON();
        layerRef.current = layer;
        onPolygonCreated(geoJSON.geometry);
      };

      // Listen for polygon editing
      const handleEdit = (e: any) => {
        const layers = e.layers;
        layers.eachLayer((layer: any) => {
          const geoJSON = layer.toGeoJSON();
          onPolygonCreated(geoJSON.geometry);
        });
      };

      map.on('pm:create', handleCreate);
      map.on('pm:edit', handleEdit);

      return () => {
        map.pm.removeControls();
        map.off('pm:create', handleCreate);
        map.off('pm:edit', handleEdit);

        // Remove drawn layer if exists
        if (layerRef.current) {
          map.removeLayer(layerRef.current);
        }
      };
    }
  }, [mode, map, onPolygonCreated]);

  // Load initial polygon if exists
  useEffect(() => {
    if (initialPolygon && mode === 'manual') {
      const geoJsonLayer = L.geoJSON(initialPolygon, {
        pmIgnore: false,
      });
      geoJsonLayer.addTo(map);
      layerRef.current = geoJsonLayer;

      // Fit bounds to polygon
      map.fitBounds(geoJsonLayer.getBounds(), { padding: [50, 50] });
    }
  }, [initialPolygon, map, mode]);

  return null;
};

const PolygonCreator = forwardRef<PolygonCreatorHandle, PolygonCreatorProps>(({
  gpsPoints = [],
  onPolygonChange,
  initialPolygon,
}, ref) => {
  const [mode, setMode] = useState<'auto' | 'manual'>('auto');
  const [polygon, setPolygon] = useState<any>(initialPolygon);
  const [error, setError] = useState<string>('');
  const [validation, setValidation] = useState<{
    valid: boolean;
    error?: string;
    warnings?: string[];
  } | null>(null);

  // Refs for map control
  const mapRef = useRef<L.Map | null>(null);
  const wardBoundaryLayerRef = useRef<L.GeoJSON | null>(null);

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    zoomToBounds: (bounds: [number, number, number, number]) => {
      console.log('[PolygonCreator] zoomToBounds called:', bounds);
      if (mapRef.current) {
        try {
          mapRef.current.fitBounds([
            [bounds[1], bounds[0]],  // Southwest corner
            [bounds[3], bounds[2]]   // Northeast corner
          ], {
            padding: [50, 50],
            maxZoom: 16
          });
          console.log('[PolygonCreator] Map zoomed to bounds');
        } catch (error) {
          console.error('[PolygonCreator] Error zooming to bounds:', error);
        }
      } else {
        console.warn('[PolygonCreator] Map ref not available yet');
      }
    },
    setWardBoundary: (geometry: any) => {
      console.log('[PolygonCreator] setWardBoundary called:', geometry ? 'show' : 'hide');
      if (!mapRef.current) {
        console.warn('[PolygonCreator] Map ref not available');
        return;
      }

      // Remove existing ward boundary
      if (wardBoundaryLayerRef.current) {
        mapRef.current.removeLayer(wardBoundaryLayerRef.current);
        wardBoundaryLayerRef.current = null;
        console.log('[PolygonCreator] Removed existing ward boundary');
      }

      // Add new ward boundary if geometry provided
      if (geometry) {
        try {
          const layer = L.geoJSON(geometry, {
            style: {
              color: '#fbbf24',      // Yellow
              weight: 2,
              fillOpacity: 0.05,
              fillColor: '#fbbf24',
              dashArray: '8, 4'      // Dashed line
            }
          });
          layer.addTo(mapRef.current);
          wardBoundaryLayerRef.current = layer;
          console.log('[PolygonCreator] Added ward boundary to map');
        } catch (error) {
          console.error('[PolygonCreator] Error adding ward boundary:', error);
        }
      }
    }
  }));

  // Capture map reference when ready
  const handleMapReady = (map: L.Map) => {
    console.log('[PolygonCreator] Map ready');
    mapRef.current = map;
  };

  // Handle mode change
  const handleModeChange = (newMode: 'auto' | 'manual') => {
    setMode(newMode);
    setError('');

    if (newMode === 'auto' && gpsPoints.length < 3) {
      setError('At least 3 GPS points are required for auto-create mode');
    }
  };

  // Auto-create polygon from GPS points
  const handleAutoCreate = () => {
    setError('');

    if (gpsPoints.length < 3) {
      setError('At least 3 GPS points are required to create a polygon');
      return;
    }

    try {
      const autoPolygon = gpsPointsToPolygon(gpsPoints);
      const geometry = autoPolygon.geometry;

      // Validate
      const validationResult = validatePolygonGeometry(geometry);
      setValidation(validationResult);

      if (!validationResult.valid) {
        setError(validationResult.error || 'Invalid polygon');
        return;
      }

      setPolygon(geometry);
      onPolygonChange(geometry);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create polygon');
    }
  };

  // Handle manually drawn polygon
  const handleManualPolygon = (geometry: any) => {
    setError('');

    // Validate
    const validationResult = validatePolygonGeometry(geometry);
    setValidation(validationResult);

    if (!validationResult.valid) {
      setError(validationResult.error || 'Invalid polygon');
      return;
    }

    setPolygon(geometry);
    onPolygonChange(geometry);
  };

  // Simplify polygon (reduce vertices)
  const handleSimplify = () => {
    if (!polygon) return;

    try {
      const simplified = simplifyPolygon(polygon, 0.0001);
      setPolygon(simplified);
      onPolygonChange(simplified);
    } catch (err) {
      setError('Failed to simplify polygon');
    }
  };

  // Calculate area
  const area = polygon ? calculateAreaHectares(polygon) : 0;

  // Prepare map data
  const mapCenter: [number, number] =
    gpsPoints.length > 0
      ? [gpsPoints[0].latitude, gpsPoints[0].longitude]
      : [27.7172, 85.3240];

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-bold mb-4">Create Outer Boundary</h2>

        {/* Mode Selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Creation Method
          </label>
          <div className="flex gap-4">
            <button
              onClick={() => handleModeChange('auto')}
              className={`flex-1 px-4 py-3 rounded-lg border-2 transition-colors ${
                mode === 'auto'
                  ? 'border-green-600 bg-green-50 text-green-700'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <div className="font-semibold">Auto-create from GPS Points</div>
              <div className="text-sm text-gray-600 mt-1">
                Connect GPS points in order to form polygon
              </div>
            </button>
            <button
              onClick={() => handleModeChange('manual')}
              className={`flex-1 px-4 py-3 rounded-lg border-2 transition-colors ${
                mode === 'manual'
                  ? 'border-green-600 bg-green-50 text-green-700'
                  : 'border-gray-300 hover:border-gray-400'
              }`}
            >
              <div className="font-semibold">Manual Digitizing</div>
              <div className="text-sm text-gray-600 mt-1">
                Draw polygon directly on map
              </div>
            </button>
          </div>
        </div>

        {/* Auto-create Mode */}
        {mode === 'auto' && (
          <div className="space-y-4">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm text-blue-800">
                <strong>{gpsPoints.length}</strong> GPS points loaded.{' '}
                {gpsPoints.length >= 3
                  ? 'Click "Create Polygon" to connect points in order.'
                  : `Need ${3 - gpsPoints.length} more points.`}
              </p>
            </div>

            <button
              onClick={handleAutoCreate}
              disabled={gpsPoints.length < 3}
              className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
            >
              Create Polygon from GPS Points
            </button>
          </div>
        )}

        {/* Manual Mode */}
        {mode === 'manual' && (
          <div className="space-y-4">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
              <p className="text-sm text-blue-800">
                <strong>Instructions:</strong>
                <br />
                • Click the <strong>polygon icon</strong> in the map toolbar to start drawing
                <br />
                • Click on the map to add vertices
                <br />
                • Double-click or click the first point to complete
                <br />
                • Use <strong>edit mode</strong> to move vertices
                <br />• Use <strong>delete mode</strong> to remove polygon
              </p>
            </div>
          </div>
        )}

        {/* Error Messages */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md">
            {error}
          </div>
        )}

        {/* Validation Messages */}
        {validation && validation.warnings && validation.warnings.length > 0 && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 text-yellow-700 rounded-md">
            <strong>Warnings:</strong>
            <ul className="list-disc list-inside mt-1">
              {validation.warnings.map((warning, i) => (
                <li key={i}>{warning}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Polygon Info */}
        {polygon && (
          <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-md">
            <h3 className="font-semibold text-green-800 mb-2">Polygon Created</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Area:</span>
                <span className="ml-2 font-semibold">{formatArea(area)}</span>
              </div>
              <div>
                <span className="text-gray-600">Type:</span>
                <span className="ml-2 font-semibold">{polygon.type}</span>
              </div>
            </div>

            <div className="mt-3 flex gap-2">
              {mode === 'auto' && gpsPoints.length > 20 && (
                <button
                  onClick={handleSimplify}
                  className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                >
                  Simplify (Reduce Vertices)
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Map</h3>
        <div className="h-[600px] rounded overflow-hidden border border-gray-300">
          <MapContainer
            center={mapCenter}
            zoom={13}
            style={{ height: '100%', width: '100%' }}
          >
            <MapRefCapture onMapReady={handleMapReady} />
            <BaseMapSelector />

            {/* Show GPS points if in auto mode */}
            {mode === 'auto' && gpsPoints.length > 0 && (
              <>
                {/* GPS point markers */}
                {gpsPoints.map((point) => (
                  <Marker key={point.id} position={[point.latitude, point.longitude]} />
                ))}

                {/* Line connecting GPS points */}
                <Polyline
                  positions={gpsPoints.map((p) => [p.latitude, p.longitude])}
                  color="blue"
                  weight={2}
                  dashArray="5, 5"
                />
              </>
            )}

            {/* Show created polygon */}
            {polygon && mode === 'auto' && (
              <GeoJSON
                data={polygon}
                style={{
                  color: '#10b981',
                  weight: 3,
                  fillOpacity: 0.2,
                }}
              />
            )}

            {/* Drawing controls for manual mode */}
            <DrawingControls
              mode={mode}
              onPolygonCreated={handleManualPolygon}
              initialPolygon={initialPolygon}
            />
          </MapContainer>
        </div>
      </div>
    </div>
  );
});

export default PolygonCreator;
