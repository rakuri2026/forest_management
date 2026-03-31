import { useState, useEffect } from 'react';
import { samplingApi, forestApi } from '../services/api';
import { SamplingMapView } from './SamplingMapView';
import { AccessibleForestPreview } from './AccessibleForestPreview';

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

  // Navigation support options (Phase 2 enhancement)
  const [includeElevation, setIncludeElevation] = useState(true); // Default: ON
  const [includeTopoFeatures, setIncludeTopoFeatures] = useState(true); // Default: ON (ridge/river info)

  // Calculation and blocks data
  const [calculation, setCalculation] = useState<any>(null);
  const [blocks, setBlocks] = useState<any[]>([]);

  // Block overrides state
  const [enableBlockOverrides, setEnableBlockOverrides] = useState(false);
  const [blockOverrides, setBlockOverrides] = useState<Record<string, BlockOverride>>({});
  const [expandedBlocks, setExpandedBlocks] = useState<Record<string, boolean>>({});

  // Form state
  const [samplingMethod, setSamplingMethod] = useState<'guideline_2061' | 'manual'>('guideline_2061');
  const [samplingType, setSamplingType] = useState<'systematic' | 'random'>('systematic');
  const [samplingIntensity, setSamplingIntensity] = useState(0.5); // percentage of block area
  const [productiveIntensity, setProductiveIntensity] = useState<'0.5' | '1.0'>('0.5');
  const [sampleProtectedZone, setSampleProtectedZone] = useState(false);
  const [plotSizeSqm, setPlotSizeSqm] = useState(500);
  const [protectedZoneInfo, setProtectedZoneInfo] = useState<any>(null);
  const [loadingProtectedInfo, setLoadingProtectedInfo] = useState(false);
  const [minSamplesPerBlock, setMinSamplesPerBlock] = useState(5); // NEW: min for blocks >= 1ha
  const [minSamplesSmallBlocks, setMinSamplesSmallBlocks] = useState(2); // NEW: min for blocks < 1ha
  const [minDistance, setMinDistance] = useState(30);
  const [plotShape, setPlotShape] = useState<'circular' | 'square'>('circular');
  const [plotRadius, setPlotRadius] = useState(12.6156);
  const [plotSide, setPlotSide] = useState(10);

  // Accessible forest filtering (Phase 2)
  const [filterTreeCover, setFilterTreeCover] = useState(true); // Default: ON
  const [filterSlope, setFilterSlope] = useState(false); // Default: OFF
  const [maxSlopeDegrees, setMaxSlopeDegrees] = useState(45.0); // Default: 45°

  // Forest area preview
  const [previewData, setPreviewData] = useState<any>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    loadDesigns();
    loadCalculation();
  }, [calculationId]);

  const loadProtectedZoneInfo = async () => {
    setLoadingProtectedInfo(true);
    try {
      const data = await samplingApi.getProtectedZones(calculationId);
      setProtectedZoneInfo(data);
    } catch (err: any) {
      console.error('Failed to load protected zone info:', err);
      setProtectedZoneInfo(null);
    } finally {
      setLoadingProtectedInfo(false);
    }
  };

  // Load protected zone info when guideline method is selected
  useEffect(() => {
    if (samplingMethod === 'guideline_2061' && showCreateForm) {
      loadProtectedZoneInfo();
    }
  }, [samplingMethod, showCreateForm, calculationId]);

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
      const data = await samplingApi.getPoints(designId, {
        include_elevation: includeElevation,
        include_topographic_features: includeTopoFeatures,
      });
      setSamplingPoints(data.points || []);
      setSelectedDesignId(designId);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load sampling points');
    } finally {
      setLoadingPoints(false);
    }
  };

  const handlePreviewForestAreas = async () => {
    setLoadingPreview(true);
    setPreviewData(null);
    setError(null);

    try {
      const data = await samplingApi.previewAccessibleForest(calculationId, {
        filter_tree_cover: filterTreeCover,
        filter_slope: filterSlope,
        max_slope_degrees: maxSlopeDegrees,
      });
      setPreviewData(data);
      setShowPreview(true);
    } catch (err: any) {
      const errorDetail = err.response?.data?.detail || 'Failed to preview forest areas';

      // Check if it's a timeout error (408 status)
      if (err.response?.status === 408) {
        setError(
          `⏱️ Preview Timeout: ${errorDetail}\n\n` +
          `For large forest areas with slope filtering, the preview can be slow.\n\n` +
          `Options:\n` +
          `1. Disable "Filter by Slope" for faster preview\n` +
          `2. Skip preview and create sampling design directly\n` +
          `   (Slope filtering will still work during sampling, it's just slower for visualization)`
        );
      } else {
        setError(errorDetail);
      }

      setShowPreview(false);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const params: any = {
        sampling_method: samplingMethod,
        plot_shape: plotShape,
        filter_tree_cover: filterTreeCover,
        filter_slope: filterSlope,
        max_slope_degrees: maxSlopeDegrees,
      };

      if (samplingMethod === 'guideline_2061') {
        params.productive_intensity = productiveIntensity;
        params.sample_protected_zone = sampleProtectedZone;
        params.plot_size_sqm = plotSizeSqm;
      } else {
        params.sampling_type = samplingType;
        params.sampling_intensity_percent = samplingIntensity;
        params.min_samples_per_block = minSamplesPerBlock;
        params.min_samples_small_blocks = minSamplesSmallBlocks;

        if (samplingType === 'random') {
          params.min_distance_meters = minDistance;
        }

        if (plotShape === 'circular') {
          params.plot_radius_meters = plotRadius;
        } else {
          params.plot_length_meters = plotSide;
          params.plot_width_meters = plotSide;
        }

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
      try {
        await loadDesigns();
      } catch (loadErr) {
        console.error('Failed to reload designs:', loadErr);
      }
    } catch (err: any) {
      console.error('Create sampling error:', err);
      let errorMsg = 'Failed to create sampling design';
      if (err.response?.data?.detail) {
        errorMsg = typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail);
      } else if (err.message) {
        errorMsg = err.message;
      } else if (typeof err === 'string') {
        errorMsg = err;
      }
      setError(errorMsg);
      alert(`Error: ${errorMsg}`);
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
            {/* Sampling Method Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Sampling Method
              </label>
              <div className="space-y-3">
                <label className="flex items-start cursor-pointer border border-blue-300 rounded-lg p-4 bg-blue-50 hover:bg-blue-100 transition-colors">
                  <input
                    type="radio"
                    value="guideline_2061"
                    checked={samplingMethod === 'guideline_2061'}
                    onChange={(e) => setSamplingMethod(e.target.value as 'guideline_2061' | 'manual')}
                    className="mt-1 h-5 w-5 text-blue-600"
                  />
                  <div className="ml-3 flex-1">
                    <div className="font-semibold text-gray-900">
                      Guideline-2061 (Recommended)
                      <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                        Standard
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      Nepal Department of Forest standard sampling method. Sample counts automatically
                      determined based on block size and plot size using official guideline tables.
                    </p>
                  </div>
                </label>

                <label className="flex items-start cursor-pointer border border-gray-300 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                  <input
                    type="radio"
                    value="manual"
                    checked={samplingMethod === 'manual'}
                    onChange={(e) => setSamplingMethod(e.target.value as 'guideline_2061' | 'manual')}
                    className="mt-1 h-5 w-5 text-gray-600"
                  />
                  <div className="ml-3 flex-1">
                    <div className="font-semibold text-gray-900">Manual (Advanced)</div>
                    <p className="text-sm text-gray-600 mt-1">
                      Custom sampling with full control over intensity, spacing, and algorithms.
                      For advanced users or special requirements.
                    </p>
                  </div>
                </label>
              </div>
            </div>

            {/* Guideline-2061 Specific Options */}
            {samplingMethod === 'guideline_2061' && (
              <div className="space-y-4 border-t pt-4">
                <h4 className="font-semibold text-gray-900 flex items-center gap-2">
                  <span className="text-blue-600">📋</span>
                  Guideline-2061 Configuration
                </h4>

                {/* Sampling Intensity */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Sampling Intensity for Productive Forest
                  </label>
                  <select
                    value={productiveIntensity}
                    onChange={(e) => setProductiveIntensity(e.target.value as '0.5' | '1.0')}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white"
                  >
                    <option value="0.5">0.5% - Standard intensity (Recommended)</option>
                    <option value="1.0">1.0% - Detailed inventory (More samples)</option>
                  </select>
                  <p className="mt-1 text-xs text-gray-500">
                    Sample count per block will be determined from Guideline-2061 lookup tables based on block size
                  </p>
                </div>

                {/* Plot Size */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Plot Size
                  </label>
                  <select
                    value={plotSizeSqm}
                    onChange={(e) => setPlotSizeSqm(parseInt(e.target.value))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white"
                  >
                    <option value="500">500 m² (12.62m radius) - Standard</option>
                    <option value="400">400 m² (11.28m radius)</option>
                    <option value="300">300 m² (9.77m radius)</option>
                    <option value="200">200 m² (7.98m radius)</option>
                    <option value="100">100 m² (5.64m radius)</option>
                  </select>
                  <p className="mt-1 text-xs text-gray-500">
                    Circular plots with radius calculated from area. Sample counts vary by plot size.
                  </p>
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-xs text-gray-700">
                    <strong className="text-blue-900">Note:</strong> Guideline-2061 method uses <strong>systematic (grid) sampling only</strong>,
                    as specified by the Department of Forest. Sample counts are predetermined by lookup tables.
                    For random or stratified sampling, use the Manual method.
                  </p>
                </div>
              </div>
            )}

            {/* Manual Method Options */}
            {samplingMethod === 'manual' && (
              <div className="space-y-4 border-t pt-4">
                <h4 className="font-semibold text-gray-900 flex items-center gap-2">
                  <span className="text-gray-600">⚙️</span>
                  Manual Sampling Configuration
                </h4>

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

                {/* Sampling Intensity */}
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

              </div>
            )}

            {/* Accessible Forest Filtering (common to both methods) */}
            <div className="border-t pt-6 mt-6">
              <h4 className="text-md font-semibold text-gray-900 mb-3">
                Sampling Area Filters
              </h4>
              <p className="text-xs text-gray-600 mb-4">
                Control which areas are eligible for sample plot placement
              </p>

              {/* Tree Cover Filter */}
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                <div className="flex items-start justify-between">
                  <label className="flex items-start space-x-3 cursor-pointer flex-1">
                    <input
                      type="checkbox"
                      checked={filterTreeCover}
                      onChange={(e) => setFilterTreeCover(e.target.checked)}
                      className="mt-1 h-5 w-5 text-green-600 focus:ring-green-500 border-gray-300 rounded"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">Filter to Tree Cover Only</div>
                      <p className="text-sm text-gray-600 mt-1">
                        Exclude non-forest areas (grassland, cropland, water bodies, settlements)
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Uses ESA WorldCover data (10m resolution) to identify tree-covered pixels
                      </p>
                    </div>
                  </label>
                  <span className="ml-3 text-xs bg-green-100 text-green-800 px-2 py-1 rounded whitespace-nowrap">
                    Recommended
                  </span>
                </div>
              </div>

              {/* Slope Filter */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <div className="flex items-start justify-between">
                  <label className="flex items-start space-x-3 cursor-pointer flex-1">
                    <input
                      type="checkbox"
                      checked={filterSlope}
                      onChange={(e) => setFilterSlope(e.target.checked)}
                      className="mt-1 h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-900">Filter by Slope Accessibility</div>
                      <p className="text-sm text-gray-600 mt-1">
                        Exclude steep slopes that may be difficult or unsafe to access
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Calculated from DEM (Digital Elevation Model) data
                      </p>
                    </div>
                  </label>
                  <span className="ml-3 text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded whitespace-nowrap">
                    Optional
                  </span>
                </div>

                {/* Max Slope Selector */}
                {filterSlope && (
                  <div className="mt-4 ml-8">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Maximum Slope Threshold
                    </label>
                    <select
                      value={maxSlopeDegrees}
                      onChange={(e) => setMaxSlopeDegrees(parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md bg-white"
                    >
                      <option value="30">30° - Conservative (gentle slopes only)</option>
                      <option value="45">45° - Standard (moderate slopes)</option>
                      <option value="60">60° - Aggressive (steep slopes OK)</option>
                    </select>
                    <p className="mt-2 text-xs text-gray-500">
                      <span className="font-medium">Slope Reference:</span><br/>
                      • 0-15°: Flat to gentle (easy walking)<br/>
                      • 15-30°: Moderate (hiking with caution)<br/>
                      • 30-45°: Steep (difficult, experienced crews)<br/>
                      • 45-60°: Very steep (safety equipment needed)<br/>
                      • 60-90°: Extremely steep to cliff (inaccessible)
                    </p>
                  </div>
                )}
              </div>

              {/* Filter Summary */}
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                <div className="text-xs text-gray-700">
                  <span className="font-semibold">Active Filters:</span>
                  {filterTreeCover && (
                    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                      Tree Cover
                    </span>
                  )}
                  {filterSlope && (
                    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800 line-through">
                      Slope ≤ {maxSlopeDegrees}° (DISABLED)
                    </span>
                  )}
                  {!filterTreeCover && !filterSlope && (
                    <span className="ml-2 text-gray-500">None - Sampling across entire boundary</span>
                  )}
                </div>
              </div>

              {/* Slope Filter Disabled Warning */}
              {filterSlope && (
                <div className="bg-red-50 border border-red-300 rounded-lg p-4">
                  <h5 className="text-sm font-semibold text-red-900 mb-2">
                    ⚠️ SLOPE FILTERING TEMPORARILY DISABLED
                  </h5>
                  <p className="text-sm text-red-800 mb-2">
                    Slope filtering causes severe server hangs and has been <strong>completely disabled</strong> for system stability.
                  </p>
                  <p className="text-sm text-red-700 mb-2">
                    <strong>Current Behavior:</strong> Sampling design will use <strong>tree cover filter ONLY</strong>,
                    regardless of slope checkbox status.
                  </p>
                  <p className="text-xs text-red-600">
                    <strong>Recommendation:</strong> Uncheck the "Filter by Slope" option to avoid confusion.
                    All tree-covered areas will be eligible for sampling.
                  </p>
                </div>
              )}

              {/* Preview Button */}
              {(filterTreeCover || filterSlope) && (
                <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
                  <h5 className="text-sm font-semibold text-yellow-900 mb-2">
                    📊 Preview Forest Classification
                  </h5>
                  <p className="text-xs text-yellow-800 mb-3">
                    Before creating the sampling design, preview which areas will be classified as "Accessible" (green) vs "Protected" (red) based on your filter settings.
                  </p>
                  {filterSlope && (
                    <div className="bg-orange-100 border border-orange-300 rounded px-3 py-2 mb-3">
                      <p className="text-xs text-orange-800">
                        ⚠️ <strong>Slope filtering enabled:</strong> Preview may take 30-120 seconds for large areas.
                        {calculation && calculation.result_data?.total_area > 100 && (
                          <span className="block mt-1">
                            Your forest is {calculation.result_data.total_area.toFixed(0)} ha - expect slower processing.
                          </span>
                        )}
                      </p>
                    </div>
                  )}
                  <button
                    onClick={handlePreviewForestAreas}
                    disabled={loadingPreview}
                    className="w-full bg-yellow-600 text-white px-4 py-2 rounded-md hover:bg-yellow-700 disabled:bg-gray-400 font-medium transition-colors"
                  >
                    {loadingPreview ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        <span>Analyzing forest areas... {filterSlope ? '(may take 30-120s)' : ''}</span>
                      </span>
                    ) : '🗺️ Preview Accessible & Protected Forest Areas'}
                  </button>
                  {!showPreview && (
                    <p className="text-xs text-gray-600 mt-2 text-center">
                      Or skip preview and create sampling design directly below
                    </p>
                  )}
                </div>
              )}

              {/* Preview Visualization */}
              {showPreview && previewData && (
                <div className="border-t pt-4 mt-4">
                  <div className="flex justify-between items-center mb-3">
                    <h4 className="text-md font-semibold text-gray-900">
                      Forest Area Preview
                    </h4>
                    <button
                      onClick={() => setShowPreview(false)}
                      className="text-sm text-gray-600 hover:text-gray-800"
                    >
                      ✕ Hide Preview
                    </button>
                  </div>
                  <AccessibleForestPreview previewData={previewData} />
                </div>
              )}
            </div>

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
                  {/* Navigation Support Options */}
                  <div className="bg-gray-50 border border-gray-200 rounded p-3 mb-2">
                    <div className="text-xs font-semibold text-gray-700 mb-2">Field Navigation Support:</div>
                    <div className="flex gap-4 text-sm">
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={includeElevation}
                          onChange={(e) => {
                            setIncludeElevation(e.target.checked);
                            // Reload points if currently viewing them
                            if (selectedDesignId === design.id && samplingPoints.length > 0) {
                              setTimeout(() => loadSamplingPoints(design.id), 100);
                            }
                          }}
                          className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <span className="text-gray-700">Elevation (ASLM)</span>
                      </label>
                      <label className="flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={includeTopoFeatures}
                          onChange={(e) => {
                            setIncludeTopoFeatures(e.target.checked);
                            // Reload points if currently viewing them
                            if (selectedDesignId === design.id && samplingPoints.length > 0) {
                              setTimeout(() => loadSamplingPoints(design.id), 100);
                            }
                          }}
                          className="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <span className="text-gray-700">Nearest Ridge/Valley</span>
                      </label>
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Help field crews navigate to sampling points with elevation and topographic landmarks
                    </p>
                  </div>

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
                              {includeElevation && samplingPoints.some(p => p.elevation_m !== undefined) && (
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase bg-blue-50">
                                  Elevation (m)
                                </th>
                              )}
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM Easting</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM Northing</th>
                              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">UTM Zone</th>
                              {includeTopoFeatures && samplingPoints.some(p => p.topographic_context) && (
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase bg-green-50">
                                  Nearest Ridge/Valley
                                </th>
                              )}
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
                                {includeElevation && samplingPoints.some(p => p.elevation_m !== undefined) && (
                                  <td className="px-4 py-2 text-sm font-semibold bg-blue-50">
                                    {point.elevation_m ? `${point.elevation_m}m` : 'N/A'}
                                  </td>
                                )}
                                <td className="px-4 py-2 text-sm font-mono">{point.utm_easting ? parseFloat(point.utm_easting).toFixed(2) : 'N/A'}</td>
                                <td className="px-4 py-2 text-sm font-mono">{point.utm_northing ? parseFloat(point.utm_northing).toFixed(2) : 'N/A'}</td>
                                <td className="px-4 py-2 text-sm">{point.utm_zone || 'N/A'}</td>
                                {includeTopoFeatures && samplingPoints.some(p => p.topographic_context) && (
                                  <td className="px-4 py-2 text-sm bg-green-50" title={point.nearest_feature_type ? `${point.nearest_feature_type} at bearing ${point.nearest_feature_bearing}°` : undefined}>
                                    {point.topographic_context || 'N/A'}
                                  </td>
                                )}
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

                    {/* Interactive Map Visualization */}
                    <div className="mt-8">
                      <h4 className="text-md font-semibold text-gray-700 mb-4">
                        📍 Interactive Map - Sampling Points & Accessible Forest Area
                      </h4>
                      <div className="bg-gray-50 rounded-lg p-3 mb-4 border border-gray-200">
                        <div className="text-sm text-gray-700">
                          <strong>Map Features:</strong>
                          <ul className="list-disc list-inside mt-1 text-xs text-gray-600 space-y-1">
                            <li>🛰️ <strong>Satellite basemap</strong> - Switch using layer control (top-right)</li>
                            <li>🔷 <strong>Forest boundary</strong> - Blue outline</li>
                            {design.default_parameters && (design.default_parameters.filter_tree_cover || design.default_parameters.filter_slope) && (
                              <li>🟢 <strong>Accessible forest area</strong> - Green shaded area (filtered by tree cover/slope)</li>
                            )}
                            <li>📍 <strong>Sample plot locations</strong> - Red markers (click for details)</li>
                            <li>🧭 <strong>North arrow</strong> - Top-right corner</li>
                            <li>📏 <strong>Scale bar</strong> - Bottom-left corner</li>
                          </ul>
                        </div>
                      </div>
                      <SamplingMapView designId={design.id} />
                    </div>
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
