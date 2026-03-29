import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import * as turf from '@turf/turf';
import { forestApi } from '../services/api';
import { calculateAreaHectares, calculateSubAreaByBlock, detectBlockForSubArea } from '../utils/geometryValidation';

interface SubArea {
  id: string;
  name: string;
  category: string;
  geometry: any;
  area_hectares: number;
  block_id?: string;
  block_name?: string;
  block_breakdown?: Array<{ blockId: string; blockName: string; area: number; percentage: number }>;
  is_excluded: boolean;
}

interface MapEditorProps {
  calculationId: string;
  initialGeometry: any;
  initialSubAreas?: SubArea[];
  initialBlocks?: any[];
  onSave: (geometry: any, subAreas: SubArea[]) => void;
  onCancel: () => void;
}

const SUB_AREA_CATEGORIES = [
  { value: 'protected', label: 'Protected Zone', color: '#ef4444', isExcluded: false },
  { value: 'plantation', label: 'Plantation Area', color: '#10b981', isExcluded: false },
  { value: 'pro-poor', label: 'Pro-Poor Income Generation', color: '#f59e0b', isExcluded: false },
  { value: 'religious', label: 'Religious Area', color: '#8b5cf6', isExcluded: false },
  { value: 'biodiversity', label: 'Bio-diversity Rich', color: '#06b6d4', isExcluded: false },
  { value: 'tourist', label: 'Tourist Attraction', color: '#ec4899', isExcluded: false },
  { value: 'office', label: 'Office Area', color: '#6b7280', isExcluded: false },
  { value: 'private_land', label: 'Private Land (Excluded)', color: '#dc2626', isExcluded: true },
];

const MapEditor: React.FC<MapEditorProps> = ({
  calculationId,
  initialGeometry,
  initialSubAreas = [],
  initialBlocks = [],
  onSave,
  onCancel,
}) => {
  console.log('[MapEditor] Component rendered with calculationId:', calculationId);
  
  const [geometry, setGeometry] = useState<any>(initialGeometry);
  const [blocks, setBlocks] = useState<any[]>(initialBlocks);
  const [subAreas, setSubAreas] = useState<SubArea[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);
  
  // Update blocks when initialBlocks prop changes
  useEffect(() => {
    console.log('[MapEditor] initialBlocks changed:', initialBlocks?.length || 0);
    setBlocks(initialBlocks || []);
  }, [initialBlocks]);
  
  // Load sub-areas from backend on mount
  useEffect(() => {
    console.log('[MapEditor] Loading sub-areas from backend...');
    forestApi.listSubAreas(calculationId).then(data => {
      console.log('[MapEditor] Loaded sub-areas:', data.sub_areas?.length || 0);
      console.log('[MapEditor] Full API response:', JSON.stringify(data).substring(0, 1000));
      if (data.sub_areas && data.sub_areas.length > 0) {
        console.log('[MapEditor] First sub-area keys:', Object.keys(data.sub_areas[0]));
        console.log('[MapEditor] First sub-area area:', data.sub_areas[0].area_hectares);
        console.log('[MapEditor] First sub-area geometry:', JSON.stringify(data.sub_areas[0].geometry).substring(0, 500));
        console.log('[MapEditor] First sub-area full:', JSON.stringify(data.sub_areas[0]).substring(0, 500));
      }
      setSubAreas(data.sub_areas || []);
      setIsLoaded(true);
      console.log('[MapEditor] setSubAreas called with:', data.sub_areas?.length || 0, 'items');
    }).catch(err => {
      console.log('[MapEditor] Error loading, using initial:', err);
      setSubAreas(initialSubAreas || []);
      setIsLoaded(true);
    });
  }, [calculationId]);
  const [selectedCategory, setSelectedCategory] = useState<string>(SUB_AREA_CATEGORIES[0].value);
  const [selectedSubAreaId, setSelectedSubAreaId] = useState<string | null>(null);
  const [mode, setMode] = useState<'edit_boundary' | 'edit_subareas'>('edit_boundary');
  
  // Auto-switch to subareas mode if there are existing sub-areas (after loading)
  useEffect(() => {
    if (isLoaded && subAreas.length > 0) {
      setMode('edit_subareas');
    }
  }, [isLoaded, subAreas]);
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mapInstance, setMapInstance] = useState<L.Map | null>(null);
  const [boundaryLayer, setBoundaryLayer] = useState<L.GeoJSON | null>(null);
  const [blockLayers, setBlockLayers] = useState<L.GeoJSON[]>([]);
  const [subAreaLayers, setSubAreaLayers] = useState<Map<string, L.GeoJSON>>(new Map());
  const [pendingLayers, setPendingLayers] = useState<L.Layer[]>([]);

  const mapRef = useRef<L.Map | null>(null);

  // Calculate map center from geometry
  const getMapCenter = () => {
    if (!geometry) return [27.7172, 85.3240];
    try {
      const layer = L.geoJSON(geometry);
      const bounds = layer.getBounds();
      if (bounds.isValid()) {
        return [(bounds.getNorth() + bounds.getSouth()) / 2, (bounds.getEast() + bounds.getWest()) / 2] as [number, number];
      }
    } catch (e) {
      console.error('Error calculating center:', e);
    }
    return [27.7172, 85.3240];
  };

  // Add drawing controls for boundary editing
  useEffect(() => {
    if (!mapInstance || mode !== 'edit_boundary') return;

    // Check if PM is available
    if (mapInstance.pm) {
      try {
        mapInstance.pm.setOptIn(true);
      } catch (e) {
        console.log('[MapEditor] PM setOptIn not available');
      }
    }

    mapInstance.pm.addControls({
      position: 'topleft',
      drawPolygon: true,
      drawMarker: false,
      drawCircle: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: true,
      editMode: true,
      dragMode: false,
      cutPolygon: true,
      removalMode: true,
    });

    const handleCreate = (e: any) => {
      const layer = e.layer;
      const geoJSON = layer.toGeoJSON();
      setGeometry(geoJSON.geometry);
      setPendingLayers(prev => [...prev, layer]);
    };

    const handleEdit = (e: any) => {
      const layers = e.layers;
      layers.eachLayer((layer: any) => {
        const geoJSON = layer.toGeoJSON();
        setGeometry(geoJSON.geometry);
      });
    };

    const handleRemove = (e: any) => {
      const layer = e.layer;
      setGeometry(null);
      if (pendingLayers.includes(layer)) {
        setPendingLayers(prev => prev.filter(l => l !== layer));
      }
    };

    mapInstance.on('pm:create', handleCreate);
    mapInstance.on('pm:edit', handleEdit);
    mapInstance.on('pm:remove', handleRemove);

    return () => {
      mapInstance.pm.removeControls();
      mapInstance.off('pm:create', handleCreate);
      mapInstance.off('pm:edit', handleEdit);
      mapInstance.off('pm:remove', handleRemove);
    };
  }, [mapInstance, mode]);

  // Setup sub-area drawing controls
  useEffect(() => {
    if (!mapInstance) {
      console.log('[MapEditor] No mapInstance yet');
      return;
    }
    
    if (mode !== 'edit_subareas') {
      console.log('[MapEditor] Not in edit_subareas mode, skipping controls');
      return;
    }
    
    console.log('[MapEditor] Setting up sub-area drawing controls');

    // Set global PM options - disable opt-in mode so we can draw on any layer
    if (mapInstance.pm) {
      try {
        mapInstance.pm.setOptIn(false); // Allow drawing on all layers
      } catch (e) {
        console.log('[MapEditor] PM setOptIn error:', e);
      }
    }

    const category = SUB_AREA_CATEGORIES.find(c => c.value === selectedCategory);
    const categoryColor = category?.color || '#3b82f6';

    mapInstance.pm.addControls({
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

    const handleDrawStart = (e: any) => {
      const layer = e.workingLayer;
      if (layer) {
        layer.setStyle({
          color: categoryColor,
          fillColor: categoryColor,
          fillOpacity: 0.3,
          weight: 3,
        });
      }
    };

    const handleCreate = (e: any) => {
      const layer = e.layer;
      const geoJSON = layer.toGeoJSON();

      layer.setStyle({
        color: categoryColor,
        fillColor: categoryColor,
        fillOpacity: 0.3,
        weight: 3,
      });

      if (layer.pm) {
        layer.pm.disable();
      }

      setPendingLayers(prev => [...prev, layer]);

      // Calculate area using turf.js for accurate geodesic calculation
      const geom = geoJSON.geometry;
      let area = 0;
      try {
        // Use turf for accurate geodesic area calculation
        const turfFeature = turf.feature(geom);
        area = turf.area(turfFeature) / 10000;
        console.log('[MapEditor] Created sub-area with area:', area);
      } catch (e) {
        console.error('Error calculating area:', e);
      }
      
      // Ensure minimum area
      area = Math.max(0.0001, area);

      // Transform blocks to match expected format (id, name, geometry)
      const transformedBlocks = blocks.map(b => ({
        id: b.id || b.block_id || `block-${b.block_index}`,
        name: b.block_name || b.name || b.block_index,
        geometry: b.geometry
      }));

      // Detect which block(s) this sub-area belongs to
      const detection = detectBlockForSubArea(geom, transformedBlocks);

      // Calculate block-wise breakdown for cross-block sub-areas
      const blockBreakdown = calculateSubAreaByBlock(geom, transformedBlocks);
      console.log('[MapEditor] Block breakdown:', blockBreakdown);

      const categoryInfo = SUB_AREA_CATEGORIES.find(c => c.value === selectedCategory);
      const newSubArea: SubArea = {
        id: `subarea-${Date.now()}`,
        name: `${categoryInfo?.label || 'Sub-area'} ${subAreas.length + 1}`,
        category: selectedCategory,
        geometry: geom,
        area_hectares: Math.max(0.01, area),
        block_id: detection.blockId,
        block_name: detection.blockName,
        block_breakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
        is_excluded: categoryInfo?.isExcluded || false,
      };

      setSubAreas(prev => [...prev, newSubArea]);
    };

    const handleEdit = (e: any) => {
      const layers = e.layers;
      layers.eachLayer((layer: any) => {
        const geoJSON = layer.toGeoJSON();
        const subAreaId = Array.from(subAreaLayers.entries()).find(([_, l]) => l === layer)?.[0];
        if (subAreaId) {
          setSubAreas(prev =>
            prev.map(sa =>
              sa.id === subAreaId ? { ...sa, geometry: geoJSON.geometry } : sa
            )
          );
        }
      });
    };

    const handleRemove = (e: any) => {
      const layer = e.layer;
      const subAreaId = Array.from(subAreaLayers.entries()).find(([_, l]) => l === layer)?.[0];
      if (subAreaId) {
        setSubAreas(prev => prev.filter(sa => sa.id !== subAreaId));
        const newLayers = new Map(subAreaLayers);
        newLayers.delete(subAreaId);
        setSubAreaLayers(newLayers);
      }
    };

    mapInstance.on('pm:drawstart', handleDrawStart);
    mapInstance.on('pm:create', handleCreate);
    mapInstance.on('pm:edit', handleEdit);
    mapInstance.on('pm:remove', handleRemove);
    
    // Debug: log any PM errors
    mapInstance.on('pm:error', (e: any) => {
      console.log('[MapEditor] PM Error:', e);
    });

    return () => {
      mapInstance.pm.removeControls();
      mapInstance.off('pm:drawstart', handleDrawStart);
      mapInstance.off('pm:create', handleCreate);
      mapInstance.off('pm:edit', handleEdit);
      mapInstance.off('pm:remove', handleRemove);
    };
  }, [mapInstance, mode, selectedCategory]);

  // Render boundary geometry
  useEffect(() => {
    if (!mapInstance || !geometry) return;

    if (boundaryLayer) {
      mapInstance.removeLayer(boundaryLayer);
    }

    const newLayer = L.geoJSON(geometry, {
      style: {
        color: '#2563eb',
        weight: 3,
        fillOpacity: 0.1,
        fillColor: '#3b82f6',
      },
      pmIgnore: true,
      interactive: false, // Disable all mouse events on this layer
      bubblingMouseEvents: false,
    });

    // Prevent any events on the layer
    newLayer.on = function() { return newLayer; };
    newLayer.off = function() { return newLayer; };
    newLayer.getEvents = function() { return {}; };
    
    newLayer.addTo(mapInstance);
    setBoundaryLayer(newLayer);

    // Zoom to bounds
    if (newLayer.getBounds().isValid()) {
      mapInstance.fitBounds(newLayer.getBounds(), { padding: [50, 50] });
    }
  }, [mapInstance, geometry]);

  // Render block boundaries
  useEffect(() => {
    if (!mapInstance) return;
    
    console.log('[MapEditor] Rendering blocks:', blocks?.length || 0);
    if (blocks && blocks.length > 0) {
      console.log('[MapEditor] First block:', JSON.stringify(blocks[0]).substring(0, 300));
    }

    // Remove old block layers
    blockLayers.forEach((layer) => {
      try {
        mapInstance.removeLayer(layer);
      } catch (e) {
        // Layer may already be removed
      }
    });

    if (!blocks || blocks.length === 0) return;

    // Create new block layers
    const newBlockLayers: L.GeoJSON[] = [];
    const blockColors = ['#ef4444', '#f59e0b', '#10b981', '#06b6d4', '#8b5cf6', '#ec4899'];

    blocks.forEach((block, index) => {
      if (!block.geometry) return;

      const layer = L.geoJSON(block.geometry, {
        style: {
          color: blockColors[index % blockColors.length],
          weight: 3,
          fillOpacity: 0.2,
          fillColor: blockColors[index % blockColors.length],
        },
        pmIgnore: true,
        interactive: false,
        bubblingMouseEvents: false,
      });
      
      // Disable mouse events
      layer.on = function() { return layer; };
      layer.off = function() { return layer; };
      layer.getEvents = function() { return {}; };

      // Add popup with block info
      layer.bindPopup(`
        <strong>${block.block_name || `Block ${index + 1}`}</strong><br/>
        Area: ${block.area_hectares?.toFixed(2) || 'N/A'} ha
      `);

      layer.addTo(mapInstance);
      newBlockLayers.push(layer);
    });

    setBlockLayers(newBlockLayers);
  }, [mapInstance, blocks]);

  // Render sub-areas
  useEffect(() => {
    console.log('[MapEditor Render] Checking conditions: mapInstance=', !!mapInstance, 'mode=', mode, 'subAreas.length=', subAreas.length);
    if (!mapInstance || mode !== 'edit_subareas') {
      console.log('[MapEditor Render] Skipping render - conditions not met');
      return;
    }

    console.log('[MapEditor Render] Rendering', subAreas.length, 'sub-areas');
    // Clear old sub-area layers - use a ref to track current layers
    const currentLayers = Array.from(subAreaLayers.values());
    currentLayers.forEach((layer) => {
      try {
        mapInstance.removeLayer(layer);
      } catch (e) {
        // Layer may already be removed
      }
    });

    const newLayers = new Map<string, L.GeoJSON>();

    subAreas.forEach((subArea) => {
      console.log('[MapEditor Render] Processing sub-area:', subArea.name, 'geometry exists:', !!subArea.geometry);
      if (!subArea.geometry) {
        console.log('[MapEditor Render] Skipping sub-area - no geometry');
        return;
      }
      
      const category = SUB_AREA_CATEGORIES.find(c => c.value === subArea.category);
      const color = category?.color || '#6b7280';
      const isSelected = subArea.id === selectedSubAreaId;
      const isExcluded = subArea.is_excluded;

      const layer = L.geoJSON(subArea.geometry, {
        style: {
          color: isSelected ? '#000000' : color,
          weight: isSelected ? 4 : 2,
          fillOpacity: isExcluded ? 0.5 : 0.3,
          fillColor: isExcluded ? '#dc2626' : color,
          dashArray: isExcluded ? '10, 10' : undefined,
        },
        pmIgnore: true,
        interactive: false,
        bubblingMouseEvents: false,
      });
      
      // Disable mouse events
      layer.on = function() { return layer; };
      layer.off = function() { return layer; };
      layer.getEvents = function() { return {}; };

      layer.bindPopup(`
        <strong>${subArea.name}</strong><br/>
        Category: ${category?.label || subArea.category}<br/>
        Area: ${subArea.area_hectares.toFixed(4)} ha<br/>
        ${isExcluded ? '<br/><strong style="color: red;">EXCLUDED FROM FOREST</strong>' : ''}
      `);

      layer.addTo(mapInstance);
      newLayers.set(subArea.id, layer);
    });

    setSubAreaLayers(newLayers);
  }, [mapInstance, subAreas, selectedSubAreaId, mode]);

  const handleSave = async () => {
    if (!geometry) {
      setError('Please draw a boundary geometry');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // First update the boundary geometry
      await forestApi.updateGeometry(calculationId, geometry, false);

      // Get existing sub-areas from backend to avoid duplicates
      let existingSubAreas: any[] = [];
      try {
        const response = await forestApi.listSubAreas(calculationId);
        existingSubAreas = response.sub_areas || [];
      } catch (e) {
        console.log('No existing sub-areas to compare');
      }

      // Track which sub-areas we've saved
      const savedIds = new Set(existingSubAreas.map((sa: any) => sa.id));

      // Update EXISTING sub-areas (those that already have IDs in backend)
      for (const subArea of subAreas) {
        if (savedIds.has(subArea.id)) {
          // Find the existing version to check if name/category changed
          const existing = existingSubAreas.find((sa: any) => sa.id === subArea.id);
          if (existing && (existing.name !== subArea.name || existing.category !== subArea.category)) {
            console.log('Updating sub-area:', subArea.id, subArea.name);
            try {
              await forestApi.updateSubArea(calculationId, subArea.id, {
                name: subArea.name,
                category: subArea.category,
              });
            } catch (e: any) {
              const errorMsg = e.response?.data?.detail || e.message;
              console.error('Error updating sub-area:', errorMsg);
            }
          }
        }
      }

      // Add new sub-areas only (those with temp IDs we generated)
      for (const subArea of subAreas) {
        // Skip if this ID already exists in backend
        if (savedIds.has(subArea.id)) continue;
        
        console.log('Saving sub-area:', subArea.name, 'geometry:', subArea.geometry, 'area:', subArea.area_hectares);
        
        try {
          console.log('Sending sub-area data:', {
            name: subArea.name,
            category: subArea.category,
            block_id: subArea.block_id,
            block_name: subArea.block_name,
            block_breakdown: subArea.block_breakdown,
            is_excluded: subArea.is_excluded,
            area_hectares: subArea.area_hectares,
          });

          const result = await forestApi.addSubArea(calculationId, {
            name: subArea.name,
            category: subArea.category,
            geometry: subArea.geometry,
            block_id: subArea.block_id,
            block_name: subArea.block_name,
            block_breakdown: subArea.block_breakdown,
            is_excluded: subArea.is_excluded,
            area_hectares: subArea.area_hectares,
          });
          console.log('Sub-area saved successfully:', result);
        } catch (e: any) {
          // Handle validation errors (array) or simple error messages (string)
          let errorMsg = '';
          if (Array.isArray(e.response?.data?.detail)) {
            errorMsg = e.response.data.detail.map((err: any) =>
              `${err.loc?.join('.') || 'Field'}: ${err.msg}`
            ).join('; ');
          } else {
            errorMsg = e.response?.data?.detail || e.message;
          }
          console.error('Error adding sub-area:', e.response?.data || e.message);
          console.error('Full error:', e);
          setError(`Failed to save sub-area "${subArea.name}": ${errorMsg}`);
          return; // Stop saving on first error
        }
      }

      // Verify saved sub-areas
      const verifyResponse = await forestApi.listSubAreas(calculationId);
      console.log('Verified sub-areas after save:', verifyResponse.sub_areas.length);

      onSave(geometry, subAreas);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to save changes');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSubArea = async (subAreaId: string) => {
    try {
      await forestApi.deleteSubArea(calculationId, subAreaId);
      setSubAreas(prev => prev.filter(sa => sa.id !== subAreaId));
    } catch (e) {
      console.error('Error deleting sub-area:', e);
      // Still remove locally
      setSubAreas(prev => prev.filter(sa => sa.id !== subAreaId));
    }
  };

  const formatArea = (ha: number) => {
    if (!ha || ha === 0) return '0.0000 ha';
    if (ha >= 100) return `${(ha / 100).toFixed(2)} ha`;
    return `${ha.toFixed(4)} ha`;
  };

  const totalSubAreaArea = subAreas.reduce((sum, sa) => sum + sa.area_hectares, 0);
  const excludedArea = subAreas.filter(sa => sa.is_excluded).reduce((sum, sa) => sum + sa.area_hectares, 0);

  console.log('[MapEditor] Rendering, geometry:', !!geometry, 'blocks:', blocks?.length, 'subAreas:', subAreas.length);

  // Don't render until loaded
  if (!isLoaded) {
    return (
      <div style={{ position: 'fixed', inset: 0, zIndex: 2000, backgroundColor: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: '#666' }}>Loading...</div>
      </div>
    );
  }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 2000, backgroundColor: 'white', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ backgroundColor: '#1f2937', color: 'white', padding: '1rem 1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>Edit Forest Boundary & Sub-areas</h2>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button
            onClick={handleSave}
            disabled={loading || !geometry}
            style={{ padding: '0.5rem 1rem', backgroundColor: loading || !geometry ? '#6b7280' : '#16a34a', color: 'white', borderRadius: '0.25rem', fontWeight: '600' }}
          >
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={onCancel}
            style={{ padding: '0.5rem 1rem', backgroundColor: '#dc2626', color: 'white', borderRadius: '0.25rem', fontWeight: '600' }}
          >
            Done (Close)
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3">
          {error}
        </div>
      )}

      {/* Loading indicator */}
      {!isLoaded && (
        <div className="p-4 text-center text-gray-600">
          Loading...
        </div>
      )}

      {/* Mode Selector */}
      <div className="bg-gray-100 px-6 py-3 flex gap-4 border-b">
        <button
          onClick={() => setMode('edit_boundary')}
          className={`px-4 py-2 rounded font-medium ${
            mode === 'edit_boundary'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 hover:bg-gray-200'
          }`}
        >
          Edit Boundary
        </button>
        <button
          onClick={() => setMode('edit_subareas')}
          className={`px-4 py-2 rounded font-medium ${
            mode === 'edit_subareas'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 hover:bg-gray-200'
          }`}
        >
          Manage Sub-areas ({subAreas.length})
        </button>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-80 bg-gray-50 border-r overflow-y-auto p-4">
          {mode === 'edit_boundary' ? (
            <div>
              <h3 className="font-semibold mb-3">Boundary Editing Tools</h3>
              <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm">
                <p className="mb-2"><strong>Instructions:</strong></p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Use the drawing tools on the left to draw or edit the boundary</li>
                  <li>Click on existing boundary to edit vertices</li>
                  <li>Use the scissors tool to split polygons</li>
                  <li>Use trash icon to delete</li>
                </ul>
              </div>
            </div>
          ) : (
            <div>
              <h3 className="font-semibold mb-3">Sub-area Categories</h3>
              <div className="grid grid-cols-2 gap-2 mb-4">
                {SUB_AREA_CATEGORIES.map((cat) => (
                  <button
                    key={cat.value}
                    onClick={() => setSelectedCategory(cat.value)}
                    className={`px-3 py-2 rounded text-sm text-left border-2 transition-colors ${
                      selectedCategory === cat.value
                        ? 'border-gray-800 bg-gray-100'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                    style={{ borderLeftWidth: '4px', borderLeftColor: cat.color }}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>

              {subAreas.length > 0 && (
                <div className="mt-4">
                  <h4 className="font-semibold mb-2">Current Sub-areas</h4>
                  <div className="space-y-2">
                    {subAreas.map((sa) => {
                      const category = SUB_AREA_CATEGORIES.find(c => c.value === sa.category);
                      const isSelected = selectedSubAreaId === sa.id;
                      return (
                        <div
                          key={sa.id}
                          className={`p-3 bg-white border rounded cursor-pointer ${
                            isSelected ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                          }`}
                          onClick={() => setSelectedSubAreaId(sa.id)}
                        >
                          {isSelected ? (
                            <div>
                              <label className="block text-xs text-gray-500 mb-1">Name</label>
                              <input
                                type="text"
                                value={sa.name}
                                onChange={(e) => {
                                  e.stopPropagation();
                                  setSubAreas(prev =>
                                    prev.map(s =>
                                      s.id === sa.id ? { ...s, name: e.target.value } : s
                                    )
                                  );
                                }}
                                onClick={(e) => e.stopPropagation()}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-sm mb-2"
                                placeholder="Enter sub-area name"
                              />
                              <div className="text-xs text-gray-600">
                                <span style={{ color: category?.color }}>{category?.label}</span>
                                <span className="ml-2">- {formatArea(sa.area_hectares)}</span>
                              </div>
                              {sa.block_breakdown && sa.block_breakdown.length > 1 && (
                                <div className="text-xs mt-1 text-orange-600">
                                  <div className="font-medium">Spans {sa.block_breakdown.length} blocks:</div>
                                  {sa.block_breakdown.map((bd: any, idx: number) => (
                                    <div key={idx} className="text-gray-700">
                                      • {bd.blockName}: {formatArea(bd.area)} ({bd.percentage.toFixed(0)}%)
                                    </div>
                                  ))}
                                </div>
                              )}
                              {sa.is_excluded && (
                                <span className="text-xs text-red-600 font-medium block mt-1">EXCLUDED FROM FOREST</span>
                              )}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDeleteSubArea(sa.id);
                                }}
                                className="mt-2 w-full px-2 py-1 bg-red-100 text-red-700 rounded text-sm hover:bg-red-200"
                              >
                                Delete
                              </button>
                            </div>
                          ) : (
                            <div className="flex justify-between items-start">
                              <div>
                                <div className="font-medium text-sm">{sa.name}</div>
                                <div className="text-xs text-gray-600">
                                  {category?.label} - {formatArea(sa.area_hectares)}
                                </div>
                                {sa.is_excluded && (
                                  <span className="text-xs text-red-600 font-medium">EXCLUDED</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <div className="mt-3 p-2 bg-gray-200 rounded text-sm">
                    <div>Total: {formatArea(totalSubAreaArea)}</div>
                    {excludedArea > 0 && (
                      <div className="text-red-600">Excluded: {formatArea(excludedArea)}</div>
                    )}
                  </div>
                </div>
              )}

              <div className="mt-4 bg-blue-50 border border-blue-200 rounded p-3 text-sm">
                <p className="mb-2"><strong>Instructions:</strong></p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Select a category above</li>
                  <li>Draw polygons on the map</li>
                  <li>Sub-areas will be automatically added</li>
                  <li>Click a sub-area to select/delete</li>
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Map */}
        <div className="flex-1">
          <MapContainer
            center={getMapCenter()}
            zoom={14}
            style={{ height: '100%', width: '100%' }}
            whenReady={(map) => {
              console.log('[MapEditor] Map is ready');
              const mapObj = map.target;
              setMapInstance(mapObj);
              
              // Enable PM global options - wrapped in try/catch
              setTimeout(() => {
                if (mapObj.pm) {
                  try {
                    mapObj.pm.setOptIn(true);
                    mapObj.pm.setGlobalOptions({
                      limitDrawerToDrawingable: false,
                    });
                  } catch (e) {
                    console.log('[MapEditor] PM not fully initialized yet');
                  }
                }
              }, 500); // Wait for PM to initialize
            }}
          >
            <TileLayer
              attribution='&copy; OpenStreetMap'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </MapContainer>
        </div>
      </div>
    </div>
  );
};

export default MapEditor;