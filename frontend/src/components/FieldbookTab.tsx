import { useState, useEffect } from 'react';
import { fieldbookApi } from '../services/api';
import { MapContainer, TileLayer, CircleMarker, Popup, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface FieldbookTabProps {
  calculationId: string;
}

export function FieldbookTab({ calculationId }: FieldbookTabProps) {
  const [fieldbook, setFieldbook] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  // Generation settings
  const [interpolationDistance, setInterpolationDistance] = useState(20);
  const [extractElevation, setExtractElevation] = useState(true);

  useEffect(() => {
    loadFieldbook();
  }, [calculationId]);

  const loadFieldbook = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fieldbookApi.list(calculationId);
      setFieldbook(data);
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
      });

      alert(`Fieldbook generated successfully!\n\nTotal points: ${result.total_points}\nVertices: ${result.total_vertices}\nInterpolated: ${result.interpolated_points}\nPerimeter: ${parseFloat(result.total_perimeter_meters).toFixed(2)}m`);

      await loadFieldbook();
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
      a.download = `fieldbook_${calculationId}.${format === 'geojson' ? 'geojson' : format}`;
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

            <div className="flex gap-2">
              <button
                onClick={() => handleExport('csv')}
                className="flex-1 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
              >
                Export CSV
              </button>
              <button
                onClick={() => handleExport('geojson')}
                className="flex-1 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
              >
                Export GeoJSON
              </button>
              <button
                onClick={() => handleExport('gpx')}
                className="flex-1 bg-green-600 text-white px-4 py-2 rounded-md hover:bg-green-700 text-sm"
              >
                Export GPX
              </button>
              <button
                onClick={handleDelete}
                className="bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700 text-sm"
              >
                Delete
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

      {/* Points Table */}
      {fieldbook && fieldbook.points && fieldbook.points.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold">Fieldbook Points ({fieldbook.total_count})</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Point</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Block</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Longitude</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Latitude</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Elevation (m)</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM Zone</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {fieldbook.points.slice(0, 50).map((point: any) => (
                  <tr key={point.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-sm font-mono">P{point.point_number}</td>
                    <td className="px-4 py-2 text-sm">
                      <span className={`px-2 py-1 rounded text-xs ${
                        point.point_type === 'vertex'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {point.point_type}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-sm">
                      {point.block_number ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                          {point.block_name || `Block ${point.block_number}`}
                        </span>
                      ) : '-'}
                    </td>
                    <td className="px-4 py-2 text-sm font-mono">{parseFloat(point.longitude).toFixed(7)}</td>
                    <td className="px-4 py-2 text-sm font-mono">{parseFloat(point.latitude).toFixed(7)}</td>
                    <td className="px-4 py-2 text-sm">{point.elevation ? parseFloat(point.elevation).toFixed(2) : 'N/A'}</td>
                    <td className="px-4 py-2 text-sm">{point.utm_zone}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {fieldbook.total_count > 50 && (
              <div className="px-6 py-4 bg-gray-50 text-sm text-gray-600 text-center">
                Showing first 50 of {fieldbook.total_count} points. Export to see all.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
