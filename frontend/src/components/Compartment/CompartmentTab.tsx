import { useState, useEffect, useCallback } from 'react';
import { compartmentApi, inventoryApi, forestApi } from '../../services/api';
import { AvailableBlock, SplitConfig, SplitPreviewResponse } from './types';
import { CompartmentTreeView } from './CompartmentTreeView';
import { CompartmentDetailsPanel } from './CompartmentDetailsPanel';
import { SplitConfigurationPanel } from './SplitConfigurationPanel';
import { TreeReassignmentDialog } from './TreeReassignmentDialog';
import { MapContainer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import BaseMapSelector from '../MapCreation/BaseMapSelector';
import { generateExportFileName, CONTENT_TYPES } from '../../utils/fileNaming';

// DBH Class colors and sizes (1/3 of original)
const DBH_CLASS_CONFIG: Record<string, { color: string; fillColor: string; radius: number; label: string }> = {
  'Regeneration (0.1-4)': { color: '#8b5cf6', fillColor: '#a78bfa', radius: 1, label: 'पुनरोत्पादन' },
  'Sapling (4-10)': { color: '#3b82f6', fillColor: '#60a5fa', radius: 1, label: 'बोटविरुवा' },
  'Small pole (10-20)': { color: '#22c55e', fillColor: '#4ade80', radius: 1.5, label: 'सानो खाँट' },
  'Large pole (20-30)': { color: '#eab308', fillColor: '#facc15', radius: 2, label: 'ठूलो खाँट' },
  'Small tree (30-40)': { color: '#f97316', fillColor: '#fb923c', radius: 2, label: 'सानो रूख' },
  'Medium tree (40-50)': { color: '#ef4444', fillColor: '#f87171', radius: 2.5, label: 'मध्यम रूख' },
  'Large tree (50-60)': { color: '#dc2626', fillColor: '#fca5a5', radius: 3, label: 'ठूलो रूख' },
  'Very large tree (>60)': { color: '#991b1b', fillColor: '#fecaca', radius: 3, label: 'अति ठूलो रूख' },
};

// Default config for unknown classes
const DEFAULT_DBH_CONFIG = { color: '#6b7280', fillColor: '#9ca3af', radius: 3, label: 'अन्य' };

// Component to create grid overlay based on grid cells from backend API
function GridOverlay({ 
  inventoryId, 
  show 
}: { 
  inventoryId: string | null, 
  show: boolean 
}) {
  const map = useMap();
  const [gridCells, setGridCells] = useState<any[]>([]);
  const [metadata, setMetadata] = useState<any>(null);
  
  useEffect(() => {
    console.log('[GridOverlay] Rendering - show:', show, 'inventoryId:', inventoryId);
    
    // Clear existing grid first
    map.eachLayer((layer: any) => {
      if (layer.options && (layer.options.isGridCell || layer.options.isGridLine)) {
        map.removeLayer(layer);
      }
    });
    
    // Clear grid labels
    map.eachLayer((layer: any) => {
      if (layer instanceof L.Marker && layer.options && layer.options.icon && 
          layer.options.icon.options && layer.options.icon.options.className === 'grid-label') {
        map.removeLayer(layer);
      }
    });
    
    if (!show || !inventoryId) {
      console.log('[GridOverlay] Skipping - no show or inventoryId');
      setGridCells([]);
      setMetadata(null);
      return;
    }
    
    // Fetch grid cells from API
    const fetchGridCells = async () => {
      try {
        console.log('[GridOverlay] Fetching grid cells for inventory:', inventoryId);
        const data = await inventoryApi.getGridCells(inventoryId);
        console.log('[GridOverlay] Grid cells fetched:', data);
        
        if (data && data.features) {
          setGridCells(data.features);
          setMetadata(data.metadata);
        } else {
          setGridCells([]);
          setMetadata(null);
        }
      } catch (err) {
        console.error('[GridOverlay] Error fetching grid cells:', err);
        setGridCells([]);
        setMetadata(null);
      }
    };
    
    fetchGridCells();
  }, [show, inventoryId, map]);
  
  // Render grid cells when they change
  useEffect(() => {
    if (gridCells.length === 0) return;
    
    console.log('[GridOverlay] Rendering', gridCells.length, 'grid cells from API');
    
    const gridGroup = L.layerGroup();
    (gridGroup as any).options.isGridCell = true;
    
    gridCells.forEach((cell) => {
      const geom = cell.geometry;
      if (!geom || !geom.coordinates) return;
      
      // Convert GeoJSON to Leaflet polygon
      const coords = geom.coordinates[0].map((c: number[]) => [c[1], c[0]]);
      
      const polygon = L.polygon(coords, {
        color: '#94a3b8',
        weight: 1,
        fillColor: '#cbd5e1',
        fillOpacity: 0.2,
        interactive: false
      });
      (polygon as any).options.isGridCell = true;
      gridGroup.addLayer(polygon);
      
      // Add cell_id label at centroid
      const cellId = cell.properties?.cell_id;
      if (cellId !== undefined) {
        let latSum = 0, lonSum = 0;
        coords.forEach((c: number[]) => {
          latSum += c[0];
          lonSum += c[1];
        });
        const centerLat = latSum / coords.length;
        const centerLon = lonSum / coords.length;
        
        const marker = L.marker([centerLat, centerLon], {
          icon: L.divIcon({
            className: 'grid-label',
            html: `<div style="font-size:9px;color:#64748b;background:rgba(255,255,255,0.8);padding:1px 2px;border-radius:2px;">${cellId}</div>`,
            iconSize: [35, 15]
          })
        });
        marker.addTo(map);
      }
    });
    
    gridGroup.addTo(map);
    
    console.log('[GridOverlay] Grid cells added from API');
    
    return () => {
      map.eachLayer((layer: any) => {
        if (layer.options && layer.options.isGridCell) {
          map.removeLayer(layer);
        }
      });
      map.eachLayer((layer: any) => {
        if (layer instanceof L.Marker && layer.options && layer.options.icon && 
            layer.options.icon.options && layer.options.icon.options.className === 'grid-label') {
          map.removeLayer(layer);
        }
      });
    };
  }, [gridCells, map]);
  
  return null;
}

// Component to fit map bounds
function MapBoundsController({ bounds }: { bounds: [[number, number], [number, number]] | null }) {
  const map = useMap();
  
  useEffect(() => {
    if (bounds) {
      try {
        map.fitBounds(bounds, { padding: [30, 30] });
      } catch (e) {
        console.error('Error fitting bounds:', e);
      }
    }
  }, [bounds, map]);
  
  return null;
}

// Component to add labels to polygons
function PolygonLabels({ features }: { features: any[] }) {
  const map = useMap();
  
  useEffect(() => {
    // Clear existing labels
    map.eachLayer((layer: any) => {
      if (layer instanceof L.Marker && layer.options && layer.options.zIndexOffset === 1000) {
        map.removeLayer(layer);
      }
    });
    
    // Add labels for each feature
    features.forEach((feature) => {
      const geom = feature.geometry;
      if (!geom || !geom.coordinates || !geom.coordinates[0]) return;
      
      // Calculate centroid
      const coords = geom.coordinates[0];
      if (!Array.isArray(coords) || coords.length < 3) return;
      let latSum = 0, lonSum = 0;
      let valid = true;
      coords.forEach((c: number[]) => {
        if (c && typeof c[0] === 'number' && typeof c[1] === 'number' && !isNaN(c[0]) && !isNaN(c[1])) {
          lonSum += c[0];
          latSum += c[1];
        } else {
          valid = false;
        }
      });
      if (!valid) return;
      const centerLat = latSum / coords.length;
      const centerLon = lonSum / coords.length;
      if (isNaN(centerLat) || isNaN(centerLon)) return;
      
      const labelColor = feature.is_compartment ? '#10b981' : '#3b82f6';
      
      // Text-only label with area and text stroke for satellite visibility
      const areaText = feature.area_hectares >= 1 
        ? `${feature.area_hectares.toFixed(1)} ha` 
        : `${(feature.area_hectares * 10000).toFixed(0)} m²`;
      
      const svgLabel = `
        <svg width="150" height="20" xmlns="http://www.w3.org/2000/svg">
          <text 
            x="75" 
            y="14" 
            text-anchor="middle" 
            font-family="Arial, sans-serif" 
            font-size="11" 
            font-weight="bold" 
            fill="white"
            paint-order="stroke"
            stroke="black"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
          >${feature.name} (${areaText})</text>
        </svg>
      `;
      
      const icon = L.divIcon({
        html: svgLabel,
        className: 'polygon-svg-label',
        iconSize: [150, 20],
        iconAnchor: [75, 10]
      });
      
      const marker = L.marker([centerLat, centerLon], { 
        icon, 
        interactive: false,
        keyboard: false,
        zIndexOffset: 1000
      });
      marker.addTo(map);
    });
    
    return () => {
      map.eachLayer((layer: any) => {
        if (layer instanceof L.Marker && layer.options && layer.options.zIndexOffset === 1000) {
          map.removeLayer(layer);
        }
      });
    };
  }, [features, map]);
  
  return null;
}

interface CompartmentTabProps {
  calculationId: string;
}

export function CompartmentTab({ calculationId }: CompartmentTabProps) {
  const [blocks, setBlocks] = useState<AvailableBlock[]>([]);
  const [allFeatures, setAllFeatures] = useState<any[]>([]);
  const [selectedBlock, setSelectedBlock] = useState<AvailableBlock | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [showTrees, setShowTrees] = useState(false);
  const [showGrid, setShowGrid] = useState(false);
  const [showMotherTrees, setShowMotherTrees] = useState(false);
  const [gridSpacing, setGridSpacing] = useState(20);
  const [trees, setTrees] = useState<any[]>([]);
  const [inventoryId, setInventoryId] = useState<string | null>(null);

  const [showReassignmentDialog, setShowReassignmentDialog] = useState(false);
  const [reassignmentBlockId, setReassignmentBlockId] = useState<string | null>(null);
  const [reassignmentBlockName, setReassignmentBlockName] = useState<string>('');

  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  // Forest name for export
  const [forestName, setForestName] = useState<string>('UnknownForest');
  
  // Base Map Selection
  const [baseMap, setBaseMap] = useState<string>('satellite');
  
  const baseMapOptions = [
    { value: 'satellite', label: 'Satellite', icon: '🛰️' },
    { value: 'topographic', label: 'Topographic', icon: '🗻' },
    { value: 'osm', label: 'Street Map', icon: '🗺️' },
  ];

  // NEW: Compartment tree state
  const [compartmentTree, setCompartmentTree] = useState<any[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<any | null>(null);

  useEffect(() => {
    loadBlocks();
    loadTrees();
    loadCompartmentTree();
    forestApi.getCalculation(calculationId).then(data => {
      setForestName(data.forest_name || 'UnknownForest');
    }).catch(() => {});
  }, [calculationId]);

  const loadTrees = async () => {
    try {
      console.log('[CompartmentTab] Loading trees for calculation:', calculationId);
      const result = await compartmentApi.getTreesForMap(calculationId);
      console.log('[CompartmentTab] Trees loaded:', result.count, result.trees?.length);
      setTrees(result.trees || []);
      
      // Get grid spacing and inventory ID from API response
      if (result.grid_spacing_meters) {
        console.log('[CompartmentTab] Grid spacing from API:', result.grid_spacing_meters);
        setGridSpacing(result.grid_spacing_meters);
      }
      if (result.inventory_id) {
        console.log('[CompartmentTab] Inventory ID from API:', result.inventory_id);
        setInventoryId(result.inventory_id);
      }
    } catch (err: any) {
      console.error('[CompartmentTab] Error loading trees:', err);
    }
  };

  // NEW: Load compartment tree
  const loadCompartmentTree = async () => {
    try {
      console.log('[CompartmentTab] Loading compartment tree for:', calculationId);
      const data = await compartmentApi.getCompartmentTree(calculationId);
      console.log('[CompartmentTab] Compartment tree loaded:', data);
      setCompartmentTree(data.blocks || []);
    } catch (err: any) {
      console.error('[CompartmentTab] Error loading compartment tree:', err);
    }
  };

  const loadBlocks = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('[CompartmentTab] Loading blocks for calculation:', calculationId);
      
      // Load parent blocks for selection panel
      const data = await compartmentApi.getAvailableBlocks(calculationId);
      console.log('[CompartmentTab] Received blocks:', data);
      setBlocks(data);

      // Load all blocks (including compartments) for the map
      const allBlocks = await compartmentApi.getAllBlocks(calculationId);
      console.log('[CompartmentTab] All blocks for map:', allBlocks);
      setAllFeatures(allBlocks);

      if (selectedBlock) {
        const updated = data.find((b: AvailableBlock) => b.id === selectedBlock.id);
        if (updated) {
          setSelectedBlock(updated);
        } else {
          setSelectedBlock(null);
        }
      }
    } catch (err: any) {
      console.error('[CompartmentTab] Error loading blocks:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load blocks');
    } finally {
      setLoading(false);
    }
  }, [calculationId, selectedBlock?.id]);

  const handlePreviewSplit = async (config: SplitConfig): Promise<SplitPreviewResponse | null> => {
    if (!selectedBlock) return null;

    try {
      const preview = await compartmentApi.previewSplit({
        block_id: selectedBlock.id,
        method: config.method,
        parameters: config.parameters,
      });
      return preview;
    } catch (err: any) {
      throw err;
    }
  };

  const handleExecuteSplit = async (config: SplitConfig): Promise<void> => {
    if (!selectedBlock) return;

    try {
      const result = await compartmentApi.executeSplit({
        block_id: selectedBlock.id,
        method: config.method,
        parameters: config.parameters,
        naming_pattern: config.naming_pattern,
        reassign_trees: config.reassign_trees,
        notes: config.notes,
      });

      setSuccessMessage(result.message);
      setTimeout(() => setSuccessMessage(null), 5000);

      if (result.trees_reassigned > 0) {
        setReassignmentBlockId(selectedBlock.id);
        setReassignmentBlockName(selectedBlock.name);
        setShowReassignmentDialog(true);
      } else {
        await loadBlocks();
        setSelectedBlock(null);
      }
    } catch (err: any) {
      throw err;
    }
  };

  const handleReassignmentComplete = async () => {
    setShowReassignmentDialog(false);
    setReassignmentBlockId(null);
    setReassignmentBlockName('');
    await loadBlocks();
    setSelectedBlock(null);
  };

  const handleReassignmentCancel = () => {
    setShowReassignmentDialog(false);
    setReassignmentBlockId(null);
    setReassignmentBlockName('');
    loadBlocks();
    setSelectedBlock(null);
  };

  const handleDeleteCompartments = async (blockId: string, blockName: string) => {
    try {
      const result = await compartmentApi.deleteCompartments(blockId);
      setSuccessMessage(`Deleted ${result.compartments_deleted} compartments for "${result.block_name}".`);
      setTimeout(() => setSuccessMessage(null), 5000);
      await loadBlocks();
      if (selectedBlock?.id === blockId) {
        setSelectedBlock(null);
      }
    } catch (err: any) {
      // Check if it's the tree association error
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to delete compartments';
      if (errorMsg.includes('trees are associated')) {
        setError(errorMsg + ' Please go to the Tree Upload section and delete the tree inventory first, then come back to delete the compartments.');
      } else {
        setError(errorMsg);
      }
    }
  };

  // NEW: Handle node selection (highlight on map)
  const handleSelectNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    
    // Find node in tree
    const findNode = (nodes: any[]): any | null => {
      for (const node of nodes) {
        if (node.id === nodeId) return node;
        if (node.children && node.children.length > 0) {
          const found = findNode(node.children);
          if (found) return found;
        }
      }
      return null;
    };
    
    const node = findNode(compartmentTree);
    setSelectedNode(node);
    
    // If node is a block, set selectedBlock for split configuration
    if (node && !node.is_compartment) {
      // Find the block in blocks array
      const block = blocks.find(b => b.id === nodeId);
      if (block) {
        setSelectedBlock(block);
      }
    }
    
    console.log('[CompartmentTab] Selected node:', node?.name, 'ID:', nodeId);
  };

  // NEW: Handle rename
  const handleRename = async (nodeId: string, newName: string) => {
    try {
      await compartmentApi.updateCompartmentName(nodeId, newName);
      setSuccessMessage(`Renamed to "${newName}"`);
      setTimeout(() => setSuccessMessage(null), 3000);
      
      // Reload tree
      await loadCompartmentTree();
      await loadBlocks();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to rename');
      console.error('[CompartmentTab] Rename failed:', err);
    }
  };

  // NEW: Handle delete compartment
  const handleDeleteNode = async (nodeId: string, nodeName: string) => {
    if (!confirm(`Delete compartment "${nodeName}"? This will also delete any sub-compartments.`)) {
      return;
    }
    try {
      const result = await compartmentApi.deleteCompartment(nodeId);
      setSuccessMessage(`Deleted "${nodeName}"${result.children_deleted > 0 ? ` and ${result.children_deleted} sub-compartment(s)` : ''}.`);
      setTimeout(() => setSuccessMessage(null), 3000);

      // Reload tree
      await loadCompartmentTree();
      await loadBlocks();
      if (selectedNodeId === nodeId) {
        setSelectedNodeId(null);
        setSelectedNode(null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete compartment');
      console.error('[CompartmentTab] Delete failed:', err);
    }
  };

  // NEW: Handle toggle lock
  const handleToggleLock = async (nodeId: string) => {
    try {
      const result = await compartmentApi.toggleLockBlock(nodeId);
      setSuccessMessage(result.message || 'Lock status updated');
      setTimeout(() => setSuccessMessage(null), 3000);
      
      // Reload tree
      await loadCompartmentTree();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to toggle lock');
      console.error('[CompartmentTab] Toggle lock failed:', err);
    }
  };

  // NEW: Handle sub-divide (redirects to split configuration)
  const handleSubDivide = (nodeId: string) => {
    // Find the node in tree
    const findNode = (nodes: any[]): any | null => {
      for (const node of nodes) {
        if (node.id === nodeId) return node;
        if (node.children && node.children.length > 0) {
          const found = findNode(node.children);
          if (found) return found;
        }
      }
      return null;
    };
    
    const node = findNode(compartmentTree);
    if (node && node.is_compartment) {
      // Set selectedBlock to show split configuration
      const block = blocks.find(b => b.id === nodeId);
      if (block) {
        setSelectedBlock(block);
      } else {
        // If not in blocks array, create a temporary AvailableBlock object
        setSelectedBlock({
          id: node.id,
          name: node.name,
          area_sqm: node.area_sqm,
          area_hectares: node.area_hectares,
          geometry: null,
          has_compartments: node.child_count > 0,
          tree_count: node.tree_count || 0,
          compartment_count: node.child_count || 0,
          total_trees_in_calculation: 0
        });
      }
    }
  };

  const handleDownloadGpkg = async () => {
    console.log('[CompartmentTab] Download GPKG clicked, calculationId:', calculationId);
    try {
      setError(null);
      setDownloading(true);
      await compartmentApi.exportGpkg(calculationId, forestName);
      console.log('[CompartmentTab] GPKG download completed');
    } catch (err: any) {
      console.error('[CompartmentTab] GPKG download error:', err);
      const errorMsg = err.message || err.response?.data?.detail || 'Failed to download GPKG';
      setError(errorMsg);
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadKml = async () => {
    console.log('[CompartmentTab] Download KML clicked, calculationId:', calculationId);
    try {
      setError(null);
      setDownloading(true);
      await compartmentApi.exportKml(calculationId, forestName);
      console.log('[CompartmentTab] KML download completed');
    } catch (err: any) {
      console.error('[CompartmentTab] KML download error:', err);
      const errorMsg = err.message || err.response?.data?.detail || 'Failed to download KML';
      setError(errorMsg);
    } finally {
      setDownloading(false);
    }
  };

  // Calculate map center from features
  const getMapCenter = (): [number, number] => {
    if (allFeatures.length === 0) return [27.7172, 85.3240];
    
    // Find first compartment or block to center on
    const targetFeatures = allFeatures.filter(f => f.is_compartment) || allFeatures;
    
    const lats = targetFeatures.map(b => {
      const geom = b.geometry;
      if (geom?.coordinates && geom.coordinates[0]) {
        const coords = geom.coordinates[0];
        if (!Array.isArray(coords) || coords.length < 3) return NaN;
        let sum = 0, count = 0;
        coords.forEach((c: number[]) => {
          if (c && typeof c[1] === 'number' && !isNaN(c[1])) { sum += c[1]; count++; }
        });
        return count > 0 ? sum / count : NaN;
      }
      return NaN;
    }).filter((v: number) => !isNaN(v));
    
    const lons = targetFeatures.map(b => {
      const geom = b.geometry;
      if (geom?.coordinates && geom.coordinates[0]) {
        const coords = geom.coordinates[0];
        if (!Array.isArray(coords) || coords.length < 3) return NaN;
        let sum = 0, count = 0;
        coords.forEach((c: number[]) => {
          if (c && typeof c[0] === 'number' && !isNaN(c[0])) { sum += c[0]; count++; }
        });
        return count > 0 ? sum / count : NaN;
      }
      return NaN;
    }).filter((v: number) => !isNaN(v));
    
    if (lats.length === 0 || lons.length === 0) return [27.7172, 85.3240];
    
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    
    if (isNaN(minLat) || isNaN(maxLat) || isNaN(minLon) || isNaN(maxLon)) return [27.7172, 85.3240];
    
    return [
      (minLat + maxLat) / 2,
      (minLon + maxLon) / 2
    ];
  };

  // Get bounds for map fitting - prioritize compartments
  const getMapBounds = () => {
    if (allFeatures.length === 0) return null;
    
    // Find compartments to zoom to
    const compartments = allFeatures.filter(f => f.is_compartment);
    const featuresToUse = compartments.length > 0 ? compartments : allFeatures;
    
    let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
    
    for (const feature of featuresToUse) {
      const geom = feature.geometry;
      if (geom?.coordinates && geom.coordinates[0]) {
        for (const coord of geom.coordinates[0]) {
          if (!coord || coord.length < 2 || isNaN(coord[0]) || isNaN(coord[1])) continue;
          minLat = Math.min(minLat, coord[1]);
          maxLat = Math.max(maxLat, coord[1]);
          minLon = Math.min(minLon, coord[0]);
          maxLon = Math.max(maxLon, coord[0]);
        }
      }
    }
    
    if (minLat === 90 || isNaN(minLat) || isNaN(maxLat) || isNaN(minLon) || isNaN(maxLon)) return null;
    
    return [[minLat, minLon], [maxLat, maxLon]];
  };

  return (
    <div className="h-full flex flex-col">
      {/* Success message */}
      {successMessage && (
        <div className="mx-4 mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-sm text-green-800">{successMessage}</span>
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="mx-4 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            <span className="text-sm text-red-800">{error}</span>
          </div>
        </div>
      )}

      {/* Map Section - Square layout */}
      <div className="border-b bg-gray-50">
        <div className="flex justify-between items-center px-4 py-2 border-b bg-white">
          <h3 className="text-sm font-medium text-gray-700">Block & Compartment Map</h3>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-600">Base Map:</span>
            <div className="flex rounded-md overflow-hidden border border-gray-300">
              {baseMapOptions.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setBaseMap(opt.value)}
                  className={`px-2 py-0.5 text-xs transition-colors ${
                    baseMap === opt.value
                      ? 'bg-green-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {opt.icon}
                </button>
              ))}
            </div>
            <span className="text-xs text-gray-500 ml-2">{allFeatures.length} features</span>
            <button
              onClick={handleDownloadGpkg}
              disabled={downloading || allFeatures.length === 0}
              className="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              title="Download as GeoPackage"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              GPKG
            </button>
            <button
              onClick={handleDownloadKml}
              disabled={downloading || allFeatures.length === 0}
              className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              title="Download for Google Earth"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              KML
            </button>
          </div>
        </div>
        <div className="w-full relative" style={{ height: 'calc(100vh - 380px)', minHeight: '300px' }}>
          <MapContainer
            center={getMapCenter()}
            zoom={14}
            style={{ height: '100%', width: '100%' }}
          >
            <BaseMapSelector baseMap={baseMap} />
            
            <MapBoundsController bounds={getMapBounds()} />
            
            <GridOverlay inventoryId={inventoryId} show={showGrid} />
            
            {/* Render all blocks and compartments */}
            {allFeatures.map((feature) => {
              const geom = feature.geometry;
              if (geom?.coordinates?.[0]?.[0] && (isNaN(geom.coordinates[0][0][0]) || isNaN(geom.coordinates[0][0][1]))) return null;
              return (
              <GeoJSON
                key={feature.id}
                data={feature.geometry}
                style={{
                  color: selectedNodeId === feature.id ? '#ef4444' : (feature.is_compartment ? (feature.color || '#10b981') : '#3b82f6'),
                  weight: selectedNodeId === feature.id ? 4 : (feature.is_compartment ? 1.5 : 2),
                  fillOpacity: selectedNodeId === feature.id ? 0.4 : (feature.is_compartment ? 0.4 : 0.15),
                  fillColor: feature.is_compartment ? (feature.color || '#86efac') : '#93c5fd',
                  interactive: false
                }}
              />
              );
            })}
            
            {/* Add tree points if visible */}
            {showTrees && trees.length > 0 && (
              <>
                {trees.map((tree) => {
                  // Get DBH class config based on dbh_class property
                  const dbhClass = tree.dbh_class || 'Unknown';
                  const config = DBH_CLASS_CONFIG[dbhClass] || DEFAULT_DBH_CONFIG;
                  
                  return (
                    <GeoJSON
                      key={`tree-${tree.id}`}
                      data={{
                        type: 'Feature',
                        geometry: {
                          type: 'Point',
                          coordinates: [tree.longitude, tree.latitude]
                        },
                        properties: {
                          species: tree.species,
                          dbh: tree.dbh_cm,
                          height: tree.height_m,
                          dbh_class: tree.dbh_class,
                          grid_cell_id: tree.grid_cell_id,
                          remark: tree.remark
                        }
                      }}
                      pointToLayer={(feature, latlng) => {
                        return L.circleMarker(latlng, {
                          radius: config.radius,
                          fillColor: config.fillColor,
                          color: config.color,
                          weight: 1.5,
                          fillOpacity: 0.85
                        });
                      }}
                      onEachFeature={(feature, layer) => {
                        layer.bindPopup(`
                          <strong>${feature.properties.species}</strong><br/>
                          DBH: ${feature.properties.dbh} cm<br/>
                          Height: ${feature.properties.height} m<br/>
                          Class: ${feature.properties.dbh_class}<br/>
                          Grid Cell: ${feature.properties.grid_cell_id ?? 'N/A'}<br/>
                          Remark: ${feature.properties.remark ?? 'None'}
                        `);
                      }}
                    />
                  );
                })}
              </>
            )}
            
            {/* Mother Trees Layer - Red markers */}
            {showMotherTrees && trees.length > 0 && (
              <>
                {trees.filter(t => t.remark === 'Mother Tree').map((tree) => (
                  <GeoJSON
                    key={`mother-${tree.id}`}
                    data={{
                      type: 'Feature',
                      geometry: {
                        type: 'Point',
                        coordinates: [tree.longitude, tree.latitude]
                      },
                      properties: {
                        species: tree.species,
                        dbh: tree.dbh_cm,
                        height: tree.height_m,
                        dbh_class: tree.dbh_class,
                        grid_cell_id: tree.grid_cell_id
                      }
                    }}
                    pointToLayer={(feature, latlng) => {
                      return L.circleMarker(latlng, {
                        radius: 8,
                        fillColor: '#dc2626',
                        color: '#991b1b',
                        weight: 2,
                        fillOpacity: 0.9
                      });
                    }}
                    onEachFeature={(feature, layer) => {
                      layer.bindPopup(`
                        <strong>${feature.properties.species}</strong><br/>
                        DBH: ${feature.properties.dbh} cm<br/>
                        Height: ${feature.properties.height} m<br/>
                        Class: ${feature.properties.dbh_class}<br/>
                        Grid Cell: ${feature.properties.grid_cell_id ?? 'N/A'}
                      `);
                    }}
                  />
                ))}
              </>
            )}
            
            {/* Add labels */}
            <PolygonLabels features={allFeatures} />
          </MapContainer>
          
          {/* Tree toggle button and legend */}
          {trees.length > 0 && (
            <div className="absolute bottom-4 left-4 z-[1000] flex flex-col gap-2">
              <button
                onClick={() => setShowTrees(!showTrees)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg transition-all ${
                  showTrees 
                    ? 'bg-amber-500 text-white' 
                    : 'bg-white text-gray-700 border border-gray-300'
                }`}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
                {showTrees ? 'Hide Trees' : `Show Trees (${trees.length})`}
              </button>
              
              {/* DBH Class Legend - shown when trees are visible */}
              {showTrees && (
                <div className="bg-white/95 p-2 rounded-lg shadow-lg text-xs max-h-40 overflow-y-auto">
                  <p className="font-medium text-gray-700 mb-1">DBH Classification / डीबीएच वर्गीकरण</p>
                  {Object.entries(DBH_CLASS_CONFIG).map(([key, config]) => (
                    <div key={key} className="flex items-center gap-2 py-0.5">
                      <span 
                        className="w-3 h-3 rounded-full" 
                        style={{ backgroundColor: config.fillColor, border: `1px solid ${config.color}` }}
                      />
                      <span className="text-gray-600 truncate">{config.label}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {/* Mother Trees toggle button */}
              <button
                onClick={() => setShowMotherTrees(!showMotherTrees)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg transition-all ${
                  showMotherTrees 
                    ? 'bg-red-600 text-white' 
                    : 'bg-white text-gray-700 border border-gray-300'
                }`}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
                {showMotherTrees ? 'Hide Mother Trees' : 'Show Mother Trees'}
              </button>
              
              {/* Grid toggle button */}
              <button
                onClick={() => setShowGrid(!showGrid)}
                disabled={!gridSpacing}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg shadow-lg transition-all ${
                  showGrid 
                    ? 'bg-purple-500 text-white' 
                    : gridSpacing
                      ? 'bg-white text-gray-700 border border-gray-300'
                      : 'bg-gray-100 text-gray-400 border border-gray-200 cursor-not-allowed'
                }`}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 9h16M4 13h16M4 17h16M9 4v16M13 4v16" />
                </svg>
                {showGrid ? 'Hide Grid' : 'Show Grid'}
              </button>
              
              {/* Show grid spacing value if available */}
              {gridSpacing && (
                <div className="bg-white/95 p-2 rounded-lg shadow-lg text-xs">
                  <p className="text-gray-600">Grid: <span className="font-medium">{gridSpacing}m</span></p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

        {/* Bottom panels: Tree View + Details/Configuration */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left panel: Compartment Tree View */}
          <div className="w-1/3 border-r overflow-y-auto">
            <CompartmentTreeView 
              tree={compartmentTree}
              selectedNodeId={selectedNodeId}
              onSelectNode={handleSelectNode}
              onRenameNode={handleRename}
              onToggleLock={handleToggleLock}
              onSubDivide={handleSubDivide}
              onDeleteNode={handleDeleteNode}
            />
          </div>

          {/* Right panel: Details or Configuration */}
          <div className="w-2/3 p-4 overflow-y-auto">
            {selectedNode ? (
              <>
                {/* Show split configuration if it's a block or unlocked compartment */}
                {(!selectedNode.is_compartment || !selectedNode.is_locked) && selectedBlock && (
                  <SplitConfigurationPanel
                    key={selectedBlock.id}
                    block={selectedBlock}
                    onPreviewSplit={handlePreviewSplit}
                    onExecuteSplit={handleExecuteSplit}
                  />
                )}
                
                {/* Show details panel */}
                <CompartmentDetailsPanel 
                  node={selectedNode}
                  onSubDivide={() => handleSubDivide(selectedNode.id)}
                  onDelete={handleDeleteNode}
                />
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <svg
                  className="w-16 h-16 text-gray-300 mb-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2"
                  />
                </svg>
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  Select a Compartment
                </h3>
                <p className="text-gray-500 max-w-sm">
                  Choose a compartment from the tree view to view details or configure splitting options.
                  You can sub-divide compartments and lock them from further division.
                </p>
              </div>
            )}
          </div>
        </div>

      {/* Tree Reassignment Dialog */}
      {showReassignmentDialog && reassignmentBlockId && (
        <TreeReassignmentDialog
          blockId={reassignmentBlockId}
          blockName={reassignmentBlockName}
          onComplete={handleReassignmentComplete}
          onCancel={handleReassignmentCancel}
        />
      )}
    </div>
  );
}
