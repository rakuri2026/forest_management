import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, GeoJSON, Popup, useMap, Marker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import * as turf from '@turf/turf';
import { forestApi } from '../services/api';
import { Tooltip } from '../components/Tooltip';
import '../styles/compact.css';

interface BlockPolygon {
  index: number;
  geometry: any;
  area_hectares: number;
  current_name: string;
}

interface Calculation {
  id: string;
  forest_name: string;
  geometry: any; // GeoJSON geometry from API
}

type BlockMode = 'single' | 'multiple';

const COLORS = ['#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'];

// Component to fit map bounds to show boundary geometry
const FitBoundaryBounds: React.FC<{ geometry: any }> = ({ geometry }) => {
  const map = useMap();

  useEffect(() => {
    if (!geometry) return;
    
    try {
      const allCoords: [number, number][] = [];
      
      if (geometry.type === 'Polygon') {
        geometry.coordinates[0].forEach((coord: number[]) => {
          allCoords.push([coord[1], coord[0]]);
        });
      } else if (geometry.type === 'MultiPolygon') {
        geometry.coordinates.forEach((polygon: any) => {
          polygon[0].forEach((coord: number[]) => {
            allCoords.push([coord[1], coord[0]]);
          });
        });
      }

      if (allCoords.length > 0) {
        const bounds = L.latLngBounds(allCoords);
        map.fitBounds(bounds, { padding: [50, 50] });
      }
    } catch (e) {
      console.error('Error fitting bounds:', e);
    }
  }, [geometry, map]);

  return null;
};

// Component to fit map bounds to show all polygons
const FitBounds: React.FC<{ polygons: BlockPolygon[] }> = ({ polygons }) => {
  const map = useMap();

  useEffect(() => {
    if (polygons.length > 0) {
      const allCoords: [number, number][] = [];

      polygons.forEach(poly => {
        if (poly.geometry.type === 'Polygon') {
          poly.geometry.coordinates[0].forEach((coord: number[]) => {
            allCoords.push([coord[1], coord[0]]);
          });
        } else if (poly.geometry.type === 'MultiPolygon') {
          poly.geometry.coordinates.forEach((polygon: any) => {
            polygon[0].forEach((coord: number[]) => {
              allCoords.push([coord[1], coord[0]]);
            });
          });
        }
      });

      if (allCoords.length > 0) {
        const bounds = L.latLngBounds(allCoords);
        map.fitBounds(bounds, { padding: [50, 50] });
      }
    }
  }, [polygons, map]);

  return null;
};

const BlockNamingPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // State
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [blockMode, setBlockMode] = useState<BlockMode>('multiple');
  const [singleBlockName, setSingleBlockName] = useState('');
  const [polygons, setPolygons] = useState<BlockPolygon[]>([]);
  const [namedPolygons, setNamedPolygons] = useState<Map<number, string>>(new Map());
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Load calculation and polygons
  useEffect(() => {
    if (id) {
      loadData();
    }
  }, [id]);

  const loadData = async () => {
    try {
      setLoading(true);

      // Fetch calculation details
      const calc = await forestApi.getCalculation(id!);
      setCalculation(calc);

      // Set default block name
      setSingleBlockName(`${calc.forest_name} - Block 1`);

      // Fetch polygons for multi-block mode
      const response = await forestApi.getPolygons(id!);
      if (response.polygons && response.polygons.length > 0) {
        setPolygons(response.polygons);

        // Initialize named polygons with default names
        const initialNames = new Map<number, string>();
        response.polygons.forEach((p: BlockPolygon) => {
          initialNames.set(p.index, p.current_name || `Block ${p.index + 1}`);
        });
        setNamedPolygons(initialNames);
      }
    } catch (error: any) {
      console.error('Failed to load data:', error);
      alert(`Failed to load: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!id) return;

    try {
      setSaving(true);

      if (blockMode === 'single') {
        // Create single block
        await forestApi.createSingleBlock(id, singleBlockName);
      } else {
        // Create multiple blocks
        const blocksInput = Array.from(namedPolygons.entries()).map(([index, name]) => ({
          polygon_index: index,
          name: name
        }));
        await forestApi.createBlocks(id, blocksInput);
      }

      // Navigate to calculation detail page
      navigate(`/calculations/${id}`);
    } catch (error: any) {
      console.error('Failed to save blocks:', error);
      alert(`Failed to save: ${error.response?.data?.detail || error.message}`);
      setSaving(false);
    }
  };

  const handleBlockNameChange = (index: number, newName: string) => {
    setNamedPolygons(new Map(namedPolygons.set(index, newName.trim())));
  };

  const handleRowClick = (index: number) => {
    setSelectedIndex(index);
    setEditingIndex(null);
  };

  const handleEditClick = (index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingIndex(index);
    setSelectedIndex(index);
  };

  const getColorForIndex = (index: number): string => {
    return COLORS[index % COLORS.length];
  };

  const geoJsonStyle = (feature: any, index: number) => {
    const isSelected = selectedIndex === index;
    return {
      color: getColorForIndex(index),
      weight: isSelected ? 3 : 2,
      fillColor: getColorForIndex(index),
      fillOpacity: blockMode === 'multiple' ? (isSelected ? 0.5 : 0.3) : 0.2
    };
  };

  // Calculate centroid for a polygon
  const getPolygonCentroid = (geometry: any): [number, number] | null => {
    try {
      let turfPoly;
      if (geometry.type === 'MultiPolygon') {
        const areas = geometry.coordinates.map((ring: any) => {
          try {
            return turf.area(turf.polygon(ring));
          } catch {
            return 0;
          }
        });
        const maxIdx = areas.indexOf(Math.max(...areas));
        turfPoly = turf.polygon(geometry.coordinates[maxIdx]);
      } else if (geometry.type === 'Polygon') {
        turfPoly = turf.polygon(geometry.coordinates);
      }

      if (turfPoly) {
        const center = turf.centroid(turfPoly);
        return [center.geometry.coordinates[1], center.geometry.coordinates[0]];
      }
    } catch (e) {
      console.error('Error calculating centroid:', e);
    }
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Debug info
  console.log('[BlockNaming] State:', {
    hasCalculation: !!calculation,
    hasGeometry: !!calculation?.geometry,
    geometryType: calculation?.geometry?.type,
    polygonsCount: polygons.length,
    blockMode,
    singleBlockName
  });

  return (
    <div className="compact-page">
      {/* Header - compact */}
      <div className="compact-header flex items-center justify-between" style={{ minHeight: '48px', padding: '8px 16px' }}>
        <h1 className="text-base font-semibold text-gray-800">
          Block Configuration: {calculation?.forest_name}
        </h1>
        <button
          onClick={() => navigate(`/calculations/${id}`)}
          className="text-gray-500 hover:text-gray-700 text-lg font-bold"
        >
          ✕
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - Compact, takes ~20% height */}
        {/* Left Sidebar - Compact, takes ~20% height */}
        <div className="w-64 bg-white border-r border-gray-200 flex flex-col overflow-hidden" style={{ maxHeight: '25vh' }}>
          {/* Block Mode Selection */}
          <div className="p-2 border-b border-gray-200 bg-gray-50 shrink-0">
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-1 cursor-pointer text-xs">
                <input
                  type="radio"
                  value="single"
                  checked={blockMode === 'single'}
                  onChange={() => setBlockMode('single')}
                  className="w-3 h-3 text-blue-600"
                />
                <span className="font-medium">Single</span>
              </label>
              <label className="flex items-center gap-1 cursor-pointer text-xs">
                <input
                  type="radio"
                  value="multiple"
                  checked={blockMode === 'multiple'}
                  onChange={() => setBlockMode('multiple')}
                  className="w-3 h-3 text-blue-600"
                />
                <span className="font-medium">Multiple</span>
              </label>
            </div>
          </div>

          {/* Single Block Name Input */}
          {blockMode === 'single' && (
            <div className="p-2 border-b border-gray-200 shrink-0">
              <h3 className="text-xs font-medium text-gray-700 mb-1">Block Name</h3>
              <input
                type="text"
                value={singleBlockName}
                onChange={(e) => setSingleBlockName(e.target.value)}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Enter block name"
              />
            </div>
          )}

          {/* Multiple Blocks List */}
          {blockMode === 'multiple' && (
            <div className="flex-1 overflow-hidden flex flex-col min-h-0">
              <div className="px-3 py-1.5 border-b border-gray-200 bg-gray-50 shrink-0">
                <h3 className="text-xs font-semibold text-gray-700">
                  Blocks ({polygons.length})
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto min-h-0">
                <table className="w-full text-xs">
                  <tbody className="divide-y divide-gray-100">
                    {polygons.map((poly, idx) => (
                      <tr
                        key={idx}
                        onClick={() => handleRowClick(idx)}
                        className={`cursor-pointer transition-colors ${
                          selectedIndex === idx ? 'bg-blue-50' : 'hover:bg-gray-50'
                        }`}
                      >
                        <td className="px-2 py-1.5 w-6">
                          <div
                            className="w-4 h-4 rounded border"
                            style={{
                              backgroundColor: getColorForIndex(idx),
                              borderColor: getColorForIndex(idx)
                            }}
                          ></div>
                        </td>
                        <td className="px-2 py-1.5">
                          {editingIndex === idx ? (
                            <input
                              type="text"
                              value={namedPolygons.get(idx) || ''}
                              onChange={(e) => handleBlockNameChange(idx, e.target.value)}
                              onBlur={() => setEditingIndex(null)}
                              onKeyPress={(e) => {
                                if (e.key === 'Enter') setEditingIndex(null);
                              }}
                              autoFocus
                              className="w-full px-1 py-0.5 text-xs border border-blue-500 rounded focus:outline-none"
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <div className="flex items-center justify-between">
                              <span className="truncate text-gray-900 text-xs">
                                {namedPolygons.get(idx) || `Block ${idx + 1}`}
                              </span>
                              <button
                                onClick={(e) => handleEditClick(idx, e)}
                                className="text-gray-400 hover:text-blue-600 shrink-0"
                              >
                                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                </svg>
                              </button>
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-1.5 text-gray-500 whitespace-nowrap text-xs">
                          {poly.area_hectares.toFixed(2)} ha
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="p-2 border-t border-gray-200 bg-gray-50 shrink-0">
            <button
              onClick={handleSave}
              disabled={saving || (blockMode === 'multiple' && namedPolygons.size !== polygons.length)}
              className="w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors text-sm"
            >
              {saving ? 'Saving...' : 'Save & Continue'}
            </button>
            <p className="text-xs text-gray-500 text-center mt-1">
              {blockMode === 'multiple' 
                ? `${namedPolygons.size}/${polygons.length} named`
                : 'Single block'}
            </p>
          </div>
        </div>

        {/* Map Area - 80% of height */}
        <div className="flex-1 relative">
          <MapContainer
            center={[27.7, 85.3]}
            zoom={13}
            style={{ height: '100%', width: '100%' }}
            className="z-0"
          >
            {/* Satellite imagery as default */}
            <TileLayer
              attribution='&copy; <a href="https://www.esri.com/">Esri</a>'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              maxZoom={19}
            />

            {/* Show boundary */}
            {calculation?.geometry && (
              <GeoJSON
                data={calculation.geometry}
                style={{
                  color: '#10b981',
                  weight: 3,
                  fillColor: '#10b981',
                  fillOpacity: 0.15
                }}
              />
            )}

            {/* Auto-fit bounds to boundary */}
            <FitBoundaryBounds geometry={calculation?.geometry} />

            {/* Show polygons for multi-block mode */}
            {blockMode === 'multiple' && polygons.map((poly, idx) => {
              const centroid = getPolygonCentroid(poly.geometry);
              const blockName = namedPolygons.get(idx) || `Block ${idx + 1}`;

              return (
                <React.Fragment key={`polygon-${idx}`}>
                  <GeoJSON
                    data={poly.geometry}
                    style={geoJsonStyle(poly.geometry, idx)}
                    eventHandlers={{ click: () => handleRowClick(idx) }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <strong>{blockName}</strong><br />
                        Area: {poly.area_hectares.toFixed(2)} ha
                      </div>
                    </Popup>
                  </GeoJSON>

                  {centroid && (
                    <Marker
                      position={centroid}
                      icon={L.divIcon({
                        className: 'block-label',
                        html: `<div style="background: white; padding: 4px 8px; border-radius: 4px; border: 2px solid ${getColorForIndex(idx)}; font-weight: bold; font-size: 12px; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">${blockName}</div>`,
                        iconSize: [0, 0],
                        iconAnchor: [0, 0]
                      })}
                    />
                  )}
                </React.Fragment>
              );
            })}

            {blockMode === 'multiple' && polygons.length > 0 && (
              <FitBounds polygons={polygons} />
            )}
          </MapContainer>
        </div>
      </div>
    </div>
  );
};

export default BlockNamingPage;
