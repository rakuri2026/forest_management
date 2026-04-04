import { useState, useEffect, useCallback } from 'react';
import { compartmentApi } from '../../services/api';
import { AvailableBlock, SplitConfig, SplitPreviewResponse } from './types';
import { BlockSelectionPanel } from './BlockSelectionPanel';
import { SplitConfigurationPanel } from './SplitConfigurationPanel';
import { TreeReassignmentDialog } from './TreeReassignmentDialog';
import { MapContainer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import BaseMapSelector from '../MapCreation/BaseMapSelector';

// Component to fit map bounds
function MapBoundsController({ bounds }: { bounds: [[number, number], [number, number]] | null }) {
  const map = useMap();
  
  useEffect(() => {
    if (bounds) {
      map.fitBounds(bounds, { padding: [30, 30] });
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
      let latSum = 0, lonSum = 0;
      coords.forEach((c: number[]) => {
        lonSum += c[0];
        latSum += c[1];
      });
      const centerLat = latSum / coords.length;
      const centerLon = lonSum / coords.length;
      
      // Format area
      const areaText = feature.area_hectares >= 1 
        ? `${feature.area_hectares.toFixed(2)} ha` 
        : `${(feature.area_hectares * 10000).toFixed(0)} m²`;
      
      const labelColor = feature.is_compartment ? '#059669' : '#2563eb';
      
      // Create SVG text label with halo effect
      const svgLabel = `
        <svg width="200" height="50" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <filter id="shadow-${feature.id}" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="1" dy="1" stdDeviation="1" flood-color="white" flood-opacity="0.8"/>
            </filter>
          </defs>
          <text 
            x="100" 
            y="18" 
            text-anchor="middle" 
            font-family="Arial, sans-serif" 
            font-size="12" 
            font-weight="bold" 
            fill="${labelColor}"
            stroke="white" 
            stroke-width="3"
            paint-order="stroke"
            filter="url(#shadow-${feature.id})"
          >${feature.name}</text>
          <text 
            x="100" 
            y="35" 
            text-anchor="middle" 
            font-family="Arial, sans-serif" 
            font-size="11" 
            fill="#666"
            stroke="white" 
            stroke-width="2"
            paint-order="stroke"
            filter="url(#shadow-${feature.id})"
          >${areaText}</text>
        </svg>
      `;
      
      const icon = L.divIcon({
        html: svgLabel,
        className: 'polygon-svg-label',
        iconSize: [200, 50],
        iconAnchor: [100, 25]
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
  const [trees, setTrees] = useState<any[]>([]);

  const [showReassignmentDialog, setShowReassignmentDialog] = useState(false);
  const [reassignmentBlockId, setReassignmentBlockId] = useState<string | null>(null);
  const [reassignmentBlockName, setReassignmentBlockName] = useState<string>('');

  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    loadBlocks();
    loadTrees();
  }, [calculationId]);

  const loadTrees = async () => {
    try {
      console.log('[CompartmentTab] Loading trees for calculation:', calculationId);
      const result = await compartmentApi.getTreesForMap(calculationId);
      console.log('[CompartmentTab] Trees loaded:', result.count, result.trees?.length);
      setTrees(result.trees || []);
    } catch (err: any) {
      console.error('[CompartmentTab] Error loading trees:', err);
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

  const handleDownloadGpkg = async () => {
    console.log('[CompartmentTab] Download GPKG clicked, calculationId:', calculationId);
    try {
      setError(null);
      setDownloading(true);
      await compartmentApi.exportGpkg(calculationId);
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
      await compartmentApi.exportKml(calculationId);
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
        return coords.reduce((sum: number, c: number[]) => sum + c[1], 0) / coords.length;
      }
      return 27.7172;
    });
    const lons = targetFeatures.map(b => {
      const geom = b.geometry;
      if (geom?.coordinates && geom.coordinates[0]) {
        const coords = geom.coordinates[0];
        return coords.reduce((sum: number, c: number[]) => sum + c[0], 0) / coords.length;
      }
      return 85.324;
    });
    
    if (lats.length === 0) return [27.7172, 85.3240];
    
    return [
      (Math.min(...lats) + Math.max(...lats)) / 2,
      (Math.min(...lons) + Math.max(...lons)) / 2
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
          minLat = Math.min(minLat, coord[1]);
          maxLat = Math.max(maxLat, coord[1]);
          minLon = Math.min(minLon, coord[0]);
          maxLon = Math.max(maxLon, coord[0]);
        }
      }
    }
    
    if (minLat === 90) return null;
    
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
            <span className="text-xs text-gray-500">{allFeatures.length} features</span>
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
            <BaseMapSelector />
            
            <MapBoundsController bounds={getMapBounds()} />
            
            {/* Render all blocks and compartments */}
            {allFeatures.map((feature) => (
              <GeoJSON
                key={feature.id}
                data={feature.geometry}
                style={{
                  color: selectedBlock?.id === feature.id ? '#ef4444' : (feature.is_compartment ? '#10b981' : '#3b82f6'),
                  weight: selectedBlock?.id === feature.id ? 3 : (feature.is_compartment ? 1.5 : 2),
                  fillOpacity: selectedBlock?.id === feature.id ? 0.3 : (feature.is_compartment ? 0.4 : 0.15),
                  fillColor: feature.is_compartment ? '#86efac' : '#93c5fd',
                  interactive: false
                }}
              />
            ))}
            
            {/* Add tree points if visible */}
            {showTrees && trees.length > 0 && (
              <>
                {trees.map((tree) => (
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
                        height: tree.height_m
                      }
                    }}
                    pointToLayer={(feature, latlng) => {
                      return L.circleMarker(latlng, {
                        radius: 6,
                        fillColor: '#f59e0b',
                        color: '#d97706',
                        weight: 1,
                        fillOpacity: 0.8
                      });
                    }}
                    onEachFeature={(feature, layer) => {
                      layer.bindPopup(`
                        <strong>${feature.properties.species}</strong><br/>
                        DBH: ${feature.properties.dbh} cm<br/>
                        Height: ${feature.properties.height} m
                      `);
                    }}
                  />
                ))}
              </>
            )}
            
            {/* Add labels */}
            <PolygonLabels features={allFeatures} />
          </MapContainer>
          
          {/* Tree toggle button */}
          {trees.length > 0 && (
            <div className="absolute bottom-4 left-4 z-[1000]">
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
            </div>
          )}
        </div>
      </div>

      {/* Bottom panels: Block selection + Configuration */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel: Block selection */}
        <div className="w-1/3 border-r p-4 overflow-y-auto">
          <BlockSelectionPanel
            blocks={blocks}
            selectedBlock={selectedBlock}
            onSelectBlock={setSelectedBlock}
            onDeleteCompartments={handleDeleteCompartments}
            loading={loading}
          />
        </div>

        {/* Right panel: Configuration */}
        <div className="w-2/3 p-4 overflow-y-auto">
          {selectedBlock ? (
            <SplitConfigurationPanel
              key={selectedBlock.id}
              block={selectedBlock}
              onPreviewSplit={handlePreviewSplit}
              onExecuteSplit={handleExecuteSplit}
            />
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
                  d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2"
                />
              </svg>
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Select a Forest Block
              </h3>
              <p className="text-gray-500 max-w-sm">
                Choose a forest block from the list or click on the map to configure compartment splitting options.
                You can split blocks into parallel strips or grid patterns.
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
