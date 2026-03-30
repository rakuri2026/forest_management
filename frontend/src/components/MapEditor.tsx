import React, { useState, useEffect, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import * as turf from '@turf/turf';
import { forestApi } from '../services/api';
import { calculateAreaHectares, calculateSubAreaByBlock, detectBlockForSubArea, validateSubAreasNoOverlap, validateSubAreaSum } from '../utils/geometryValidation';

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
  const [activeCategory, setActiveCategory] = useState<string | null>(null); // Drawing mode - category that will trigger auto-draw
  const [selectedSubAreaId, setSelectedSubAreaId] = useState<string | null>(null);
  const [mode, setMode] = useState<'edit_boundary' | 'edit_blocks' | 'edit_subareas'>('edit_boundary');
  
  // Auto-switch to subareas mode if there are existing sub-areas (after loading) - but only on initial load
  useEffect(() => {
    if (isLoaded && subAreas.length > 0 && mode === 'edit_boundary') {
      // Only auto-switch on initial load, not after saves
      setMode('edit_subareas');
    }
  }, [isLoaded, subAreas]); // Intentionally not including mode in deps to only run on load
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mapInstance, setMapInstance] = useState<L.Map | null>(null);
  const [boundaryLayer, setBoundaryLayer] = useState<L.GeoJSON | null>(null);
  const [blockLayers, setBlockLayers] = useState<L.GeoJSON[]>([]);
  const [subAreaLayers, setSubAreaLayers] = useState<Map<string, L.GeoJSON>>(new Map());
  const [pendingLayers, setPendingLayers] = useState<L.Layer[]>([]);
  const [validationWarnings, setValidationWarnings] = useState<string[]>([]);
  const [isEditingVertices, setIsEditingVertices] = useState(false);
  const [editingLayer, setEditingLayer] = useState<L.Layer | null>(null);
  const [blocksSaved, setBlocksSaved] = useState(false);

  const mapRef = useRef<L.Map | null>(null);
  const subAreaLayersRef = useRef<Map<string, L.GeoJSON>>(new Map());

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
      
      // Remove any previous pending layers (only one new polygon at a time)
      pendingLayers.forEach(prevLayer => {
        try { mapInstance?.removeLayer(prevLayer); } catch (e) {}
      });
      
      // Style the new layer distinctly (purple, not dashed)
      layer.setStyle({
        color: '#a855f7',
        weight: 4,
        fillOpacity: 0.3,
        fillColor: '#a855f7',
      });
      
      setPendingLayers([layer]);
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
      if (pendingLayers.includes(layer)) {
        // Restore to original boundary when new polygon is removed
        setGeometry(initialGeometry);
        setPendingLayers([]);
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

    const category = SUB_AREA_CATEGORIES.find(c => c.value === selectedCategory);
    const categoryColor = category?.color || '#3b82f6';

    mapInstance.pm.addControls({
      position: 'topleft',
      drawPolygon: false, // Disabled - category buttons auto-activate drawing
      drawMarker: false,
      drawCircle: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: false,
      editMode: true, // Enable vertex editing
      dragMode: false,
      cutPolygon: false,
      removalMode: true, // Keep for deleting sub-areas
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
      setValidationWarnings([]); // Clear warnings
      
      // Clear active category after drawing is complete (polygon tool disabled until next activation)
      setActiveCategory(null);
    };

    const handleEdit = (e: any) => {
      console.log('[MapEditor] ========== pm:edit event fired! ==========');
      console.log('[MapEditor] Event object:', e);
      const layers = e.layers;
      if (!layers) {
        console.log('[MapEditor] No layers in event');
        return;
      }
      layers.eachLayer((layer: any) => {
        const geoJSON = layer.toGeoJSON();
        
        // Handle FeatureCollection (from L.geoJSON) vs Feature
        let editedGeometry = null;
        if (geoJSON.type === 'FeatureCollection' && geoJSON.features && geoJSON.features.length > 0) {
          editedGeometry = geoJSON.features[0].geometry;
        } else if (geoJSON.type === 'Feature') {
          editedGeometry = geoJSON.geometry;
        } else if (geoJSON.geometry) {
          editedGeometry = geoJSON.geometry;
        }
        
        // Use the stored _subAreaId property for reliable lookup
        const subAreaId = layer._subAreaId || Array.from(subAreaLayersRef.current.entries()).find(([id, l]) => l === layer)?.[0];
        console.log('[MapEditor] Found subAreaId:', subAreaId);
        if (subAreaId && editedGeometry) {
          console.log('[MapEditor] Sub-area edited:', subAreaId);
          
          const warnings: string[] = [];
          
          // Transform blocks to expected format
          const transformedBlocks = blocks.map(b => ({
            id: b.id || b.block_id || `block-${b.block_index}`,
            name: b.block_name || b.name || b.block_index,
            area: b.area_hectares || 0,
            geometry: b.geometry
          }));
          
          // Calculate new area
          let newArea = 0;
          try {
            const turfFeature = turf.feature(editedGeometry);
            newArea = turf.area(turfFeature) / 10000;
          } catch (e) {
            console.error('Error calculating area after edit:', e);
          }
          
          // Re-detect which block this sub-area belongs to
          const detection = detectBlockForSubArea(editedGeometry, transformedBlocks);
          
          // Calculate block-wise breakdown
          const blockBreakdown = calculateSubAreaByBlock(editedGeometry, transformedBlocks);
          
          // Check for overlaps with other sub-areas
          const otherSubAreas = subAreas.filter(sa => sa.id !== subAreaId);
          const overlapResult = validateSubAreasNoOverlap([...otherSubAreas, { ...subAreas.find(sa => sa.id === subAreaId)!, geometry: editedGeometry }]);
          
          if (!overlapResult.valid) {
            warnings.push(`⚠️ Overlap: ${overlapResult.error}`);
          }
          
          // Check block sum validation
          if (detection.blockId) {
            const updatedSubAreas = subAreas.map(sa => 
              sa.id === subAreaId ? { ...sa, geometry: editedGeometry } : sa
            );
            const sumResult = validateSubAreaSum(
              detection.blockId, 
              updatedSubAreas.filter(sa => sa.block_id === detection.blockId),
              5
            );
            if (!sumResult.valid) {
              warnings.push(`⚠️ ${sumResult.error}`);
            }
          }
          
          // Warn if spanning multiple blocks
          if (blockBreakdown.length > 1) {
            warnings.push(`ℹ️ Spans ${blockBreakdown.length} blocks`);
          }
          
          setValidationWarnings(warnings);
          
          setSubAreas(prev =>
            prev.map(sa =>
              sa.id === subAreaId ? { 
                ...sa, 
                geometry: editedGeometry, 
                area_hectares: Math.max(0.01, newArea),
                block_id: detection.blockId,
                block_name: detection.blockName,
                block_breakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
              } : sa
            )
          );
          
          // Save geometry to backend
          forestApi.updateSubArea(calculationId, subAreaId, {
            geometry: editedGeometry,
            block_id: detection.blockId,
            block_name: detection.blockName,
          }).then(() => {
            console.log('[MapEditor] Sub-area geometry saved');
          }).catch((err: any) => {
            console.error('[MapEditor] Failed to save sub-area geometry:', err);
            // Don't clear warnings on save failure
          });
        }
      });
    };

    const handleRemove = (e: any) => {
      const layer = e.layer;
      // Use the stored _subAreaId property for reliable lookup
      const subAreaId = layer._subAreaId || Array.from(subAreaLayersRef.current.entries()).find(([_, l]) => l === layer)?.[0];
      if (subAreaId) {
        console.log('[MapEditor] Sub-area deleted:', subAreaId);
        setSubAreas(prev => prev.filter(sa => sa.id !== subAreaId));
        const newLayers = new Map(subAreaLayersRef.current);
        newLayers.delete(subAreaId);
        setSubAreaLayers(newLayers);
        subAreaLayersRef.current = newLayers;
        if (selectedSubAreaId === subAreaId) {
          setSelectedSubAreaId(null);
        }
      }
    };

    mapInstance.on('pm:drawstart', handleDrawStart);
    mapInstance.on('pm:create', handleCreate);
    mapInstance.on('pm:edit', handleEdit);
    mapInstance.on('pm:remove', handleRemove);
    
    // Track when vertex editing starts/stops
    mapInstance.on('pm:editstart', (e: any) => {
      console.log('[MapEditor] pm:editstart - layer is being edited');
      const layer = e.layer;
      if (layer) {
        // Mark this layer as being edited to prevent recreation during render
        (layer as any)._pmEditMode = true;
        setIsEditingVertices(true);
        setEditingLayer(layer);
        
        // Find which sub-area this layer belongs to using stored property
        const subAreaId = layer._subAreaId || Array.from(subAreaLayersRef.current.entries()).find(([_, l]) => l === layer)?.[0];
        if (subAreaId) {
          setSelectedSubAreaId(subAreaId);
        }
      }
    });
    
    mapInstance.on('pm:editend', (e: any) => {
      console.log('[MapEditor] pm:editend - editing finished');
      const layer = e.layer || editingLayer;
      if (layer) {
        // Clear the editing flag
        (layer as any)._pmEditMode = false;
        
        // Get the updated geometry
        const geoJSON = layer.toGeoJSON();
        
        // Handle FeatureCollection (from L.geoJSON) vs Feature
        let editedGeometry = null;
        if (geoJSON.type === 'FeatureCollection' && geoJSON.features && geoJSON.features.length > 0) {
          editedGeometry = geoJSON.features[0].geometry;
        } else if (geoJSON.type === 'Feature') {
          editedGeometry = geoJSON.geometry;
        } else if (geoJSON.geometry) {
          editedGeometry = geoJSON.geometry;
        }
        
        console.log('[MapEditor] Updated geometry:', editedGeometry ? JSON.stringify(editedGeometry).substring(0, 200) : 'NOT FOUND');
        
        // Find the sub-area ID using the stored property first
        const subAreaId = layer._subAreaId || Array.from(subAreaLayersRef.current.entries()).find(([_, l]) => l === layer)?.[0];
        console.log('[MapEditor] Sub-area ID for editend:', subAreaId);
        
        if (subAreaId && editedGeometry) {
          // Transform blocks
          const transformedBlocks = blocks.map(b => ({
            id: b.id || b.block_id || `block-${b.block_index}`,
            name: b.block_name || b.name || b.block_index,
            area: b.area_hectares || 0,
            geometry: b.geometry
          }));
          
          // Calculate new area
          let newArea = 0;
          try {
            const turfFeature = turf.feature(editedGeometry);
            newArea = turf.area(turfFeature) / 10000;
          } catch (err) {
            console.error('Error calculating area:', err);
          }
          
          // Re-detect block
          const detection = detectBlockForSubArea(editedGeometry, transformedBlocks);
          const blockBreakdown = calculateSubAreaByBlock(editedGeometry, transformedBlocks);
          
          // Update local state
          setSubAreas(prev =>
            prev.map(sa =>
              sa.id === subAreaId ? { 
                ...sa, 
                geometry: editedGeometry, 
                area_hectares: Math.max(0.01, newArea),
                block_id: detection.blockId,
                block_name: detection.blockName,
                block_breakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
              } : sa
            )
          );
          
          // Save to backend
          forestApi.updateSubArea(calculationId, subAreaId, {
            geometry: editedGeometry,
            block_id: detection.blockId,
            block_name: detection.blockName,
          }).then(() => {
            console.log('[MapEditor] Sub-area geometry saved via editend');
          }).catch((err: any) => {
            console.error('[MapEditor] Failed to save sub-area:', err);
          });
        }
      }
      
      setIsEditingVertices(false);
      setEditingLayer(null);
    });
    
    // Debug: log any PM errors
    mapInstance.on('pm:error', (e: any) => {
      console.log('[MapEditor] PM Error:', e);
    });
    
    // Log all PM events for debugging
    const pmEvents = ['pm:editstart', 'pm:editend', 'pm:edit', 'pm:editmode', 'pm:vertexadded', 'pm:vertexremoved', 'pm:snapdrag', 'pm:markerdragend'];
    pmEvents.forEach(eventName => {
      mapInstance.on(eventName, (e: any) => {
        console.log(`[MapEditor] Event: ${eventName}`, e.layer ? 'has layer' : 'no layer');
      });
    });

    return () => {
      mapInstance.pm.removeControls();
      mapInstance.off('pm:drawstart', handleDrawStart);
      mapInstance.off('pm:create', handleCreate);
      mapInstance.off('pm:edit', handleEdit);
      mapInstance.off('pm:remove', handleRemove);
    };
  }, [mapInstance, mode, selectedCategory, blocks]);

  // Auto-activate polygon drawing when a category is activated
  useEffect(() => {
    if (!mapInstance || mode !== 'edit_subareas') return;
    
    if (activeCategory) {
      console.log('[MapEditor] Activating polygon drawing for category:', activeCategory);
      // Auto-start polygon drawing
      mapInstance.pm.enableDraw('Polygon', {
        snappable: true,
        snapDistance: 20,
      });
    } else {
      // Disable polygon drawing when no active category
      mapInstance.pm.disableDraw('Polygon');
    }
  }, [mapInstance, activeCategory, mode]);

  // Block editing controls
  useEffect(() => {
    if (!mapInstance) {
      console.log('[MapEditor] No mapInstance yet');
      return;
    }
    
    if (mode !== 'edit_blocks') {
      console.log('[MapEditor] Not in edit_blocks mode, skipping controls');
      return;
    }
    
    console.log('[MapEditor] Setting up block editing controls');
    console.log('[MapEditor] Blocks available:', blocks.length);

    // Add drawing controls for block editing
    mapInstance.pm.addControls({
      position: 'topleft',
      drawPolygon: false,
      drawMarker: false,
      drawCircle: false,
      drawCircleMarker: false,
      drawPolyline: false,
      drawRectangle: false,
      editMode: true, // Enable vertex editing
      dragMode: false,
      cutPolygon: false,
      removalMode: true, // Allow deleting vertices and blocks
      vertexDeletion: true, // Enable vertex deletion
    });

    // Track editing state
    let isEditingBlock = false;
    let editingBlockId: string | null = null;

    const handleEditStart = (e: any) => {
      const layer = e.layer;
      if (layer) {
        isEditingBlock = true;
        // Find which block this layer belongs to
        const blockId = (layer as any)._blockId;
        if (blockId) {
          editingBlockId = blockId;
          console.log('[MapEditor] Started editing block:', blockId);
          (layer as any)._pmEditMode = true;
        }
      }
    };

    const handleEdit = (e: any) => {
      console.log('[MapEditor] Block edit event fired');
      const layers = e.layers;
      if (!layers) return;
      
      layers.eachLayer((layer: any) => {
        const geoJSON = layer.toGeoJSON();
        
        // Handle FeatureCollection vs Feature
        let editedGeometry = null;
        if (geoJSON.type === 'FeatureCollection' && geoJSON.features && geoJSON.features.length > 0) {
          editedGeometry = geoJSON.features[0].geometry;
        } else if (geoJSON.type === 'Feature') {
          editedGeometry = geoJSON.geometry;
        } else if (geoJSON.geometry) {
          editedGeometry = geoJSON.geometry;
        }
        
        const blockId = (layer as any)._blockId;
        console.log('[MapEditor] Block edited:', blockId, 'has geometry:', !!editedGeometry);
        
        if (blockId && editedGeometry) {
          // Calculate new area
          let newArea = 0;
          try {
            const turfFeature = turf.feature(editedGeometry);
            newArea = turf.area(turfFeature) / 10000;
            console.log('[MapEditor] New block area:', newArea);
          } catch (err) {
            console.error('Error calculating area:', err);
          }
          
          // Update local state
          setBlocks(prev => prev.map(b => 
            b.block_id === blockId || b.id === blockId
              ? { ...b, geometry: editedGeometry, area_hectares: Math.max(0.01, newArea) }
              : b
          ));
          setBlocksSaved(false);
        }
      });
    };

    const handleEditEnd = (e: any) => {
      console.log('[MapEditor] Block edit ended');
      const layer = e.layer;
      if (layer) {
        (layer as any)._pmEditMode = false;
        
        const geoJSON = layer.toGeoJSON();
        
        // Handle FeatureCollection vs Feature
        let editedGeometry = null;
        if (geoJSON.type === 'FeatureCollection' && geoJSON.features && geoJSON.features.length > 0) {
          editedGeometry = geoJSON.features[0].geometry;
        } else if (geoJSON.type === 'Feature') {
          editedGeometry = geoJSON.geometry;
        } else if (geoJSON.geometry) {
          editedGeometry = geoJSON.geometry;
        }
        
        const blockId = (layer as any)._blockId;
        console.log('[MapEditor] Block edit end - blockId:', blockId);
        
        if (blockId && editedGeometry) {
          // Calculate new area
          let newArea = 0;
          try {
            const turfFeature = turf.feature(editedGeometry);
            newArea = turf.area(turfFeature) / 10000;
          } catch (err) {
            console.error('Error calculating area:', err);
          }
          
          // Update blocks in state
          setBlocks(prev => prev.map(b => 
            b.block_id === blockId || b.id === blockId
              ? { ...b, geometry: editedGeometry, area_hectares: Math.max(0.01, newArea) }
              : b
          ));
          setBlocksSaved(false);
          
          console.log('[MapEditor] Block geometry updated locally, will save on button click');
        }
      }
      
      isEditingBlock = false;
      editingBlockId = null;
    };

    const handleRemove = (e: any) => {
      const layer = e.layer;
      const blockId = (layer as any)._blockId;
      if (blockId) {
        console.log('[MapEditor] Block removed:', blockId);
        // Remove from local state
        setBlocks(prev => prev.filter(b => (b.block_id || b.id) !== blockId));
        setBlocksSaved(false);
      }
    };

    mapInstance.on('pm:editstart', handleEditStart);
    mapInstance.on('pm:edit', handleEdit);
    mapInstance.on('pm:editend', handleEditEnd);
    mapInstance.on('pm:remove', handleRemove);

    return () => {
      mapInstance.pm.removeControls();
      mapInstance.off('pm:editstart', handleEditStart);
      mapInstance.off('pm:edit', handleEdit);
      mapInstance.off('pm:editend', handleEditEnd);
      mapInstance.off('pm:remove', handleRemove);
    };
  }, [mapInstance, mode, blocks]);

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
    
    console.log('[MapEditor] Rendering blocks:', blocks?.length || 0, 'mode:', mode);
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

    // Only render blocks in edit_boundary or edit_blocks mode
    if (mode !== 'edit_boundary' && mode !== 'edit_blocks') {
      console.log('[MapEditor] Skipping block render - not in edit_boundary or edit_blocks mode');
      return;
    }

    // Create new block layers
    const newBlockLayers: L.GeoJSON[] = [];
    const blockColors = ['#ef4444', '#f59e0b', '#10b981', '#06b6d4', '#8b5cf6', '#ec4899'];

    // Determine if blocks should be editable
    const isEditable = mode === 'edit_blocks';

    blocks.forEach((block, index) => {
      if (!block.geometry) return;

      const blockId = block.block_id || block.id || `block-${index}`;
      const blockName = block.block_name || block.name || `Block ${index + 1}`;

      const layer = L.geoJSON(block.geometry, {
        style: {
          color: blockColors[index % blockColors.length],
          weight: isEditable ? 3 : 3,
          fillOpacity: 0.2,
          fillColor: blockColors[index % blockColors.length],
        },
        pmIgnore: !isEditable, // Only allow editing in edit_blocks mode
        interactive: true, // Always allow interactions for clicking and selection
        bubblingMouseEvents: false,
      });
      
      // Store block ID on layer for event handling
      (layer as any)._blockId = blockId;
      
      if (isEditable) {
        // Allow click events for selection
        layer.on('click', () => {
          console.log('[MapEditor] Block clicked:', blockId);
        });
      } else {
        // Disable mouse events when not in edit mode
        layer.on = function() { return layer; };
        layer.off = function() { return layer; };
        layer.getEvents = function() { return {}; };
      }

      // Add popup with block info
      layer.bindPopup(`
        <strong>${blockName}</strong><br/>
        Area: ${block.area_hectares?.toFixed(2) || 'N/A'} ha
      `);

      layer.addTo(mapInstance);
      newBlockLayers.push(layer);
    });

    setBlockLayers(newBlockLayers);
  }, [mapInstance, blocks, mode]);

  // Render sub-areas
  useEffect(() => {
    console.log('[MapEditor Render] Checking conditions: mapInstance=', !!mapInstance, 'mode=', mode, 'subAreas.length=', subAreas.length);
    if (!mapInstance || mode !== 'edit_subareas') {
      console.log('[MapEditor Render] Skipping render - conditions not met');
      return;
    }

    console.log('[MapEditor Render] Rendering', subAreas.length, 'sub-areas');
    
    // Track which sub-area IDs are in the new render
    const newSubAreaIds = new Set(subAreas.map(sa => sa.id));
    
    // Get current layers from ref (not state, which might be stale)
    const currentLayersRef = subAreaLayersRef.current;
    const currentLayersArray = Array.from(currentLayersRef.values());
    
    // Only remove layers that are NOT being edited right now
    currentLayersArray.forEach((layer) => {
      const layerSubAreaId = (layer as any)._subAreaId;
      // Skip if this layer is currently being edited (has _pmEditMode)
      if (layerSubAreaId && (layer as any)._pmEditMode) {
        console.log('[MapEditor Render] Keeping layer that is being edited:', layerSubAreaId);
        return;
      }
      // Remove layers that are no longer in subAreas
      if (!newSubAreaIds.has(layerSubAreaId)) {
        try {
          mapInstance.removeLayer(layer);
        } catch (e) {
          // Layer may already be removed
        }
      }
    });

    const newLayers = new Map<string, L.GeoJSON>();

    subAreas.forEach((subArea) => {
      console.log('[MapEditor Render] Processing sub-area:', subArea.name, 'geometry exists:', !!subArea.geometry);
      if (!subArea.geometry) {
        console.log('[MapEditor Render] Skipping sub-area - no geometry');
        return;
      }
      
      // Check if we already have a layer for this sub-area (and it's not being edited)
      let layer = currentLayersRef.get(subArea.id);
      const existingLayerIsEdited = layer && (layer as any)._pmEditMode;
      
      // Only reuse existing layer if it's not being edited
      if (layer && !existingLayerIsEdited) {
        console.log('[MapEditor Render] Reusing existing layer for:', subArea.id);
        // Update the layer's geometry in case it changed
        try {
          layer.clearLayers();
          layer.addData(subArea.geometry);
        } catch (e) {
          console.log('[MapEditor Render] Error updating layer geometry, recreating:', e);
          layer = undefined;
        }
      }
      
      // Create new layer only if needed
      if (!layer) {
        console.log('[MapEditor Render] Creating new layer for:', subArea.id);
        const category = SUB_AREA_CATEGORIES.find(c => c.value === subArea.category);
        const color = category?.color || '#6b7280';
        const isSelected = subArea.id === selectedSubAreaId;
        const isExcluded = subArea.is_excluded;

        layer = L.geoJSON(subArea.geometry, {
          style: {
            color: isSelected ? '#000000' : color,
            weight: isSelected ? 4 : 2,
            fillOpacity: isExcluded ? 0.5 : 0.3,
            fillColor: isExcluded ? '#dc2626' : color,
            dashArray: isExcluded ? '10, 10' : undefined,
          },
          pmIgnore: false, // Always allow editing - will be controlled by toolbar
          interactive: true, // Allow clicking
          bubblingMouseEvents: false,
        });
        
        // Store sub-area ID on the layer for reliable lookup during editing
        (layer as any)._subAreaId = subArea.id;
        
        // Add click handler to select sub-area
        layer.on('click', () => {
          if (subArea.id !== selectedSubAreaId) {
            setSelectedSubAreaId(subArea.id);
          }
        });

        layer.bindPopup(`
          <strong>${subArea.name}</strong><br/>
          Category: ${category?.label || subArea.category}<br/>
          Area: ${subArea.area_hectares.toFixed(4)} ha<br/>
          ${isExcluded ? '<br/><strong style="color: red;">EXCLUDED FROM FOREST</strong>' : ''}
        `);

        layer.addTo(mapInstance);
      }
      
      // Update selection styling without recreating layer
      const category = SUB_AREA_CATEGORIES.find(c => c.value === subArea.category);
      const color = category?.color || '#6b7280';
      const isSelected = subArea.id === selectedSubAreaId;
      const isExcluded = subArea.is_excluded;
      
      layer.setStyle({
        color: isSelected ? '#000000' : color,
        weight: isSelected ? 4 : 2,
        fillOpacity: isExcluded ? 0.5 : 0.3,
        fillColor: isExcluded ? '#dc2626' : color,
        dashArray: isExcluded ? '10, 10' : undefined,
      });

      newLayers.set(subArea.id, layer);
    });

    setSubAreaLayers(newLayers);
    subAreaLayersRef.current = newLayers; // Update ref for edit handler
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
          const existing = existingSubAreas.find((sa: any) => sa.id === subArea.id);
          
          // Check if name, category, or geometry changed
          const nameChanged = existing && existing.name !== subArea.name;
          const categoryChanged = existing && existing.category !== subArea.category;
          
          // Get current geometry from layer (in case vertices were edited)
          const layer = subAreaLayersRef.current.get(subArea.id);
          let currentGeometry = subArea.geometry;
          let newArea = subArea.area_hectares;
          
          if (layer) {
            try {
              const geoJSON = layer.toGeoJSON();
              currentGeometry = geoJSON.geometry;
              
              // Recalculate area from current layer geometry
              const turfFeature = turf.feature(currentGeometry);
              newArea = turf.area(turfFeature) / 10000;
            } catch (err) {
              console.error('Error getting layer geometry:', err);
            }
          }
          
          // Check if geometry changed
          const existingGeomStr = existing?.geometry ? JSON.stringify(existing.geometry) : '';
          const currentGeomStr = currentGeometry ? JSON.stringify(currentGeometry) : '';
          const geometryChanged = existingGeomStr !== currentGeomStr;
          
          if (nameChanged || categoryChanged || geometryChanged) {
            console.log(`Updating sub-area ${subArea.id}: name=${nameChanged}, category=${categoryChanged}, geometry=${geometryChanged}`);
            
            const transformedBlocks = blocks.map(b => ({
              id: b.id || b.block_id || `block-${b.block_index}`,
              name: b.block_name || b.name || b.block_index,
              area: b.area_hectares || 0,
              geometry: b.geometry
            }));
            
            const detection = detectBlockForSubArea(currentGeometry, transformedBlocks);
            const blockBreakdown = calculateSubAreaByBlock(currentGeometry, transformedBlocks);
            
            try {
              await forestApi.updateSubArea(calculationId, subArea.id, {
                name: subArea.name,
                category: subArea.category,
                geometry: currentGeometry,
                block_id: detection.blockId,
                block_name: detection.blockName,
              });
              console.log('Sub-area updated successfully');
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
            is_excluded: subArea.is_excluded,
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

      // Only call onSave callback if NOT in edit_blocks mode (edit_blocks has its own save button)
      if (mode !== 'edit_blocks') {
        onSave(geometry, subAreas);
      } else {
        // Stay on edit_blocks page after saving
        console.log('[MapEditor] Block save complete, staying on edit_blocks page');
      }
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
          onClick={() => setMode('edit_blocks')}
          className={`px-4 py-2 rounded font-medium ${
            mode === 'edit_blocks'
              ? 'bg-blue-600 text-white'
              : 'bg-white text-gray-700 hover:bg-gray-200'
          }`}
        >
          Edit Blocks ({blocks.length})
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
              <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm mb-4">
                <p className="mb-2"><strong>Instructions:</strong></p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Use the drawing tools on the left to draw or edit the boundary</li>
                  <li>Click on existing boundary to edit vertices</li>
                  <li>Use the scissors tool to split polygons</li>
                  <li>Click <strong>Delete Boundary</strong> button below to remove</li>
                </ul>
              </div>
              
              {geometry && (
                <div className="space-y-2">
                  {pendingLayers.length > 0 && (
                    <div className="mb-3">
                      <div className="p-3 bg-purple-50 border border-purple-300 rounded-lg">
                        <p className="text-sm font-medium text-purple-800 mb-1">
                          New boundary drawn (purple)
                        </p>
                        <p className="text-xs text-gray-600">
                          Drawing a new polygon will replace this one
                        </p>
                      </div>
                      <button
                        onClick={() => {
                          if (confirm('Remove the new polygon? The original boundary will be restored.')) {
                            pendingLayers.forEach(layer => {
                              try { mapInstance?.removeLayer(layer); } catch (e) {}
                            });
                            setPendingLayers([]);
                            setGeometry(initialGeometry); // Restore original
                          }
                        }}
                        className="w-full px-4 py-3 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition-colors"
                      >
                        Remove New Polygon
                      </button>
                    </div>
                  )}
                  
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-xs text-gray-700">
                      <strong>Original boundary (blue)</strong> cannot be deleted.
                      <br/>Use drawing tools to create a new boundary.
                    </p>
                  </div>
                  
                  <button
                    onClick={() => {
                      if (confirm('Reset to original boundary? All changes will be lost.')) {
                        setGeometry(initialGeometry);
                        pendingLayers.forEach(layer => {
                          try { mapInstance?.removeLayer(layer); } catch (e) {}
                        });
                        setPendingLayers([]);
                      }
                    }}
                    className="w-full px-4 py-3 bg-gray-600 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
                  >
                    Reset to Original
                  </button>
                </div>
              )}
              
              {!geometry && (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
                  No boundary drawn. Use the <strong>polygon tool</strong> (top-left of map) to draw one.
                </div>
              )}
            </div>
          ) : mode === 'edit_blocks' ? (
            <div>
              <h3 className="font-semibold mb-3">Block Editing</h3>
              <div className="bg-purple-50 border border-purple-200 rounded p-3 text-sm mb-4">
                <p className="mb-2"><strong>Instructions:</strong></p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Click on a <strong>block</strong> to select it</li>
                  <li>Use the <strong>pencil tool</strong> (top-left) to edit vertices</li>
                  <li><strong>Move</strong> vertices by dragging</li>
                  <li><strong>Add</strong> vertex by clicking on edge</li>
                  <li><strong>Delete</strong> vertex by selecting and pressing Delete</li>
                  <li><strong>Delete entire block</strong> by selecting block and clicking trash icon</li>
                </ul>
              </div>
              
              {blocks.length > 0 ? (
                <div className="space-y-2 mb-4">
                  <h4 className="font-medium text-sm">Blocks ({blocks.length})</h4>
                  {blocks.map((block, index) => {
                    const blockColors = ['#ef4444', '#f59e0b', '#10b981', '#06b6d4', '#8b5cf6', '#ec4899'];
                    const color = blockColors[index % blockColors.length];
                    return (
                      <div key={block.block_id || block.id || index} className="p-2 bg-white border rounded flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <div className="w-4 h-4 rounded" style={{ backgroundColor: color }}></div>
                          <span className="text-sm font-medium">{block.block_name || block.name || `Block ${index + 1}`}</span>
                        </div>
                        <span className="text-xs text-gray-500">{block.area_hectares?.toFixed(2) || 'N/A'} ha</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded text-sm">
                  No blocks defined. Blocks are created during forest creation.
                </div>
              )}
              
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded text-sm">
                <p className="font-medium text-blue-800 mb-1">Outer vs Inner Vertices:</p>
                <ul className="list-disc pl-4 space-y-1 text-gray-700">
                  <li><strong>Outer vertices</strong> (shared with forest boundary) - moving these updates the forest boundary too</li>
                  <li><strong>Inner vertices</strong> (between blocks) - can be edited freely</li>
                </ul>
              </div>
              
              <button
                onClick={async () => {
                  if (!calculationId) return;
                  setLoading(true);
                  try {
                    console.log('[MapEditor] Saving block edits...');
                    
                    // Prepare blocks data for API
                    const blocksData = blocks.map((block, index) => ({
                      block_id: block.block_id || block.id || `block-${index}`,
                      block_name: block.block_name || block.name || `Block ${index + 1}`,
                      geometry: block.geometry,
                      area_hectares: block.area_hectares || 0,
                      index: index,
                    }));
                    
                    console.log('[MapEditor] Blocks to save:', JSON.stringify(blocksData).substring(0, 500));
                    
                    // Call API to update blocks
                    const result = await forestApi.updateBlocksGeometry(calculationId, {
                      blocks: blocksData,
                      update_boundary: true, // Always update boundary for outer vertices
                    });
                    
                    console.log('[MapEditor] Save result:', result);
                    
                    if (result.success) {
                      // Silently save - no alert
                      console.log('[MapEditor] Blocks saved successfully');
                      
                      // Reload sub-areas to get clipped versions
                      const subAreaData = await forestApi.listSubAreas(calculationId);
                      setSubAreas(subAreaData.sub_areas || []);
                      
                      // Mark as saved
                      setBlocksSaved(true);
                    } else {
                      console.error('[MapEditor] Failed to save blocks:', result);
                    }
                  } catch (err: any) {
                    console.error('Error saving blocks:', err);
                  } finally {
                    setLoading(false);
                  }
                }}
                disabled={loading || blocksSaved}
                className={`mt-4 w-full px-4 py-2 rounded font-semibold ${
                  blocksSaved 
                    ? 'bg-green-500 text-white cursor-default' 
                    : 'bg-green-600 text-white hover:bg-green-700 disabled:bg-gray-400'
                }`}
              >
                {loading ? 'Saving...' : blocksSaved ? 'Saved ✓' : 'Save Block Changes'}
              </button>
            </div>
          ) : (
            <div>
              <h3 className="font-semibold mb-3">Sub-area Categories</h3>
              <div className="grid grid-cols-2 gap-2 mb-4">
                {SUB_AREA_CATEGORIES.map((cat) => {
                  const isActive = activeCategory === cat.value;
                  const isSelected = selectedCategory === cat.value;
                  return (
                    <button
                      key={cat.value}
                      onClick={() => {
                        setSelectedCategory(cat.value);
                        setActiveCategory(cat.value); // Start drawing immediately
                      }}
                      className={`px-3 py-2 rounded text-sm text-left border-2 transition-all relative ${
                        isActive
                          ? 'text-white shadow-md'
                          : isSelected
                          ? 'border-gray-800 bg-gray-100'
                          : 'border-gray-300 hover:border-gray-400'
                      }`}
                      style={{
                        borderLeftWidth: '4px',
                        borderLeftColor: cat.color,
                        backgroundColor: isActive ? cat.color : undefined,
                      }}
                    >
                      {cat.label}
                      {isActive && (
                        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs bg-white bg-opacity-20 px-1 rounded">
                          Drawing...
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Active Drawing Indicator */}
              {activeCategory && (
                <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="animate-pulse w-3 h-3 bg-blue-500 rounded-full"></div>
                    <span className="text-blue-800 font-medium">
                      Drawing {SUB_AREA_CATEGORIES.find(c => c.value === activeCategory)?.label}...
                    </span>
                  </div>
                  <button
                    onClick={() => setActiveCategory(null)}
                    className="text-blue-600 hover:text-blue-800 text-sm"
                  >
                    Cancel
                  </button>
                </div>
              )}

              {subAreas.length > 0 && (
                <div className="mt-4">
                  {/* Vertex Edit Save Button */}
                  {isEditingVertices && editingLayer && (
                    <div className="mb-4 p-3 bg-green-50 border-2 border-green-500 rounded-lg">
                      <p className="text-sm font-medium text-green-800 mb-2">
                        Vertex Editing Active
                      </p>
                      <p className="text-xs text-gray-600 mb-2">
                        Move, add, or delete vertices on the map. Changes are saved when you click the <strong>Save</strong> button below.
                      </p>
                      <button
                        onClick={() => {
                          // Trigger save by calling the edit end handler logic
                          const geoJSON = editingLayer.toGeoJSON();
                          
                          // Handle FeatureCollection (from L.geoJSON) vs Feature
                          let editedGeometry = null;
                          if (geoJSON.type === 'FeatureCollection' && geoJSON.features && geoJSON.features.length > 0) {
                            editedGeometry = geoJSON.features[0].geometry;
                          } else if (geoJSON.type === 'Feature') {
                            editedGeometry = geoJSON.geometry;
                          } else if (geoJSON.geometry) {
                            editedGeometry = geoJSON.geometry;
                          }
                          
                          // Use the stored _subAreaId property for reliable lookup
                          const subAreaId = editingLayer._subAreaId || Array.from(subAreaLayersRef.current.entries()).find(([_, l]) => l === editingLayer)?.[0];
                          
                          if (subAreaId && editedGeometry) {
                            const transformedBlocks = blocks.map(b => ({
                              id: b.id || b.block_id || `block-${b.block_index}`,
                              name: b.block_name || b.name || b.block_index,
                              area: b.area_hectares || 0,
                              geometry: b.geometry
                            }));
                            
                            let newArea = 0;
                            try {
                              const turfFeature = turf.feature(editedGeometry);
                              newArea = turf.area(turfFeature) / 10000;
                            } catch (err) {}
                            
                            const detection = detectBlockForSubArea(editedGeometry, transformedBlocks);
                            const blockBreakdown = calculateSubAreaByBlock(editedGeometry, transformedBlocks);
                            
                            setSubAreas(prev =>
                              prev.map(sa =>
                                sa.id === subAreaId ? { 
                                  ...sa, 
                                  geometry: editedGeometry, 
                                  area_hectares: Math.max(0.01, newArea),
                                  block_id: detection.blockId,
                                  block_name: detection.blockName,
                                  block_breakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
                                } : sa
                              )
                            );
                            
                            forestApi.updateSubArea(calculationId, subAreaId, {
                              geometry: editedGeometry,
                              block_id: detection.blockId,
                              block_name: detection.blockName,
                            }).then(() => {
                              console.log('[MapEditor] Sub-area geometry saved');
                              alert('Sub-area geometry saved successfully!');
                            }).catch((err) => {
                              console.error('[MapEditor] Failed to save:', err);
                              alert('Failed to save. Check console for details.');
                            });
                          }
                          
                          // Disable editing mode
                          if (editingLayer.pm) {
                            editingLayer.pm.disable();
                          }
                          setIsEditingVertices(false);
                          setEditingLayer(null);
                        }}
                        className="w-full px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700"
                      >
                        Save Vertices
                      </button>
                      <button
                        onClick={() => {
                          // Cancel editing
                          if (editingLayer.pm) {
                            editingLayer.pm.disable();
                          }
                          setIsEditingVertices(false);
                          setEditingLayer(null);
                        }}
                        className="w-full mt-2 px-4 py-2 bg-gray-200 text-gray-700 rounded font-medium hover:bg-gray-300"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  
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
                          onClick={() => {
                            setSelectedSubAreaId(sa.id);
                            setValidationWarnings([]);
                          }}
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
                              <button
                                onClick={async (e) => {
                                  e.stopPropagation();
                                  console.log('========== SAVE GEOMETRY CLICKED ==========');
                                  console.log('[MapEditor] Sub-area ID to update:', sa.id);
                                  console.log('[MapEditor] All sub-area IDs:', subAreas.map(s => s.id));
                                  console.log('[MapEditor] Available layer IDs:', Array.from(subAreaLayersRef.current.keys()));
                                  
                                  let layer = subAreaLayersRef.current.get(sa.id);
                                  let geometry = sa.geometry; // Default to stored geometry
                                  let newArea = sa.area_hectares;
                                  
                                  if (layer) {
                                    try {
                                      const geoJSON = layer.toGeoJSON();
                                      console.log('[MapEditor] Layer geoJSON type:', geoJSON.type);
                                      console.log('[MapEditor] Layer geoJSON:', JSON.stringify(geoJSON).substring(0, 200));
                                      
                                      // Handle FeatureCollection (from L.geoJSON) vs Feature
                                      let extractedGeometry = null;
                                      if (geoJSON.type === 'FeatureCollection' && geoJSON.features && geoJSON.features.length > 0) {
                                        extractedGeometry = geoJSON.features[0].geometry;
                                      } else if (geoJSON.type === 'Feature') {
                                        extractedGeometry = geoJSON.geometry;
                                      } else if (geoJSON.geometry) {
                                        // Direct geometry object
                                        extractedGeometry = geoJSON.geometry;
                                      }
                                      
                                      if (extractedGeometry) {
                                        geometry = extractedGeometry;
                                        console.log('[MapEditor] Extracted geometry:', JSON.stringify(geometry).substring(0, 200));
                                        
                                        // Recalculate area
                                        try {
                                          const turfFeature = turf.feature(geometry);
                                          newArea = turf.area(turfFeature) / 10000;
                                          console.log('[MapEditor] Recalculated area:', newArea);
                                        } catch (err) {
                                          console.log('[MapEditor] Error calculating area from layer:', err);
                                        }
                                      } else {
                                        console.log('[MapEditor] Could not extract geometry from layer');
                                      }
                                    } catch (err) {
                                      console.log('[MapEditor] Error getting geoJSON from layer:', err);
                                    }
                                  } else {
                                    console.log('[MapEditor] Layer not found in ref, using stored geometry');
                                  }
                                  
                                  // Validate geometry
                                  if (!geometry || !geometry.type || !geometry.coordinates) {
                                    alert('Invalid geometry. Please redraw the sub-area.');
                                    return;
                                  }
                                  
                                  console.log('[MapEditor] Sending to API - subAreaId:', sa.id);
                                  console.log('[MapEditor] Sending to API - geometry type:', geometry.type);
                                  console.log('[MapEditor] Sending to API - geometry coords length:', geometry.coordinates?.length);
                                  console.log('[MapEditor] Sending to API - first coord:', JSON.stringify(geometry.coordinates?.[0] || []).substring(0, 100));
                                  
                                  const transformedBlocks = blocks.map(b => ({
                                    id: b.id || b.block_id || `block-${b.block_index}`,
                                    name: b.block_name || b.name || b.block_index,
                                    area: b.area_hectares || 0,
                                    geometry: b.geometry
                                  }));
                                  
                                  const detection = detectBlockForSubArea(geometry, transformedBlocks);
                                  const blockBreakdown = calculateSubAreaByBlock(geometry, transformedBlocks);

                                  setSubAreas(prev =>
                                    prev.map(s =>
                                      s.id === sa.id ? { 
                                        ...s, 
                                        geometry: geometry, 
                                        area_hectares: Math.max(0.01, newArea),
                                        block_id: detection.blockId,
                                        block_name: detection.blockName,
                                        block_breakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
                                      } : s
                                    )
                                  );
                                  
                                  try {
                                    console.log('[MapEditor] Calling updateSubArea API...');
                                    const result = await forestApi.updateSubArea(calculationId, sa.id, {
                                      geometry: geometry,
                                      block_id: detection.blockId,
                                      block_name: detection.blockName,
                                    });
                                    console.log('[MapEditor] API response:', result);
                                    alert('Sub-area geometry saved successfully!');
                                    
                                    // Verify by reloading
                                    console.log('[MapEditor] Reloading to verify...');
                                    const verifyData = await forestApi.listSubAreas(calculationId);
                                    const updatedSA = verifyData.sub_areas?.find((s: any) => s.id === sa.id);
                                    console.log('[MapEditor] Verified geometry:', updatedSA?.geometry ? JSON.stringify(updatedSA.geometry).substring(0, 200) : 'NOT FOUND');
                                  } catch (err: any) {
                                    console.error('[MapEditor] Failed to save:', err);
                                    console.error('[MapEditor] Error response:', err.response?.data);
                                    alert('Failed to save: ' + (err.response?.data?.detail || err.message));
                                  }
                                }}
                                className="mt-2 w-full px-2 py-1 bg-green-100 text-green-700 rounded text-sm hover:bg-green-200"
                              >
                                Save Geometry
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

              {validationWarnings.length > 0 && (
                <div className="mt-4 p-3 bg-yellow-50 border-2 border-yellow-400 rounded-lg">
                  <p className="font-semibold text-yellow-800 mb-2">Validation Warnings:</p>
                  <ul className="text-sm text-yellow-700 space-y-1">
                    {validationWarnings.map((warning, idx) => (
                      <li key={idx}>{warning}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              <div className="mt-4 bg-blue-50 border border-blue-200 rounded p-3 text-sm">
                <p className="mb-2"><strong>How to Edit Sub-areas:</strong></p>
                <ol className="list-decimal pl-4 space-y-1">
                  <li><strong>Click</strong> a sub-area polygon on the map to select it</li>
                  <li><strong>Click edit tool</strong> (pencil icon) in toolbar</li>
                  <li><strong>Move/add/delete</strong> vertices as needed</li>
                  <li>Click <strong>Save Vertices</strong> button above, OR</li>
                  <li>Click the <strong>✓ Save</strong> button that appears near the vertices</li>
                </ol>
                <div className="mt-2 p-2 bg-yellow-100 border border-yellow-300 rounded">
                  <strong>Important:</strong> Pressing <strong>Escape</strong> cancels changes!
                </div>
              </div>
              
              <button
                onClick={async () => {
                  // Force save all sub-area geometries
                  console.log('[MapEditor] Force saving all sub-areas...');
                  console.log('[MapEditor] Current subAreas:', subAreas.length);
                  console.log('[MapEditor] Current layers:', subAreaLayersRef.current.size);
                  
                  for (const [subAreaId, layer] of subAreaLayersRef.current.entries()) {
                    console.log('[MapEditor] Processing layer for subAreaId:', subAreaId);
                    
                    const geoJSON = layer.toGeoJSON();
                    const geometry = geoJSON.geometry;
                    const subArea = subAreas.find(sa => sa.id === subAreaId);
                    
                    const layerGeomStr = geometry ? JSON.stringify(geometry).substring(0, 100) : 'undefined';
                    const storedGeomStr = subArea?.geometry ? JSON.stringify(subArea.geometry).substring(0, 100) : 'undefined';
                    console.log('[MapEditor] Layer geometry:', layerGeomStr);
                    console.log('[MapEditor] Stored geometry:', storedGeomStr);
                    
                    // Validate geometry before saving
                    if (!geometry || !geometry.type || !geometry.coordinates) {
                      console.error('[MapEditor] Invalid geometry - skipping:', subAreaId);
                      alert(`Invalid geometry for ${subArea?.name || subAreaId}. Please check the polygon.`);
                      continue;
                    }
                    
                    if (geometry.type !== 'Polygon' && geometry.type !== 'MultiPolygon') {
                      console.error('[MapEditor] Invalid geometry type:', geometry.type);
                      alert(`Invalid geometry type: ${geometry.type}. Must be Polygon or MultiPolygon.`);
                      continue;
                    }
                    
                    const hasValidCoords = geometry.coordinates && 
                      Array.isArray(geometry.coordinates) && 
                      geometry.coordinates.length > 0;
                    
                    if (!hasValidCoords) {
                      console.error('[MapEditor] Invalid coordinates');
                      alert(`Invalid coordinates for ${subArea?.name || subAreaId}.`);
                      continue;
                    }
                    
                    const storedGeomJson = subArea?.geometry ? JSON.stringify(subArea.geometry) : null;
                    const layerGeomJson = JSON.stringify(geometry);
                    const hasChanges = storedGeomJson !== layerGeomJson;
                    
                    console.log('[MapEditor] Has changes:', hasChanges);
                    
                    if (hasChanges) {
                      console.log('[MapEditor] Saving sub-area:', subAreaId);
                      
                      const transformedBlocks = blocks.map(b => ({
                        id: b.id || b.block_id || `block-${b.block_index}`,
                        name: b.block_name || b.name || b.block_index,
                        area: b.area_hectares || 0,
                        geometry: b.geometry
                      }));
                      
                      let newArea = 0;
                      try {
                        const turfFeature = turf.feature(geometry);
                        newArea = turf.area(turfFeature) / 10000;
                      } catch (err) {
                        console.error('[MapEditor] Area calculation failed:', err);
                      }
                      
                      const detection = detectBlockForSubArea(geometry, transformedBlocks);
                      const blockBreakdown = calculateSubAreaByBlock(geometry, transformedBlocks);
                      
                      setSubAreas(prev =>
                        prev.map(sa =>
                          sa.id === subAreaId ? { 
                            ...sa, 
                            geometry: geometry, 
                            area_hectares: Math.max(0.01, newArea),
                            block_id: detection.blockId,
                            block_name: detection.blockName,
                            block_breakdown: blockBreakdown.length > 0 ? blockBreakdown : undefined,
                          } : sa
                        )
                      );
                      
                      try {
                        await forestApi.updateSubArea(calculationId, subAreaId, {
                          geometry: geometry,
                          block_id: detection.blockId,
                          block_name: detection.blockName,
                        });
                        console.log('[MapEditor] Saved successfully:', subAreaId);
                        alert(`Saved ${subArea?.name || subAreaId} successfully!`);
                      } catch (err) {
                        console.error('[MapEditor] Failed to save:', subAreaId, err);
                        alert(`Failed to save ${subArea?.name || subAreaId}. Check console for details.`);
                      }
                    } else {
                      console.log('[MapEditor] No changes detected for:', subAreaId);
                    }
                  }
                }}
                className="mt-4 w-full px-4 py-3 bg-purple-600 text-white rounded-lg font-semibold hover:bg-purple-700"
              >
                Force Save All Sub-area Geometries
              </button>
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