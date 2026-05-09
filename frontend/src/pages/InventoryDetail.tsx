import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { inventoryApi } from '../services/api';

export default function InventoryDetail() {
  const { id } = useParams<{ id: string }>();
  const [inventory, setInventory] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      loadInventory();
    }
  }, [id]);

  const loadInventory = async () => {
    try {
      setLoading(true);
      const [statusData, summaryData] = await Promise.all([
        inventoryApi.getInventoryStatus(id!),
        inventoryApi.getInventorySummary(id!).catch(() => null),
      ]);
      setInventory(statusData);
      setSummary(summaryData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load inventory');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'csv' | 'geojson') => {
    try {
      const blob = await inventoryApi.exportInventory(id!, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `inventory_${id}.${format === 'geojson' ? 'geojson' : 'csv'}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError('Failed to export inventory');
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading inventory...</p>
        </div>
      </div>
    );
  }

  if (error || !inventory) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error || 'Inventory not found'}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto py-8 px-4">
      <div className="mb-6 flex justify-between items-center">
        <div>
          <Link to="/inventory" className="text-green-600 hover:text-green-900 text-sm mb-2 inline-block">
            ← Back to Inventories
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">{inventory.uploaded_filename}</h1>
          <p className="mt-2 text-gray-600">Uploaded on {new Date(inventory.created_at).toLocaleString()}</p>
        </div>
        <div className="space-x-2">
          <button
            onClick={() => handleExport('csv')}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Export CSV
          </button>
          <button
            onClick={() => handleExport('geojson')}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            Export GeoJSON
          </button>
        </div>
      </div>

      {/* Status Card */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Processing Status</h2>
        <div className="flex items-center">
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
            inventory.status === 'completed' ? 'bg-green-100 text-green-800' :
            inventory.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
            inventory.status === 'validated' ? 'bg-blue-100 text-blue-800' :
            'bg-gray-100 text-gray-800'
          }`}>
            {inventory.status}
          </span>
          {inventory.processing_time_seconds && (
            <span className="ml-4 text-sm text-gray-600">
              Processed in {inventory.processing_time_seconds.toFixed(1)} seconds
            </span>
          )}
        </div>
      </div>

      {/* Summary Statistics */}
      {summary && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Summary Statistics</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p className="text-sm text-gray-500">Total Trees</p>
              <p className="mt-1 text-3xl font-bold text-gray-900">{summary.total_trees || 0}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Mother Trees</p>
              <p className="mt-1 text-3xl font-bold text-green-600">{summary.mother_trees_count || 0}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Felling Trees</p>
              <p className="mt-1 text-3xl font-bold text-orange-600">{summary.felling_trees_count || 0}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Seedlings</p>
              <p className="mt-1 text-3xl font-bold text-blue-600">{summary.seedling_count || 0}</p>
            </div>
          </div>

          <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="p-4 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-500">Total Volume</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{(summary.total_volume_m3 || 0).toFixed(2)} m³</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-500">Net Volume</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{(summary.total_net_volume_m3 || 0).toFixed(2)} m³</p>
              <p className="text-xs text-gray-500 mt-1">{(summary.total_net_volume_cft || 0).toFixed(2)} cft</p>
            </div>
            <div className="p-4 bg-gray-50 rounded-md">
              <p className="text-sm text-gray-500">Firewood</p>
              <p className="mt-1 text-2xl font-bold text-gray-900">{(summary.total_firewood_m3 || 0).toFixed(2)} m³</p>
              <p className="text-xs text-gray-500 mt-1">{(summary.total_firewood_chatta || 0).toFixed(0)} chatta</p>
            </div>
          </div>
        </div>
      )}

      {/* Species Distribution */}
      {summary?.species_distribution && Object.keys(summary.species_distribution).length > 0 && (
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Species Distribution</h2>
          <div className="space-y-2">
            {Object.entries(summary.species_distribution)
              .sort(([, a]: any, [, b]: any) => b - a)
              .map(([species, count]: any) => (
                <div key={species} className="flex items-center">
                  <div className="flex-1">
                    <div className="flex justify-between mb-1">
                      <span className="text-sm font-medium text-gray-700">{species}</span>
                      <span className="text-sm text-gray-500">{count} trees</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-green-600 h-2 rounded-full"
                        style={{ width: `${(count / (summary.total_trees || 1)) * 100}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Configuration */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Configuration</h2>
        <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
          <div>
            <dt className="text-sm font-medium text-gray-500">Grid Spacing</dt>
            <dd className="mt-1 text-sm text-gray-900">{inventory.grid_spacing_meters} meters</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">Projection</dt>
            <dd className="mt-1 text-sm text-gray-900">EPSG:{inventory.projection_epsg}</dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
