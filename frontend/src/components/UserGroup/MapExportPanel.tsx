import React, { useState, useEffect } from 'react';
import { Image as ImageIcon, X, Download, Grid3X3 } from 'lucide-react';
import L from 'leaflet';
import html2canvas from 'html2canvas';

interface MapExportPanelProps {
  forestBoundary: any;
  extentBoundary?: any;
  settlements: any[];
  buildings: any[];
  poiData?: any;
  mapRef: React.RefObject<{ getMap: () => L.Map | null }>;
  forestName?: string;
  onClose: () => void;
}

export function MapExportPanel({
  forestBoundary,
  extentBoundary,
  settlements,
  buildings,
  poiData,
  mapRef,
  forestName,
  onClose
}: MapExportPanelProps) {
  const getDefaultTitle = () => forestName ? `User Group Map - ${forestName}` : 'User Group Map';
  const [exportTitle, setExportTitle] = useState(getDefaultTitle());
  
  // Update title when forestName prop changes
  useEffect(() => {
    setExportTitle(getDefaultTitle());
  }, [forestName]);
  const [showGrid, setShowGrid] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exportedImage, setExportedImage] = useState<string | null>(null);
  const [legendLayers, setLegendLayers] = useState({
    forestBoundary: true,
    userGroupExtent: true,
    settlements: true,
    buildings: true,
    rivers: true,
    education: true,
    health: true,
  });

  const handleLayerToggle = (layer: keyof typeof legendLayers) => {
    setLegendLayers(prev => ({ ...prev, [layer]: !prev[layer] }));
  };

  const getBoundsFromFeatures = () => {
    const bounds = L.latLngBounds([]);
    let hasCoords = false;

    // Helper to extract coordinates from GeoJSON
    const extractCoords = (geom: any) => {
      if (!geom) return;
      try {
        if (geom.type === 'Polygon') {
          geom.coordinates[0].forEach((coord: number[]) => {
            bounds.extend([coord[1], coord[0]]);
            hasCoords = true;
          });
        } else if (geom.type === 'MultiPolygon') {
          geom.coordinates.forEach((poly: number[][]) => {
            poly[0].forEach((coord: number[]) => {
              bounds.extend([coord[1], coord[0]]);
              hasCoords = true;
            });
          });
        }
      } catch (e) {
        console.warn('Error extracting coordinates:', e);
      }
    };

    // Forest boundary
    extractCoords(forestBoundary);
    // Extent boundary
    extractCoords(extentBoundary);
    // Settlements
    settlements.forEach(s => {
      if (s.lat && s.lon) {
        bounds.extend([s.lat, s.lon]);
        hasCoords = true;
      }
    });
    // Buildings
    buildings.forEach(b => {
      if (b.lat && b.lon) {
        bounds.extend([b.lat, b.lon]);
        hasCoords = true;
      }
    });

    return hasCoords ? bounds : null;
  };

  const generateExportMap = async () => {
    // Wait for map to be ready
    if (!mapRef.current) {
      alert('Map is still loading. Please try again in a moment.');
      return;
    }
    
    const map = mapRef.current.getMap();
    if (!map) {
      alert('Map is not available. Please ensure the map is loaded.');
      return;
    }

    setGenerating(true);
    
    try {
      // Save current map state
      const currentCenter = map.getCenter();
      const currentZoom = map.getZoom();

      // Calculate bounds to fit all features
      const featureBounds = getBoundsFromFeatures();
      
      // Fit map to show all features FIRST
      if (featureBounds && featureBounds.isValid()) {
        map.fitBounds(featureBounds, { padding: [0, 0] });
        map.zoomIn();
      }
      
      // Force Leaflet to update its internal container size
      map.invalidateSize();
      
      // Wait for map to settle and tiles to load at new zoom
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Get the map container AFTER fitBounds
      const mapContainer = map.getContainer();
      
      // Get actual map dimensions
      const mapRect = mapContainer.getBoundingClientRect();
      const headerHeight = 40;
      const footerHeight = 80;
      
      // Use actual map dimensions
      const exportWidth = Math.round(mapRect.width);
      const mapHeight = Math.round(mapRect.height);
      const exportHeight = headerHeight + mapHeight + footerHeight;

      // Hide Leaflet controls before capture
      const controlSelectors = [
        '.leaflet-control-zoom',      // Zoom +/- buttons
        '.leaflet-control-layers',    // Layer panel button
        '.leaflet-control-attribution', // Attribution (optional, can keep)
      ];
      const hiddenControls: HTMLElement[] = [];
      controlSelectors.forEach(selector => {
        const controls = mapContainer.querySelectorAll(selector);
        controls.forEach((ctrl: any) => {
          hiddenControls.push(ctrl);
          ctrl.style.display = 'none';
        });
      });
      
      // Capture the map container
      const mapCanvas = await html2canvas(mapContainer, {
        scale: 1,
        useCORS: true,
        backgroundColor: '#e8e8e8',
        onclone: (clonedDoc) => {
          const panes = clonedDoc.querySelectorAll('.leaflet-pane');
          panes.forEach((pane: any) => {
            const transform = pane.style.transform;
            if (transform && transform.includes('translate3d')) {
              pane.style.transform = transform.replace('translate3d', 'translate').replace(/, 0px\)/g, ')');
            }
          });
        }
      });
      
      // Restore controls after capture
      hiddenControls.forEach(ctrl => {
        ctrl.style.display = '';
      });

      // Create final canvas
      const finalCanvas = document.createElement('canvas');
      finalCanvas.width = exportWidth;
      finalCanvas.height = exportHeight;
      const ctx = finalCanvas.getContext('2d');
      
      if (!ctx) {
        throw new Error('Could not get canvas context');
      }
      
      // Draw white background
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, exportWidth, exportHeight);
      
      // Draw header
      ctx.fillStyle = '#f8f8f8';
      ctx.fillRect(0, 0, exportWidth, headerHeight);
      ctx.fillStyle = '#333';
      ctx.font = 'bold 16px Arial';
      ctx.textAlign = 'center';
      ctx.fillText(exportTitle || 'User Group Map', exportWidth / 2, 26);
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, headerHeight);
      ctx.lineTo(exportWidth, headerHeight);
      ctx.stroke();
      
      // Draw map image (full width, full height)
      const mapImg = new Image();
      mapImg.src = mapCanvas.toDataURL('image/png');
      
      // Wait for image to load
      await new Promise((resolve) => {
        mapImg.onload = resolve;
        setTimeout(resolve, 3000);
      });
      
      // Draw map to fill the entire map area
      ctx.drawImage(mapImg, 0, headerHeight, exportWidth, mapHeight);
      
      // Add grid overlay if enabled
      if (showGrid) {
        // Get map bounds for coordinate labels
        const bounds = map.getBounds();
        const north = bounds.getNorth();
        const south = bounds.getSouth();
        const east = bounds.getEast();
        const west = bounds.getWest();
        
        // Calculate grid intervals (5 lines in each direction)
        const numLines = 5;
        const latStep = (north - south) / numLines;
        const lonStep = (east - west) / numLines;
        
        // Draw vertical grid lines
        for (let i = 0; i <= numLines; i++) {
          const x = (exportWidth / numLines) * i;
          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = 0.3;
          ctx.beginPath();
          ctx.moveTo(x, headerHeight);
          ctx.lineTo(x, headerHeight + mapHeight);
          ctx.stroke();
          
          // Add longitude label at top (inside map area, white with black outline)
          const lon = west + (lonStep * i);
          const lonText = lon.toFixed(5) + '°E';
          ctx.font = 'bold 10px Arial';
          ctx.textAlign = 'center';
          ctx.strokeStyle = '#000000';
          ctx.lineWidth = 2;
          const lonLabelY = headerHeight + 12;
          ctx.strokeText(lonText, x, lonLabelY);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(lonText, x, lonLabelY);
        }
        
        // Draw horizontal grid lines and latitude labels
        for (let i = 0; i <= numLines; i++) {
          const y = headerHeight + (mapHeight / numLines) * i;
          ctx.strokeStyle = '#FFFFFF';
          ctx.lineWidth = 0.3;
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(exportWidth, y);
          ctx.stroke();
          
          // Add latitude label at left edge (white with black outline)
          const lat = north - (latStep * i);
          const latText = lat.toFixed(5) + '°N';
          ctx.font = 'bold 11px Arial';
          ctx.textAlign = 'right';
          ctx.strokeStyle = '#000000';
          ctx.lineWidth = 3;
          ctx.strokeText(latText, 60, y + 4);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(latText, 60, y + 4);
        }
        
        // Add coordinate system label
        ctx.font = 'bold 12px Arial';
        ctx.textAlign = 'right';
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 2;
        ctx.strokeText('WGS 84', exportWidth - 10, headerHeight + 20);
        ctx.fillStyle = '#ffffff';
        ctx.fillText('WGS 84', exportWidth - 10, headerHeight + 20);
        
        // Add axis labels
        ctx.font = 'bold 11px Arial';
        ctx.fillStyle = '#ffffff';
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 2;
        
        // Longitude label (bottom center)
        ctx.textAlign = 'center';
        ctx.strokeText('Longitude (°E)', exportWidth / 2, headerHeight + mapHeight + 20);
        ctx.fillText('Longitude (°E)', exportWidth / 2, headerHeight + mapHeight + 20);
        
        // Latitude label (rotated on left side)
        ctx.save();
        ctx.translate(15, headerHeight + mapHeight / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.textAlign = 'center';
        ctx.strokeText('Latitude (°N)', 0, 0);
        ctx.fillText('Latitude (°N)', 0, 0);
        ctx.restore();
      }
      
      // Draw footer border
      const footerY = headerHeight + mapHeight;
      ctx.strokeStyle = '#ccc';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, footerY);
      ctx.lineTo(exportWidth, footerY);
      ctx.stroke();
      
      // Draw footer background
      ctx.fillStyle = '#fafafa';
      ctx.fillRect(0, footerY, exportWidth, footerHeight);
      
      // Draw North Arrow (left side)
      const arrowX = 50;
      const arrowY = footerY + 15;
      ctx.fillStyle = '#333';
      ctx.beginPath();
      ctx.moveTo(arrowX, arrowY);
      ctx.lineTo(arrowX - 8, arrowY + 25);
      ctx.lineTo(arrowX, arrowY + 20);
      ctx.lineTo(arrowX + 8, arrowY + 25);
      ctx.closePath();
      ctx.fill();
      ctx.font = 'bold 12px Arial';
      ctx.textAlign = 'center';
      ctx.fillText('N', arrowX, arrowY + 35);
      
      // Draw Scale Bar
      const scaleX = 20;
      const scaleY = footerY + 50;
      ctx.fillStyle = '#333';
      ctx.fillRect(scaleX, scaleY, 60, 3);
      ctx.fillStyle = '#fff';
      ctx.fillRect(scaleX + 60, scaleY, 60, 3);
      ctx.fillStyle = '#333';
      ctx.fillRect(scaleX + 120, scaleY, 60, 3);
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 1;
      ctx.strokeRect(scaleX, scaleY, 180, 3);
      ctx.font = '9px Arial';
      ctx.textAlign = 'left';
      ctx.fillText('0', scaleX, scaleY + 12);
      ctx.fillText('100m', scaleX + 60, scaleY + 12);
      ctx.fillText('200m', scaleX + 120, scaleY + 12);
      
      // Draw Legend (middle section)
      const legendX = Math.min(200, exportWidth / 4);
      const legendY = footerY + 10;
      const legendItems = [
        { key: 'forestBoundary', label: 'Forest Boundary', color: '#00aa00' },
        { key: 'userGroupExtent', label: 'User Group', color: '#0000ff', dashed: true },
        { key: 'settlements', label: 'Settlements', icon: '🏠' },
        { key: 'buildings', label: 'Buildings', color: '#ff0000', circle: true },
        { key: 'rivers', label: 'Rivers', color: '#0066ff' },
        { key: 'education', label: 'Education', icon: '🏫' },
        { key: 'health', label: 'Health', icon: '🏥' },
      ];
      
      let currentX = legendX;
      let currentY = legendY;
      
      legendItems.forEach((item, idx) => {
        if (!legendLayers[item.key as keyof typeof legendLayers]) return;
        
        const itemWidth = 90;
        
        // Check if we need to wrap to next line
        if (currentX + itemWidth > exportWidth - 60 && idx > 0) {
          currentX = legendX;
          currentY += 22;
        }
        
        // Draw background
        ctx.fillStyle = '#fff';
        ctx.fillRect(currentX, currentY, itemWidth - 5, 18);
        ctx.strokeStyle = '#ddd';
        ctx.lineWidth = 1;
        ctx.strokeRect(currentX, currentY, itemWidth - 5, 18);
        
        // Draw symbol
        if (item.circle) {
          ctx.fillStyle = '#ff0000';
          ctx.beginPath();
          ctx.arc(currentX + 10, currentY + 9, 5, 0, Math.PI * 2);
          ctx.fill();
        } else if (item.dashed) {
          ctx.strokeStyle = '#0000ff';
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.moveTo(currentX + 3, currentY + 9);
          ctx.lineTo(currentX + 20, currentY + 9);
          ctx.stroke();
          ctx.setLineDash([]);
        } else if (item.icon) {
          ctx.font = '11px Arial';
          ctx.fillText(item.icon, currentX + 2, currentY + 13);
        } else {
          ctx.fillStyle = item.color;
          ctx.fillRect(currentX + 3, currentY + 7, 16, 4);
        }
        
        // Draw label
        ctx.fillStyle = '#333';
        ctx.font = '10px Arial';
        ctx.textAlign = 'left';
        ctx.fillText(item.label, currentX + 23, currentY + 13);
        
        currentX += itemWidth;
      });
      
      // Draw grid status (right side)
      ctx.font = '10px Arial';
      ctx.textAlign = 'center';
      ctx.fillStyle = '#666';
      ctx.fillText(showGrid ? 'Grid: ON' : 'Grid: OFF', exportWidth - 40, footerY + footerHeight / 2);
      
      // Restore original map state
      map.setView(currentCenter, currentZoom);

      // Export as PNG
      const dataUrl = finalCanvas.toDataURL('image/png');
      setExportedImage(dataUrl);

    } catch (error) {
      console.error('Error generating export:', error);
      alert('Failed to generate map export: ' + (error instanceof Error ? error.message : 'Unknown error'));
    } finally {
      setGenerating(false);
    }
  };

  const downloadImage = () => {
    if (!exportedImage) return;

    const link = document.createElement('a');
    link.href = exportedImage;
    link.download = `user_group_map_${Date.now()}.png`;
    link.click();
  };

  const deleteExport = () => {
    setExportedImage(null);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="bg-purple-600 text-white px-6 py-4 flex justify-between items-center">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <ImageIcon size={24} />
            Export Map as PNG (A5 Size)
          </h2>
          <button
            onClick={onClose}
            className="text-white hover:bg-purple-700 rounded p-1"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left: Settings */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">Export Settings</h3>

              {/* Map Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Map Title
                </label>
                <input
                  type="text"
                  value={exportTitle}
                  onChange={(e) => setExportTitle(e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  placeholder="Enter map title"
                />
              </div>

              {/* Grid Toggle */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="showGrid"
                  checked={showGrid}
                  onChange={(e) => setShowGrid(e.target.checked)}
                  className="w-4 h-4 text-purple-600 rounded"
                />
                <label htmlFor="showGrid" className="text-sm font-medium text-gray-700 flex items-center gap-2">
                  <Grid3X3 size={16} />
                  Show Grid Overlay
                </label>
              </div>

              {/* Legend Layers */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Include in Legend
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { key: 'forestBoundary', label: 'Forest Boundary', color: '#00aa00' },
                    { key: 'userGroupExtent', label: 'User Group Extent', color: '#0000ff' },
                    { key: 'settlements', label: 'Settlements', icon: '🏠' },
                    { key: 'buildings', label: 'Buildings', color: '#ff0000' },
                    { key: 'rivers', label: 'Rivers', color: '#0066ff' },
                    { key: 'education', label: 'Education', icon: '🏫' },
                    { key: 'health', label: 'Health', icon: '🏥' },
                  ].map((layer) => (
                    <div key={layer.key} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id={`legend-${layer.key}`}
                        checked={legendLayers[layer.key as keyof typeof legendLayers]}
                        onChange={() => handleLayerToggle(layer.key as keyof typeof legendLayers)}
                        className="w-4 h-4 text-purple-600 rounded"
                      />
                      <label htmlFor={`legend-${layer.key}`} className="text-sm text-gray-600 flex items-center gap-1">
                        {layer.color && (
                          <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: layer.color }} />
                        )}
                        {layer.icon && <span>{layer.icon}</span>}
                        {layer.label}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Info */}
              <div className="bg-purple-50 border border-purple-200 rounded p-3">
                <p className="text-sm text-purple-800">
                  <strong>Size:</strong> A5 (148mm × 210mm)
                </p>
                <p className="text-sm text-purple-800 mt-1">
                  <strong>Format:</strong> PNG (high quality)
                </p>
                <p className="text-sm text-purple-800 mt-1">
                  <strong>Includes:</strong> North arrow, Scale bar, Legend
                </p>
              </div>

              {/* Generate Button */}
              <button
                onClick={generateExportMap}
                disabled={generating}
                className={`w-full py-3 rounded font-semibold flex items-center justify-center gap-2 ${
                  generating
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-700 text-white'
                }`}
              >
                <ImageIcon size={20} />
                {generating ? 'Generating...' : 'Generate Map Preview'}
              </button>
            </div>

            {/* Right: Preview/Download */}
            <div className="space-y-4">
              <h3 className="font-semibold text-lg border-b pb-2">Preview & Download</h3>

              {exportedImage ? (
                <>
                  <div className="border-2 border-gray-300 rounded bg-gray-100 p-2">
                    <img
                      src={exportedImage}
                      alt="Exported Map Preview"
                      className="w-full h-auto"
                    />
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={downloadImage}
                      className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded font-semibold flex items-center justify-center gap-2"
                    >
                      <Download size={20} />
                      Download PNG
                    </button>
                    <button
                      onClick={deleteExport}
                      className="bg-red-600 hover:bg-red-700 text-white py-2 px-4 rounded font-semibold"
                      title="Delete and generate new"
                    >
                      <X size={20} />
                    </button>
                  </div>
                </>
              ) : (
                <div className="border-2 border-dashed border-gray-300 rounded bg-gray-50 h-80 flex items-center justify-center">
                  <div className="text-center text-gray-500">
                    <ImageIcon size={48} className="mx-auto mb-2 opacity-50" />
                    <p>Click "Generate Map Preview"</p>
                    <p className="text-sm">to create your A5 export</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default MapExportPanel;
