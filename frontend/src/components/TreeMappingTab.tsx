import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { inventoryApi } from '../services/api';
import { compartmentApi } from '../services/api';
import { CorrectionPreviewDialog } from './CorrectionPreviewDialog';
import ColumnMappingPreview from './ColumnMappingPreview';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { MapContainer, GeoJSON, useMap, CircleMarker, Popup } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import '@geoman-io/leaflet-geoman-free';
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css';
import BaseMapSelector from './MapCreation/BaseMapSelector';

interface TreeMappingTabProps {
  calculationId: string;
}

const COLORS = ['#22c55e', '#f97316', '#eab308', '#3b82f6', '#8b5cf6', '#ec4899', '#14b8a6'];

export function TreeMappingTab({ calculationId }: TreeMappingTabProps) {
  const navigate = useNavigate();
  const [treeMapping, setTreeMapping] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [trees, setTrees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [gridSpacing, setGridSpacing] = useState(20);
  const [projectionEpsg, setProjectionEpsg] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Column mapping state
  const [showColumnMapping, setShowColumnMapping] = useState(false);
  const [columnMappingData, setColumnMappingData] = useState<any>(null);

  // Boundary correction state
  const [showCorrectionDialog, setShowCorrectionDialog] = useState(false);
  const [correctionData, setCorrectionData] = useState<any>(null);
  const [applyingCorrections, setApplyingCorrections] = useState(false);

  // Map state
  const [showMap, setShowMap] = useState(false);
  const [gridCells, setGridCells] = useState<any[]>([]);
  const [gridMetadata, setGridMetadata] = useState<any>(null);

  // Check if tree mapping exists for this calculation
  useEffect(() => {
    checkTreeMapping();
  }, [calculationId]);

  const checkTreeMapping = async () => {
    try {
      setLoading(true);
      const mapping = await inventoryApi.getTreeMappingByCalculation(calculationId);
      setTreeMapping(mapping);

      // Load summary and tree preview if mapping exists
      if (mapping?.id) {
        loadTreeData(mapping.id);
      }
    } catch (err: any) {
      // 404 means no tree mapping exists yet
      if (err.response?.status === 404) {
        setTreeMapping(null);
        setSummary(null);
        setTrees([]);
      } else {
        console.error('Error checking tree mapping:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  const loadTreeData = async (mappingId: string) => {
    try {
      setLoadingData(true);
      
      // Load all trees in multiple pages if needed
      let allTrees: any[] = [];
      let page = 1;
      let hasMore = true;
      
      while (hasMore) {
        const treesData = await inventoryApi.listInventoryTrees(mappingId, { 
          page: page, 
          page_size: 100 
        }).catch(() => ({ trees: [], has_more: false }));
        
        if (treesData.trees && treesData.trees.length > 0) {
          allTrees = [...allTrees, ...treesData.trees];
          hasMore = treesData.has_more || false;
          page++;
        } else {
          hasMore = false;
        }
      }
      
      const summaryData = await inventoryApi.getInventorySummary(mappingId).catch(() => null);
      
      setSummary(summaryData);
      setTrees(allTrees);
      console.log('Loaded trees:', allTrees.length, 'trees');
      if (allTrees.length > 0) {
        console.log('Sample tree:', JSON.stringify(allTrees[0], null, 2));
      }
    } catch (err: any) {
      console.error('Error loading tree data:', err);
    } finally {
      setLoadingData(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setValidationResult(null);
      setError(null);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await inventoryApi.downloadTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'TreeMapping_Template.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError('Failed to download template');
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
      const previewData = await inventoryApi.previewColumnMapping(file);
      setColumnMappingData(previewData);
      setShowColumnMapping(true);
      setUploading(false);

    } catch (err: any) {
      console.error('Preview error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to preview file';
      setError(errorMessage);
      setUploading(false);
    }
  };

  const handleConfirmMapping = async (
    mapping: Record<string, string>,
    savePreference: boolean
  ) => {
    if (!file) return;

    try {
      setUploading(true);
      setShowColumnMapping(false);
      setError(null);

      const epsg = projectionEpsg ? parseInt(projectionEpsg) : undefined;

      // Step 2: Confirm mapping and upload
      const result = await inventoryApi.confirmColumnMapping(
        file,
        mapping,
        savePreference,
        gridSpacing,
        calculationId,
        epsg
      );
      setValidationResult(result);

      // DEBUG: Log validation response
      console.log('[TREE MAPPING] Validation result:', result);
      console.log('[TREE MAPPING] ready_for_processing:', result.summary?.ready_for_processing);
      console.log('[TREE MAPPING] inventory_id:', result.inventory_id);
      console.log('[TREE MAPPING] boundary_check:', result.boundary_check);
      console.log('[TREE MAPPING] ERRORS:', result.errors);
      console.log('[TREE MAPPING] WARNINGS:', result.warnings);
      console.log('[TREE MAPPING] Full summary:', result.summary);

      // Step 2: Check if boundary corrections are needed
      if (result.summary?.ready_for_processing && result.inventory_id) {
        console.log('[TREE MAPPING] Condition met - proceeding with processing check');
        // Check for boundary issues
        if (result.boundary_check?.needs_correction) {
          console.log('[TREE MAPPING] Boundary corrections needed - showing dialog');
          // Show correction dialog
          setCorrectionData({
            inventoryId: result.inventory_id,
            boundaryCheck: result.boundary_check,
            result: result
          });
          setShowCorrectionDialog(true);
          setUploading(false);
          return;
        }

        console.log('[TREE MAPPING] No boundary corrections needed - proceeding with processing');
        // No corrections needed - proceed with normal processing
        // Update status to show processing
        setValidationResult({
          ...result,
          summary: {
            ...result.summary,
            status: 'Processing tree mapping (calculating volumes)...'
          }
        });

        try {
          console.log('[TREE MAPPING] Calling processInventory API...');
          // Process the inventory (re-upload file)
          await inventoryApi.processInventory(result.inventory_id, file);
          console.log('[TREE MAPPING] Processing completed successfully');

          // Reload tree mapping data
          await checkTreeMapping();
          setFile(null);
          setValidationResult(null);
        } catch (processErr: any) {
          console.error('[TREE MAPPING] Processing error:', processErr);
          console.error('Error response:', processErr.response);
          console.error('Error data:', processErr.response?.data);

          const errorMessage = processErr.response?.data?.detail || processErr.message || 'Processing failed';
          setError(errorMessage);
          setValidationResult(null); // Clear validation result to show error
        }
      } else {
        // CRITICAL FIX: If not ready for processing (e.g., boundary error),
        // stop loading immediately so user can see the error
        console.log('[TREE MAPPING] Condition NOT met - not calling processInventory');
        console.log('[TREE MAPPING] ready_for_processing:', result.summary?.ready_for_processing);
        console.log('[TREE MAPPING] inventory_id:', result.inventory_id);
        setUploading(false);
      }
    } catch (err: any) {
      console.error('Upload error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to upload file';
      setError(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!treeMapping?.id) return;

    if (!confirm('Are you sure you want to delete this tree mapping? This action cannot be undone.')) {
      return;
    }

    try {
      setDeleting(true);
      await inventoryApi.deleteInventory(treeMapping.id);
      setTreeMapping(null);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete tree mapping');
    } finally {
      setDeleting(false);
    }
  };

  const handleAcceptCorrections = async () => {
    if (!correctionData || !file) return;

    try {
      setApplyingCorrections(true);
      setError(null);

      // Apply corrections
      console.log('Applying corrections for inventory:', correctionData.inventoryId);
      const result = await inventoryApi.acceptCorrections(correctionData.inventoryId, file);
      console.log('Corrections applied successfully:', result);

      // Close dialog
      setShowCorrectionDialog(false);
      setCorrectionData(null);

      // Show success message
      setValidationResult({
        ...correctionData.result,
        summary: {
          ...correctionData.result.summary,
          status: `Corrections applied (${result.corrections_count} trees). Processing tree mapping...`
        }
      });

      // Process the inventory with corrected data
      await inventoryApi.processInventory(correctionData.inventoryId, file);

      // Reload tree mapping data
      await checkTreeMapping();
      setFile(null);
      setValidationResult(null);

    } catch (err: any) {
      console.error('Correction error:', err);
      console.error('Error response:', err.response);

      // Extract detailed error message
      let errorMessage = 'Failed to apply corrections';
      if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail;
      } else if (err.message) {
        errorMessage = err.message;
      }

      setError(errorMessage);
      setShowCorrectionDialog(false);
    } finally {
      setApplyingCorrections(false);
    }
  };

  const handleCancelCorrections = () => {
    setShowCorrectionDialog(false);
    setCorrectionData(null);
    setFile(null);
    setValidationResult(null);
    setError('Upload cancelled. Please fix the data manually or try again.');
  };

  const handleCancelMapping = () => {
    setShowColumnMapping(false);
    setColumnMappingData(null);
  };

  const handleViewDetails = () => {
    if (treeMapping?.id) {
      navigate(`/inventory/${treeMapping.id}`);
    }
  };

  const handleExport = async (format: 'csv' | 'geojson' | 'excel') => {
    if (!treeMapping?.id) return;

    try {
      const { blob, filename } = await inventoryApi.exportInventory(treeMapping.id, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      setError(`Failed to export ${format.toUpperCase()}`);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
      </div>
    );
  }

  // If tree mapping exists, show summary and delete option
  if (treeMapping) {
    return (
      <div className="space-y-6">
        {/* Header with Actions */}
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-1">Tree Mapping Data</h3>
              <p className="text-sm text-gray-600">{treeMapping.uploaded_filename}</p>
              <span className={`inline-block mt-2 px-3 py-1 rounded-full text-sm font-semibold ${
                treeMapping.status === 'completed' ? 'bg-green-100 text-green-800' :
                treeMapping.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {treeMapping.status}
              </span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleExport('csv')}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
              >
                Export CSV
              </button>
              <button
                onClick={() => handleExport('excel')}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
              >
                Export Excel
              </button>
              <button
                onClick={() => handleExport('geojson')}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
              >
                Export GeoJSON
              </button>
              <button
                onClick={() => setShowMap(!showMap)}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
              >
                {showMap ? 'Hide Map' : 'View Map'}
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm disabled:bg-gray-400"
              >
                Export GeoJSON
              </button>
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

        {/* Map Section - Before Summary */}
        {showMap && treeMapping && (
          <TreeMappingMap 
            inventoryId={treeMapping.id}
            trees={trees}
            calculationId={calculationId}
          />
        )}

        {/* Summary Statistics */}
        {summary && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Summary Statistics</h3>
            
            {/* Tree Categories - Only show if count > 0 */}
            {(summary.mother_trees_count > 0 || summary.felling_trees_count > 0 || summary.pole_count > 0 || summary.seedling_count > 0) && (
              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Tree Categories</h4>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div>
                    <p className="text-sm text-gray-500">Total Trees</p>
                    <p className="mt-1 text-2xl font-bold text-gray-900">{summary.total_trees || 0}</p>
                  </div>
                  {summary.mother_trees_count > 0 && (
                    <div>
                      <p className="text-sm text-gray-500">Mother Trees</p>
                      <p className="mt-1 text-2xl font-bold text-green-600">{summary.mother_trees_count}</p>
                    </div>
                  )}
                  {summary.felling_trees_count > 0 && (
                    <div>
                      <p className="text-sm text-gray-500">Felling Trees</p>
                      <p className="mt-1 text-2xl font-bold text-orange-600">{summary.felling_trees_count}</p>
                    </div>
                  )}
                  {summary.pole_count > 0 && (
                    <div>
                      <p className="text-sm text-gray-500">Poles</p>
                      <p className="mt-1 text-2xl font-bold text-yellow-600">{summary.pole_count}</p>
                    </div>
                  )}
                  {summary.seedling_count > 0 && (
                    <div>
                      <p className="text-sm text-gray-500">Seedlings</p>
                      <p className="mt-1 text-2xl font-bold text-blue-600">{summary.seedling_count}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Stand Types - Only show if any stand type has count > 0 */}
            {(summary.regeneration_count > 0 || summary.sapling_count > 0 || summary.stand_pole_count > 0 || summary.tree_count > 0) && (
              <div className="mb-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Stand Types</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {summary.regeneration_count > 0 && (
                    <div className="p-3 bg-purple-50 rounded-md">
                      <p className="text-sm text-gray-600">Regeneration</p>
                      <p className="mt-1 text-xl font-bold text-purple-700">{summary.regeneration_count}</p>
                    </div>
                  )}
                  {summary.sapling_count > 0 && (
                    <div className="p-3 bg-blue-50 rounded-md">
                      <p className="text-sm text-gray-600">Sapling</p>
                      <p className="mt-1 text-xl font-bold text-blue-700">{summary.sapling_count}</p>
                    </div>
                  )}
                  {summary.stand_pole_count > 0 && (
                    <div className="p-3 bg-yellow-50 rounded-md">
                      <p className="text-sm text-gray-600">Pole</p>
                      <p className="mt-1 text-xl font-bold text-yellow-700">{summary.stand_pole_count}</p>
                    </div>
                  )}
                  {summary.tree_count > 0 && (
                    <div className="p-3 bg-green-50 rounded-md">
                      <p className="text-sm text-gray-600">Tree</p>
                      <p className="mt-1 text-xl font-bold text-green-700">{summary.tree_count}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Volume Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 bg-gray-50 rounded-md">
                <p className="text-sm text-gray-500">Total Volume</p>
                <p className="mt-1 text-xl font-bold text-gray-900">{(summary.total_volume_m3 || 0).toFixed(2)} m³</p>
              </div>
              {summary.timber_volume_m3 > 0 && (
                <div className="p-4 bg-amber-50 rounded-md">
                  <p className="text-sm text-gray-500">Timber Volume</p>
                  <p className="mt-1 text-xl font-bold text-amber-700">{(summary.timber_volume_m3 || 0).toFixed(2)} m³</p>
                  <p className="text-xs text-gray-500 mt-1">{(summary.timber_volume_cft || 0).toFixed(2)} cft</p>
                </div>
              )}
              {summary.total_firewood_m3 > 0 && (
                <div className="p-4 bg-orange-50 rounded-md">
                  <p className="text-sm text-gray-500">Firewood</p>
                  <p className="mt-1 text-xl font-bold text-orange-700">{(summary.total_firewood_m3 || 0).toFixed(2)} m³</p>
                  <p className="text-xs text-gray-500 mt-1">{(summary.total_firewood_chatta || 0).toFixed(0)} chatta</p>
                </div>
              )}
              <div className="p-4 bg-gray-50 rounded-md">
                <p className="text-sm text-gray-500">Net Volume</p>
                <p className="mt-1 text-xl font-bold text-gray-900">{(summary.total_net_volume_m3 || 0).toFixed(2)} m³</p>
                <p className="text-xs text-gray-500 mt-1">{(summary.total_net_volume_cft || 0).toFixed(2)} cft</p>
              </div>
            </div>

            {/* Volume by Category - Only show if values > 0 */}
            {(summary.felling_volume_m3 > 0 || summary.mother_volume_m3 > 0 || summary.pole_volume_m3 > 0) && (
              <div className="mt-6">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Volume by Category</h4>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  {summary.felling_volume_m3 > 0 && (
                    <div className="p-3 bg-orange-50 rounded-md">
                      <p className="text-sm text-gray-600">Felling Trees</p>
                      <p className="mt-1 text-lg font-semibold text-orange-700">{(summary.felling_volume_m3 || 0).toFixed(2)} m³</p>
                    </div>
                  )}
                  {summary.mother_volume_m3 > 0 && (
                    <div className="p-3 bg-green-50 rounded-md">
                      <p className="text-sm text-gray-600">Mother Trees</p>
                      <p className="mt-1 text-lg font-semibold text-green-700">{(summary.mother_volume_m3 || 0).toFixed(2)} m³</p>
                    </div>
                  )}
                  {summary.pole_volume_m3 > 0 && (
                    <div className="p-3 bg-yellow-50 rounded-md">
                      <p className="text-sm text-gray-600">Poles</p>
                      <p className="mt-1 text-lg font-semibold text-yellow-700">{(summary.pole_volume_m3 || 0).toFixed(2)} m³</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Charts Section */}
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Tree Category Pie Chart */}
              {summary.total_trees > 0 && (
                <div className="bg-white p-4 rounded-lg shadow">
                  <h4 className="text-sm font-medium text-gray-700 mb-4">रूखको प्रकार (Tree Categories)</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'Mother Tree', value: summary.mother_trees_count || 0 },
                          { name: 'Felling Tree', value: summary.felling_trees_count || 0 },
                          { name: 'Pole', value: summary.pole_count || 0 },
                          { name: 'Seedling', value: summary.seedling_count || 0 },
                        ].filter(d => d.value > 0)}
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        dataKey="value"
                      >
                        {[
                          { name: 'Mother Tree', value: summary.mother_trees_count || 0 },
                          { name: 'Felling Tree', value: summary.felling_trees_count || 0 },
                          { name: 'Pole', value: summary.pole_count || 0 },
                          { name: 'Seedling', value: summary.seedling_count || 0 },
                        ].filter(d => d.value > 0).map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Volume by Category Bar Chart */}
              {(summary.felling_volume_m3 > 0 || summary.mother_volume_m3 > 0 || summary.pole_volume_m3 > 0) && (
                <div className="bg-white p-4 rounded-lg shadow">
                  <h4 className="text-sm font-medium text-gray-700 mb-4">आयतन (Volume by Category)</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart
                      data={[
                        { name: 'Mother Tree', volume: summary.mother_volume_m3 || 0 },
                        { name: 'Felling Tree', volume: summary.felling_volume_m3 || 0 },
                        { name: 'Pole', volume: summary.pole_volume_m3 || 0 },
                      ].filter(d => d.volume > 0)}
                      layout="vertical"
                      margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="name" type="category" width={100} />
                      <Tooltip />
                      <Bar dataKey="volume" fill="#22c55e" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Stand Type Pie Chart */}
              {(summary.tree_count > 0 || summary.stand_pole_count > 0 || summary.sapling_count > 0 || summary.regeneration_count > 0) && (
                <div className="bg-white p-4 rounded-lg shadow">
                  <h4 className="text-sm font-medium text-gray-700 mb-4">बस्तु प्रकार (Stand Types)</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie
                        data={[
                          { name: 'Tree', value: summary.tree_count || 0 },
                          { name: 'Pole', value: summary.stand_pole_count || 0 },
                          { name: 'Sapling', value: summary.sapling_count || 0 },
                          { name: 'Regeneration', value: summary.regeneration_count || 0 },
                        ].filter(d => d.value > 0)}
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                        dataKey="value"
                      >
                        {[
                          { name: 'Tree', value: summary.tree_count || 0 },
                          { name: 'Pole', value: summary.stand_pole_count || 0 },
                          { name: 'Sapling', value: summary.sapling_count || 0 },
                          { name: 'Regeneration', value: summary.regeneration_count || 0 },
                        ].filter(d => d.value > 0).map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Top Species Bar Chart */}
              {summary.species_distribution && Object.keys(summary.species_distribution).length > 0 && (
                <div className="bg-white p-4 rounded-lg shadow">
                  <h4 className="text-sm font-medium text-gray-700 mb-4">प्रमुख प्रजाती (Top Species)</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart
                      data={Object.entries(summary.species_distribution)
                        .sort(([,a], [,b]) => b - a)
                        .slice(0, 10)
                        .map(([name, value]) => ({ name, value }))}
                      layout="vertical"
                      margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="name" type="category" width={70} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#3b82f6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>
        )}

        {summary?.compartment_breakdown && summary.compartment_breakdown.length > 0 && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold">रूखको वर्गीकरण बमोजिम सारांश</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">बनको नाम</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">बन खण्ड</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">कम्पार्टमेन्ट</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">रूखको हैसियत</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">रूख संख्या</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">जम्मा आयतन m³</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">जम्मा आयतन cft</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">दाउरा m³</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">दाउरा चट्टा</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {summary.compartment_breakdown.map((item: any, idx: number) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-3 text-sm font-medium text-gray-900">{item.forest_name}</td>
                      <td className="px-3 py-3 text-sm text-gray-700">{item.block_name}</td>
                      <td className="px-3 py-3 text-sm text-gray-700">{item.compartment_name}</td>
                      <td className="px-3 py-3 text-sm">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          item.remark === 'Mother Tree' ? 'bg-green-100 text-green-800' :
                          item.remark === 'Felling Tree' ? 'bg-orange-100 text-orange-800' :
                          item.remark === 'Seedling' ? 'bg-blue-100 text-blue-800' :
                          item.remark === 'Pole' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {item.remark}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-sm text-right font-medium">{item.tree_count}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.net_volume_m3?.toFixed(3) || '0.000'}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.net_volume_cft?.toFixed(3) || '0.000'}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.firewood_m3?.toFixed(3) || '0.000'}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.firewood_chatta?.toFixed(3) || '0.000'}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-100">
                  <tr>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900" colSpan={4}>जम्मा (Total)</td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.compartment_breakdown.reduce((sum: number, item: any) => sum + item.tree_count, 0)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.compartment_breakdown.reduce((sum: number, item: any) => sum + (item.net_volume_m3 || 0), 0).toFixed(3)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.compartment_breakdown.reduce((sum: number, item: any) => sum + (item.net_volume_cft || 0), 0).toFixed(3)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.compartment_breakdown.reduce((sum: number, item: any) => sum + (item.firewood_m3 || 0), 0).toFixed(3)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.compartment_breakdown.reduce((sum: number, item: any) => sum + (item.firewood_chatta || 0), 0).toFixed(3)}
                    </td>
                    </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* Species Breakdown Table */}
        {summary?.species_breakdown && summary.species_breakdown.length > 0 && (
          <div className="bg-white rounded-lg shadow overflow-hidden mt-6">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold">प्रजाती बमोजिम सारांश</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">प्रजाती</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">स्थानीय नाम</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">रूखको हैसियत</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">रूख संख्या</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">जम्मा आयतन m³</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">जम्मा आयतन cft</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">दाउरा m³</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">दाउरा चट्टा</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {summary.species_breakdown.map((item: any, idx: number) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-3 text-sm font-medium text-gray-900">{item.species}</td>
                      <td className="px-3 py-3 text-sm text-gray-700">{item.local_name || '-'}</td>
                      <td className="px-3 py-3 text-sm">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${
                          item.remark === 'Mother Tree' ? 'bg-green-100 text-green-800' :
                          item.remark === 'Felling Tree' ? 'bg-orange-100 text-orange-800' :
                          item.remark === 'Seedling' ? 'bg-blue-100 text-blue-800' :
                          item.remark === 'Pole' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {item.remark}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-sm text-right font-medium">{item.tree_count}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.net_volume_m3?.toFixed(3) || '0.000'}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.net_volume_cft?.toFixed(3) || '0.000'}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.firewood_m3?.toFixed(3) || '0.000'}</td>
                      <td className="px-3 py-3 text-sm text-right">{item.firewood_chatta?.toFixed(3) || '0.000'}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-100">
                  <tr>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900" colSpan={3}>जम्मा (Total)</td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.species_breakdown.reduce((sum: number, item: any) => sum + item.tree_count, 0)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.species_breakdown.reduce((sum: number, item: any) => sum + (item.net_volume_m3 || 0), 0).toFixed(3)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.species_breakdown.reduce((sum: number, item: any) => sum + (item.net_volume_cft || 0), 0).toFixed(3)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.species_breakdown.reduce((sum: number, item: any) => sum + (item.firewood_m3 || 0), 0).toFixed(3)}
                    </td>
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 text-right">
                      {summary.species_breakdown.reduce((sum: number, item: any) => sum + (item.firewood_chatta || 0), 0).toFixed(3)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        )}

        {/* Tree Data Preview - Only show if no compartment breakdown */}
        {(!summary?.compartment_breakdown || summary.compartment_breakdown.length === 0) && trees && trees.length > 0 && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
              <h3 className="text-lg font-semibold">Tree Data Preview ({trees.length} of {summary?.total_trees || 0})</h3>
              {trees.length < (summary?.total_trees || 0) && (
                <button
                  onClick={handleViewDetails}
                  className="text-sm text-green-600 hover:text-green-800 font-medium"
                >
                  View All Trees →
                </button>
              )}
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Species</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">DBH (cm)</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Height (m)</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Volume (m³)</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Remark</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Compartment</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {trees.map((tree: any, idx: number) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-2 text-sm">{tree.species || '-'}</td>
                      <td className="px-4 py-2 text-sm">{tree.dia_dbh ? tree.dia_dbh.toFixed(1) : '-'}</td>
                      <td className="px-4 py-2 text-sm">{tree.height ? tree.height.toFixed(1) : '-'}</td>
                      <td className="px-4 py-2 text-sm">{tree.volume_m3 ? tree.volume_m3.toFixed(3) : '-'}</td>
                      <td className="px-4 py-2 text-sm">
                        <span className={`px-2 py-1 rounded text-xs ${
                          tree.remark === 'Mother Tree' ? 'bg-green-100 text-green-800' :
                          tree.remark === 'Felling Tree' ? 'bg-orange-100 text-orange-800' :
                          tree.remark === 'Seedling' ? 'bg-blue-100 text-blue-800' :
                          tree.remark === 'Pole' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {tree.remark || 'Normal'}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm">{tree.compartment_name || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Removed individual tree preview table - showing summary above instead */}

        {loadingData && (
          <div className="bg-white rounded-lg shadow p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading tree data...</p>
          </div>
        )}
      </div>
    );
  }

  // If no tree mapping exists, show upload form
  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {validationResult && (
        <div className={`border rounded-lg p-6 ${
          validationResult.summary?.ready_for_processing
            ? 'bg-green-50 border-green-200'
            : 'bg-red-50 border-red-200'
        }`}>
          <h3 className="font-semibold mb-2 text-lg">
            {validationResult.summary?.ready_for_processing ? 'Validation Successful' : 'Validation Failed'}
          </h3>

          {/* Show errors if validation failed */}
          {!validationResult.summary?.ready_for_processing && validationResult.errors && validationResult.errors.length > 0 && (
            <div className="space-y-2">
              {validationResult.errors.map((err: any, idx: number) => (
                <div key={idx} className="bg-red-100 border border-red-300 rounded-md p-3">
                  <p className="text-sm font-medium text-red-800">{err.type || 'Error'}</p>
                  <p className="text-sm text-red-700 mt-1">{err.message}</p>
                </div>
              ))}

              {/* Boundary check details */}
              {validationResult.boundary_check && (
                <div className="mt-4 p-3 bg-white rounded-md border border-red-200">
                  <h4 className="text-sm font-semibold text-gray-900 mb-2">Boundary Check Details:</h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-600">Total Points:</span>
                      <span className="ml-2 font-semibold">{validationResult.boundary_check.total_points}</span>
                    </div>
                    <div>
                      <span className="text-gray-600">Outside Boundary:</span>
                      <span className="ml-2 font-semibold text-red-600">
                        {validationResult.boundary_check.out_of_boundary_count} ({validationResult.boundary_check.out_of_boundary_percentage}%)
                      </span>
                    </div>
                    <div>
                      <span className="text-gray-600">Within Tolerance:</span>
                      <span className="ml-2 font-semibold">
                        {validationResult.boundary_check.within_tolerance ? 'Yes' : 'No'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Show status if ready for processing */}
          {validationResult.summary?.ready_for_processing && (
            <p className="text-sm text-green-700">
              {validationResult.summary?.status || 'Ready for processing'}
            </p>
          )}
        </div>
      )}

      {/* Step 1: Download Template */}
      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center h-10 w-10 rounded-full bg-green-100 text-green-600 font-bold">
              1
            </div>
          </div>
          <div className="ml-4 flex-1">
            <h3 className="text-lg font-semibold text-gray-900">Download Template</h3>
            <p className="mt-1 text-sm text-gray-600">
              Download the CSV template with required columns and format
            </p>
            <button
              onClick={handleDownloadTemplate}
              className="mt-3 inline-flex items-center px-4 py-2 border border-green-600 text-sm font-medium rounded-md text-green-600 bg-white hover:bg-green-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
            >
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Download Template
            </button>
          </div>
        </div>
      </div>

      {/* Step 2: Upload File */}
      <div className="bg-white border rounded-lg p-6">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center h-10 w-10 rounded-full bg-green-100 text-green-600 font-bold">
              2
            </div>
          </div>
          <div className="ml-4 flex-1">
            <h3 className="text-lg font-semibold text-gray-900">Upload CSV File</h3>
            <p className="mt-1 text-sm text-gray-600">
              Select your filled tree mapping CSV file
            </p>

            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  CSV File
                </label>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-green-50 file:text-green-700 hover:file:bg-green-100"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Grid Spacing (meters)
                  </label>
                  <input
                    type="number"
                    value={gridSpacing}
                    onChange={(e) => setGridSpacing(Number(e.target.value))}
                    min="10"
                    max="100"
                    className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500"
                  />
                  <p className="mt-1 text-xs text-gray-500">For mother tree selection</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Projection EPSG (optional)
                  </label>
                  <input
                    type="text"
                    value={projectionEpsg}
                    onChange={(e) => setProjectionEpsg(e.target.value)}
                    placeholder="e.g., 32644"
                    className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-green-500 focus:border-green-500"
                  />
                  <p className="mt-1 text-xs text-gray-500">Auto-detected if not specified</p>
                </div>
              </div>

              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {uploading ? (
                  <span className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Processing...
                  </span>
                ) : (
                  'Upload and Process'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-blue-900 mb-2">Required CSV Columns:</h4>
        <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
          <li>Species (tree species name)</li>
          <li>Dia/DBH (diameter in cm)</li>
          <li>Height (tree height in meters)</li>
          <li>X/Longitude and Y/Latitude (coordinates)</li>
        </ul>
      </div>

      {/* Correction Preview Dialog */}
      {showCorrectionDialog && correctionData?.boundaryCheck && (
        <CorrectionPreviewDialog
          boundaryCheck={correctionData.boundaryCheck}
          corrections={correctionData.boundaryCheck.corrections || []}
          summary={correctionData.boundaryCheck.correction_summary || {
            total_corrections: 0,
            max_distance: 0,
            min_distance: 0,
            avg_distance: 0
          }}
          onAccept={handleAcceptCorrections}
          onCancel={handleCancelCorrections}
          isProcessing={applyingCorrections}
        />
      )}

      {/* Column Mapping Modal */}
      {showColumnMapping && columnMappingData && (
        <ColumnMappingPreview
          previewData={columnMappingData}
          onConfirm={handleConfirmMapping}
          onCancel={handleCancelMapping}
        />
      )}
    </div>
  );
}

// Tree Mapping Map Component
interface TreeMappingMapProps {
  inventoryId: string;
  trees: any[];
  calculationId?: string;
}

// Measure Control Component - handles Geoman polyline drawing for distance measurement
function MeasureControl({ measureMode, setMeasureMode }: { measureMode: boolean; setMeasureMode: (v: boolean) => void }) {
  const map = useMap();

  useEffect(() => {
    if (measureMode) {
      map.pm.addControls({
        position: 'topleft',
        drawPolygon: false,
        drawMarker: false,
        drawCircle: false,
        drawCircleMarker: false,
        drawPolyline: true,
        drawRectangle: false,
        editMode: false,
        dragMode: false,
        cutPolygon: false,
        removalMode: false,
      });

      // Listen for polyline creation and show measurement
      const handleCreate = (e: any) => {
        const layer = e.layer;
        if (!layer) return;
        
        // Get coordinates - handle both array and flat formats
        let latlngs = layer.getLatLngs();
        
        // For Polyline, latlngs is an array of LatLng. For complex shapes, it might be nested.
        // Flatten if needed
        if (latlngs.length > 0 && Array.isArray(latlngs[0]) && latlngs[0].lat === undefined) {
          latlngs = latlngs.flat();
        }
        
        if (!latlngs || latlngs.length < 2) return;
        
        // Calculate distance in meters
        let totalDistance = 0;
        
        for (let i = 0; i < latlngs.length - 1; i++) {
          totalDistance += latlngs[i].distanceTo(latlngs[i + 1]);
        }

        // Add measurement label to the map
        const midIdx = Math.floor(latlngs.length / 2);
        const midPoint = latlngs[midIdx];
        
        const measureLabel = L.divIcon({
          className: 'measure-label',
          html: `<div style="background: white; padding: 4px 8px; border-radius: 4px; border: 1px solid #333; font-weight: bold; font-size: 12px; white-space: nowrap;">
            ${totalDistance.toFixed(1)} m
          </div>`,
          iconSize: [80, 24],
          iconAnchor: [40, 12]
        });
        
        L.marker(midPoint, { icon: measureLabel }).addTo(map);
        
        // Add total distance text at the end point
        const endPoint = latlngs[latlngs.length - 1];
        const endLabel = L.divIcon({
          className: 'measure-label',
          html: `<div style="background: #22c55e; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px; white-space: nowrap;">
            ${totalDistance.toFixed(1)} m
          </div>`,
          iconSize: [60, 20],
          iconAnchor: [30, 10]
        });
        L.marker(endPoint, { icon: endLabel }).addTo(map);
        
        console.log('Measurement:', totalDistance.toFixed(1), 'm');
      };

      map.on('pm:create', handleCreate);

      return () => {
        map.off('pm:create', handleCreate);
      };
    } else {
      map.pm.removeControls();
    }

    return () => {
      if (map.pm) {
        map.pm.removeControls();
      }
    };
  }, [measureMode, map]);

  return null;
}

function TreeMappingMap({ inventoryId, trees, calculationId }: TreeMappingMapProps) {
  const [gridCells, setGridCells] = useState<any[]>([]);
  const [gridMetadata, setGridMetadata] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [baseMap, setBaseMap] = useState('osm');
  const [forestBlocks, setForestBlocks] = useState<any[]>([]);
  const [blocksLoading, setBlocksLoading] = useState(false);

  // Layer toggles - Grid and Mother Trees ON by default
  const [showGrid, setShowGrid] = useState(true);
  const [showMotherTrees, setShowMotherTrees] = useState(true);
  const [showFellingTrees, setShowFellingTrees] = useState(false);
  const [showPoles, setShowPoles] = useState(false);
  const [showSeedlings, setShowSeedlings] = useState(false);
  const [showForestBlocks, setShowForestBlocks] = useState(false);
  const [showCompartments, setShowCompartments] = useState(false);
  const [measureMode, setMeasureMode] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch grid cells
        const gridData = await inventoryApi.getGridCells(inventoryId);
        if (gridData?.features) {
          setGridCells(gridData.features);
          setGridMetadata(gridData.metadata);
        }
      } catch (err) {
        console.error('Error fetching grid cells:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [inventoryId]);

  // Fetch forest blocks and compartments if calculationId provided
  useEffect(() => {
    if (!calculationId) return;
    
    const fetchBlocks = async () => {
      setBlocksLoading(true);
      try {
        const blocksData = await compartmentApi.getAllBlocks(calculationId);
        if (blocksData && blocksData.length > 0) {
          setForestBlocks(blocksData);
        }
      } catch (err) {
        console.log('No forest blocks found for this calculation');
      } finally {
        setBlocksLoading(false);
      }
    };
    fetchBlocks();
  }, [calculationId]);

  // Calculate center from trees or grid or blocks
  const getCenter = () => {
    if (trees && trees.length > 0) {
      const lats = trees.map((t: any) => t.location?.y || t.latitude).filter(Boolean);
      const lons = trees.map((t: any) => t.location?.x || t.longitude).filter(Boolean);
      if (lats.length > 0 && lons.length > 0) {
        return [lats.reduce((a: number, b: number) => a + b) / lats.length, lons.reduce((a: number, b: number) => a + b) / lons.length];
      }
    }
    if (forestBlocks && forestBlocks.length > 0) {
      // Find centroid of all blocks
      const lats: number[] = [];
      const lons: number[] = [];
      forestBlocks.forEach((block: any) => {
        if (block.geometry?.coordinates) {
          const coords = block.geometry.type === 'MultiPolygon' 
            ? block.geometry.coordinates[0][0] 
            : block.geometry.coordinates[0];
          coords.forEach((c: number[]) => {
            lats.push(c[1]);
            lons.push(c[0]);
          });
        }
      });
      if (lats.length > 0) {
        return [lats.reduce((a, b) => a + b) / lats.length, lons.reduce((a, b) => a + b) / lons.length];
      }
    }
    if (gridMetadata) {
      const centerLat = (gridMetadata.origin_y + (gridMetadata.num_rows * gridMetadata.spacing_meters / 2)) / 111320;
      const centerLon = (gridMetadata.origin_x + (gridMetadata.num_cols * gridMetadata.spacing_meters / 2)) / 111320;
      return [centerLat, centerLon];
    }
    return [27.45, 85.04];
  };

  const getZoom = () => {
    if (forestBlocks && forestBlocks.length > 0) return 13;
    if (trees && trees.length > 0) return 14;
    if (gridMetadata) return 14;
    return 12;
  };

  // Tree marker color based on type
  const getTreeColor = (tree: any) => {
    if (tree.remark === 'Mother Tree') return '#22c55e'; // Green - bigger
    if (tree.remark === 'Felling Tree') return '#f97316'; // Orange
    if (tree.remark === 'Pole') return '#eab308'; // Yellow
    if (tree.remark === 'Seedling') return '#3b82f6'; // Blue
    return '#6b7280'; // Gray
  };

  const getTreeRadius = (tree: any) => {
    if (tree.remark === 'Mother Tree') return 12;
    return 6;
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
        <h3 className="text-lg font-semibold">Tree & Grid Map</h3>
        
        {/* Layer Toggles */}
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showGrid}
              onChange={(e) => setShowGrid(e.target.checked)}
              className="w-4 h-4"
            />
            <span className={showGrid ? 'font-medium' : 'text-gray-500'}>Grid</span>
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showMotherTrees}
              onChange={(e) => setShowMotherTrees(e.target.checked)}
              className="w-4 h-4"
            />
            <span className={showMotherTrees ? 'font-medium text-green-700' : 'text-gray-500'}>Mother</span>
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showFellingTrees}
              onChange={(e) => setShowFellingTrees(e.target.checked)}
              className="w-4 h-4"
            />
            <span className={showFellingTrees ? 'font-medium text-orange-700' : 'text-gray-500'}>Felling</span>
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showPoles}
              onChange={(e) => setShowPoles(e.target.checked)}
              className="w-4 h-4"
            />
            <span className={showPoles ? 'font-medium text-yellow-700' : 'text-gray-500'}>Poles</span>
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showSeedlings}
              onChange={(e) => setShowSeedlings(e.target.checked)}
              className="w-4 h-4"
            />
            <span className={showSeedlings ? 'font-medium text-blue-700' : 'text-gray-500'}>Seedlings</span>
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showForestBlocks}
              onChange={(e) => setShowForestBlocks(e.target.checked)}
              className="w-4 h-4"
            />
            <span className={showForestBlocks ? 'font-medium text-blue-700' : 'text-gray-500'}>Blocks</span>
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={showCompartments}
              onChange={(e) => setShowCompartments(e.target.checked)}
              className="w-4 h-4"
            />
            <span className={showCompartments ? 'font-medium text-green-700' : 'text-gray-500'}>Compartments</span>
          </label>
          <select
            value={baseMap}
            onChange={(e) => setBaseMap(e.target.value)}
            className="border rounded px-2 py-1 text-sm ml-2"
          >
            <option value="osm">OSM</option>
            <option value="satellite">Satellite</option>
            <option value="terrain">Terrain</option>
          </select>
          <button
            onClick={() => setMeasureMode(!measureMode)}
            className={`px-3 py-1 text-sm rounded ml-2 ${
              measureMode 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {measureMode ? 'Measure ON' : 'Measure'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="h-96 flex items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600"></div>
        </div>
      ) : (
        <div className="h-96 rounded-lg overflow-hidden">
          <MapContainer
            center={getCenter()}
            zoom={getZoom()}
            className="h-full w-full"
          >
            <BaseMapSelector baseMap={baseMap} />
            
            {/* Measure Mode Control */}
            <MeasureControl measureMode={measureMode} setMeasureMode={setMeasureMode} />
            
            {/* Grid cells - ON by default */}
            {showGrid && gridCells.map((cell: any) => (
              <GeoJSON
                key={cell.properties?.cell_id || cell.id}
                data={cell.geometry}
                style={{
                  fillColor: '#3b82f6',
                  fillOpacity: 0.1,
                  color: '#3b82f6',
                  weight: 1
                }}
                onEachFeature={(feature, layer) => {
                  const cellId = cell.properties?.cell_id || cell.id;
                  layer.bindTooltip(`Cell: ${cellId}`, { 
                    permanent: false, 
                    direction: 'center',
                    className: 'bg-white border border-gray-400 px-1 text-xs'
                  });
                }}
              />
            ))}

            {/* Felling Trees */}
            {showFellingTrees && trees
              .filter((t: any) => t.remark === 'Felling Tree')
              .map((tree: any, idx: number) => {
                const lat = tree.latitude;
                const lon = tree.longitude;
                if (!lat || !lon) return null;
                
                return (
                  <CircleMarker
                    key={`felling-${tree.id || idx}`}
                    center={[lat, lon]}
                    radius={4}
                    pathOptions={{
                      fillColor: '#f97316',
                      color: '#c2410c',
                      fillOpacity: 0.8,
                      weight: 1
                    }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <p className="font-bold text-orange-700">Felling Tree</p>
                        <p><strong>Species:</strong> {tree.species || '-'}</p>
                        <p><strong>DBH:</strong> {tree.dia_cm ? `${tree.dia_cm.toFixed(1)} cm` : '-'}</p>
                        {tree.grid_cell_id && <p><strong>Grid ID:</strong> {tree.grid_cell_id}</p>}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}

            {/* Poles */}
            {showPoles && trees
              .filter((t: any) => t.remark === 'Pole')
              .map((tree: any, idx: number) => {
                const lat = tree.latitude;
                const lon = tree.longitude;
                if (!lat || !lon) return null;
                
                return (
                  <CircleMarker
                    key={`pole-${tree.id || idx}`}
                    center={[lat, lon]}
                    radius={3}
                    pathOptions={{
                      fillColor: '#eab308',
                      color: '#a16207',
                      fillOpacity: 0.8,
                      weight: 1
                    }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <p className="font-bold text-yellow-700">Pole</p>
                        <p><strong>Species:</strong> {tree.species || '-'}</p>
                        <p><strong>DBH:</strong> {tree.dia_cm ? `${tree.dia_cm.toFixed(1)} cm` : '-'}</p>
                        {tree.grid_cell_id && <p><strong>Grid ID:</strong> {tree.grid_cell_id}</p>}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}

            {/* Seedlings */}
            {showSeedlings && trees
              .filter((t: any) => t.remark === 'Seedling')
              .map((tree: any, idx: number) => {
                const lat = tree.latitude;
                const lon = tree.longitude;
                if (!lat || !lon) return null;
                
                return (
                  <CircleMarker
                    key={`seedling-${tree.id || idx}`}
                    center={[lat, lon]}
                    radius={2}
                    pathOptions={{
                      fillColor: '#3b82f6',
                      color: '#1d4ed8',
                      fillOpacity: 0.8,
                      weight: 1
                    }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <p className="font-bold text-blue-700">Seedling</p>
                        <p><strong>Species:</strong> {tree.species || '-'}</p>
                        <p><strong>DBH:</strong> {tree.dia_cm ? `${tree.dia_cm.toFixed(1)} cm` : '-'}</p>
                        {tree.grid_cell_id && <p><strong>Grid ID:</strong> {tree.grid_cell_id}</p>}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}

            {/* Mother Trees Only - ON by default */}
            {showMotherTrees && trees
              .filter((t: any) => t.remark === 'Mother Tree')
              .map((tree: any, idx: number) => {
                const lat = tree.latitude;
                const lon = tree.longitude;
                if (!lat || !lon) return null;
                
                return (
                  <CircleMarker
                    key={`mother-${tree.id || idx}`}
                    center={[lat, lon]}
                    radius={4}
                    pathOptions={{
                      fillColor: '#22c55e',
                      color: '#15803d',
                      fillOpacity: 0.9,
                      weight: 2
                    }}
                  >
                    <Popup>
                      <div className="text-sm">
                        <p className="font-bold text-green-700">Mother Tree</p>
                        <p><strong>Species:</strong> {tree.species || '-'}</p>
                        <p><strong>DBH:</strong> {tree.dia_cm ? `${tree.dia_cm.toFixed(1)} cm` : '-'}</p>
                        <p><strong>Height:</strong> {tree.height_m ? `${tree.height_m.toFixed(1)} m` : '-'}</p>
                        {tree.grid_cell_id && <p><strong>Grid ID:</strong> {tree.grid_cell_id}</p>}
                      </div>
                    </Popup>
                  </CircleMarker>
                );
              })}

            {/* Forest Blocks */}
            {showForestBlocks && forestBlocks.filter((b: any) => !b.is_compartment).map((block: any, idx: number) => (
              <GeoJSON
                key={`block-${block.id || idx}`}
                data={block.geometry}
                style={{
                  fillColor: '#3b82f6',
                  fillOpacity: 0.2,
                  color: '#2563eb',
                  weight: 2
                }}
              />
            ))}

            {/* Compartments */}
            {showCompartments && forestBlocks.filter((b: any) => b.is_compartment).map((comp: any, idx: number) => (
              <GeoJSON
                key={`comp-${comp.id || idx}`}
                data={comp.geometry}
                style={{
                  fillColor: '#10b981',
                  fillOpacity: 0.3,
                  color: '#059669',
                  weight: 2
                }}
              />
            ))}
          </MapContainer>
        </div>
      )}

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 justify-center text-sm">
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded-full bg-green-500"></div>
          <span>Mother Tree</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded-full bg-orange-500"></div>
          <span>Felling Tree</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
          <span>Pole</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 rounded-full bg-blue-500"></div>
          <span>Seedling</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 border border-blue-500 bg-blue-100"></div>
          <span>Grid Cell</span>
        </div>
        {forestBlocks.length > 0 && (
          <>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 border-2 border-blue-600 bg-blue-200"></div>
              <span>Forest Block</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 border-2 border-green-600 bg-green-200"></div>
              <span>Compartment</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
