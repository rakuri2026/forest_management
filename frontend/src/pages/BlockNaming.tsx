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
  const [blockMode, setBlockMode] = useState<BlockMode>('single');
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

        // Auto-select mode based on polygon count
        if (response.polygons.length === 1) {
          setBlockMode('single');
        }

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

  return (
    <div className="compact-page">
      {/* Header */}
      <div className="compact-header flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-800">
          Block Configuration: {calculation?.forest_name}
        </h1>
        <button
          onClick={() => navigate(`/calculations/${id}`)}
          className="text-gray-500 hover:text-gray-700 text-xl font-bold"
        >
          ✕
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - Block Table (only for multiple mode) */}
        {blockMode === 'multiple' && (
          <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-sm font-semibold text-gray-700">Blocks ({polygons.length})</h2>
              <p className="text-xs text-gray-500 mt-1">Click to select, double-click name to edit</p>
            </div>
            <div className="flex-1 overflow-y-auto">
              <table className="w-full">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Color</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Name</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-700">Area (ha)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {polygons.map((poly, idx) => (
                    <tr
                      key={idx}
                      onClick={() => handleRowClick(idx)}
                      className={`cursor-pointer transition-colors ${
                        selectedIndex === idx
                          ? 'bg-blue-50 border-l-4 border-blue-500'
                          : 'hover:bg-gray-50'
                      }`}
                    >
                      <td className="px-4 py-2">
                        <div
                          className="w-6 h-6 rounded border-2"
                          style={{
                            backgroundColor: getColorForIndex(idx),
                            borderColor: getColorForIndex(idx)
                          }}
                        ></div>
                      </td>
                      <td className="px-4 py-2">
                        {editingIndex === idx ? (
                          <input
                            type="text"
                            value={namedPolygons.get(idx) || ''}
                            onChange={(e) => handleBlockNameChange(idx, e.target.value)}
                            onBlur={() => setEditingIndex(null)}
                            onKeyPress={(e) => {
                              if (e.key === 'Enter') {
                                setEditingIndex(null);
                              }
                            }}
                            autoFocus
                            className="w-full px-2 py-1 text-sm border border-blue-500 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <div
                            className="text-sm font-medium text-gray-900 flex items-center justify-between"
                            onDoubleClick={(e) => handleEditClick(idx, e)}
                          >
                            <span>{namedPolygons.get(idx) || `Block ${idx + 1}`}</span>
                            <button
                              onClick={(e) => handleEditClick(idx, e)}
                              className="ml-2 text-gray-400 hover:text-blue-600"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                              </svg>
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-600">
                        {poly.area_hectares.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Map Area */}
        <div className="flex-1 relative">
          <MapContainer
            center={[27.7, 85.3]}
            zoom={13}
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />

            {/* Show boundary for single block mode */}
            {calculation?.geometry && blockMode === 'single' && (
              <GeoJSON
                data={calculation.geometry}
                style={{
                  color: '#3b82f6',
                  weight: 2,
                  fillColor: '#3b82f6',
                  fillOpacity: 0.2
                }}
              />
            )}

            {/* Show polygons for multi-block mode */}
            {blockMode === 'multiple' && polygons.map((poly, idx) => {
              const centroid = getPolygonCentroid(poly.geometry);
              const blockName = namedPolygons.get(idx) || `Block ${idx + 1}`;

              return (
                <React.Fragment key={`polygon-${idx}`}>
                  <GeoJSON
                    data={poly.geometry}
                    style={geoJsonStyle(poly.geometry, idx)}
                    eventHandlers={{
                      click: () => handleRowClick(idx)
                    }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <strong>{blockName}</strong><br />
                        Area: {poly.area_hectares.toFixed(2)} ha<br />
                        <span className="text-gray-600 text-xs">Click row in table to edit</span>
                      </div>
                    </Popup>
                  </GeoJSON>

                  {/* Show live label at centroid */}
                  {centroid && (
                    <Marker
                      position={centroid}
                      icon={L.divIcon({
                        className: 'block-label',
                        html: `<div style="background: white; padding: 4px 8px; border-radius: 4px; border: 2px solid ${getColorForIndex(idx)}; font-weight: bold; font-size: 12px; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.2); ${selectedIndex === idx ? 'border-width: 3px;' : ''}">${blockName}</div>`,
                        iconSize: [0, 0],
                        iconAnchor: [0, 0]
                      })}
                    />
                  )}
                </React.Fragment>
              );
            })}

            {/* Fit bounds to show all polygons */}
            {blockMode === 'multiple' && polygons.length > 0 && (
              <FitBounds polygons={polygons} />
            )}
          </MapContainer>
        </div>
      </div>

      {/* Compact Controls Bar */}
      <div className="compact-controls">
        <div className="compact-controls-row">
          {/* Single Block Option */}
          <label className="compact-radio-label">
            <input
              type="radio"
              value="single"
              checked={blockMode === 'single'}
              onChange={() => setBlockMode('single')}
            />
            <span>Single Block</span>
          </label>

          {/* Block Name Input - Only shown for single mode */}
          {blockMode === 'single' && (
            <div className="flex items-center gap-2 flex-1">
              <label className="text-sm text-gray-600">Name:</label>
              <input
                type="text"
                value={singleBlockName}
                onChange={(e) => setSingleBlockName(e.target.value)}
                className="compact-input flex-1 max-w-md"
                placeholder="Block name"
              />
            </div>
          )}

          {/* Multiple Blocks Option */}
          <label className="compact-radio-label">
            <input
              type="radio"
              value="multiple"
              checked={blockMode === 'multiple'}
              onChange={() => setBlockMode('multiple')}
            />
            <span>Multiple Blocks</span>
          </label>

          {/* Help text for multiple mode */}
          {blockMode === 'multiple' && (
            <span className="compact-help-text">
              Edit names in table or double-click
            </span>
          )}

          {/* Tooltip Help */}
          <Tooltip content="Choose single block or split into multiple blocks. You can add sub-areas and modify blocks later.">
            <button className="text-gray-400 hover:text-gray-600">
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
              </svg>
            </button>
          </Tooltip>

          {/* Save Button */}
          <button
            onClick={handleSave}
            disabled={saving || (blockMode === 'multiple' && namedPolygons.size !== polygons.length)}
            className="ml-auto compact-button compact-button-primary"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>

        {/* Multi-block naming status */}
        {blockMode === 'multiple' && polygons.length > 0 && (
          <div className="mt-2 text-sm text-gray-600">
            All blocks ready: {namedPolygons.size} / {polygons.length}
          </div>
        )}
      </div>
    </div>
  );
};

export default BlockNamingPage;
