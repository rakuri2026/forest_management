import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { inventoryApi } from '../services/api';
import { CorrectionPreviewDialog } from './CorrectionPreviewDialog';

interface TreeMappingTabProps {
  calculationId: string;
}

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

  // Boundary correction state
  const [showCorrectionDialog, setShowCorrectionDialog] = useState(false);
  const [correctionData, setCorrectionData] = useState<any>(null);
  const [applyingCorrections, setApplyingCorrections] = useState(false);

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
      const [summaryData, treesData] = await Promise.all([
        inventoryApi.getInventorySummary(mappingId).catch(() => null),
        inventoryApi.listInventoryTrees(mappingId, { page: 1, page_size: 50 }).catch(() => ({ trees: [] }))
      ]);
      setSummary(summaryData);
      setTrees(treesData.trees || []);
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

      const epsg = projectionEpsg ? parseInt(projectionEpsg) : undefined;

      // Step 1: Upload and validate
      const result = await inventoryApi.uploadInventory(file, gridSpacing, epsg, calculationId);
      setValidationResult(result);

      // Step 2: Check if boundary corrections are needed
      if (result.summary?.ready_for_processing && result.inventory_id) {
        // Check for boundary issues
        if (result.boundary_check?.needs_correction) {
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
          // Process the inventory (re-upload file)
          await inventoryApi.processInventory(result.inventory_id, file);

          // Reload tree mapping data
          await checkTreeMapping();
          setFile(null);
          setValidationResult(null);
        } catch (processErr: any) {
          setError(processErr.response?.data?.detail || 'Processing failed');
        }
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

  const handleViewDetails = () => {
    if (treeMapping?.id) {
      navigate(`/inventory/${treeMapping.id}`);
    }
  };

  const handleExport = async (format: 'csv' | 'geojson') => {
    if (!treeMapping?.id) return;

    try {
      const blob = await inventoryApi.exportInventory(treeMapping.id, format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tree_mapping_${calculationId}.${format === 'geojson' ? 'geojson' : 'csv'}`;
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
                onClick={() => handleExport('geojson')}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm"
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

        {/* Summary Statistics */}
        {summary && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Summary Statistics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-6">
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

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

        {/* Tree Data Preview */}
        {trees && trees.length > 0 && (
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
                          tree.remark === 'Mother' ? 'bg-green-100 text-green-800' :
                          tree.remark === 'Felling' ? 'bg-orange-100 text-orange-800' :
                          tree.remark === 'Seedling' ? 'bg-blue-100 text-blue-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {tree.remark || 'Normal'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

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
        <div className={`border rounded-lg p-4 ${
          validationResult.summary?.ready_for_processing
            ? 'bg-green-50 border-green-200'
            : 'bg-yellow-50 border-yellow-200'
        }`}>
          <h3 className="font-semibold mb-2">
            {validationResult.summary?.ready_for_processing ? 'Validation Successful' : 'Validation Results'}
          </h3>
          <p className="text-sm">
            {validationResult.summary?.status || 'Processing...'}
          </p>
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
    </div>
  );
}
