import { useState, useEffect } from 'react';
import { samplingApi, forestApi } from '../services/api';

interface SamplingTabProps {
  calculationId: string;
}

interface BlockOverride {
  enabled: boolean;
  sampling_type?: 'systematic' | 'random';
  sampling_intensity_percent?: number;
  min_samples_per_block?: number;
  boundary_buffer_meters?: number;
  min_distance_meters?: number;
}

export function SamplingTab({ calculationId }: SamplingTabProps) {
  const [designs, setDesigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

  // Sampling points table
  const [selectedDesignId, setSelectedDesignId] = useState<string | null>(null);
  const [samplingPoints, setSamplingPoints] = useState<any[]>([]);
  const [loadingPoints, setLoadingPoints] = useState(false);

  // Calculation and blocks data
  const [calculation, setCalculation] = useState<any>(null);
  const [blocks, setBlocks] = useState<any[]>([]);

  // Block overrides state
  const [enableBlockOverrides, setEnableBlockOverrides] = useState(false);
  const [blockOverrides, setBlockOverrides] = useState<Record<string, BlockOverride>>({});
  const [expandedBlocks, setExpandedBlocks] = useState<Record<string, boolean>>({});

  // Form state
  const [samplingType, setSamplingType] = useState<'systematic' | 'random'>('systematic');
  const [samplingIntensity, setSamplingIntensity] = useState(0.5); // NEW: percentage of block area
  const [minSamplesPerBlock, setMinSamplesPerBlock] = useState(5); // NEW: min for blocks >= 1ha
  const [minSamplesSmallBlocks, setMinSamplesSmallBlocks] = useState(2); // NEW: min for blocks < 1ha
  const [minDistance, setMinDistance] = useState(30);
  const [plotShape, setPlotShape] = useState<'circular' | 'square'>('circular');
  const [plotRadius, setPlotRadius] = useState(12.6156);
  const [plotSide, setPlotSide] = useState(10);

  useEffect(() => {
    loadDesigns();
    loadCalculation();
  }, [calculationId]);

  const loadCalculation = async () => {
    try {
      const data = await forestApi.getCalculation(calculationId);
      setCalculation(data);
      const extractedBlocks = data.result_data?.blocks || [];
      setBlocks(extractedBlocks);

      // Initialize block overrides for all blocks
      const initialOverrides: Record<string, BlockOverride> = {};
      extractedBlocks.forEach((block: any) => {
        initialOverrides[block.block_name] = { enabled: false };
      });
      setBlockOverrides(initialOverrides);
    } catch (err: any) {
      console.error('Failed to load calculation:', err);
    }
  };

  const loadDesigns = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await samplingApi.list(calculationId);
      setDesigns(data);

      // Auto-load sampling points for the first design by default
      if (data.length > 0 && !selectedDesignId) {
        loadSamplingPoints(data[0].id);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load sampling designs');
    } finally {
      setLoading(false);
    }
  };

  const loadSamplingPoints = async (designId: string) => {
    setLoadingPoints(true);
    try {
      const data = await samplingApi.getPoints(designId);
      setSamplingPoints(data.points || []);
      setSelectedDesignId(designId);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load sampling points');
    } finally {
      setLoadingPoints(false);
    }
  };

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const params: any = {
        sampling_type: samplingType,
        sampling_intensity_percent: samplingIntensity, // NEW: Use percentage instead of grid spacing
        min_samples_per_block: minSamplesPerBlock, // NEW: Minimum for blocks >= 1ha
        min_samples_small_blocks: minSamplesSmallBlocks, // NEW: Minimum for blocks < 1ha
        plot_shape: plotShape,
      };

      // For random sampling, add minimum distance
      if (samplingType === 'random') {
        params.min_distance_meters = minDistance;
      }

      if (plotShape === 'circular') {
        params.plot_radius_meters = plotRadius;
      } else {
        params.plot_length_meters = plotSide;
        params.plot_width_meters = plotSide;
      }

      // Add block overrides if enabled
      if (enableBlockOverrides) {
        const overrides: Record<string, any> = {};
        Object.entries(blockOverrides).forEach(([blockName, override]) => {
          if (override.enabled) {
            const blockOverride: any = {};
            if (override.sampling_type !== undefined) {
              blockOverride.sampling_type = override.sampling_type;
            }
            if (override.sampling_intensity_percent !== undefined) {
              blockOverride.sampling_intensity_percent = override.sampling_intensity_percent;
            }
            if (override.min_samples_per_block !== undefined) {
              blockOverride.min_samples_per_block = override.min_samples_per_block;
            }
            if (override.boundary_buffer_meters !== undefined) {
              blockOverride.boundary_buffer_meters = override.boundary_buffer_meters;
            }
            if (override.min_distance_meters !== undefined) {
              blockOverride.min_distance_meters = override.min_distance_meters;
            }

            if (Object.keys(blockOverride).length > 0) {
              overrides[blockName] = blockOverride;
            }
          }
        });

        if (Object.keys(overrides).length > 0) {
          params.block_overrides = overrides;
        }
      }

      const result = await samplingApi.create(calculationId, params);

      // Build per-block summary for alert
      let blockSummary = '';
      if (result.blocks_info && result.blocks_info.length > 0) {
        blockSummary = '\n\nPer-Block Summary:';
        result.blocks_info.forEach((block: any) => {
          const warning = block.minimum_enforced ? ' ⚠️ Min enforced' : '';
          blockSummary += `\n- ${block.block_name}: ${block.samples_generated} samples (${parseFloat(block.actual_intensity_percent).toFixed(2)}%)${warning}`;
        });
      }

      alert(`Sampling design created successfully!\n\nType: ${result.sampling_type}\nTotal Blocks: ${result.total_blocks}\nTotal Points: ${result.total_points}\nRequested Intensity: ${result.requested_intensity_percent}%\nActual Sampling: ${parseFloat(result.sampling_percentage || 0).toFixed(2)}%${blockSummary}`);

      setShowCreateForm(false);
      await loadDesigns();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create sampling design');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (designId: string) => {
    if (!confirm('Delete sampling design? This cannot be undone.')) {
      return;
    }

    try {
      await samplingApi.delete(designId);
      await loadDesigns();
      alert('Sampling design deleted successfully');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete sampling design');
    }
  };

  const handleExport = async (designId: string, format: 'csv' | 'gpx' | 'geojson' | 'kml') => {
    try {
      const blob = await samplingApi.export(designId, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `sampling_${designId.substring(0, 8)}.${format}`;
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
        <div className="text-gray-600">Loading sampling designs...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Create Button */}
      {!showCreateForm && designs.length === 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <button
            onClick={() => setShowCreateForm(true)}
            className="w-full bg-blue-600 text-white px-4 py-3 rounded-md hover:bg-blue-700"
          >
            + Create New Sampling Design
          </button>
        </div>
      )}

      {/* Warning if design exists */}
      {!showCreateForm && designs.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-yellow-800 mb-2">
            One Sampling Design Per Forest
          </h3>
          <p className="text-sm text-yellow-700 mb-4">
            Only one sampling design is allowed per community forest. To create a new design, please delete the existing one first.
          </p>
          <button
            onClick={() => setShowCreateForm(true)}
            disabled
            className="w-full bg-gray-400 text-white px-4 py-3 rounded-md cursor-not-allowed"
          >
            + Create New Sampling Design (Delete existing first)
          </button>
        </div>
      )}

      {/* Create Form */}
      {showCreateForm && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-semibold">Create Sampling Design</h3>
            <button
              onClick={() => setShowCreateForm(false)}
              className="text-gray-500 hover:text-gray-700"
            >
              ✕
            </button>
          </div>

          <div className="space-y-4">
            {/* Sampling Type */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Sampling Type
              </label>
              <select
                value={samplingType}
                onChange={(e) => setSamplingType(e.target.value as 'systematic' | 'random')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="systematic">Systematic (Grid) - Recommended</option>
                <option value="random">Random</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">
                Systematic sampling is preferred in forestry for even coverage
              </p>
            </div>

            {/* Sampling Intensity (Common to both types) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Sampling Intensity (% of block area)
              </label>
              <input
                type="number"
                min="0.1"
                max="10"
                step="0.1"
                value={samplingIntensity}
                onChange={(e) => setSamplingIntensity(parseFloat(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
              <p className="mt-1 text-xs text-gray-500">
                Default: 0.5% (grid spacing calculated automatically)
              </p>
            </div>

            {/* Minimum Samples Configuration */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Min Samples (blocks ≥ 1 ha)
                </label>
                <input
                  type="number"
                  min="2"
                  max="10"
                  value={minSamplesPerBlock}
                  onChange={(e) => setMinSamplesPerBlock(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="mt-1 text-xs text-gray-500">Default: 5</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Min Samples (blocks &lt; 1 ha)
                </label>
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={minSamplesSmallBlocks}
                  onChange={(e) => setMinSamplesSmallBlocks(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="mt-1 text-xs text-gray-500">Default: 2</p>
              </div>
            </div>

            {/* Random-specific Options */}
            {samplingType === 'random' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Minimum Distance Between Points (meters)
                </label>
                <input
                  type="number"
                  min="0"
                  max="200"
                  value={minDistance}
                  onChange={(e) => setMinDistance(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Optional spacing constraint for random points
                </p>
              </div>
            )}

            {/* Plot Shape */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Plot Shape
              </label>
              <select
                value={plotShape}
                onChange={(e) => setPlotShape(e.target.value as 'circular' | 'square')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              >
                <option value="circular">Circular</option>
                <option value="square">Square</option>
              </select>
            </div>

            {/* Plot Size */}
            {plotShape === 'circular' ? (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Plot Radius (meters)
                </label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={plotRadius}
                  onChange={(e) => setPlotRadius(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            ) : (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Plot Side Length (meters)
                </label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={plotSide}
                  onChange={(e) => setPlotSide(parseFloat(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                />
              </div>
            )}

            {/* Block Overrides Section */}
            {blocks.length > 1 && (
              <div className="border-t pt-6 mt-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h4 className="text-md font-semibold text-gray-900">Per-Block Customization</h4>
                    <p className="text-xs text-gray-500 mt-1">
                      Optionally customize sampling parameters for individual blocks
                    </p>
                  </div>
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={enableBlockOverrides}
                      onChange={(e) => setEnableBlockOverrides(e.target.checked)}
                      className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <span className="text-sm font-medium text-gray-700">Enable</span>
                  </label>
                </div>

                {enableBlockOverrides && (
                  <div className="space-y-3">
                    {blocks.map((block: any, index: number) => {
                      const blockName = block.block_name;
                      const override = blockOverrides[blockName] || { enabled: false };
                      const isExpanded = expandedBlocks[blockName];

                      return (
                        <div key={index} className="border border-gray-200 rounded-lg overflow-hidden">
                          <div className="bg-gray-50 px-4 py-3 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <button
                                onClick={() => setExpandedBlocks(prev => ({
                                  ...prev,
                                  [blockName]: !prev[blockName]
                                }))}
                                className="text-gray-500 hover:text-gray-700"
                              >
                                {isExpanded ? '▼' : '▶'}
                              </button>
                              <div>
                                <div className="font-medium text-gray-900">{blockName}</div>
                                <div className="text-xs text-gray-500">
                                  {block.area_hectares?.toFixed(2)} ha
                                  {override.enabled && (
                                    <span className="ml-2 text-blue-600 font-semibold">⚡ Customized</span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <label className="flex items-center cursor-pointer">
                              <input
                                type="checkbox"
                                checked={override.enabled}
                                onChange={(e) => setBlockOverrides(prev => ({
                                  ...prev,
                                  [blockName]: { ...prev[blockName], enabled: e.target.checked }
                                }))}
                                className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                              />
                              <span className="text-sm text-gray-700">Customize</span>
                            </label>
                          </div>

                          {isExpanded && override.enabled && (
                            <div className="px-4 py-4 space-y-3 bg-white">
                              {/* Sampling Type Override */}
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                  Sampling Type (override)
                                </label>
                                <select
                                  value={override.sampling_type || ''}
                                  onChange={(e) => setBlockOverrides(prev => ({
                                    ...prev,
                                    [blockName]: {
                                      ...prev[blockName],
                                      sampling_type: e.target.value ? e.target.value as 'systematic' | 'random' : undefined
                                    }
                                  }))}
                                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                                >
                                  <option value="">Use default ({samplingType})</option>
                                  <option value="systematic">Systematic</option>
                                  <option value="random">Random</option>
                                </select>
                              </div>

                              {/* Intensity Override */}
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                  Sampling Intensity % (override)
                                </label>
                                <input
                                  type="number"
                                  min="0.1"
                                  max="10"
                                  step="0.1"
                                  placeholder={`Default: ${samplingIntensity}%`}
                                  value={override.sampling_intensity_percent || ''}
                                  onChange={(e) => setBlockOverrides(prev => ({
                                    ...prev,
                                    [blockName]: {
                                      ...prev[blockName],
                                      sampling_intensity_percent: e.target.value ? parseFloat(e.target.value) : undefined
                                    }
                                  }))}
                                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                                />
                              </div>

                              {/* Min Samples Override */}
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                  Min Samples (override)
                                </label>
                                <input
                                  type="number"
                                  min="2"
                                  max="20"
                                  placeholder={`Default: ${minSamplesPerBlock}`}
                                  value={override.min_samples_per_block || ''}
                                  onChange={(e) => setBlockOverrides(prev => ({
                                    ...prev,
                                    [blockName]: {
                                      ...prev[blockName],
                                      min_samples_per_block: e.target.value ? parseInt(e.target.value) : undefined
                                    }
                                  }))}
                                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                                />
                              </div>

                              {/* Boundary Buffer Override */}
                              <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                  Boundary Buffer (meters, override)
                                </label>
                                <input
                                  type="number"
                                  min="0"
                                  max="200"
                                  placeholder="Default: 50m"
                                  value={override.boundary_buffer_meters || ''}
                                  onChange={(e) => setBlockOverrides(prev => ({
                                    ...prev,
                                    [blockName]: {
                                      ...prev[blockName],
                                      boundary_buffer_meters: e.target.value ? parseFloat(e.target.value) : undefined
                                    }
                                  }))}
                                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                                />
                              </div>

                              {/* Min Distance Override (for random sampling) */}
                              {(override.sampling_type === 'random' || (!override.sampling_type && samplingType === 'random')) && (
                                <div>
                                  <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Min Distance Between Points (meters, override)
                                  </label>
                                  <input
                                    type="number"
                                    min="5"
                                    max="500"
                                    placeholder={`Default: ${minDistance}m`}
                                    value={override.min_distance_meters || ''}
                                    onChange={(e) => setBlockOverrides(prev => ({
                                      ...prev,
                                      [blockName]: {
                                        ...prev[blockName],
                                        min_distance_meters: e.target.value ? parseInt(e.target.value) : undefined
                                      }
                                    }))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                                  />
                                </div>
                              )}

                              {/* Reset Button */}
                              <button
                                onClick={() => setBlockOverrides(prev => ({
                                  ...prev,
                                  [blockName]: { enabled: true }
                                }))}
                                className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                              >
                                Reset to Defaults
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Buttons */}
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={creating}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:bg-gray-400"
              >
                {creating ? 'Creating...' : 'Create Design'}
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </div>

          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}
        </div>
      )}

      {/* Designs List */}
      {designs.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-semibold">Sampling Designs ({designs.length})</h3>
          </div>
          <div className="divide-y divide-gray-200">
            {designs.map((design) => (
              <div key={design.id} className="p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`px-3 py-1 rounded text-sm font-medium ${
                        design.sampling_type === 'systematic'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-green-100 text-green-800'
                      }`}>
                        {design.sampling_type}
                      </span>
                      <span className="text-sm text-gray-600">
                        {new Date(design.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-4">
                      <div>
                        <div className="text-gray-600">Total Points</div>
                        <div className="font-semibold">{design.total_points}</div>
                      </div>
                      {design.total_blocks && (
                        <div>
                          <div className="text-gray-600">Total Blocks</div>
                          <div className="font-semibold">{design.total_blocks}</div>
                        </div>
                      )}
                      {design.requested_intensity_percent && (
                        <div>
                          <div className="text-gray-600">Requested Intensity</div>
                          <div className="font-semibold">{design.requested_intensity_percent}%</div>
                        </div>
                      )}
                      {design.plot_area_sqm && (
                        <div>
                          <div className="text-gray-600">Plot Area</div>
                          <div className="font-semibold">{parseFloat(design.plot_area_sqm).toFixed(2)} m²</div>
                        </div>
                      )}
                    </div>

                    {/* Per-Block Summary */}
                    {design.blocks_info && design.blocks_info.length > 0 && (
                      <div className="mt-4 border-t pt-4">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Per-Block Distribution:</h4>
                        <div className="space-y-2">
                          {design.blocks_info.map((block: any, idx: number) => (
                            <div key={idx} className="flex justify-between items-center text-sm bg-gray-50 rounded px-3 py-2">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{block.block_name}</span>
                                <span className="text-gray-500">({parseFloat(block.block_area_hectares).toFixed(2)} ha)</span>
                                {block.minimum_enforced && (
                                  <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">
                                    Min enforced
                                  </span>
                                )}
                              </div>
                              <div className="font-semibold">
                                {block.samples_generated} samples ({parseFloat(block.actual_intensity_percent).toFixed(2)}%)
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => handleDelete(design.id)}
                    className="text-red-600 hover:text-red-800 text-sm"
                  >
                    Delete
                  </button>
                </div>

                <div className="space-y-2">
                  {/* Toggle Points Button */}
                  <button
                    onClick={() => {
                      if (selectedDesignId === design.id && samplingPoints.length > 0) {
                        setSelectedDesignId(null);
                        setSamplingPoints([]);
                      } else {
                        loadSamplingPoints(design.id);
                      }
                    }}
                    className="w-full bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700"
                  >
                    {selectedDesignId === design.id && samplingPoints.length > 0
                      ? '▲ Hide Sampling Points'
                      : '▼ View Sampling Points'}
                  </button>

                  {/* Export Buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleExport(design.id, 'csv')}
                      className="flex-1 bg-green-600 text-white px-3 py-1.5 rounded text-sm hover:bg-green-700"
                    >
                      CSV
                    </button>
                    <button
                      onClick={() => handleExport(design.id, 'geojson')}
                      className="flex-1 bg-green-600 text-white px-3 py-1.5 rounded text-sm hover:bg-green-700"
                    >
                      GeoJSON
                    </button>
                    <button
                      onClick={() => handleExport(design.id, 'gpx')}
                      className="flex-1 bg-green-600 text-white px-3 py-1.5 rounded text-sm hover:bg-green-700"
                    >
                      GPX
                    </button>
                    <button
                      onClick={() => handleExport(design.id, 'kml')}
                      className="flex-1 bg-green-600 text-white px-3 py-1.5 rounded text-sm hover:bg-green-700"
                    >
                      KML
                    </button>
                  </div>
                </div>

                {/* Sampling Points Table */}
                {selectedDesignId === design.id && samplingPoints.length > 0 && (
                  <div className="mt-6 border-t pt-6">
                    <div className="flex justify-between items-center mb-4">
                      <h4 className="text-md font-semibold text-gray-700">
                        Sampling Points ({samplingPoints.length} total)
                      </h4>
                      {samplingPoints.length > 100 && (
                        <span className="text-sm text-gray-600">
                          Showing first 100 rows - Export for full data
                        </span>
                      )}
                    </div>

                    {loadingPoints ? (
                      <div className="text-center py-8 text-gray-600">Loading points...</div>
                    ) : (
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200">
                          <thead className="bg-gray-50">
                            <tr>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Plot #</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Block</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Longitude</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Latitude</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM Easting</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM Northing</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM Zone</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Distance from Boundary (m)</th>
                            </tr>
                          </thead>
                          <tbody className="bg-white divide-y divide-gray-200">
                            {samplingPoints.slice(0, 100).map((point: any) => (
                              <tr key={point.id} className="hover:bg-gray-50">
                                <td className="px-4 py-2 text-sm font-mono">P{point.plot_number}</td>
                                <td className="px-4 py-2 text-sm">
                                  <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs font-medium">
                                    {point.block_name || `Block ${point.block_number}`}
                                  </span>
                                </td>
                                <td className="px-4 py-2 text-sm font-mono">{parseFloat(point.longitude).toFixed(7)}</td>
                                <td className="px-4 py-2 text-sm font-mono">{parseFloat(point.latitude).toFixed(7)}</td>
                                <td className="px-4 py-2 text-sm font-mono">{point.utm_easting ? parseFloat(point.utm_easting).toFixed(2) : 'N/A'}</td>
                                <td className="px-4 py-2 text-sm font-mono">{point.utm_northing ? parseFloat(point.utm_northing).toFixed(2) : 'N/A'}</td>
                                <td className="px-4 py-2 text-sm">{point.utm_zone || 'N/A'}</td>
                                <td className="px-4 py-2 text-sm">{point.distance_from_boundary ? parseFloat(point.distance_from_boundary).toFixed(2) : 'N/A'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {samplingPoints.length > 100 && (
                          <div className="px-6 py-4 bg-gray-50 text-sm text-gray-600 text-center">
                            Showing first 100 of {samplingPoints.length} points. Export to see all.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {designs.length === 0 && !showCreateForm && (
        <div className="bg-white rounded-lg shadow p-12 text-center text-gray-500">
          No sampling designs yet. Create one to get started.
        </div>
      )}
    </div>
  );
}
