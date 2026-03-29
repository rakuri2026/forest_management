import { useState, useEffect } from 'react';
import { fieldInventoryApi } from '../services/api';

interface FieldInventoryTabProps {
  calculationId: string;
}

export function FieldInventoryTab({ calculationId }: FieldInventoryTabProps) {
  const [fieldInventory, setFieldInventory] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [speciesBreakdown, setSpeciesBreakdown] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [componentError, setComponentError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  // Sample plot sizes (configurable)
  const [sampleSizes, setSampleSizes] = useState({
    regeneration_area_sqm: 10.0,
    sapling_area_sqm: 25.0,
    pole_area_sqm: 100.0,
    tree_area_sqm: 500.0,
  });

  // MAI and AAH data
  const [maiAahData, setMaiAahData] = useState<any>(null);
  const [aahMultipliers, setAahMultipliers] = useState({
    good: 75.0,
    moderate: 60.0,
    weak: 40.0,
  });

  // Custom multipliers per block (blockName -> multiplier percentage)
  const [customMultipliers, setCustomMultipliers] = useState<Record<string, number>>({});

  // Inline editing state
  const [editingBlock, setEditingBlock] = useState<string | null>(null);
  const [editingValue, setEditingValue] = useState<string>('');

  // Modal editing state
  const [modalBlock, setModalBlock] = useState<any | null>(null);

  const checkFieldInventory = async () => {
    try {
      setLoading(true);
      setComponentError(null);
      setError(null);

      console.log('Fetching field inventory for calculation:', calculationId);

      const inventory = await fieldInventoryApi.getByCalculation(calculationId);
      console.log('Field inventory found:', inventory);
      setFieldInventory(inventory);

      // Load summary and species breakdown if inventory exists
      if (inventory?.id) {
        try {
          console.log('Loading summary for inventory:', inventory.id);
          const summaryData = await fieldInventoryApi.getSummary(inventory.id);
          setSummary(summaryData);
        } catch (summaryErr: any) {
          console.warn('Failed to load summary:', summaryErr);
          setSummary(null);
        }

        try {
          console.log('Loading species breakdown for inventory:', inventory.id);
          const speciesData = await fieldInventoryApi.getSpeciesBreakdown(inventory.id);
          setSpeciesBreakdown(speciesData);
        } catch (speciesErr: any) {
          console.warn('Failed to load species breakdown:', speciesErr);
          setSpeciesBreakdown(null);
        }

        try {
          console.log('Loading MAI/AAH data for inventory:', inventory.id);
          const maiAahResult = await fieldInventoryApi.getMaiAah(
            inventory.id,
            aahMultipliers.good,
            aahMultipliers.moderate,
            aahMultipliers.weak,
            Object.keys(customMultipliers).length > 0 ? customMultipliers : undefined
          );
          setMaiAahData(maiAahResult);
        } catch (maiErr: any) {
          console.warn('Failed to load MAI/AAH data:', maiErr);
          setMaiAahData(null);
        }
      }
      setInitialized(true);
    } catch (err: any) {
      console.error('Error in checkFieldInventory:', err);
      // 404 means no field inventory exists yet
      if (err?.response?.status === 404) {
        console.log('No field inventory found (404), showing upload interface');
        setFieldInventory(null);
        setSummary(null);
        setSpeciesBreakdown(null);
        setMaiAahData(null);
        setInitialized(true);
      } else {
        const errorMessage = err?.response?.data?.detail || err?.message || 'Unknown error occurred';
        console.error('Field inventory error:', errorMessage);
        setComponentError(`Failed to load field inventory: ${errorMessage}`);
        setInitialized(true);
      }
    } finally {
      setLoading(false);
    }
  };

  // Load field inventory on mount and when calculationId changes
  useEffect(() => {
    if (!calculationId) {
      console.error('No calculationId provided to FieldInventoryTab');
      setComponentError('No calculation ID provided');
      setLoading(false);
      return;
    }

    console.log('FieldInventoryTab mounted, calculationId:', calculationId);
    checkFieldInventory();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calculationId]);

  // Handlers for AAH multiplier editing
  const handleStartInlineEdit = (blockName: string, currentValue: number) => {
    setEditingBlock(blockName);
    setEditingValue(currentValue.toString());
  };

  const handleSaveInlineEdit = async (blockName: string) => {
    const value = parseFloat(editingValue);
    if (!isNaN(value) && value >= 0 && value <= 100) {
      const newCustomMultipliers = { ...customMultipliers, [blockName]: value };
      setCustomMultipliers(newCustomMultipliers);

      // Recalculate AAH
      if (fieldInventory?.id) {
        const result = await fieldInventoryApi.getMaiAah(
          fieldInventory.id,
          aahMultipliers.good,
          aahMultipliers.moderate,
          aahMultipliers.weak,
          newCustomMultipliers
        );
        setMaiAahData(result);
      }
    }
    setEditingBlock(null);
    setEditingValue('');
  };

  const handleCancelInlineEdit = () => {
    setEditingBlock(null);
    setEditingValue('');
  };

  const handleOpenModal = (block: any) => {
    setModalBlock(block);
  };

  const handleCloseModal = () => {
    setModalBlock(null);
  };

  const handleSaveModal = async (multiplier: number) => {
    if (modalBlock && !isNaN(multiplier) && multiplier >= 0 && multiplier <= 100) {
      const newCustomMultipliers = { ...customMultipliers, [modalBlock.block_name]: multiplier };
      setCustomMultipliers(newCustomMultipliers);

      // Recalculate AAH
      if (fieldInventory?.id) {
        const result = await fieldInventoryApi.getMaiAah(
          fieldInventory.id,
          aahMultipliers.good,
          aahMultipliers.moderate,
          aahMultipliers.weak,
          newCustomMultipliers
        );
        setMaiAahData(result);
      }
    }
    setModalBlock(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setValidationResult(null);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    try {
      setUploading(true);
      setError(null);

      // Step 1: Preview column mapping
      const previewData = await fieldInventoryApi.previewMapping(file);

      // Auto-detect mapping (exclude validation/check columns)
      const autoMapping: Record<string, string> = {};
      previewData.csv_columns.forEach((col: string) => {
        const lowerCol = col.toLowerCase().replace(/[_\s]/g, '');

        // Skip validation/check columns (contain "check", "valid", "status", etc.)
        if (lowerCol.includes('check') || lowerCol.includes('valid') || lowerCol.includes('status')) {
          return;
        }

        // Map common columns
        if ((lowerCol.includes('block') && lowerCol.includes('name')) || lowerCol === 'blockname') {
          autoMapping['block_name'] = col;
        }
        if ((lowerCol.includes('sample') && lowerCol.includes('plot')) || lowerCol.includes('plotnumber')) {
          autoMapping['sample_plot_number'] = col;
        }
        if (lowerCol === 'latitude' || lowerCol === 'lat') autoMapping['latitude'] = col;
        if (lowerCol === 'longitude' || lowerCol === 'lon' || lowerCol === 'long') autoMapping['longitude'] = col;

        // Species columns - exact match to avoid confusion
        if (lowerCol === 'regenspeciesscientific' || lowerCol === 'regenspecies') {
          autoMapping['regen_species_scientific'] = col;
        }
        if (lowerCol === 'saplingspeciesscientific' || lowerCol === 'saplingspecies') {
          autoMapping['sapling_species_scientific'] = col;
        }
        if (lowerCol === 'polespeciesscientific' || lowerCol === 'polespecies') {
          autoMapping['pole_species_scientific'] = col;
        }
        if (lowerCol === 'treespeciesscientific' || lowerCol === 'treespecies') {
          autoMapping['tree_species_scientific'] = col;
        }

        // DBH columns - exact match to avoid picking up *_dbh_check columns
        if (lowerCol === 'regendbh' || lowerCol === 'regendbhcm') {
          autoMapping['regen_dbh_cm'] = col;
        }
        if (lowerCol === 'saplingdbh' || lowerCol === 'saplingdbhcm') {
          autoMapping['sapling_dbh_cm'] = col;
        }
        if (lowerCol === 'poledbh' || lowerCol === 'poledbhcm') {
          autoMapping['pole_dbh_cm'] = col;
        }
        if (lowerCol === 'treedbh' || lowerCol === 'treedbhcm') {
          autoMapping['tree_dbh_cm'] = col;
        }

        // Height columns - exact match to avoid picking up *_height_check columns
        if (lowerCol === 'poleheight' || lowerCol === 'poleheightm' || lowerCol === 'pole_height_m') {
          autoMapping['pole_height_m'] = col;
        }
        if (lowerCol === 'treeheight' || lowerCol === 'treeheightm' || lowerCol === 'tree_height_m') {
          autoMapping['tree_height_m'] = col;
        }

        // Class columns
        if (lowerCol === 'poleclass' || lowerCol === 'pole_class') {
          autoMapping['pole_class'] = col;
        }
        if (lowerCol === 'treeclass' || lowerCol === 'tree_class') {
          autoMapping['tree_class'] = col;
        }

        // Count columns
        if (lowerCol === 'regencount') autoMapping['regen_count'] = col;
        if (lowerCol === 'saplingcount') autoMapping['sapling_count'] = col;
      });

      // Step 2: Upload with mapping
      const result = await fieldInventoryApi.upload(
        file,
        calculationId,
        autoMapping,
        sampleSizes
      );

      setValidationResult(result);

      // If validation passed, proceed to processing
      if (result.summary?.ready_for_processing && result.field_inventory_id) {
        await handleProcess(result.field_inventory_id, file);
      }

    } catch (err: any) {
      console.error('Upload error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to upload file';
      setError(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const handleProcess = async (inventoryId: string, fileToProcess: File) => {
    try {
      setProcessing(true);
      setError(null);

      await fieldInventoryApi.process(inventoryId, fileToProcess);

      // Reload data
      await checkFieldInventory();
      setFile(null);
      setValidationResult(null);

    } catch (err: any) {
      console.error('Processing error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Processing failed';
      setError(errorMessage);
    } finally {
      setProcessing(false);
    }
  };

  const handleDelete = async () => {
    if (!fieldInventory?.id) return;

    if (!confirm('Are you sure you want to delete this field inventory? This action cannot be undone.')) {
      return;
    }

    try {
      setDeleting(true);
      await fieldInventoryApi.delete(fieldInventory.id);
      setFieldInventory(null);
      setSummary(null);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete field inventory');
    } finally {
      setDeleting(false);
    }
  };

  // Validation check
  if (!calculationId) {
    return (
      <div className="p-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-yellow-900 mb-2">Invalid Calculation</h3>
          <p className="text-sm text-yellow-800">No calculation ID provided. Please select a valid calculation.</p>
        </div>
      </div>
    );
  }

  // Component-level error display
  if (componentError) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-red-900 mb-2">Error Loading Field Inventory</h3>
          <p className="text-sm text-red-800 mb-4">{componentError}</p>
          <div className="space-x-2">
            <button
              onClick={() => {
                setComponentError(null);
                setInitialized(false);
                checkFieldInventory();
              }}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
            >
              Retry
            </button>
            <button
              onClick={() => {
                setComponentError(null);
                setFieldInventory(null);
                setInitialized(true);
              }}
              className="px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 text-sm"
            >
              Clear Error & Continue
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (loading && !initialized) {
    return (
      <div className="flex flex-col justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mb-4"></div>
        <p className="text-sm text-gray-600">Loading field inventory data...</p>
      </div>
    );
  }

  // If field inventory exists, show summary
  if (fieldInventory) {
    return (
      <div className="space-y-6">
        {/* Header with Actions */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-1">Field Inventory Data</h3>
              <p className="text-sm text-gray-600">{fieldInventory.uploaded_filename}</p>
              <span className={`inline-block mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                fieldInventory.status === 'completed' ? 'bg-green-100 text-green-800' :
                fieldInventory.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {fieldInventory.status}
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm disabled:bg-gray-400"
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>

        {/* Summary Statistics */}
        {summary && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Overall Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-6">
              <div>
                <p className="text-sm text-gray-500">Total Sample Plots</p>
                <p className="mt-1 text-3xl font-bold text-gray-900">{summary.total_sample_plots || 0}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Total Blocks</p>
                <p className="mt-1 text-3xl font-bold text-gray-900">{summary.total_blocks || 0}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Status</p>
                <p className="mt-1 text-lg font-semibold text-green-600">{summary.status}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Processing Time</p>
                <p className="mt-1 text-lg font-semibold text-gray-900">
                  {summary.processing_time_seconds ? `${Number(summary.processing_time_seconds).toFixed(2)}s` : 'N/A'}
                </p>
              </div>
            </div>

            {/* Forest-Wide Summary */}
            {summary && summary.total_blocks > 0 && (
              <div className="mt-6 mb-6 bg-gradient-to-r from-green-50 to-teal-50 rounded-lg border-2 border-green-400 p-6 shadow-lg">
                <h3 className="text-xl font-bold text-green-800 mb-4 flex items-center">
                  <svg className="w-6 h-6 mr-2" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M3 12v3c0 1.657 3.134 3 7 3s7-1.343 7-3v-3c0 1.657-3.134 3-7 3s-7-1.343-7-3z"/>
                    <path d="M3 7v3c0 1.657 3.134 3 7 3s7-1.343 7-3V7c0 1.657-3.134 3-7 3S3 8.657 3 7z"/>
                    <path d="M17 5c0 1.657-3.134 3-7 3S3 6.657 3 5s3.134-3 7-3 7 1.343 7 3z"/>
                  </svg>
                  Community Forest Summary (Entire Forest)
                </h3>

                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                  {/* Basic Stats */}
                  <div className="bg-white rounded-lg p-4 shadow-md border border-green-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Total Blocks</div>
                    <div className="text-3xl font-bold text-green-700">{summary.total_blocks || 0}</div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-green-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Sample Plots</div>
                    <div className="text-3xl font-bold text-green-700">{summary.total_sample_plots || 0}</div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-blue-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Regeneration/ha</div>
                    <div className="text-2xl font-bold text-blue-700">
                      {summary.total_regeneration_per_ha ? summary.total_regeneration_per_ha.toLocaleString() : 0}
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-blue-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Sapling/ha</div>
                    <div className="text-2xl font-bold text-blue-700">
                      {summary.total_sapling_per_ha ? summary.total_sapling_per_ha.toLocaleString() : 0}
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-blue-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Pole/ha</div>
                    <div className="text-2xl font-bold text-blue-700">
                      {summary.total_pole_per_ha ? summary.total_pole_per_ha.toLocaleString() : 0}
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-blue-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Tree/ha</div>
                    <div className="text-2xl font-bold text-blue-700">
                      {summary.total_tree_per_ha ? summary.total_tree_per_ha.toLocaleString() : 0}
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-amber-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Growing Stock</div>
                    <div className="text-xl font-bold text-amber-700">
                      {summary.total_growing_stock_m3_per_ha ? Number(summary.total_growing_stock_m3_per_ha).toFixed(2) : '0.00'}
                      <span className="text-sm font-normal"> m³/ha</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-purple-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">MAI</div>
                    <div className="text-2xl font-bold text-purple-700">
                      {summary.average_mai_percent ? Number(summary.average_mai_percent).toFixed(1) : '0.0'}%
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-red-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Forest Condition</div>
                    <div className={`text-lg font-bold ${
                      summary.overall_forest_condition === 'Good' ? 'text-green-600' :
                      summary.overall_forest_condition === 'Moderate' ? 'text-yellow-600' :
                      summary.overall_forest_condition === 'Weak' ? 'text-red-600' : 'text-gray-400'
                    }`}>
                      {summary.overall_forest_condition || '-'}
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-teal-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Wood Density</div>
                    <div className="text-xl font-bold text-teal-700">
                      {summary.average_wood_density ? Number(summary.average_wood_density).toFixed(3) : '0.000'}
                      <span className="text-sm font-normal"> t/m³</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-teal-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">AGB</div>
                    <div className="text-xl font-bold text-teal-700">
                      {summary.average_agb_t_per_ha ? Number(summary.average_agb_t_per_ha).toFixed(2) : '0.00'}
                      <span className="text-sm font-normal"> t/ha</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-teal-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">BGB</div>
                    <div className="text-xl font-bold text-teal-700">
                      {summary.average_bgb_t_per_ha ? Number(summary.average_bgb_t_per_ha).toFixed(2) : '0.00'}
                      <span className="text-sm font-normal"> t/ha</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-teal-200">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Total Biomass</div>
                    <div className="text-xl font-bold text-teal-700">
                      {summary.average_total_biomass_t_per_ha ? Number(summary.average_total_biomass_t_per_ha).toFixed(2) : '0.00'}
                      <span className="text-sm font-normal"> t/ha</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-teal-200 col-span-2 md:col-span-1">
                    <div className="text-xs text-gray-500 mb-1 font-medium">Carbon Stock</div>
                    <div className="text-xl font-bold text-teal-700">
                      {summary.average_carbon_stock_tc_per_ha ? Number(summary.average_carbon_stock_tc_per_ha).toFixed(2) : '0.00'}
                      <span className="text-sm font-normal"> tC/ha</span>
                    </div>
                  </div>

                  <div className="bg-white rounded-lg p-4 shadow-md border border-teal-300 col-span-2 md:col-span-1 bg-teal-50">
                    <div className="text-xs text-gray-600 mb-1 font-medium">CO₂ Equivalent</div>
                    <div className="text-2xl font-bold text-teal-800">
                      {summary.average_co2_equivalent_tco2_per_ha ? Number(summary.average_co2_equivalent_tco2_per_ha).toFixed(2) : '0.00'}
                      <span className="text-sm font-normal"> tCO₂/ha</span>
                    </div>
                  </div>

                  {/* MAI and AAH Summary */}
                  {maiAahData && (
                    <>
                      <div className="bg-white rounded-lg p-4 shadow-md border border-purple-200 col-span-2 md:col-span-1">
                        <div className="text-xs text-gray-500 mb-1 font-medium">MAI Total Volume</div>
                        <div className="text-xl font-bold text-purple-700">
                          {maiAahData.mai_overall?.total_mai_m3_per_ha ? Number(maiAahData.mai_overall.total_mai_m3_per_ha).toFixed(2) : '0.00'}
                          <span className="text-sm font-normal"> m³/ha/yr</span>
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Pole: {maiAahData.mai_overall?.pole_per_ha?.toLocaleString() || 0} |
                          Tree: {maiAahData.mai_overall?.tree_per_ha?.toLocaleString() || 0}
                        </div>
                      </div>

                      <div className="bg-white rounded-lg p-4 shadow-md border border-amber-300 col-span-2 md:col-span-1 bg-amber-50">
                        <div className="text-xs text-gray-600 mb-1 font-medium">AAH Total Volume</div>
                        <div className="text-2xl font-bold text-amber-800">
                          {maiAahData.aah_overall?.total_aah_m3_per_ha ? Number(maiAahData.aah_overall.total_aah_m3_per_ha).toFixed(2) : '0.00'}
                          <span className="text-sm font-normal"> m³/ha/yr</span>
                        </div>
                        <div className="text-xs text-gray-600 mt-1">
                          Pole: {maiAahData.aah_overall?.pole_per_ha?.toLocaleString() || 0} |
                          Tree: {maiAahData.aah_overall?.tree_per_ha?.toLocaleString() || 0}
                        </div>
                      </div>

                      <div className="bg-white rounded-lg p-4 shadow-md border border-red-200">
                        <div className="text-xs text-gray-500 mb-1 font-medium">AAH Multiplier</div>
                        <div className="text-2xl font-bold text-red-700">
                          {maiAahData.aah_overall?.aah_multiplier_percent ? Number(maiAahData.aah_overall.aah_multiplier_percent).toFixed(0) : '0'}%
                        </div>
                        <div className={`text-xs mt-1 font-medium ${
                          maiAahData.aah_overall?.forest_condition === 'Good' ? 'text-green-600' :
                          maiAahData.aah_overall?.forest_condition === 'Moderate' ? 'text-yellow-600' :
                          'text-red-600'
                        }`}>
                          {maiAahData.aah_overall?.forest_condition || '-'}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Block-wise Results */}
            {summary?.blocks && Array.isArray(summary.blocks) && summary.blocks.length > 0 && (
              <div className="mt-6">
                <h4 className="text-md font-semibold text-gray-900 mb-3">Block-wise Results</h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Block Name</th>
                        <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Plots</th>
                        <th colSpan={4} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-blue-50">Trees per Hectare</th>
                        <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-green-50">Pole Volume (m³/ha)</th>
                        <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-amber-50">Tree Volume (m³/ha)</th>
                        <th rowSpan={2} className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-purple-50">Growing Stock (Timber m³/ha)</th>
                        <th rowSpan={2} className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-indigo-50">Total Volume (All m³/ha)</th>
                        <th rowSpan={2} className="px-3 py-3 text-right text-xs font-bold italic text-blue-800 uppercase border-r-2 border-blue-400 bg-blue-100 shadow-sm">Total Volume (All m³/ha) (from satellite)</th>
                        <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Regen Cond.</th>
                        <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Forest Cond.</th>
                        <th rowSpan={2} className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">MAI %</th>
                        <th colSpan={6} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-teal-50">Carbon & Biomass (IPCC/REDD+)</th>
                      </tr>
                      <tr>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50">Regen</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50">Sapling</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50">Pole</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50 border-r border-gray-300">Tree</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-green-50">Timber</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-green-50">Firewood</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-green-50 border-r border-gray-300">Total</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-amber-50">Timber</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-amber-50">Firewood</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-amber-50 border-r border-gray-300">Total</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">Wood Density (t/m³)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">AGB (t/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">BGB (t/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">Total Biomass (t/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">Carbon (tC/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">CO₂e (tCO₂/ha)</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {summary.blocks.map((block: any, idx: number) => {
                        const poleTimber = Number(block.pole_timber_m3_per_ha || 0);
                        const poleFirewood = Number(block.pole_firewood_m3_per_ha || 0);
                        const poleTotal = poleTimber + poleFirewood;
                        const treeTimber = Number(block.tree_timber_m3_per_ha || 0);
                        const treeFirewood = Number(block.tree_firewood_m3_per_ha || 0);
                        const treeTotal = treeTimber + treeFirewood;

                        return (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-3 py-3 text-sm font-medium text-gray-900 border-r border-gray-200">{block.block_name}</td>
                            <td className="px-3 py-3 text-sm text-gray-700 border-r border-gray-200">{block.total_sample_plots}</td>

                            {/* Trees per hectare */}
                            <td className="px-2 py-3 text-sm text-right text-gray-700">
                              {Number(block.regeneration_per_ha || 0).toLocaleString()}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-gray-700">
                              {Number(block.sapling_per_ha || 0).toLocaleString()}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-gray-700">
                              {Number(block.pole_per_ha || 0).toLocaleString()}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-gray-700 border-r border-gray-200">
                              {Number(block.tree_per_ha || 0).toLocaleString()}
                            </td>

                            {/* Pole volumes */}
                            <td className="px-2 py-3 text-sm text-right text-green-700 bg-green-50">
                              {poleTimber.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-green-600 bg-green-50">
                              {poleFirewood.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-green-900 font-semibold bg-green-50 border-r border-gray-200">
                              {poleTotal.toFixed(2)}
                            </td>

                            {/* Tree volumes */}
                            <td className="px-2 py-3 text-sm text-right text-amber-700 bg-amber-50">
                              {treeTimber.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-amber-600 bg-amber-50">
                              {treeFirewood.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-amber-900 font-semibold bg-amber-50 border-r border-gray-200">
                              {treeTotal.toFixed(2)}
                            </td>

                            {/* Growing stock (timber only) */}
                            <td className="px-3 py-3 text-sm text-right text-purple-700 font-bold border-r border-gray-200 bg-purple-50">
                              {Number(block.total_growing_stock_m3_per_ha || 0).toFixed(2)}
                            </td>

                            {/* Total volume (timber + firewood) */}
                            <td className="px-3 py-3 text-sm text-right text-indigo-700 font-bold border-r border-gray-200 bg-indigo-50">
                              {(poleTotal + treeTotal).toFixed(2)}
                            </td>

                            {/* Satellite-derived volume */}
                            <td className="px-3 py-3 text-sm text-right text-blue-900 font-bold italic border-r-2 border-blue-400 bg-blue-100 shadow-sm">
                              {block.satellite_volume_m3_per_ha ? Number(block.satellite_volume_m3_per_ha).toFixed(2) : '-'}
                            </td>

                            {/* Conditions */}
                            <td className="px-3 py-3 text-sm border-r border-gray-200">
                              <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                                block.regeneration_condition === 'Good' ? 'bg-green-100 text-green-800' :
                                block.regeneration_condition === 'Moderate' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-red-100 text-red-800'
                              }`}>
                                {block.regeneration_condition || 'N/A'}
                              </span>
                            </td>
                            <td className="px-3 py-3 text-sm border-r border-gray-200">
                              <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                                block.forest_condition === 'Good' ? 'bg-green-100 text-green-800' :
                                block.forest_condition === 'Moderate' ? 'bg-yellow-100 text-yellow-800' :
                                'bg-red-100 text-red-800'
                              }`}>
                                {block.forest_condition || 'N/A'}
                              </span>
                            </td>

                            {/* MAI */}
                            <td className="px-3 py-3 text-sm text-right font-semibold text-gray-900 border-r border-gray-200">
                              {Number(block.mai_percent || 0).toFixed(1)}%
                            </td>

                            {/* Carbon & Biomass (IPCC/REDD+) */}
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{block.weighted_wood_density ? Number(block.weighted_wood_density).toFixed(3) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{block.agb_t_per_ha ? Number(block.agb_t_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{block.bgb_t_per_ha ? Number(block.bgb_t_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{block.total_biomass_t_per_ha ? Number(block.total_biomass_t_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{block.carbon_stock_tc_per_ha ? Number(block.carbon_stock_tc_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50 font-semibold text-teal-900">{block.co2_equivalent_tco2_per_ha ? Number(block.co2_equivalent_tco2_per_ha).toFixed(2) : '-'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Species-wise Breakdown */}
            {speciesBreakdown && speciesBreakdown.species_breakdown && Array.isArray(speciesBreakdown.species_breakdown) && speciesBreakdown.species_breakdown.length > 0 && (
              <div className="mt-8">
                <h4 className="text-md font-semibold text-gray-900 mb-3">Species-wise Breakdown by Block</h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Block Name</th>
                        <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Species (Scientific)</th>
                        <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Local Name</th>
                        <th colSpan={4} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-blue-50">Trees per Hectare</th>
                        <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-green-50">Pole Volume (m³/ha)</th>
                        <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-amber-50">Tree Volume (m³/ha)</th>
                        <th rowSpan={2} className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-purple-50">Growing Stock</th>
                        <th rowSpan={2} className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-indigo-50">Total Volume</th>
                        <th colSpan={6} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-teal-50">Carbon & Biomass (IPCC/REDD+)</th>
                      </tr>
                      <tr>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50">Regen</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50">Sapling</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50">Pole</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-blue-50 border-r border-gray-300">Tree</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-green-50">Timber</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-green-50">Firewood</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-green-50 border-r border-gray-300">Total</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-amber-50">Timber</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-amber-50">Firewood</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-amber-50 border-r border-gray-300">Total</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">Wood Density (t/m³)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">AGB (t/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">BGB (t/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">Total Biomass (t/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">Carbon (tC/ha)</th>
                        <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase bg-teal-50">CO₂e (tCO₂/ha)</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {speciesBreakdown.species_breakdown.map((species: any, idx: number) => {
                        const poleTimber = Number(species.pole_timber_m3_per_ha || 0);
                        const poleFirewood = Number(species.pole_firewood_m3_per_ha || 0);
                        const poleTotal = poleTimber + poleFirewood;
                        const treeTimber = Number(species.tree_timber_m3_per_ha || 0);
                        const treeFirewood = Number(species.tree_firewood_m3_per_ha || 0);
                        const treeTotal = treeTimber + treeFirewood;

                        return (
                          <tr key={idx} className="hover:bg-gray-50">
                            <td className="px-3 py-3 text-sm text-gray-700 border-r border-gray-200">{species.block_name}</td>
                            <td className="px-3 py-3 text-sm font-medium text-gray-900 border-r border-gray-200 italic">{species.species_scientific}</td>
                            <td className="px-3 py-3 text-sm text-gray-700 border-r border-gray-200">{species.species_local || '-'}</td>

                            {/* Trees per hectare */}
                            <td className="px-2 py-3 text-sm text-right text-gray-700">
                              {Number(species.regeneration_per_ha || 0).toLocaleString()}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-gray-700">
                              {Number(species.sapling_per_ha || 0).toLocaleString()}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-gray-700">
                              {Number(species.pole_per_ha || 0).toLocaleString()}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-gray-700 border-r border-gray-200">
                              {Number(species.tree_per_ha || 0).toLocaleString()}
                            </td>

                            {/* Pole volumes */}
                            <td className="px-2 py-3 text-sm text-right text-green-700 bg-green-50">
                              {poleTimber.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-green-600 bg-green-50">
                              {poleFirewood.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-green-900 font-semibold bg-green-50 border-r border-gray-200">
                              {poleTotal.toFixed(2)}
                            </td>

                            {/* Tree volumes */}
                            <td className="px-2 py-3 text-sm text-right text-amber-700 bg-amber-50">
                              {treeTimber.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-amber-600 bg-amber-50">
                              {treeFirewood.toFixed(2)}
                            </td>
                            <td className="px-2 py-3 text-sm text-right text-amber-900 font-semibold bg-amber-50 border-r border-gray-200">
                              {treeTotal.toFixed(2)}
                            </td>

                            {/* Growing stock and total volume */}
                            <td className="px-3 py-3 text-sm text-right text-purple-700 font-bold border-r border-gray-200 bg-purple-50">
                              {Number(species.growing_stock_m3_per_ha || 0).toFixed(2)}
                            </td>
                            <td className="px-3 py-3 text-sm text-right text-indigo-700 font-bold border-r border-gray-200 bg-indigo-50">
                              {Number(species.total_volume_m3_per_ha || 0).toFixed(2)}
                            </td>

                            {/* Carbon & Biomass (IPCC/REDD+) */}
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{species.wood_density_t_m3 ? Number(species.wood_density_t_m3).toFixed(3) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{species.agb_t_per_ha ? Number(species.agb_t_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{species.bgb_t_per_ha ? Number(species.bgb_t_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{species.total_biomass_t_per_ha ? Number(species.total_biomass_t_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50">{species.carbon_stock_tc_per_ha ? Number(species.carbon_stock_tc_per_ha).toFixed(2) : '-'}</td>
                            <td className="px-2 py-3 text-sm text-right whitespace-nowrap bg-teal-50 font-semibold text-teal-900">{species.co2_equivalent_tco2_per_ha ? Number(species.co2_equivalent_tco2_per_ha).toFixed(2) : '-'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* MAI and AAH Tables */}
            {maiAahData && (
              <>
                {/* AAH Multiplier Controls */}
                <div className="mt-8 bg-yellow-50 rounded-lg border border-yellow-200 p-4">
                  <h4 className="text-sm font-semibold text-gray-900 mb-3">AAH Multiplier Settings (%)</h4>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Good Forest</label>
                      <input
                        type="number"
                        value={aahMultipliers.good}
                        onChange={(e) => setAahMultipliers({...aahMultipliers, good: Number(e.target.value)})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        min="0"
                        max="100"
                        step="5"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Moderate Forest</label>
                      <input
                        type="number"
                        value={aahMultipliers.moderate}
                        onChange={(e) => setAahMultipliers({...aahMultipliers, moderate: Number(e.target.value)})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        min="0"
                        max="100"
                        step="5"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-600 mb-1">Weak Forest</label>
                      <input
                        type="number"
                        value={aahMultipliers.weak}
                        onChange={(e) => setAahMultipliers({...aahMultipliers, weak: Number(e.target.value)})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md"
                        min="0"
                        max="100"
                        step="5"
                      />
                    </div>
                  </div>
                  <button
                    onClick={async () => {
                      if (fieldInventory?.id) {
                        const result = await fieldInventoryApi.getMaiAah(
                          fieldInventory.id,
                          aahMultipliers.good,
                          aahMultipliers.moderate,
                          aahMultipliers.weak,
                          customMultipliers
                        );
                        setMaiAahData(result);
                      }
                    }}
                    className="mt-3 px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700 text-sm"
                  >
                    Recalculate AAH
                  </button>
                  <button
                    onClick={() => {
                      setCustomMultipliers({});
                      // Recalculate will happen automatically via useEffect
                      if (fieldInventory?.id) {
                        fieldInventoryApi.getMaiAah(
                          fieldInventory.id,
                          aahMultipliers.good,
                          aahMultipliers.moderate,
                          aahMultipliers.weak,
                          {}
                        ).then(setMaiAahData);
                      }
                    }}
                    className="mt-3 ml-2 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 text-sm"
                  >
                    Reset All to Defaults
                  </button>
                </div>

                {/* MAI Table */}
                <div className="mt-8">
                  <h4 className="text-md font-semibold text-gray-900 mb-3">MAI Table (Mean Annual Increment - m³/ha/year)</h4>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead className="bg-purple-50">
                        <tr>
                          <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Block Name</th>
                          <th colSpan={2} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Trees per Hectare</th>
                          <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Pole Volume (MAI)</th>
                          <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Tree Volume (MAI)</th>
                          <th rowSpan={2} className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase bg-purple-100">Total MAI</th>
                        </tr>
                        <tr>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Pole</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Tree</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Timber</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Firewood</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Total</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Timber</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Firewood</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Total</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {maiAahData?.mai_blocks && Array.isArray(maiAahData.mai_blocks) && maiAahData.mai_blocks.map((mai: any, index: number) => (
                          <tr key={index} className="hover:bg-gray-50">
                            <td className="px-3 py-3 text-sm font-medium text-gray-900 border-r border-gray-200">{mai.block_name}</td>
                            <td className="px-2 py-3 text-sm text-right">{mai.pole_per_ha?.toLocaleString() || 0}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{mai.tree_per_ha?.toLocaleString() || 0}</td>
                            <td className="px-2 py-3 text-sm text-right">{mai.pole_timber_m3_per_ha.toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{mai.pole_firewood_m3_per_ha.toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{mai.pole_total_m3_per_ha.toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{mai.tree_timber_m3_per_ha.toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{mai.tree_firewood_m3_per_ha.toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{mai.tree_total_m3_per_ha.toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right font-bold text-purple-700 bg-purple-50">{mai.total_mai_m3_per_ha.toFixed(2)}</td>
                          </tr>
                        ))}
                        {/* Overall Row */}
                        {maiAahData?.mai_overall && (
                          <tr className="bg-purple-100 font-bold">
                            <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">Overall Forest</td>
                            <td className="px-2 py-3 text-sm text-right">{maiAahData.mai_overall.pole_per_ha?.toLocaleString() || 0}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{maiAahData.mai_overall.tree_per_ha?.toLocaleString() || 0}</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.mai_overall.pole_timber_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.mai_overall.pole_firewood_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{Number(maiAahData.mai_overall.pole_total_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.mai_overall.tree_timber_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.mai_overall.tree_firewood_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{Number(maiAahData.mai_overall.tree_total_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right font-bold text-purple-900">{Number(maiAahData.mai_overall.total_mai_m3_per_ha || 0).toFixed(2)}</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* AAH Table */}
                <div className="mt-8">
                  <h4 className="text-md font-semibold text-gray-900 mb-3">AAH Table (Annual Allowable Harvest - m³/ha/year)</h4>
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead className="bg-amber-50">
                        <tr>
                          <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Block Name</th>
                          <th colSpan={2} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Trees per Hectare</th>
                          <th rowSpan={2} className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Condition</th>
                          <th rowSpan={2} className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Multiplier</th>
                          <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Pole Volume (AAH)</th>
                          <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Tree Volume (AAH)</th>
                          <th rowSpan={2} className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase bg-amber-100">Total AAH</th>
                        </tr>
                        <tr>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Pole</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Tree</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Timber</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Firewood</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Total</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Timber</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Firewood</th>
                          <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Total</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {maiAahData?.aah_blocks && Array.isArray(maiAahData.aah_blocks) && maiAahData.aah_blocks.map((aah: any, index: number) => {
                          const block = summary?.blocks?.find((b: any) => b.block_name === aah.block_name);
                          return (
                            <tr key={index} className="hover:bg-gray-50">
                              <td className="px-3 py-3 text-sm font-medium text-gray-900 border-r border-gray-200">{aah.block_name}</td>
                              <td className="px-2 py-3 text-sm text-right">{aah.pole_per_ha?.toLocaleString() || 0}</td>
                              <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{aah.tree_per_ha?.toLocaleString() || 0}</td>
                              <td className={`px-3 py-3 text-sm text-center font-semibold border-r border-gray-200 ${
                                aah.forest_condition === 'Good' ? 'text-green-600' :
                                aah.forest_condition === 'Moderate' ? 'text-yellow-600' :
                                'text-red-600'
                              }`}>{aah.forest_condition}</td>
                              <td className="px-3 py-3 text-sm text-center border-r border-gray-200">
                                <div className="flex items-center justify-center gap-1">
                                  {editingBlock === aah.block_name ? (
                                    // Inline editing mode
                                    <div className="flex items-center gap-1">
                                      <input
                                        type="number"
                                        value={editingValue}
                                        onChange={(e) => setEditingValue(e.target.value)}
                                        onBlur={() => handleSaveInlineEdit(aah.block_name)}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter') handleSaveInlineEdit(aah.block_name);
                                          if (e.key === 'Escape') handleCancelInlineEdit();
                                        }}
                                        autoFocus
                                        className="w-16 px-2 py-1 border border-blue-500 rounded text-center focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        min="0"
                                        max="100"
                                        step="1"
                                      />
                                      <span className="text-xs">%</span>
                                    </div>
                                  ) : (
                                    // Display mode
                                    <>
                                      <span
                                        onClick={() => handleStartInlineEdit(aah.block_name, aah.aah_multiplier_percent)}
                                        className={`cursor-pointer hover:bg-gray-100 px-2 py-1 rounded ${
                                          aah.is_custom ? 'text-orange-600 font-semibold' : 'text-gray-900'
                                        }`}
                                        title={aah.is_custom ? `Custom (Default: ${aah.default_multiplier_percent}%)` : 'Click to edit'}
                                      >
                                        {aah.aah_multiplier_percent.toFixed(0)}%
                                      </span>
                                      {aah.is_custom && (
                                        <span className="text-orange-500 text-xs font-bold" title="Custom multiplier">⚠️</span>
                                      )}
                                      <button
                                        onClick={() => handleOpenModal(aah)}
                                        className="text-blue-500 hover:text-blue-700 text-xs"
                                        title="Open detailed editor"
                                      >
                                        ℹ️
                                      </button>
                                    </>
                                  )}
                                </div>
                              </td>
                              <td className="px-2 py-3 text-sm text-right">{aah.pole_timber_m3_per_ha.toFixed(2)}</td>
                              <td className="px-2 py-3 text-sm text-right">{aah.pole_firewood_m3_per_ha.toFixed(2)}</td>
                              <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{aah.pole_total_m3_per_ha.toFixed(2)}</td>
                              <td className="px-2 py-3 text-sm text-right">{aah.tree_timber_m3_per_ha.toFixed(2)}</td>
                              <td className="px-2 py-3 text-sm text-right">{aah.tree_firewood_m3_per_ha.toFixed(2)}</td>
                              <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{aah.tree_total_m3_per_ha.toFixed(2)}</td>
                              <td className="px-2 py-3 text-sm text-right font-bold text-amber-700 bg-amber-50">{aah.total_aah_m3_per_ha.toFixed(2)}</td>
                            </tr>
                          );
                        })}
                        {/* Overall Row */}
                        {maiAahData?.aah_overall && (
                          <tr className="bg-amber-100 font-bold">
                            <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">Overall Forest</td>
                            <td className="px-2 py-3 text-sm text-right">{maiAahData.aah_overall.pole_per_ha?.toLocaleString() || 0}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{maiAahData.aah_overall.tree_per_ha?.toLocaleString() || 0}</td>
                            <td className={`px-3 py-3 text-sm text-center font-bold border-r border-gray-200 ${
                              maiAahData.aah_overall.forest_condition === 'Good' ? 'text-green-700' :
                              maiAahData.aah_overall.forest_condition === 'Moderate' ? 'text-yellow-700' :
                              'text-red-700'
                            }`}>{maiAahData.aah_overall.forest_condition || 'N/A'}</td>
                            <td className="px-3 py-3 text-sm text-center border-r border-gray-200">{Number(maiAahData.aah_overall.aah_multiplier_percent || 0).toFixed(0)}%</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.aah_overall.pole_timber_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.aah_overall.pole_firewood_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{Number(maiAahData.aah_overall.pole_total_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.aah_overall.tree_timber_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right">{Number(maiAahData.aah_overall.tree_firewood_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{Number(maiAahData.aah_overall.tree_total_m3_per_ha || 0).toFixed(2)}</td>
                            <td className="px-2 py-3 text-sm text-right font-bold text-amber-900">{Number(maiAahData.aah_overall.total_aah_m3_per_ha || 0).toFixed(2)}</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* AAH Multiplier Editing Modal */}
        {modalBlock && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
              <h3 className="text-lg font-bold text-gray-900 mb-4">
                Edit AAH Multiplier - {modalBlock.block_name}
              </h3>

              <div className="space-y-4">
                {/* Forest Condition */}
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-sm text-gray-600">Forest Condition</div>
                  <div className={`text-xl font-bold ${
                    modalBlock.forest_condition === 'Good' ? 'text-green-600' :
                    modalBlock.forest_condition === 'Moderate' ? 'text-yellow-600' :
                    'text-red-600'
                  }`}>
                    {modalBlock.forest_condition}
                  </div>
                </div>

                {/* Default Multiplier */}
                <div className="bg-blue-50 rounded-lg p-3">
                  <div className="text-sm text-gray-600">Default Multiplier (System)</div>
                  <div className="text-xl font-bold text-blue-700">
                    {modalBlock.default_multiplier_percent}%
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    Based on {modalBlock.forest_condition} condition
                  </div>
                </div>

                {/* Current Multiplier */}
                <div className={`rounded-lg p-3 ${modalBlock.is_custom ? 'bg-orange-50' : 'bg-gray-50'}`}>
                  <div className="text-sm text-gray-600">Current Multiplier</div>
                  <div className={`text-xl font-bold ${modalBlock.is_custom ? 'text-orange-600' : 'text-gray-700'}`}>
                    {modalBlock.aah_multiplier_percent.toFixed(0)}%
                    {modalBlock.is_custom && <span className="text-sm ml-2">(Custom)</span>}
                  </div>
                </div>

                {/* Custom Multiplier Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Set Custom Multiplier (%)
                  </label>
                  <input
                    type="number"
                    defaultValue={modalBlock.aah_multiplier_percent.toFixed(0)}
                    onChange={(e) => {
                      const input = e.target as HTMLInputElement;
                      input.dataset.value = e.target.value;
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="0"
                    max="100"
                    step="1"
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    ℹ️ Recommended range: 40-80%
                  </div>
                </div>

                {/* Guidance */}
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                  <div className="text-xs font-semibold text-yellow-800 mb-1">Management Guidelines</div>
                  <ul className="text-xs text-yellow-700 space-y-1">
                    <li>• Good forests: Higher multiplier (70-80%)</li>
                    <li>• Moderate forests: Medium multiplier (55-65%)</li>
                    <li>• Weak forests: Lower multiplier (35-45%)</li>
                    <li>• Consider local factors: accessibility, regeneration, biodiversity</li>
                  </ul>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 mt-6">
                <button
                  onClick={() => {
                    // Reset to default
                    handleSaveModal(modalBlock.default_multiplier_percent);
                  }}
                  className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
                >
                  Use Default
                </button>
                <button
                  onClick={handleCloseModal}
                  className="px-4 py-2 text-sm bg-gray-500 text-white rounded-md hover:bg-gray-600"
                >
                  Cancel
                </button>
                <button
                  onClick={(e) => {
                    const input = (e.target as HTMLElement).closest('.bg-white')?.querySelector('input[type="number"]') as HTMLInputElement;
                    const value = parseFloat(input?.value || input?.dataset.value || '0');
                    handleSaveModal(value);
                  }}
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700"
                >
                  Apply
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Upload interface
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Upload Field Inventory Data</h3>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {validationResult && (
          <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
            <h4 className="text-sm font-semibold text-blue-900 mb-2">Validation Results</h4>
            <div className="space-y-1 text-sm text-blue-800">
              <p>Total rows: {validationResult.summary?.total_rows || 0}</p>
              <p>Ready for processing: {validationResult.summary?.ready_for_processing ? 'Yes' : 'No'}</p>
              {validationResult.errors && validationResult.errors.length > 0 && (
                <div className="mt-2">
                  <p className="font-semibold text-red-700">Errors:</p>
                  <ul className="list-disc list-inside">
                    {validationResult.errors.map((err: any, idx: number) => (
                      <li key={idx} className="text-red-700">{err.message || err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Sample Plot Sizes Configuration */}
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-gray-700 mb-3">Sample Plot Sizes (in square meters)</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Regeneration (m²)</label>
              <input
                type="number"
                value={sampleSizes.regeneration_area_sqm}
                onChange={(e) => setSampleSizes({ ...sampleSizes, regeneration_area_sqm: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                step="0.1"
              />
              <p className="text-xs text-gray-500 mt-1">Radius: {Math.sqrt(sampleSizes.regeneration_area_sqm / Math.PI).toFixed(2)}m</p>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Sapling (m²)</label>
              <input
                type="number"
                value={sampleSizes.sapling_area_sqm}
                onChange={(e) => setSampleSizes({ ...sampleSizes, sapling_area_sqm: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                step="0.1"
              />
              <p className="text-xs text-gray-500 mt-1">Radius: {Math.sqrt(sampleSizes.sapling_area_sqm / Math.PI).toFixed(2)}m</p>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Pole (m²)</label>
              <input
                type="number"
                value={sampleSizes.pole_area_sqm}
                onChange={(e) => setSampleSizes({ ...sampleSizes, pole_area_sqm: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                step="0.1"
              />
              <p className="text-xs text-gray-500 mt-1">Radius: {Math.sqrt(sampleSizes.pole_area_sqm / Math.PI).toFixed(2)}m</p>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Tree (m²)</label>
              <input
                type="number"
                value={sampleSizes.tree_area_sqm}
                onChange={(e) => setSampleSizes({ ...sampleSizes, tree_area_sqm: parseFloat(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                step="0.1"
              />
              <p className="text-xs text-gray-500 mt-1">Radius: {Math.sqrt(sampleSizes.tree_area_sqm / Math.PI).toFixed(2)}m</p>
            </div>
          </div>
        </div>

        {/* File Upload */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              CSV File (22 columns)
            </label>
            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="block w-full text-sm text-gray-500
                file:mr-4 file:py-2 file:px-4
                file:rounded-md file:border-0
                file:text-sm file:font-semibold
                file:bg-green-50 file:text-green-700
                hover:file:bg-green-100"
            />
          </div>

          <button
            onClick={handleUpload}
            disabled={!file || uploading || processing}
            className="w-full px-4 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 font-semibold"
          >
            {uploading ? 'Uploading...' : processing ? 'Processing...' : 'Upload & Process'}
          </button>
        </div>

        {/* Information */}
        <div className="mt-6 p-4 bg-gray-50 rounded-md">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Required CSV Columns:</h4>
          <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
            <li>Block Name, Sample Plot Number</li>
            <li>Latitude, Longitude</li>
            <li>4 Species Columns: Regen, Sapling, Pole, Tree</li>
            <li>4 DBH Columns: Regen (&lt;4cm), Sapling (4-10cm), Pole (10-30cm), Tree (≥30cm)</li>
            <li>2 Height Columns: Pole, Tree (optional - will be estimated if missing)</li>
            <li>2 Count Columns: Regen Count, Sapling Count</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
