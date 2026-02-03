import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { inventoryApi } from '../services/api';

export default function InventoryUpload() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [gridSpacing, setGridSpacing] = useState(20);
  const [projectionEpsg, setProjectionEpsg] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

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
      a.download = 'TreeInventory_Template.csv';
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
      const result = await inventoryApi.uploadInventory(file, gridSpacing, epsg);
      setValidationResult(result);

      // Step 2: If ready for processing, automatically process
      if (result.summary?.ready_for_processing && result.inventory_id) {
        // Update status to show processing
        setValidationResult({
          ...result,
          summary: {
            ...result.summary,
            status: 'Processing inventory (calculating volumes)...'
          }
        });

        try {
          // Process the inventory (re-upload file)
          await inventoryApi.processInventory(result.inventory_id, file);

          // Navigate to detail page after processing completes
          setTimeout(() => {
            navigate(`/inventory/${result.inventory_id}`);
          }, 1000);
        } catch (processErr: any) {
          setError(processErr.response?.data?.detail || 'Processing failed');
        }
      }
    } catch (err: any) {
      console.error('Upload error:', err);
      console.error('Error response:', err.response);
      console.error('Error data:', err.response?.data);

      const errorMessage = err.response?.data?.detail || err.message || 'Failed to upload file';
      setError(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Upload Tree Inventory</h1>
        <p className="mt-2 text-gray-600">
          Upload a CSV file with tree measurements for volume calculation
        </p>
      </div>

      {/* Step 1: Download Template */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center h-12 w-12 rounded-md bg-green-600 text-white text-xl font-bold">
              1
            </div>
          </div>
          <div className="ml-4 flex-1">
            <h3 className="text-lg font-medium text-gray-900">Download Template</h3>
            <p className="mt-2 text-sm text-gray-600">
              Download the CSV template with correct column headers and example data
            </p>
            <button
              onClick={handleDownloadTemplate}
              className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700"
            >
              <svg
                className="-ml-1 mr-2 h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"
                />
              </svg>
              Download Template
            </button>
          </div>
        </div>
      </div>

      {/* Step 2: Upload File */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-center h-12 w-12 rounded-md bg-green-600 text-white text-xl font-bold">
              2
            </div>
          </div>
          <div className="ml-4 flex-1">
            <h3 className="text-lg font-medium text-gray-900">Upload CSV File</h3>
            <p className="mt-2 text-sm text-gray-600 mb-4">
              Select your prepared CSV file with tree inventory data
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  CSV File
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

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Grid Spacing for Mother Tree Selection (meters)
                </label>
                <input
                  type="number"
                  value={gridSpacing}
                  onChange={(e) => setGridSpacing(parseFloat(e.target.value))}
                  min="10"
                  max="50"
                  step="5"
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-green-500 focus:border-green-500 sm:text-sm"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Recommended: 20 meters (one mother tree per 400m² grid cell)
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Projection EPSG Code (Optional)
                </label>
                <input
                  type="text"
                  value={projectionEpsg}
                  onChange={(e) => setProjectionEpsg(e.target.value)}
                  placeholder="e.g., 32644 for UTM Zone 44N"
                  className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-green-500 focus:border-green-500 sm:text-sm"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Leave empty for geographic coordinates (4326). Use 32644 for UTM 44N or 32645 for UTM 45N.
                </p>
              </div>

              <button
                onClick={handleUpload}
                disabled={!file || uploading}
                className="w-full inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:bg-gray-400"
              >
                {uploading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Uploading...
                  </>
                ) : (
                  'Upload & Validate'
                )}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md mb-6">
          {error}
        </div>
      )}

      {/* Validation Results */}
      {validationResult && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Validation Results</h3>

          {/* Summary */}
          <div className="mb-6 p-4 bg-gray-50 rounded-md">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-gray-500">Total Rows</p>
                <p className="text-2xl font-bold text-gray-900">{validationResult.summary?.total_rows}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Valid Rows</p>
                <p className="text-2xl font-bold text-green-600">{validationResult.summary?.valid_rows}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Errors</p>
                <p className="text-2xl font-bold text-red-600">{validationResult.summary?.error_count}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Warnings</p>
                <p className="text-2xl font-bold text-yellow-600">{validationResult.summary?.warning_count}</p>
              </div>
            </div>
          </div>

          {/* Ready for Processing */}
          {validationResult.summary?.ready_for_processing ? (
            <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-md">
              <p className="text-green-800 font-medium">
                ✓ File validated successfully! Redirecting to inventory details...
              </p>
            </div>
          ) : (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md">
              <p className="text-red-800 font-medium">
                ✗ Validation failed. Please fix the errors below and upload again.
              </p>
            </div>
          )}

          {/* Errors */}
          {validationResult.errors && validationResult.errors.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-red-900 mb-2">Errors ({validationResult.errors.length})</h4>
              <div className="space-y-2">
                {validationResult.errors.map((err: any, idx: number) => (
                  <div key={idx} className="p-3 bg-red-50 border border-red-200 rounded text-sm">
                    <p className="text-red-900">
                      {err.row && <span className="font-medium">Row {err.row}: </span>}
                      {err.message}
                    </p>
                    {err.suggestions && err.suggestions.length > 0 && (
                      <p className="mt-1 text-red-700 text-xs">
                        Suggestions: {err.suggestions.map((s: any) => s.scientific_name).join(', ')}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Warnings */}
          {validationResult.warnings && validationResult.warnings.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-yellow-900 mb-2">Warnings ({validationResult.warnings.length})</h4>
              <div className="space-y-2">
                {validationResult.warnings.map((warn: any, idx: number) => (
                  <div key={idx} className="p-3 bg-yellow-50 border border-yellow-200 rounded text-sm">
                    <p className="text-yellow-900">
                      {warn.row && <span className="font-medium">Row {warn.row}: </span>}
                      {warn.message}
                    </p>
                    {warn.original && warn.corrected && (
                      <p className="mt-1 text-yellow-700 text-xs">
                        Auto-corrected: "{warn.original}" → "{warn.corrected}" ({Math.round((warn.confidence || 0) * 100)}% confidence)
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Info */}
          {validationResult.corrections && validationResult.corrections.length > 0 && (
            <div className="mb-4">
              <h4 className="text-sm font-medium text-blue-900 mb-2">Auto-Corrections Applied</h4>
              <div className="space-y-2">
                {validationResult.corrections.map((corr: any, idx: number) => (
                  <div key={idx} className="p-3 bg-blue-50 border border-blue-200 rounded text-sm">
                    <p className="text-blue-900 font-medium">{corr.type}</p>
                    <p className="text-blue-700 text-xs mt-1">
                      Affected rows: {corr.affected_rows}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
