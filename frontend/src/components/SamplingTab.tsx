import { useState, useEffect } from 'react';
import { samplingApi } from '../services/api';

interface SamplingTabProps {
  calculationId: string;
}

export function SamplingTab({ calculationId }: SamplingTabProps) {
  const [designs, setDesigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);

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
  }, [calculationId]);

  const loadDesigns = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await samplingApi.list(calculationId);
      setDesigns(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load sampling designs');
    } finally {
      setLoading(false);
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
