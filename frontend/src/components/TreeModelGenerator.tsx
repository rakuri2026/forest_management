import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Download, Trash2, AlertCircle, CheckCircle, Clock, Loader } from 'lucide-react';
import api from '../services/api';

interface TreeModelConfig {
  min_dbh_cm: number;
  min_height_m: number;
  max_trees_per_ha: number;
  spatial_distribution: string;
  plot_buffer_meters: number;
  algorithm_version: string;
}

interface TreeModel {
  id: string;
  calculation_id: string;
  model_version: string;
  algorithm_config?: any;
  status: 'processing' | 'completed' | 'failed';
  progress_percent: number;
  current_step: string;
  total_trees: number | null;
  area_hectares: number | null;
  trees_per_hectare: number | null;
  min_dbh_cm: number | null;
  max_dbh_cm: number | null;
  min_height_m: number | null;
  max_height_m: number | null;
  gpkg_filename: string | null;
  file_size_mb: number | null;
  excel_filename: string | null;
  excel_size_mb: number | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  processing_time_seconds: number | null;
}

interface TreeModelGeneratorProps {
  calculationId: string;
}

const TreeModelGenerator: React.FC<TreeModelGeneratorProps> = ({ calculationId }) => {
  const [expanded, setExpanded] = useState(false);
  const [models, setModels] = useState<TreeModel[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Configuration state
  const [config, setConfig] = useState<TreeModelConfig>({
    min_dbh_cm: 10.0,
    min_height_m: 5.0,
    max_trees_per_ha: 500,
    spatial_distribution: 'random',
    plot_buffer_meters: 12.62,
    algorithm_version: 'v1.0'
  });

  // Polling for progress updates
  const [pollingId, setPollingId] = useState<string | null>(null);

  // Load existing models
  const loadModels = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/api/calculations/${calculationId}/tree-models`);  // Fixed: Added /api prefix
      setModels(response.data.models || []);
    } catch (err: any) {
      console.error('Error loading tree models:', err);
    } finally {
      setLoading(false);
    }
  };

  // Initial load when expanded
  useEffect(() => {
    if (expanded) {
      loadModels();
    }
  }, [expanded, calculationId]);

  // Polling for progress
  useEffect(() => {
    if (!pollingId) return;

    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/api/tree-models/${pollingId}`);  // Fixed: Added /api prefix
        const model = response.data;

        // Update model in list
        setModels(prev =>
          prev.map(m => m.id === model.id ? model : m)
        );

        // Stop polling if completed or failed
        if (model.status === 'completed' || model.status === 'failed') {
          setPollingId(null);
          setGenerating(false);
        }
      } catch (err) {
        console.error('Error polling model status:', err);
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [pollingId]);

  // Generate tree model
  const handleGenerate = async () => {
    try {
      setGenerating(true);
      setError(null);

      const response = await api.post(
        `/api/calculations/${calculationId}/generate-tree-model`,  // Fixed: Added /api prefix
        { config }
      );

      const newModel = response.data;
      setModels(prev => [newModel, ...prev]);
      setPollingId(newModel.id);

    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start tree model generation');
      setGenerating(false);
    }
  };

  // Download model (GPKG)
  const handleDownload = async (modelId: string, filename: string) => {
    try {
      const response = await api.get(`/api/tree-models/${modelId}/download`, {  // Fixed: Added /api prefix
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

    } catch (err: any) {
      alert('Failed to download file: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Download Excel
  const handleDownloadExcel = async (modelId: string, filename: string) => {
    try {
      const response = await api.get(`/api/tree-models/${modelId}/download-excel`, {
        responseType: 'blob'
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

    } catch (err: any) {
      alert('Failed to download Excel file: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Delete model
  const handleDelete = async (modelId: string) => {
    if (!confirm('Are you sure you want to delete this tree model?')) return;

    try {
      await api.delete(`/api/tree-models/${modelId}`);  // Fixed: Added /api prefix
      setModels(prev => prev.filter(m => m.id !== modelId));
    } catch (err: any) {
      alert('Failed to delete model: ' + (err.response?.data?.detail || err.message));
    }
  };

  // Format file size
  const formatFileSize = (mb: number) => {
    if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
    return `${mb.toFixed(2)} MB`;
  };

  // Format duration
  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  };

  return (
    <div className="mt-6 border border-gray-200 rounded-lg bg-white">
      {/* Header - Always Visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
            <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
          </div>
          <div className="text-left">
            <h3 className="text-lg font-semibold text-gray-900">
              Tree Distribution Model
            </h3>
            <p className="text-sm text-gray-500">
              Generate individual tree points from canopy height data (optional)
            </p>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="px-6 pb-6 border-t border-gray-200">
          {/* Description */}
          <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex gap-3">
              <AlertCircle className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-900">
                <p className="font-medium mb-1">What is this?</p>
                <p className="mb-2">
                  This tool generates a synthetic tree distribution in two formats: <strong>GPKG</strong> (GIS mapping)
                  and <strong>Excel</strong> (Forest Regulation 2079 format). Shows estimated locations of individual
                  trees based on canopy height data and species analysis. Trees are automatically assigned to sample
                  plots based on the buffer distance.
                </p>
                <p className="font-medium text-orange-700 mb-1">📋 Requirement:</p>
                <p className="mb-2 text-orange-900">
                  You must create a <strong>sampling design</strong> first (from the Sampling tab) before
                  generating tree models. Trees will be assigned to sample plots using the specified buffer.
                </p>
                <p className="font-medium text-red-700 mb-1">⚠️ Important Disclaimer:</p>
                <ul className="list-disc list-inside space-y-1 text-red-900">
                  <li>This is <strong>SYNTHETIC/MODELED data</strong>, NOT actual ground survey</li>
                  <li>For <strong>planning and visualization only</strong></li>
                  <li>Field verification required for operational plans</li>
                  <li>Accuracy: ±50% (order of magnitude estimates)</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Configuration Form */}
          <div className="mt-6">
            <h4 className="text-md font-semibold text-gray-900 mb-3">Configuration</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Minimum DBH (cm)
                </label>
                <input
                  type="number"
                  value={config.min_dbh_cm}
                  onChange={(e) => setConfig({ ...config, min_dbh_cm: parseFloat(e.target.value) })}
                  min="5"
                  max="50"
                  step="0.1"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
                  disabled={generating}
                />
                <p className="text-xs text-gray-500 mt-1">Commercial inventory threshold (default: 10cm)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Minimum Height (m)
                </label>
                <input
                  type="number"
                  value={config.min_height_m}
                  onChange={(e) => setConfig({ ...config, min_height_m: parseFloat(e.target.value) })}
                  min="2"
                  max="20"
                  step="0.1"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
                  disabled={generating}
                />
                <p className="text-xs text-gray-500 mt-1">Minimum commercial height (default: 5m)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Max Trees per Hectare
                </label>
                <input
                  type="number"
                  value={config.max_trees_per_ha}
                  onChange={(e) => setConfig({ ...config, max_trees_per_ha: parseInt(e.target.value) })}
                  min="50"
                  max="5000"
                  step="50"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
                  disabled={generating}
                />
                <p className="text-xs text-gray-500 mt-1">Upper density cap (default: 500)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Sample Plot Buffer (m)
                </label>
                <input
                  type="number"
                  value={config.plot_buffer_meters}
                  onChange={(e) => setConfig({ ...config, plot_buffer_meters: parseFloat(e.target.value) })}
                  min="5"
                  max="100"
                  step="0.01"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
                  disabled={generating}
                />
                <p className="text-xs text-gray-500 mt-1">Buffer radius for plot assignment (default: 12.62m)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Spatial Distribution
                </label>
                <select
                  value={config.spatial_distribution}
                  onChange={(e) => setConfig({ ...config, spatial_distribution: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-green-500 focus:border-green-500"
                  disabled={generating}
                >
                  <option value="random">Random</option>
                  <option value="clustered" disabled>Clustered (coming soon)</option>
                  <option value="regular" disabled>Regular (coming soon)</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">Spatial pattern (v1.0: random only)</p>
              </div>
            </div>

            {/* Error Display */}
            {error && (
              <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {/* Generate Button */}
            <div className="mt-6">
              <button
                onClick={handleGenerate}
                disabled={generating}
                className={`w-full md:w-auto px-6 py-3 rounded-md font-medium transition-colors ${
                  generating
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
              >
                {generating ? (
                  <span className="flex items-center gap-2">
                    <Loader className="w-5 h-5 animate-spin" />
                    Generating...
                  </span>
                ) : (
                  'Generate Tree Model'
                )}
              </button>
              {generating && (
                <p className="mt-2 text-sm text-gray-600">
                  This may take 5-10 minutes depending on forest size. You can close this and check back later.
                </p>
              )}
            </div>
          </div>

          {/* Models List */}
          <div className="mt-8">
            <h4 className="text-md font-semibold text-gray-900 mb-3">
              Generated Models ({models.length})
            </h4>

            {loading ? (
              <div className="text-center py-8 text-gray-500">
                <Loader className="w-6 h-6 animate-spin mx-auto mb-2" />
                Loading models...
              </div>
            ) : models.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <p>No models generated yet.</p>
                <p className="text-sm mt-1">Click "Generate Tree Model" above to create your first model.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {models.map((model) => (
                  <div
                    key={model.id}
                    className="border border-gray-200 rounded-lg p-4 bg-gray-50"
                  >
                    {/* Status Header */}
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        {model.status === 'completed' && (
                          <CheckCircle className="w-5 h-5 text-green-600" />
                        )}
                        {model.status === 'processing' && (
                          <Loader className="w-5 h-5 text-blue-600 animate-spin" />
                        )}
                        {model.status === 'failed' && (
                          <AlertCircle className="w-5 h-5 text-red-600" />
                        )}
                        <span className={`font-medium ${
                          model.status === 'completed' ? 'text-green-700' :
                          model.status === 'processing' ? 'text-blue-700' :
                          'text-red-700'
                        }`}>
                          {model.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-gray-400" />
                        <span className="text-sm text-gray-500">
                          {new Date(model.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>

                    {/* Progress Bar (if processing) */}
                    {model.status === 'processing' && (
                      <div className="mb-3">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-600">{model.current_step}</span>
                          <span className="text-sm font-medium text-gray-700">{model.progress_percent}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${model.progress_percent}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Statistics (if completed) */}
                    {model.status === 'completed' && model.total_trees && (
                      <>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
                          <div>
                            <p className="text-xs text-gray-500">Total Trees</p>
                            <p className="text-sm font-semibold text-gray-900">
                              {model.total_trees.toLocaleString()}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">Trees/ha</p>
                            <p className="text-sm font-semibold text-gray-900">
                              {model.trees_per_hectare?.toFixed(1)}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">DBH Range</p>
                            <p className="text-sm font-semibold text-gray-900">
                              {model.min_dbh_cm?.toFixed(1)} - {model.max_dbh_cm?.toFixed(1)} cm
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">File Size</p>
                            <p className="text-sm font-semibold text-gray-900">
                              {model.file_size_mb ? formatFileSize(model.file_size_mb) : 'N/A'}
                            </p>
                          </div>
                        </div>

                        {/* Overall Volume Summary */}
                        {model.algorithm_config && (
                          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mb-3 p-3 bg-amber-50 rounded-lg border border-amber-200">
                            <div>
                              <p className="text-xs text-gray-600">Pole Timber</p>
                              <p className="text-sm font-bold text-amber-800">
                                {model.algorithm_config.pole_timber_m3_per_ha?.toFixed(1) || '0'} m³/ha
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-600">Pole Firewood</p>
                              <p className="text-sm font-bold text-orange-700">
                                {model.algorithm_config.pole_firewood_m3_per_ha?.toFixed(1) || '0'} m³/ha
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-600">Tree Timber</p>
                              <p className="text-sm font-bold text-amber-900">
                                {model.algorithm_config.tree_timber_m3_per_ha?.toFixed(1) || '0'} m³/ha
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-600">Tree Firewood</p>
                              <p className="text-sm font-bold text-orange-800">
                                {model.algorithm_config.tree_firewood_m3_per_ha?.toFixed(1) || '0'} m³/ha
                              </p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-600">Total Volume</p>
                              <p className="text-sm font-bold text-red-800">
                                {model.algorithm_config.volume_per_ha?.toFixed(1) || '0'} m³/ha
                              </p>
                            </div>
                          </div>
                        )}

                        {/* Block-wise DBH Class Distribution (Per Hectare) */}
                        {model.algorithm_config?.block_dbh_distribution && (
                          <div className="mb-3">
                            <p className="text-xs text-gray-500 mb-2">Stand Density & Volume by Block (per hectare):</p>
                            <div className="space-y-2">
                              {Object.entries(model.algorithm_config.block_dbh_distribution).map(([blockName, blockData]: [string, any]) => (
                                <div key={blockName} className="bg-gray-50 p-2 rounded">
                                  <p className="text-xs font-medium text-gray-700 mb-1">{blockName} ({blockData.num_plots} plots):</p>
                                  <div className="flex flex-wrap gap-1.5">
                                    {/* Volume breakdown per hectare */}
                                    {blockData.pole_timber_m3_per_ha > 0 && (
                                      <span className="px-2 py-0.5 bg-amber-100 text-amber-800 text-xs rounded-full">
                                        Pole Timber: {blockData.pole_timber_m3_per_ha.toFixed(1)} m³/ha
                                      </span>
                                    )}
                                    {blockData.pole_firewood_m3_per_ha > 0 && (
                                      <span className="px-2 py-0.5 bg-orange-100 text-orange-800 text-xs rounded-full">
                                        Pole Firewood: {blockData.pole_firewood_m3_per_ha.toFixed(1)} m³/ha
                                      </span>
                                    )}
                                    {blockData.tree_timber_m3_per_ha > 0 && (
                                      <span className="px-2 py-0.5 bg-amber-200 text-amber-900 text-xs rounded-full">
                                        Tree Timber: {blockData.tree_timber_m3_per_ha.toFixed(1)} m³/ha
                                      </span>
                                    )}
                                    {blockData.tree_firewood_m3_per_ha > 0 && (
                                      <span className="px-2 py-0.5 bg-orange-200 text-orange-900 text-xs rounded-full">
                                        Tree Firewood: {blockData.tree_firewood_m3_per_ha.toFixed(1)} m³/ha
                                      </span>
                                    )}
                                    {/* Total volume per hectare - prominent display */}
                                    {blockData.volume_per_ha !== undefined && blockData.volume_per_ha > 0 && (
                                      <span className="px-2 py-0.5 bg-red-100 text-red-900 text-xs rounded-full font-semibold">
                                        Total: {blockData.volume_per_ha.toFixed(1)} m³/ha
                                      </span>
                                    )}
                                    {blockData.dbh_per_ha?.regeneration_1_4cm > 0 && (
                                      <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full">
                                        Regen (1-4cm): {blockData.dbh_per_ha.regeneration_1_4cm.toLocaleString()}
                                      </span>
                                    )}
                                    {blockData.dbh_per_ha?.sapling_4_10cm > 0 && (
                                      <span className="px-2 py-0.5 bg-green-200 text-green-900 text-xs rounded-full">
                                        Sapling (4-10cm): {blockData.dbh_per_ha.sapling_4_10cm.toLocaleString()}
                                      </span>
                                    )}
                                    {blockData.dbh_per_ha?.pole_10_30cm > 0 && (
                                      <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded-full">
                                        Pole (10-30cm): {blockData.dbh_per_ha.pole_10_30cm.toLocaleString()}
                                      </span>
                                    )}
                                    {blockData.dbh_per_ha?.tree_above_30cm > 0 && (
                                      <span className="px-2 py-0.5 bg-purple-100 text-purple-800 text-xs rounded-full">
                                        Tree (&gt;30cm): {blockData.dbh_per_ha.tree_above_30cm.toLocaleString()}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}

                    {/* Error Message (if failed) */}
                    {model.status === 'failed' && model.error_message && (
                      <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                        {model.error_message}
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {model.status === 'completed' && model.gpkg_filename && (
                        <button
                          onClick={() => handleDownload(model.id, model.gpkg_filename!)}
                          className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors flex items-center gap-2 text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download GPKG
                          {model.file_size_mb && <span className="text-xs opacity-80">({formatFileSize(model.file_size_mb)})</span>}
                        </button>
                      )}
                      {model.status === 'completed' && model.excel_filename && (
                        <button
                          onClick={() => handleDownloadExcel(model.id, model.excel_filename!)}
                          className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors flex items-center gap-2 text-sm"
                        >
                          <Download className="w-4 h-4" />
                          Download Excel
                          {model.excel_size_mb && <span className="text-xs opacity-80">({formatFileSize(model.excel_size_mb)})</span>}
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(model.id)}
                        className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors flex items-center gap-2 text-sm"
                      >
                        <Trash2 className="w-4 h-4" />
                        Delete
                      </button>
                      {model.processing_time_seconds && (
                        <span className="ml-auto text-sm text-gray-500">
                          Processing time: {formatDuration(model.processing_time_seconds)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default TreeModelGenerator;
