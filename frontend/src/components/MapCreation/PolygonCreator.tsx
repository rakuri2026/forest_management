import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import HelpTooltip, { helpTexts } from '../HelpTooltip';
import { GPSPoint, gpsPointsToPolygon } from '../../utils/gpsUtils';
import {
  validatePolygonGeometry,
  calculateAreaHectares,
  simplifyPolygon,
  formatArea,
} from '../../utils/geometryValidation';
import BaseMapSelector from './BaseMapSelector';
import GPSPointLayer, { LabelMode } from './GPSPointLayer';

interface PolygonCreatorProps {
  gpsPoints?: GPSPoint[];
  onPolygonChange: (polygon: any) => void;
  initialPolygon?: any;
}

export interface PolygonCreatorHandle {
  zoomToBounds: (bounds: [number, number, number, number]) => void;
  setWardBoundary: (geometry: any) => void;
}

interface Island {
  id: string;
  geometry: any;
  area: number;
  layer?: L.Layer;
}

const ISLAND_COLORS = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'];

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

// Map component with Leaflet-Geoman drawing controls for multiple islands
const MultiIslandDrawingControls: React.FC<{
  mode: 'auto' | 'manual';
  onPolygonCreated: (polygon: any) => void;
  islands: Island[];
  activeIslandId: string | null;
  onIslandLayerCreated: (islandId: string, layer: L.Layer) => void;
}> = ({ mode, onPolygonCreated, islands, activeIslandId, onIslandLayerCreated }) => {
  const map = useMap();
  const layersRef = useRef<Map<string, L.Layer>>(new Map());

  useEffect(() => {
    if (mode === 'manual') {
      // Enable Leaflet-Geoman controls (polygon disabled by default until Add Island is clicked)
      map.pm.addControls({
        position: 'topleft',
        drawPolygon: false,  // Disabled until Add Island is clicked
        drawMarker: false,
        drawCircle: false,
        drawCircleMarker: false,
        drawPolyline: false,
        drawRectangle: false,  // Also disable rectangle
        editMode: true,
        dragMode: false,
        cutPolygon: false,
        removalMode: true,
      });

      // Listen for polygon creation
      const handleCreate = (e: any) => {
        const layer = e.layer;
        const geoJSON = layer.toGeoJSON();

        // Store layer reference for the active island
        if (activeIslandId) {
          layersRef.current.set(activeIslandId, layer);
          onIslandLayerCreated(activeIslandId, layer);
        }

        onPolygonCreated(geoJSON.geometry);
        
        // Disable polygon drawing after completion
        map.pm.disableDraw('Polygon');
      };

      // Listen for polygon editing
      const handleEdit = (e: any) => {
        const layers = e.layers;
        layers.eachLayer((layer: any) => {
          const geoJSON = layer.toGeoJSON();
          onPolygonCreated(geoJSON.geometry);
        });
      };

      // Listen for polygon removal
      const handleRemove = (e: any) => {
        const layer = e.layer;
        // Find and remove from layersRef
        for (const [id, storedLayer] of layersRef.current.entries()) {
          if (storedLayer === layer) {
            layersRef.current.delete(id);
            break;
          }
        }
      };

      map.on('pm:create', handleCreate);
      map.on('pm:edit', handleEdit);
      map.on('pm:remove', handleRemove);

      return () => {
        map.pm.removeControls();
        map.off('pm:create', handleCreate);
        map.off('pm:edit', handleEdit);
        map.off('pm:remove', handleRemove);

        // DON'T remove layers here - they're managed by the islands display useEffect
        // Only cleanup event listeners
      };
    }
  }, [mode, map, onPolygonCreated]);

  // Control polygon tool based on activeIslandId
  useEffect(() => {
    if (mode === 'manual' && map) {
      if (activeIslandId) {
        // Enable polygon drawing when an island is being added
        map.pm.enableDraw('Polygon', {
          snappable: true,
          snapDistance: 20,
        });
      } else {
        // Disable polygon drawing when no island is being added
        map.pm.disableDraw('Polygon');
      }
    }
  }, [mode, activeIslandId, map]);

  // Display existing islands on map
  useEffect(() => {
    if (mode === 'manual') {
      // Remove old layers that are not in current islands
      const currentIslandIds = new Set(islands.map(i => i.id));
      for (const [id, layer] of layersRef.current.entries()) {
        if (!currentIslandIds.has(id) && map.hasLayer(layer)) {
          map.removeLayer(layer);
          layersRef.current.delete(id);
        }
      }

      // Add islands that don't have layers yet
      islands.forEach((island, index) => {
        if (!layersRef.current.has(island.id) && island.geometry) {
          const color = ISLAND_COLORS[index % ISLAND_COLORS.length];
          const geoJsonLayer = L.geoJSON(island.geometry, {
            pmIgnore: false,
            style: {
              color: color,
              weight: 3,
              fillOpacity: 0.2,
              fillColor: color,
            }
          });
          geoJsonLayer.addTo(map);
          layersRef.current.set(island.id, geoJsonLayer);
        }
      });

      // Fit bounds to show all islands
      if (islands.length > 0) {
        const allBounds: L.LatLngBounds[] = [];
        islands.forEach(island => {
          const layer = layersRef.current.get(island.id);
          if (layer && (layer as any).getBounds) {
            allBounds.push((layer as any).getBounds());
          }
        });

        if (allBounds.length > 0) {
          const combinedBounds = allBounds.reduce((acc, bounds) => acc.extend(bounds), allBounds[0]);
          map.fitBounds(combinedBounds, { padding: [50, 50] });
        }
      }
    }
  }, [islands, map, mode]);

  return null;
};

const DRAFT_STORAGE_KEY = 'polygon_creator_draft';

const PolygonCreator = forwardRef<PolygonCreatorHandle, PolygonCreatorProps>(({
  gpsPoints = [],
  onPolygonChange,
  initialPolygon,
}, ref) => {
  const [mode, setMode] = useState<'auto' | 'manual'>('auto');
  const [islands, setIslands] = useState<Island[]>([]);
  const [activeIslandId, setActiveIslandId] = useState<string | null>(null);
  const [error, setError] = useState<string>('');
  const [validation, setValidation] = useState<{
    valid: boolean;
    error?: string;
    warnings?: string[];
  } | null>(null);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [showSaveIndicator, setShowSaveIndicator] = useState(false);

  // GPS Point Layer Controls
  const [gpsPointsVisible, setGpsPointsVisible] = useState(true);
  const [gpsLabelMode, setGpsLabelMode] = useState<LabelMode>('sn');
  const [gpsPointSize, setGpsPointSize] = useState(24);
  const [gpsSnappingEnabled, setGpsSnappingEnabled] = useState(true);
  const [showDescriptionField, setShowDescriptionField] = useState(false);
  
  // Base Map Selection
  const [baseMap, setBaseMap] = useState<string>('satellite');
  
  // Base map options
  const baseMapOptions = [
    { value: 'satellite', label: 'Satellite', icon: '🛰️' },
    { value: 'topographic', label: 'Topographic', icon: '🗻' },
    { value: 'osm', label: 'Street Map', icon: '🗺️' },
  ];

  // Refs for map control
  const mapRef = useRef<L.Map | null>(null);
  const wardBoundaryLayerRef = useRef<L.GeoJSON | null>(null);

  // Load from initialPolygon on mount
  useEffect(() => {
    if (initialPolygon) {
      // Check if it's a MultiPolygon
      if (initialPolygon.type === 'MultiPolygon') {
        const loadedIslands: Island[] = initialPolygon.coordinates.map((coords: any, index: number) => {
          const polygonGeom = {
            type: 'Polygon',
            coordinates: coords
          };
          return {
            id: `island-${Date.now()}-${index}`,
            geometry: polygonGeom,
            area: calculateAreaHectares(polygonGeom),
          };
        });
        setIslands(loadedIslands);
        // Notify parent with MultiPolygon
        onPolygonChange(initialPolygon);
      } else if (initialPolygon.type === 'Polygon') {
        // Single polygon
        const newIsland = {
          id: `island-${Date.now()}-0`,
          geometry: initialPolygon,
          area: calculateAreaHectares(initialPolygon),
        };
        setIslands([newIsland]);
        // Notify parent with the polygon
        onPolygonChange(initialPolygon);
      }
    }
  }, [initialPolygon]);

  // Manual save draft (called by user clicking Save Draft button)
  const saveDraft = () => {
    try {
      const draft = {
        islands: islands,
        mode,
        activeIslandId: activeIslandId,
        timestamp: new Date().toISOString(),
      };
      localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
      setLastSaved(new Date());
      setShowSaveIndicator(true);
      setTimeout(() => setShowSaveIndicator(false), 2000);
    } catch (error) {
      console.error('[PolygonCreator] Error saving draft:', error);
    }
  };

  // Clear draft when completing (passing polygon to parent)
  const clearDraft = () => {
    try {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
      setLastSaved(null);
    } catch (error) {
      console.error('[PolygonCreator] Error clearing draft:', error);
    }
  };

  // Expose saveDraft method to parent
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
    setActiveIslandId(null);

    if (newMode === 'auto' && gpsPoints.length < 3) {
      setError('At least 3 GPS points are required for auto-create mode');
    }
  };

  // Auto-create polygon from GPS points (single island only)
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

      // Create single island from GPS points
      const newIsland: Island = {
        id: `island-${Date.now()}`,
        geometry: geometry,
        area: calculateAreaHectares(geometry),
      };

      setIslands([newIsland]);
      updateParentWithCombinedGeometry([newIsland]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create polygon');
    }
  };

  // Add new island for manual drawing
  const handleAddIsland = () => {
    const newIslandId = `island-${Date.now()}`;
    setActiveIslandId(newIslandId);
    setError('');

    // Add placeholder island (will be updated when drawn)
    const newIsland: Island = {
      id: newIslandId,
      geometry: null,
      area: 0,
    };

    setIslands(prev => [...prev, newIsland]);
  };

  // Remove island
  const handleRemoveIsland = (islandId: string) => {
    // Compute new value first
    const updatedIslands = islands.filter(i => i.id !== islandId);
    
    // Update state and parent geometry separately
    setIslands(updatedIslands);
    updateParentWithCombinedGeometry(updatedIslands);

    if (activeIslandId === islandId) {
      setActiveIslandId(null);
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

    if (activeIslandId) {
      // Update the active island - compute new value first
      const updatedIslands = islands.map(island =>
        island.id === activeIslandId
          ? { ...island, geometry, area: calculateAreaHectares(geometry) }
          : island
      );
      
      // Update state and parent geometry separately to avoid setState during render warning
      setIslands(updatedIslands);
      updateParentWithCombinedGeometry(updatedIslands);
      setActiveIslandId(null); // Clear active island after drawing
    }
  };

  // Update layer reference for island
  const handleIslandLayerCreated = (islandId: string, layer: L.Layer) => {
    setIslands(prev =>
      prev.map(island =>
        island.id === islandId ? { ...island, layer } : island
      )
    );
  };

  // Combine all islands into single geometry (Polygon or MultiPolygon)
  const updateParentWithCombinedGeometry = (islandList: Island[]) => {
    const validIslands = islandList.filter(i => i.geometry);

    if (validIslands.length === 0) {
      onPolygonChange(null);
    } else if (validIslands.length === 1) {
      // Single polygon
      onPolygonChange(validIslands[0].geometry);
    } else {
      // MultiPolygon
      const multiPolygon = {
        type: 'MultiPolygon',
        coordinates: validIslands.map(i => i.geometry.coordinates)
      };
      onPolygonChange(multiPolygon);
    }
  };

  // Calculate total area
  const totalArea = islands.reduce((sum, island) => sum + island.area, 0);
  const validIslandsCount = islands.filter(i => i.geometry).length;

  // Prepare map data
  const mapCenter: [number, number] =
    gpsPoints.length > 0
      ? [gpsPoints[0].latitude, gpsPoints[0].longitude]
      : [27.7172, 85.3240];

  return (
    <div className="space-y-6">
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Create Outer Boundary</h2>

          {/* Auto-save indicator */}
          <div className="flex items-center gap-2">
            {showSaveIndicator && (
              <span className="text-sm text-green-600 flex items-center gap-1">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Saved
              </span>
            )}
            {lastSaved && !showSaveIndicator && (
              <span className="text-xs text-gray-500">
                Last saved: {lastSaved.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

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
                Draw polygon(s) directly on map
              </div>
            </button>
          </div>
        </div>

        {/* GPS Point Display Controls */}
        {gpsPoints && gpsPoints.length > 0 && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-700">GPS Reference Points</h3>
                <p className="text-xs text-gray-600 mt-1">
                  {gpsPoints.length} points loaded. Use as reference for digitization and verification.
                </p>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={gpsPointsVisible}
                  onChange={(e) => setGpsPointsVisible(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span className="text-sm text-gray-700">Show Points</span>
              </label>
            </div>

            {gpsPointsVisible && (
              <div className="grid grid-cols-2 gap-4">
                {/* Label Mode */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Label Mode
                  </label>
                  <select
                    value={gpsLabelMode}
                    onChange={(e) => setGpsLabelMode(e.target.value as LabelMode)}
                    className="w-full text-sm border-gray-300 rounded-md"
                  >
                    <option value="sn">SN Only</option>
                    <option value="description">Description</option>
                    <option value="both">Both</option>
                    <option value="none">None</option>
                  </select>
                </div>

                {/* Point Size */}
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Point Size: {gpsPointSize}px
                  </label>
                  <input
                    type="range"
                    min="20"
                    max="32"
                    value={gpsPointSize}
                    onChange={(e) => setGpsPointSize(parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>

                {/* Show Description Field */}
                {(gpsLabelMode === 'description' || gpsLabelMode === 'both') && (
                  <div className="col-span-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={showDescriptionField}
                        onChange={(e) => setShowDescriptionField(e.target.checked)}
                        className="rounded border-gray-300"
                      />
                      <span className="text-xs text-gray-700">Show description field</span>
                    </label>
                  </div>
                )}

                {/* Snapping Control */}
                {mode === 'manual' && (
                  <div className="col-span-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={gpsSnappingEnabled}
                        onChange={(e) => setGpsSnappingEnabled(e.target.checked)}
                        className="rounded border-gray-300"
                      />
                      <span className="text-xs text-gray-700">
                        Snap to GPS points (optional - helps align digitization with reference points)
                      </span>
                    </label>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

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

        {/* Manual Mode - Island Management */}
        {mode === 'manual' && (
          <div className="space-y-4">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
              <div className="flex items-start">
                <p className="text-sm text-blue-800 flex-1">
                  <strong>Instructions:</strong>
                  <br />
                  1. Click <strong>"+ Add Island"</strong> button first
                  <br />
                  2. Then click the <strong>polygon icon</strong> in the map toolbar to draw
                  <br />
                  3. Click on map to add vertices, double-click to complete polygon
                </p>
                <HelpTooltip helpText={helpTexts.addIsland.text} position="left" />
              </div>
            </div>

            {/* Island List - Only show completed islands */}
            {validIslandsCount > 0 && (
              <div className="border border-gray-300 rounded-lg p-4">
                {/* Drawing indicator */}
                {activeIslandId && (
                  <div className="mb-3 p-2 bg-green-50 border border-green-200 rounded text-sm text-green-700">
                    <span className="font-semibold">Drawing active!</span> Click polygon tool, draw polygon, double-click to finish.
                  </div>
                )}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center">
                    <h3 className="font-semibold text-gray-800">
                      Islands: {validIslandsCount}
                    </h3>
                    <HelpTooltip helpText={helpTexts.islands.text} position="right" />
                  </div>
                  <div className="flex items-center gap-2">
                    <HelpTooltip helpText={helpTexts.addIsland.text} position="top">
                      <button
                        onClick={handleAddIsland}
                        disabled={activeIslandId !== null}
                        className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                      >
                        + Add Island
                      </button>
                    </HelpTooltip>
                  </div>
                </div>

                <div className="space-y-2">
                  {islands.filter(i => i.geometry).map((island, index) => (
                    <div
                      key={island.id}
                      className="flex items-center gap-3 p-3 rounded border-2 border-gray-200 bg-gray-50"
                    >
                      {/* Color indicator */}
                      <div
                        className="w-8 h-8 rounded border-2"
                        style={{
                          backgroundColor: ISLAND_COLORS[index % ISLAND_COLORS.length],
                          borderColor: ISLAND_COLORS[index % ISLAND_COLORS.length],
                        }}
                      ></div>

                      {/* Island info */}
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">
                          Island {index + 1}
                        </div>
                        <div className="text-sm text-gray-600">
                          Area: {formatArea(island.area)}
                        </div>
                      </div>

                      {/* Remove button */}
                      <button
                        onClick={() => handleRemoveIsland(island.id)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded transition-colors"
                        title="Remove island"
                      >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Add First Island Button */}
            {islands.length === 0 && (
              <button
                onClick={handleAddIsland}
                className="w-full px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
              >
                + Add First Island
              </button>
            )}
          </div>
        )}

        {/* Drawing Mode Indicator */}
        {activeIslandId && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md flex items-center gap-2">
            <div className="animate-pulse w-3 h-3 bg-blue-500 rounded-full"></div>
            <span className="text-blue-800 font-medium">Drawing mode active - click on the map to draw polygon</span>
            <button
              onClick={() => setActiveIslandId(null)}
              className="ml-auto text-blue-600 hover:text-blue-800 text-sm"
            >
              Cancel
            </button>
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

        {/* Total Info */}
        {validIslandsCount > 0 && (
          <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-md">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="font-semibold text-green-800 mb-2">
                  {validIslandsCount === 1 ? 'Polygon Created' : `${validIslandsCount} Islands Created`}
                </h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Total Area:</span>
                    <span className="ml-2 font-semibold">{formatArea(totalArea)}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Type:</span>
                    <span className="ml-2 font-semibold">
                      {validIslandsCount === 1 ? 'Polygon' : 'MultiPolygon'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Clear Draft Button */}
              {lastSaved && (
                <button
                  onClick={() => {
                    if (window.confirm('Clear saved draft? This cannot be undone.')) {
                      clearDraft();
                      setIslands([]);
                      setActiveIslandId(null);
                      onPolygonChange(null);
                    }
                  }}
                  className="ml-4 px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded border border-red-300 transition-colors"
                  title="Clear saved draft and start fresh"
                >
                  Clear Draft
                </button>
              )}
            </div>

            <div className="mt-3 p-2 bg-blue-50 border border-blue-200 rounded text-xs text-blue-800">
              Click <strong>Next</strong> when done drawing all islands.
            </div>
          </div>
        )}
      </div>

      {/* Map */}
      <div className="bg-white p-6 rounded-lg shadow">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Map</h3>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Base Map:</span>
            <div className="flex rounded-md overflow-hidden border border-gray-300">
              {baseMapOptions.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setBaseMap(opt.value)}
                  className={`px-3 py-1 text-sm transition-colors ${
                    baseMap === opt.value
                      ? 'bg-green-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {opt.icon} {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="h-[600px] rounded overflow-hidden border border-gray-300">
          <MapContainer
            center={mapCenter}
            zoom={13}
            style={{ height: '100%', width: '100%' }}
          >
            <MapRefCapture onMapReady={handleMapReady} />
            <BaseMapSelector baseMap={baseMap} />

            {/* GPS Point Layer - visible in both auto and manual modes */}
            {gpsPoints && gpsPoints.length > 0 && (
              <>
                <GPSPointLayer
                  points={gpsPoints}
                  visible={gpsPointsVisible}
                  labelMode={gpsLabelMode}
                  pointSize={gpsPointSize}
                  showDescriptionField={showDescriptionField}
                />

                {/* Line connecting GPS points in auto mode */}
                {mode === 'auto' && (
                  <Polyline
                    positions={gpsPoints.map((p) => [p.latitude, p.longitude])}
                    color="blue"
                    weight={2}
                    dashArray="5, 5"
                  />
                )}
              </>
            )}

            {/* Show created polygon in auto mode */}
            {mode === 'auto' && islands.length > 0 && islands[0].geometry && (
              <GeoJSON
                data={islands[0].geometry}
                style={{
                  color: '#10b981',
                  weight: 3,
                  fillOpacity: 0.2,
                }}
              />
            )}

            {/* Drawing controls for manual mode with multi-island support */}
            <MultiIslandDrawingControls
              mode={mode}
              onPolygonCreated={handleManualPolygon}
              islands={islands}
              activeIslandId={activeIslandId}
              onIslandLayerCreated={handleIslandLayerCreated}
            />
          </MapContainer>
        </div>
      </div>
    </div>
  );
});

export default PolygonCreator;
