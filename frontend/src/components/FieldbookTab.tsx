import { useState, useEffect } from 'react';
import { fieldbookApi } from '../services/api';

interface FieldbookTabProps {
  calculationId: string;
}

export function FieldbookTab({ calculationId }: FieldbookTabProps) {
  const [fieldbook, setFieldbook] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  // Generation settings
  const [interpolationDistance, setInterpolationDistance] = useState(50);
  const [extractElevation, setExtractElevation] = useState(true);

  // Topographic features toggle (default: OFF for performance)
  const [includeTopographic, setIncludeTopographic] = useState(false);

  useEffect(() => {
    loadFieldbook();
  }, [calculationId]);

  const loadFieldbook = async (skipCache: boolean = false) => {
    // Include topographic in cache key to separate cached results
    const cacheKey = `fieldbook_${calculationId}_${includeTopographic}`;

    // Try to load from cache first (unless explicitly skipped)
    if (!skipCache) {
      try {
        const cached = sessionStorage.getItem(cacheKey);
        if (cached) {
          const cachedData = JSON.parse(cached);
          setFieldbook(cachedData);
          console.log('✅ Loaded fieldbook from cache (instant)');
          return; // Return early with cached data
        }
      } catch (e) {
        console.warn('Cache read failed, fetching fresh data');
      }
    }

    // Fetch from server
    setLoading(true);
    setError(null);
    try {
      console.log('🔄 Fetching fieldbook from server...');
      const data = await fieldbookApi.list(calculationId, includeTopographic);
      setFieldbook(data);

      // Cache the result
      try {
        sessionStorage.setItem(cacheKey, JSON.stringify(data));
        console.log('💾 Cached fieldbook data for next load');
      } catch (e) {
        console.warn('Failed to cache fieldbook (storage full?)');
      }
    } catch (err: any) {
      if (err.response?.status !== 404) {
        setError(err.response?.data?.detail || 'Failed to load fieldbook');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!confirm('Generate fieldbook? This will delete any existing fieldbook for this calculation.')) {
      return;
    }

    setGenerating(true);
    setError(null);
    try {
      const result = await fieldbookApi.generate(calculationId, {
        interpolation_distance_meters: interpolationDistance,
        extract_elevation: extractElevation,
        calculate_reference: false,  // Deprecated - features calculated during export
      });

      alert(`Fieldbook generated successfully!\n\nTotal points: ${result.total_points}\nVertices: ${result.total_vertices}\nInterpolated: ${result.interpolated_points}\nPerimeter: ${parseFloat(result.total_perimeter_meters).toFixed(2)}m`);

      // Clear cache and reload fresh data
      const cacheKey = `fieldbook_${calculationId}`;
      sessionStorage.removeItem(cacheKey);
      await loadFieldbook(true); // Skip cache, fetch fresh
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate fieldbook');
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Delete fieldbook? This cannot be undone.')) {
      return;
    }

    try {
      await fieldbookApi.delete(calculationId);

      // Clear cache
      const cacheKey = `fieldbook_${calculationId}`;
      sessionStorage.removeItem(cacheKey);

      setFieldbook(null);
      alert('Fieldbook deleted successfully');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete fieldbook');
    }
  };

  const handleExport = async (format: 'csv' | 'excel' | 'gpx' | 'geojson') => {
    try {
      const blob = await fieldbookApi.export(calculationId, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      // Set appropriate file extension
      let extension = format;
      if (format === 'excel') extension = 'xlsx';
      else if (format === 'geojson') extension = 'geojson';

      a.download = `fieldbook_${calculationId}.${extension}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(err.response?.data?.detail || `Failed to export ${format}`);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="text-gray-600">Loading fieldbook...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Generation Form */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">
          {fieldbook ? 'Fieldbook Generated' : 'Generate Fieldbook'}
        </h3>

        {!fieldbook && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Interpolation Distance (meters)
              </label>
              <input
                type="number"
                min="5"
                max="100"
                value={interpolationDistance}
                onChange={(e) => setInterpolationDistance(parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="text-xs text-gray-500 mt-1">
                Distance between interpolated points along boundary edges
              </p>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="extractElevation"
                checked={extractElevation}
                onChange={(e) => setExtractElevation(e.target.checked)}
                className="h-4 w-4 text-blue-600"
              />
              <label htmlFor="extractElevation" className="ml-2 text-sm text-gray-700">
                Extract elevation from DEM
              </label>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="includeTopographic"
                checked={includeTopographic}
                onChange={(e) => setIncludeTopographic(e.target.checked)}
                className="h-4 w-4 text-blue-600"
              />
              <label htmlFor="includeTopographic" className="ml-2 text-sm text-gray-700">
                Calculate Topographic Features (Ridges/Rivers)
              </label>
            </div>

            

            <button
              onClick={handleGenerate}
              disabled={generating}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
            >
              {generating ? 'Generating...' : 'Generate Fieldbook'}
            </button>
          </div>
        )}

        {fieldbook && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-gray-600">Total Points</div>
                <div className="text-lg font-semibold">{fieldbook.total_count}</div>
              </div>
            </div>

            {/* Topographic features toggle - only when fieldbook exists */}
            <div className="flex items-center gap-4 p-3 bg-gray-50 rounded-md">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="includeTopographicView"
                  checked={includeTopographic}
                  onChange={async (e) => {
                    setIncludeTopographic(e.target.checked);
                    // Force reload after toggling
                    await loadFieldbook(true);
                  }}
                  className="h-4 w-4 text-blue-600"
                />
                <label htmlFor="includeTopographicView" className="ml-2 text-sm text-gray-700">
                  Show Topographic Features (Ridges/Rivers)
                </label>
              </div>
              <span className="text-xs text-gray-500">
                {includeTopographic ? 'Showing nearest ridge/river for each point' : 'Feature calculation is OFF'}
              </span>
            </div>

            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => handleExport('csv')}
                className="flex-1 min-w-[120px] bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
              >
                📄 CSV
              </button>
              <button
                onClick={() => handleExport('excel')}
                className="flex-1 min-w-[120px] bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
              >
                📊 Excel
              </button>
              <button
                onClick={() => handleExport('geojson')}
                className="flex-1 min-w-[120px] bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
              >
                🗺️ GeoJSON
              </button>
              <button
                onClick={() => handleExport('gpx')}
                className="flex-1 min-w-[120px] bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
              >
                📍 GPX
              </button>
              <button
                onClick={handleDelete}
                className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 text-sm"
              >
                🗑️ Delete
              </button>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}
      </div>

      {/* Enhanced Points Table with Elevation Arrows */}
      {fieldbook && fieldbook.points && fieldbook.points.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold">Fieldbook Points ({fieldbook.total_count})</h3>
            <p className="text-xs text-gray-500 mt-1">
              Elevation arrows: ↑ rise, ↓ fall, → flat. Topographic features (nearest ridge/river) shown with distance and direction.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Point</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Block</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Coordinates</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM</th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Elevation (m)</th>
                  <th className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase">Change</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">Nearest Feature</th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Azimuth (°)</th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">Distance (m)</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {fieldbook.points.slice(0, 50).map((point: any, idx: number) => {
                  // Calculate elevation change from previous point
                  let elevationChange = null;
                  let elevationDiff = 0;
                  let arrow = '→';
                  let changeColor = 'text-gray-400';

                  if (idx > 0 && point.elevation && fieldbook.points[idx - 1].elevation) {
                    const prevElevation = parseFloat(fieldbook.points[idx - 1].elevation);
                    const currElevation = parseFloat(point.elevation);
                    elevationDiff = currElevation - prevElevation;

                    if (Math.abs(elevationDiff) > 1) {
                      if (elevationDiff > 0) {
                        arrow = '↑';
                        changeColor = Math.abs(elevationDiff) > 20 ? 'text-green-700 font-bold' : 'text-green-600';
                      } else {
                        arrow = '↓';
                        changeColor = Math.abs(elevationDiff) > 20 ? 'text-red-700 font-bold' : 'text-red-600';
                      }
                      elevationChange = `${elevationDiff > 0 ? '+' : ''}${elevationDiff.toFixed(1)}m`;
                    }
                  }

                  return (
                    <tr key={point.id} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-sm font-mono font-medium">P{point.point_number}</td>
                      <td className="px-3 py-2 text-sm">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          point.point_type === 'vertex'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-gray-100 text-gray-700'
                        }`}>
                          {point.point_type === 'vertex' ? 'V' : 'I'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-sm">
                        {point.block_number ? (
                          <span className="px-2 py-1 bg-emerald-100 text-emerald-800 rounded text-xs font-medium">
                            {point.block_name || `B${point.block_number}`}
                          </span>
                        ) : (
                          <span className="text-gray-400 text-xs">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs font-mono text-gray-700">
                        <div>{parseFloat(point.longitude).toFixed(6)}</div>
                        <div className="text-gray-500">{parseFloat(point.latitude).toFixed(6)}</div>
                      </td>
                      <td className="px-3 py-2 text-xs font-mono text-gray-600">
                        {point.easting_utm && point.northing_utm ? (
                          <>
                            <div>E {parseFloat(point.easting_utm).toFixed(0)}</div>
                            <div className="text-gray-500">N {parseFloat(point.northing_utm).toFixed(0)}</div>
                            <div className="text-gray-400 text-[10px]">{point.utm_zone}N</div>
                          </>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-sm font-mono text-right font-medium">
                        {point.elevation ? (
                          <span className="text-blue-900">{parseFloat(point.elevation).toFixed(1)}</span>
                        ) : (
                          <span className="text-gray-400">N/A</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-center">
                        {elevationChange ? (
                          <div className="flex flex-col items-center">
                            <span className={`text-xl ${changeColor}`}>{arrow}</span>
                            <span className={`text-xs ${changeColor}`}>{elevationChange}</span>
                          </div>
                        ) : (
                          <span className="text-gray-300 text-sm">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {point.nearest_feature ? (
                          <div className="space-y-1">
                            <div className="flex items-center gap-1">
                              <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                point.feature_type?.toLowerCase() === 'river'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-amber-100 text-amber-800'
                              }`}>
                                {point.feature_type?.toLowerCase() === 'river' ? '🌊' : '⛰️'}
                              </span>
                              <span className="font-medium text-gray-800 truncate max-w-[120px]" title={point.nearest_feature}>
                                {point.nearest_feature}
                              </span>
                            </div>
                            <div className="text-gray-600 flex items-center gap-2">
                              <span className="font-mono">{point.distance_to_feature ? Math.round(point.distance_to_feature) : '-'}m</span>
                              {point.direction_to_feature && (
                                <span className="px-1 py-0.5 bg-gray-200 text-gray-700 rounded font-semibold text-[10px]">
                                  {point.direction_to_feature}
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-sm font-mono text-right text-gray-700">
                        {point.azimuth_to_next ? parseFloat(point.azimuth_to_next).toFixed(1) : '-'}
                      </td>
                      <td className="px-3 py-2 text-sm font-mono text-right text-gray-700">
                        {point.distance_to_next ? parseFloat(point.distance_to_next).toFixed(1) : '-'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {fieldbook.total_count > 50 && (
              <div className="px-6 py-4 bg-gray-50 text-sm text-gray-600 text-center">
                Showing first 50 of {fieldbook.total_count} points. Export CSV/Excel to see all data.
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="px-6 py-3 bg-blue-50 border-t border-blue-100">
            <div className="text-xs text-gray-700 flex flex-wrap gap-x-6 gap-y-2">
              <div><span className="font-semibold">V</span> = Vertex (original boundary point)</div>
              <div><span className="font-semibold">I</span> = Interpolated point</div>
              <div><span className="text-green-600 font-bold text-lg">↑</span> = Elevation rise</div>
              <div><span className="text-red-600 font-bold text-lg">↓</span> = Elevation fall</div>
              <div><span className="text-gray-400 text-lg">→</span> = Flat (±1m)</div>
              <div>🌊 = River</div>
              <div>⛰️ = Ridge</div>
              <div className="w-full text-blue-700 font-medium">
                💡 Showing topographic features (nearest ridge/river) with distance and direction. Export CSV/Excel for full dataset.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
