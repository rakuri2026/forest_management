import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { forestApi } from '../services/api';
import type { Calculation } from '../types';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Import leaflet scale control (built-in)
import 'leaflet/dist/leaflet.css';

// Component to handle auto-zoom to layer and add scale control
function ZoomToLayer({
  geometry,
  setMapInstance,
  orientation
}: {
  geometry: any;
  setMapInstance: (map: L.Map) => void;
  orientation: 'portrait' | 'landscape';
}) {
  const map = useMap();

  useEffect(() => {
    // Store map instance for external use
    setMapInstance(map);

    // Remove any existing scale controls first
    map.eachLayer((layer: any) => {
      if (layer instanceof L.Control.Scale) {
        map.removeControl(layer);
      }
    });

    // Add single scale control (bottom-left)
    const scaleControl = L.control.scale({
      position: 'bottomleft',
      metric: true,
      imperial: false,
      maxWidth: 150
    });
    scaleControl.addTo(map);

    // Auto-zoom to layer on initial load - same behavior for both orientations
    if (geometry) {
      const geoJsonLayer = L.geoJSON(geometry);
      const bounds = geoJsonLayer.getBounds();
      if (bounds.isValid()) {
        // Use same padding for both portrait and landscape for consistent zoom behavior
        const padding = [50, 50] as [number, number];

        map.fitBounds(bounds, { padding });
      }
    }

    // Cleanup function
    return () => {
      if (map && scaleControl) {
        map.removeControl(scaleControl);
      }
    };
  }, [geometry, map, setMapInstance, orientation]);

  return null;
}

// North Arrow Component - Points upward (North)
function NorthArrow() {
  return (
    <div className="absolute top-4 right-4 z-[1000] bg-white rounded-lg shadow-lg p-2 border border-gray-300">
      <div className="flex flex-col items-center">
        <div className="text-sm font-bold text-gray-800 mb-1">N</div>
        <svg width="30" height="50" viewBox="0 0 30 60">
          {/* Arrow shaft */}
          <line x1="15" y1="10" x2="15" y2="50" stroke="#333" strokeWidth="2"/>
          {/* North half (dark/filled) pointing UP */}
          <polygon points="15,5 10,20 15,18 20,20" fill="#1a1a1a" stroke="#000" strokeWidth="1"/>
          {/* South half (white/outline) pointing DOWN */}
          <polygon points="15,18 10,20 15,50 20,20" fill="#ffffff" stroke="#000" strokeWidth="1"/>
        </svg>
      </div>
    </div>
  );
}

export default function CalculationDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mapInstance, setMapInstance] = useState<L.Map | null>(null);
  const [mapOrientation, setMapOrientation] = useState<'portrait' | 'landscape'>('portrait');

  useEffect(() => {
    if (id) {
      loadCalculation();
    }
  }, [id]);

  // Calculate optimal map orientation based on geometry extent
  useEffect(() => {
    if (calculation?.geometry) {
      const geoJsonLayer = L.geoJSON(calculation.geometry);
      const bounds = geoJsonLayer.getBounds();

      if (bounds.isValid()) {
        const width = bounds.getEast() - bounds.getWest();
        const height = bounds.getNorth() - bounds.getSouth();

        // If width > height, use landscape; otherwise portrait
        const orientation = width > height ? 'landscape' : 'portrait';
        setMapOrientation(orientation);
      }
    }
  }, [calculation]);

  const loadCalculation = async () => {
    try {
      setLoading(true);
      const data = await forestApi.getCalculation(id!);
      setCalculation(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load calculation');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      processing: 'bg-yellow-100 text-yellow-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return styles[status as keyof typeof styles] || 'bg-gray-100 text-gray-800';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const handleZoomToLayer = () => {
    if (calculation?.geometry && mapInstance) {
      const geoJsonLayer = L.geoJSON(calculation.geometry);
      const bounds = geoJsonLayer.getBounds();
      if (bounds.isValid()) {
        // Use same padding for both portrait and landscape for consistent zoom behavior
        const padding = [50, 50] as [number, number];

        mapInstance.fitBounds(bounds, { padding });
      }
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading calculation details...</p>
        </div>
      </div>
    );
  }

  if (error || !calculation) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error || 'Calculation not found'}
        </div>
        <button
          onClick={() => navigate('/my-uploads')}
          className="mt-4 text-green-600 hover:text-green-700"
        >
          ← Back to My Uploads
        </button>
      </div>
    );
  }

  // Extract blocks from result_data
  const blocks = calculation.result_data?.blocks || [];
  const totalBlocks = calculation.result_data?.total_blocks || 1;
  const processingInfo = calculation.result_data?.processing_info || {};

  return (
    <div className="max-w-7xl mx-auto py-8 px-4">
      <div className="mb-6">
        <button
          onClick={() => navigate('/my-uploads')}
          className="text-green-600 hover:text-green-700 flex items-center"
        >
          <svg className="w-5 h-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to My Uploads
        </button>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {/* Header Section */}
        <div className="px-6 py-5 border-b border-gray-200 bg-gradient-to-r from-green-50 to-green-100">
          <h1 className="text-3xl font-bold text-gray-900">{calculation.forest_name}</h1>
          <div className="mt-2 flex items-center text-sm text-gray-600">
            <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span>Uploaded: {formatDate(calculation.created_at)}</span>
            <span className="mx-2">•</span>
            <span className="font-medium">{calculation.uploaded_filename}</span>
          </div>
          {totalBlocks > 1 && (
            <div className="mt-2 text-sm text-green-700 font-medium">
              {totalBlocks} Blocks {processingInfo.partitioned && '(Partitioned using division lines)'}
            </div>
          )}
        </div>

        {/* Blocks Table Section */}
        {blocks.length > 0 && (
          <div className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Forest Blocks</h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Block #
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Forest Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Block Name
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Area (ha)
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      UTM Zone
                    </th>
                    <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {blocks.map((block: any, index: number) => {
                    // Use pre-calculated area in hectares (accurate UTM calculation from backend)
                    const areaHa = block.area_hectares ? parseFloat(block.area_hectares).toFixed(2) : '0.00';

                    // Determine UTM zone based on centroid longitude
                    // Nepal: 80-84°E = Zone 44N (32644), 84-88°E = Zone 45N (32645)
                    const lon = block.centroid?.lon || 0;
                    const utmZone = lon >= 84 ? '45N (EPSG:32645)' : '44N (EPSG:32644)';

                    return (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {index + 1}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          <div className="font-medium">{calculation.forest_name}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          <div className="font-medium">{block.block_name}</div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right font-mono">
                          {areaHa}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 text-center">
                          {utmZone}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-center">
                          <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                            Ready
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot className="bg-gray-50">
                  <tr>
                    <td colSpan={3} className="px-6 py-3 text-sm font-semibold text-gray-900">
                      Total ({blocks.length} blocks)
                    </td>
                    <td className="px-6 py-3 text-sm font-semibold text-gray-900 text-right font-mono">
                      {blocks.reduce((sum: number, b: any) => sum + parseFloat(b.area_hectares || 0), 0).toFixed(2)} ha
                    </td>
                    <td colSpan={2}></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* Additional Information */}
        <div className="px-6 pb-6">
          <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-3">
            <div>
              <dt className="text-sm font-medium text-gray-500">Status</dt>
              <dd className="mt-1">
                <span
                  className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadge(
                    calculation.status
                  )}`}
                >
                  {calculation.status}
                </span>
              </dd>
            </div>

            {calculation.processing_time_seconds && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Processing Time</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {calculation.processing_time_seconds} seconds
                </dd>
              </div>
            )}

            {calculation.completed_at && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Completed At</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDate(calculation.completed_at)}
                </dd>
              </div>
            )}

            {calculation.error_message && (
              <div className="sm:col-span-3">
                <dt className="text-sm font-medium text-gray-500">Error Message</dt>
                <dd className="mt-1 text-sm text-red-600">{calculation.error_message}</dd>
              </div>
            )}
          </dl>

        {/* Map Section */}
        {calculation.geometry && (
          <div className="px-6 pb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                Boundary Map (A5 - {mapOrientation === 'portrait' ? 'Portrait' : 'Landscape'})
              </h2>
              <button
                onClick={handleZoomToLayer}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors shadow-sm"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                </svg>
                Zoom to Layer
              </button>
            </div>
            <div
              className="rounded-lg overflow-hidden border-2 border-gray-400 shadow-lg mx-auto relative"
              style={{
                width: mapOrientation === 'portrait' ? '560px' : '794px',
                height: mapOrientation === 'portrait' ? '794px' : '560px'
              }}
            >
              <MapContainer
                center={[27.7, 85.3]}
                zoom={7}
                style={{ height: '100%', width: '100%' }}
                zoomControl={true}
                attributionControl={true}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <GeoJSON
                  data={calculation.geometry}
                  style={{
                    color: '#059669',
                    weight: 3,
                    fillColor: '#34d399',
                    fillOpacity: 0.3
                  }}
                />
                <ZoomToLayer
                  geometry={calculation.geometry}
                  setMapInstance={setMapInstance}
                  orientation={mapOrientation}
                />
              </MapContainer>
              <NorthArrow />
            </div>
            <div className="mt-3 text-center">
              <p className="text-sm text-gray-500">
                A5 Map Size: {mapOrientation === 'portrait' ? '560px × 794px (148mm × 210mm)' : '794px × 560px (210mm × 148mm)'} at 96 DPI
                {totalBlocks > 1 && (
                  <span className="block mt-1 italic">
                    Map shows all {totalBlocks} blocks combined
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {/* Processing Info Section - Only show if partitioned */}
        {processingInfo.partitioned && (
          <div className="px-6 pb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Processing Information</h2>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm text-blue-800 font-medium">Compartment Boundary Partitioning Applied</p>
                  <p className="mt-1 text-sm text-blue-700">
                    The outer boundary was partitioned using {processingInfo.partition_info?.division_lines_used || 0} division lines,
                    creating {processingInfo.partition_info?.blocks_created || 0} separate forest blocks.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
