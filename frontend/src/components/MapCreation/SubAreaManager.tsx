import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import HelpTooltip, { helpTexts } from '../HelpTooltip';
import {
  validateSubAreasNoOverlap,
  validateSubAreaSum,
  detectBlockForSubArea,
  calculateAreaHectares,
  formatArea,
  calculateSubAreaByBlock,
} from '../../utils/geometryValidation';
import { getGeometryCenter } from '../../utils/geometryHelpers';
import BaseMapSelector from './BaseMapSelector';

interface Block {
  id: string;
  name: string;
  geometry: any;
  area: number;
}

interface SubArea {
  id: string;
  name: string;
  category: string;
  geometry: any;
  area: number;
  blockId?: string;
  blockName?: string;
  blockBreakdown?: Array<{ blockId: string; blockName: string; area: number; percentage: number }>;
  isExcluded?: boolean;  // True for private land excluded from forest calculations
}

interface SubAreaManagerProps {
  blocks: Block[];
  outerBoundary: any;
  onSubAreasChange: (subAreas: SubArea[]) => void;
  initialSubAreas?: SubArea[];
}

// Predefined sub-area categories
const SUB_AREA_CATEGORIES = [
  { value: 'protected', label: 'Protected Zone', color: '#ef4444', isExcluded: false },
  { value: 'plantation', label: 'Plantation Area', color: '#10b981', isExcluded: false },
  { value: 'pro-poor', label: 'Pro-Poor Income Generation', color: '#f59e0b', isExcluded: false },
  { value: 'religious', label: 'Religious Area', color: '#8b5cf6', isExcluded: false },
  { value: 'biodiversity', label: 'Bio-diversity Rich', color: '#06b6d4', isExcluded: false },
  { value: 'tourist', label: 'Tourist Attraction', color: '#ec4899', isExcluded: false },
  { value: 'office', label: 'Office Area', color: '#6b7280', isExcluded: false },
  { value: 'private_land', label: 'Private Land (Excluded)', color: '#dc2626', isExcluded: true },  // Excluded from forest area
];

// Map component with drawing controls for sub-areas
const SubAreaDrawingControls: React.FC<{
  blocks: Block[];
  selectedCategory: string;
  onSubAreaCreated: (geometry: any, removeTempLayer: () => void) => void;
  subAreas: SubArea[];
  selectedSubAreaId: string | null;
  onSubAreaEdit: (subAreaId: string, geometry: any) => void;
  onSubAreaDelete: (subAreaId: string) => void;
}> = ({
  blocks,
  selectedCategory,
  onSubAreaCreated,
  subAreas,
  selectedSubAreaId,
  onSubAreaEdit,
  onSubAreaDelete,
}) => {
  const map = useMap();
  const layersRef = useRef<Map<string, L.Layer>>(new Map());
  const pendingLayersRef = useRef<L.Layer[]>([]);

  // Stabilize callbacks to prevent effect re-triggering
  const callbacksRef = useRef({ onSubAreaCreated, onSubAreaEdit, onSubAreaDelete });
  useEffect(() => {
    callbacksRef.current = { onSubAreaCreated, onSubAreaEdit, onSubAreaDelete };
  }, [onSubAreaCreated, onSubAreaEdit, onSubAreaDelete]);

  // FIRST useEffect: STRICTLY Leaflet-Geoman Setup
  useEffect(() => {
    // Get the category color
    const category = SUB_AREA_CATEGORIES.find(c => c.value === selectedCategory);
    const categoryColor = category?.color || '#3b82f6';

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

    // Apply category color to drawing
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

    // Handle polygon creation
    const handleCreate = (e: any) => {
      console.log('[SubAreaDrawingControls] handleCreate triggered');
      const layer = e.layer;
      const geoJSON = layer.toGeoJSON();

      // Style the layer immediately so it's visible
      layer.setStyle({
        color: categoryColor,
        fillColor: categoryColor,
        fillOpacity: 0.3,
        weight: 3,
      });
      console.log('[SubAreaDrawingControls] Layer styled with color:', categoryColor);

      // Disable editing on this temporary layer
      if (layer.pm) {
        layer.pm.disable();
        console.log('[SubAreaDrawingControls] Disabled PM on temp layer');
      }

      // Add to pending layers list
      pendingLayersRef.current.push(layer);
      console.log('[SubAreaDrawingControls] Added to pending layers, total pending:', pendingLayersRef.current.length);

      // Call the parent handler with callback to remove this temp layer on validation failure
      callbacksRef.current.onSubAreaCreated(geoJSON.geometry, () => {
        console.log('[SubAreaDrawingControls] Remove temp layer callback called (validation failed)');
        // Remove from pending and from map on validation failure
        const index = pendingLayersRef.current.indexOf(layer);
        if (index > -1) {
          pendingLayersRef.current.splice(index, 1);
        }
        map.removeLayer(layer);
      });
      console.log('[SubAreaDrawingControls] onSubAreaCreated called, waiting for validation...');
    };

    // Handle polygon editing
    const handleEdit = (e: any) => {
      const layers = e.layers;
      layers.eachLayer((layer: any) => {
        const geoJSON = layer.toGeoJSON();

        layersRef.current.forEach((storedLayer, subAreaId) => {
          if (storedLayer === layer) {
            callbacksRef.current.onSubAreaEdit(subAreaId, geoJSON.geometry);
          }
        });
      });
    };

    // Handle polygon removal
    const handleRemove = (e: any) => {
      const layer = e.layer;

      layersRef.current.forEach((storedLayer, subAreaId) => {
        if (storedLayer === layer) {
          callbacksRef.current.onSubAreaDelete(subAreaId);
          layersRef.current.delete(subAreaId);
        }
      });
    };

    map.on('pm:drawstart', handleDrawStart);
    map.on('pm:create', handleCreate);
    map.on('pm:edit', handleEdit);
    map.on('pm:remove', handleRemove);

    return () => {
      map.pm.removeControls();
      map.off('pm:drawstart', handleDrawStart);
      map.off('pm:create', handleCreate);
      map.off('pm:edit', handleEdit);
      map.off('pm:remove', handleRemove);

      // Clean up pending layers only (removed layersRef cleanup from here)
      pendingLayersRef.current.forEach((layer) => {
        try {
          map.removeLayer(layer);
        } catch (e) {
          // Layer might already be removed
        }
      });
      pendingLayersRef.current = [];
    };
  }, [map, selectedCategory]); // Dependency array minimized - removed callback dependencies

  // SECOND useEffect: STRICTLY State to Map Rendering
  useEffect(() => {
    console.log('[SubAreaManager] useEffect triggered - subAreas:', subAreas.length);
    console.log('[SubAreaManager] Pending layers to remove:', pendingLayersRef.current.length);
    console.log('[SubAreaManager] Old managed layers to remove:', layersRef.current.size);

    // Clean up temporary layers once state updates
    pendingLayersRef.current.forEach((layer) => {
      try {
        map.removeLayer(layer);
        console.log('[SubAreaManager] Removed pending layer');
      } catch (e) {
        console.log('[SubAreaManager] Error removing pending layer:', e);
      }
    });
    pendingLayersRef.current = [];

    // Clear existing managed layers to prevent duplicates
    layersRef.current.forEach((layer) => {
      map.removeLayer(layer);
    });
    layersRef.current.clear();

    // Add new layers for each sub-area
    subAreas.forEach((subArea) => {
      const category = SUB_AREA_CATEGORIES.find(c => c.value === subArea.category);
      const color = category?.color || '#6b7280';
      const isSelected = subArea.id === selectedSubAreaId;
      const isExcluded = subArea.isExcluded || false;

      const geoJsonLayer = L.geoJSON(subArea.geometry, {
        style: {
          color: isSelected ? '#000000' : color,
          weight: isSelected ? 4 : 2,
          fillOpacity: isExcluded ? 0.5 : 0.3,  // Higher opacity for excluded areas
          fillColor: isExcluded ? '#dc2626' : color,  // Red fill for excluded areas
          dashArray: isExcluded ? '10, 10' : undefined,  // Dashed border for excluded areas
        },
        pmIgnore: false,
      });

      // Add popup with sub-area info
      const excludedNote = isExcluded ? '<br/><strong style="color: red;">EXCLUDED FROM FOREST</strong>' : '';
      geoJsonLayer.bindPopup(
        `<strong>${subArea.name}</strong><br/>` +
        `Category: ${category?.label || subArea.category}<br/>` +
        `Area: ${formatArea(subArea.area)}<br/>` +
        `Block: ${subArea.blockName || 'Unknown'}` +
        excludedNote
      );

      // Add to map
      geoJsonLayer.addTo(map);
      console.log(`[SubAreaManager] Added managed layer for ${subArea.name}, id: ${subArea.id}, excluded: ${isExcluded}`);

      layersRef.current.set(subArea.id, geoJsonLayer);
    });

    console.log('[SubAreaManager] Finished adding all managed layers, total:', layersRef.current.size);

    // Force map to invalidate size and re-render
    setTimeout(() => {
      map.invalidateSize();
      console.log('[SubAreaManager] Map invalidated');
    }, 0);
  }, [subAreas, selectedSubAreaId, map]);

  return null;
};

const SubAreaManager: React.FC<SubAreaManagerProps> = ({
  blocks,
  outerBoundary,
  onSubAreasChange,
  initialSubAreas = [],
}) => {
  const [subAreas, setSubAreas] = useState<SubArea[]>(initialSubAreas);
  const [selectedCategory, setSelectedCategory] = useState<string>(SUB_AREA_CATEGORIES[0].value);
  const [selectedSubAreaId, setSelectedSubAreaId] = useState<string | null>(null);
  const [selectedBlockFilter, setSelectedBlockFilter] = useState<string>('all');
  const [error, setError] = useState<string>('');
  const [showTable, setShowTable] = useState<boolean>(false); // Collapsed by default

  // Validate sub-areas whenever they change
  useEffect(() => {
    if (subAreas.length > 0) {
      // Validate no overlap
      const overlapResult = validateSubAreasNoOverlap(subAreas);
      if (!overlapResult.valid) {
        setError(overlapResult.error || '');
      } else {
        setError('');
      }
    }

    // Update parent
    onSubAreasChange(subAreas);
  }, [subAreas, onSubAreasChange]);

  // Handle sub-area creation (wrapped in useCallback to prevent unnecessary re-renders)
  const handleSubAreaCreated = useCallback((geometry: any, removeTempLayer: () => void) => {
    console.log('[SubAreaManager] handleSubAreaCreated called');
    setError('');

    try {
      const area = calculateAreaHectares(geometry);
      console.log('[SubAreaManager] Area calculated:', area);

      // Detect which block this sub-area belongs to
      const detection = detectBlockForSubArea(geometry, blocks);
      console.log('[SubAreaManager] Block detection:', detection);

      if (!detection.blockId) {
        console.log('[SubAreaManager] Validation failed: no block detected');
        setError('Sub-area must be drawn within a block');
        removeTempLayer(); // Remove temp layer on validation failure
        return;
      }

      if (detection.confidence < 0.9) {
        console.log('[SubAreaManager] Warning: low confidence', detection.confidence);
        setError(`Warning: Sub-area partially outside block (${(detection.confidence * 100).toFixed(0)}% inside)`);
      }

      const category = SUB_AREA_CATEGORIES.find(c => c.value === selectedCategory);

      // Calculate block-wise breakdown for cross-block sub-areas
      const blockBreakdown = calculateSubAreaByBlock(geometry, blocks);
      console.log('[SubAreaManager] Block breakdown:', blockBreakdown);

      const newSubArea: SubArea = {
        id: `subarea-${Date.now()}`,
        name: `${category?.label || 'Sub-area'} ${subAreas.filter(s => s.category === selectedCategory).length + 1}`,
        category: selectedCategory,
        geometry,
        area,
        blockId: detection.blockId,
        blockName: detection.blockName,
        blockBreakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
        isExcluded: category?.isExcluded || false,  // Set excluded flag for private land
      };

      // Check if adding this sub-area would exceed block area
      const block = blocks.find(b => b.id === detection.blockId);
      if (block) {
        const blockSubAreas = [...subAreas.filter(s => s.blockId === block.id), newSubArea];
        const sumResult = validateSubAreaSum(block.geometry, blockSubAreas, 5);

        if (!sumResult.valid) {
          console.log('[SubAreaManager] Validation failed: exceeds block area');
          setError(sumResult.error || 'Sub-area exceeds block area');
          removeTempLayer(); // Remove temp layer on validation failure
          return;
        }
      }

      console.log('[SubAreaManager] Validation passed! Updating state...');
      console.log('[SubAreaManager] Current subAreas count:', subAreas.length);
      console.log('[SubAreaManager] New subArea:', newSubArea);
      setSubAreas(prev => [...prev, newSubArea]);
      console.log('[SubAreaManager] State update called (will trigger useEffect)');
      // Temp layer will be removed and replaced by state-managed layer in useEffect
    } catch (err) {
      console.log('[SubAreaManager] Error during creation:', err);
      setError('Failed to create sub-area');
      removeTempLayer(); // Remove temp layer on error
    }
  }, [blocks, selectedCategory, subAreas]);

  // Handle sub-area edit (wrapped in useCallback to prevent unnecessary re-renders)
  const handleSubAreaEdit = useCallback((subAreaId: string, geometry: any) => {
    try {
      const area = calculateAreaHectares(geometry);

      // Re-detect block
      const detection = detectBlockForSubArea(geometry, blocks);

      // Calculate block-wise breakdown
      const blockBreakdown = calculateSubAreaByBlock(geometry, blocks);

      setSubAreas(prev =>
        prev.map((subArea) =>
          subArea.id === subAreaId
            ? {
                ...subArea,
                geometry,
                area,
                blockId: detection.blockId,
                blockName: detection.blockName,
                blockBreakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
              }
            : subArea
        )
      );
    } catch (err) {
      setError('Failed to update sub-area');
    }
  }, [blocks]);

  // Handle sub-area delete (wrapped in useCallback to prevent unnecessary re-renders)
  const handleSubAreaDelete = useCallback((subAreaId: string) => {
    setSubAreas(prev => prev.filter((s) => s.id !== subAreaId));
    if (selectedSubAreaId === subAreaId) {
      setSelectedSubAreaId(null);
    }
  }, [selectedSubAreaId]);

  // Handle sub-area name change
  const handleSubAreaNameChange = (subAreaId: string, newName: string) => {
    setSubAreas(
      subAreas.map((subArea) =>
        subArea.id === subAreaId ? { ...subArea, name: newName } : subArea
      )
    );
  };

  // Delete selected sub-area
  const handleDeleteSelected = () => {
    if (selectedSubAreaId) {
      handleSubAreaDelete(selectedSubAreaId);
    }
  };

  // Clear all sub-areas
  const handleClearAll = () => {
    if (confirm('Are you sure you want to delete all sub-areas?')) {
      setSubAreas([]);
      setSelectedSubAreaId(null);
    }
  };

  // Filter sub-areas by block
  const filteredSubAreas =
    selectedBlockFilter === 'all'
      ? subAreas
      : subAreas.filter((s) => s.blockId === selectedBlockFilter);

  // Group sub-areas by block
  const subAreasByBlock: Record<string, SubArea[]> = {};
  subAreas.forEach((subArea) => {
    const blockId = subArea.blockId || 'unknown';
    if (!subAreasByBlock[blockId]) {
      subAreasByBlock[blockId] = [];
    }
    subAreasByBlock[blockId].push(subArea);
  });

  // Use helper function that works for both Polygon and MultiPolygon
  const mapCenter = getGeometryCenter(outerBoundary, [27.7172, 85.3240]);

  return (
    <div className="space-y-4">
      <div className="bg-white p-4 rounded-lg shadow">
        <h2 className="text-lg font-bold mb-3">Define Sub-areas (Optional)</h2>

        {/* Compact Category Selection - Horizontal Chips */}
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-gray-700">Category:</span>
            <HelpTooltip helpText={helpTexts.subAreas.text} position="right" />
          </div>
          <div className="flex flex-wrap gap-2">
            {SUB_AREA_CATEGORIES.map((category) => (
              <button
                key={category.value}
                onClick={() => setSelectedCategory(category.value)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium border-2 transition-all ${
                  selectedCategory === category.value
                    ? 'text-white shadow-sm'
                    : 'bg-white text-gray-700 border-gray-300 hover:border-gray-400'
                }`}
                style={{
                  backgroundColor: selectedCategory === category.value ? category.color : 'white',
                  borderColor: category.color,
                  color: selectedCategory === category.value ? 'white' : category.color,
                }}
              >
                {category.label}
              </button>
            ))}
          </div>
        </div>

        {/* Drawing mode indicator */}
        {subAreas.length === 0 && (
          <div className="mb-3 p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-800">
            Click <strong>polygon icon</strong> on map to draw sub-areas
          </div>
        )}

        {/* Error Messages */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md">
            {error}
          </div>
        )}

        {/* Excluded Area Summary (Private Land) */}
        {subAreas.some(s => s.isExcluded) && (
          <div className="mb-4 p-4 bg-red-50 border-2 border-red-300 rounded-lg">
            <h3 className="font-semibold text-red-900 mb-2">Private Land (Excluded from Forest)</h3>
            <div className="text-sm text-red-800">
              <p className="mb-2">
                These areas are <strong>NOT part of the community forest</strong> and will be excluded from all calculations,
                sampling, and forest management activities.
              </p>
              <p className="font-semibold">
                Total Excluded Area: {formatArea(subAreas.filter(s => s.isExcluded).reduce((sum, s) => sum + s.area, 0))}
              </p>
            </div>
          </div>
        )}

        {/* Sub-areas Summary by Block */}
        {Object.keys(subAreasByBlock).length > 0 && (
          <div className="mb-4">
            <h3 className="font-semibold mb-2">Sub-areas by Block</h3>
            <div className="space-y-2">
              {Object.entries(subAreasByBlock).map(([blockId, blockSubAreas]) => {
                const block = blocks.find((b) => b.id === blockId);
                const blockName = block?.name || 'Unknown Block';
                const blockArea = block?.area || 0;
                // Only count non-excluded sub-areas
                const includedSubAreas = blockSubAreas.filter(s => !s.isExcluded);
                const excludedSubAreas = blockSubAreas.filter(s => s.isExcluded);
                const subAreasTotal = includedSubAreas.reduce((sum, s) => sum + s.area, 0);
                const excludedTotal = excludedSubAreas.reduce((sum, s) => sum + s.area, 0);
                const percentage = blockArea > 0 ? (subAreasTotal / blockArea) * 100 : 0;

                return (
                  <div key={blockId} className="p-3 bg-gray-50 border border-gray-200 rounded">
                    <div className="flex justify-between items-center">
                      <div>
                        <strong>{blockName}</strong>
                        <span className="ml-2 text-sm text-gray-600">
                          ({includedSubAreas.length} sub-areas
                          {excludedSubAreas.length > 0 && `, ${excludedSubAreas.length} excluded`})
                        </span>
                      </div>
                      <div className="text-sm">
                        <div>
                          <span className={percentage > 100 ? 'text-red-600 font-semibold' : 'text-gray-700'}>
                            {formatArea(subAreasTotal)} / {formatArea(blockArea)}
                          </span>
                          <span className="ml-2 text-gray-500">({percentage.toFixed(1)}%)</span>
                        </div>
                        {excludedTotal > 0 && (
                          <div className="text-xs text-red-600 mt-1">
                            Excluded: -{formatArea(excludedTotal)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Sub-areas List - Collapsible */}
        {subAreas.length > 0 && (
          <div className="mb-4 bg-white rounded-lg shadow">
            {/* Collapsible Header */}
            <div 
              className="flex justify-between items-center p-3 bg-gray-50 cursor-pointer rounded-t-lg"
              onClick={() => setShowTable(!showTable)}
            >
              <h3 className="font-semibold flex items-center gap-2">
                <span className="text-gray-400">{showTable ? '▼' : '▶'}</span>
                Sub-areas ({subAreas.length})
              </h3>
              <div className="flex gap-2">
                <select
                  value={selectedBlockFilter}
                  onChange={(e) => setSelectedBlockFilter(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  className="px-3 py-1 text-sm border border-gray-300 rounded"
                >
                  <option value="all">All Blocks</option>
                  {blocks.map((block) => (
                    <option key={block.id} value={block.id}>
                      {block.name}
                    </option>
                  ))}
                </select>
                {selectedSubAreaId && (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteSelected(); }}
                    className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                  >
                    Delete Selected
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); handleClearAll(); }}
                  className="px-3 py-1 text-sm bg-gray-600 text-white rounded hover:bg-gray-700"
                >
                  Clear All
                </button>
              </div>
            </div>

            {showTable && (
              <div className="max-h-80 overflow-y-auto border-t border-gray-200 rounded-b-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Block</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Area</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredSubAreas.map((subArea) => {
                    const category = SUB_AREA_CATEGORIES.find(c => c.value === subArea.category);
                    return (
                      <tr
                        key={subArea.id}
                        className={`hover:bg-gray-50 cursor-pointer ${
                          selectedSubAreaId === subArea.id ? 'bg-blue-50' : ''
                        }`}
                        onClick={() => setSelectedSubAreaId(subArea.id)}
                      >
                        <td className="px-3 py-2">
                          <input
                            type="text"
                            value={subArea.name}
                            onChange={(e) =>
                              handleSubAreaNameChange(subArea.id, e.target.value)
                            }
                            onClick={(e) => e.stopPropagation()}
                            className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                          />
                        </td>
                        <td className="px-3 py-2 text-sm">
                          <div className="flex items-center">
                            <div
                              className="w-3 h-3 rounded-full mr-2"
                              style={{ backgroundColor: category?.color }}
                            />
                            {category?.label}
                          </div>
                        </td>
                        <td className="px-3 py-2 text-sm">
                          {subArea.blockBreakdown && subArea.blockBreakdown.length > 1 ? (
                            <div className="text-xs">
                              <div className="font-medium text-orange-600 mb-1">Spans {subArea.blockBreakdown.length} blocks:</div>
                              {subArea.blockBreakdown.map((bd, idx) => (
                                <div key={idx} className="text-gray-700">
                                  • {bd.blockName}: {formatArea(bd.area)} ({bd.percentage.toFixed(0)}%)
                                </div>
                              ))}
                            </div>
                          ) : (
                            subArea.blockName || 'Unknown'
                          )}
                        </td>
                        <td className="px-3 py-2 text-sm">
                          {formatArea(subArea.area)}
                          {subArea.blockBreakdown && subArea.blockBreakdown.length > 1 && (
                            <span className="text-xs text-gray-500 block">Total</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSubAreaDelete(subArea.id);
                            }}
                            className="text-red-600 hover:text-red-800 text-sm"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Map - Compact Header */}
      <div className="bg-white rounded-lg shadow">
        {/* Compact Legend Bar */}
        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200 rounded-t-lg">
          <div className="flex items-center gap-4">
            <span className="text-xs font-medium text-gray-600">Legend:</span>
            <div className="flex flex-wrap gap-3">
              {SUB_AREA_CATEGORIES.map((category) => (
                <div key={category.value} className="flex items-center">
                  <div
                    className="w-3 h-3 rounded mr-1"
                    style={{ backgroundColor: category.color }}
                  />
                  <span className="text-xs">{category.label}</span>
                </div>
              ))}
            </div>
          </div>
          <span className="text-xs text-gray-500">Click polygon icon to draw</span>
        </div>

        <div className="h-[500px] rounded-b-lg overflow-hidden">
          <MapContainer
            center={mapCenter as [number, number]}
            zoom={14}
            style={{ height: '100%', width: '100%' }}
          >
            <BaseMapSelector />

            {/* Blocks */}
            {blocks.map((block) => (
              <GeoJSON
                key={block.id}
                data={block.geometry}
                style={{
                  color: '#3b82f6',
                  weight: 2,
                  fillOpacity: 0.05,
                  dashArray: '5, 5',
                }}
              />
            ))}

            {/* Drawing controls */}
            <SubAreaDrawingControls
              blocks={blocks}
              selectedCategory={selectedCategory}
              onSubAreaCreated={handleSubAreaCreated}
              subAreas={subAreas}
              selectedSubAreaId={selectedSubAreaId}
              onSubAreaEdit={handleSubAreaEdit}
              onSubAreaDelete={handleSubAreaDelete}
            />
          </MapContainer>
        </div>
      </div>
    </div>
  );
};

export default SubAreaManager;
