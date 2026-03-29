import { useEffect, useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { forestApi } from '../services/api';
import AnalysisOptionsPanel from '../components/AnalysisOptionsPanel';
import MapOptionsPanel from '../components/MapOptionsPanel';
import MapCreationWizard from '../components/MapCreation/MapCreationWizard';
import { DEFAULT_ANALYSIS_OPTIONS, DEFAULT_MAP_OPTIONS } from '../constants/analysisPresets';
import type { AnalysisOptions, MapOptions } from '../constants/analysisPresets';
import type { Calculation } from '../types';

type CreateMode = 'upload' | 'digitize' | null;

export default function MyUploads() {
  const navigate = useNavigate();
  const [calculations, setCalculations] = useState<Calculation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createMode, setCreateMode] = useState<CreateMode>(null);

  // Upload form state
  const [file, setFile] = useState<File | null>(null);
  const [forestName, setForestName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  // Options state
  const [analysisOptions, setAnalysisOptions] = useState<AnalysisOptions>(DEFAULT_ANALYSIS_OPTIONS);
  const [mapOptions, setMapOptions] = useState<MapOptions>(DEFAULT_MAP_OPTIONS);

  useEffect(() => {
    loadCalculations();
  }, []);

  const loadCalculations = async () => {
    try {
      setLoading(true);
      const data = await forestApi.listCalculations();
      setCalculations(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load uploads');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, forestName: string) => {
    if (!window.confirm(`Are you sure you want to delete "${forestName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await forestApi.deleteCalculation(id);
      await loadCalculations();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete calculation');
    }
  };

  // File upload handlers
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file');
      return;
    }
    if (!forestName.trim()) {
      setError('Please enter a forest name');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const result = await forestApi.uploadBoundary(file, forestName, analysisOptions, mapOptions);
      setShowCreateModal(false);
      navigate(`/calculations/${result.id}/block-naming`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDigitizeComplete = async (data: {
    outerBoundary: any;
    gpsPoints: any[];
    blocks: any[];
    subAreas: any[];
    runAnalysis?: boolean;
  }) => {
    setUploading(true);
    setError(null);

    try {
      const result = await forestApi.createFromMap({
        forest_name: forestName,
        outer_boundary: data.outerBoundary,
        gps_points: data.gpsPoints,
        blocks: data.blocks,
        sub_areas: data.subAreas,
        analysis_options: analysisOptions,
        map_options: mapOptions,
        run_analysis: data.runAnalysis ?? false,
      });
      setShowCreateModal(false);
      navigate(`/calculations/${result.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Map creation failed');
      setUploading(false);
    }
  };

  const handleStartDigitize = () => {
    if (!forestName.trim()) {
      setError('Please enter a forest name');
      return;
    }
    setCreateMode('digitize');
  };

  const handleCloseModal = () => {
    setShowCreateModal(false);
    setCreateMode(null);
    setFile(null);
    setForestName('');
    setError(null);
  };

  // Deduplicate: show only one entry per forest
  const uniqueForests = useMemo(() => {
    const forestMap = new Map<string, Calculation>();
    const sorted = [...calculations].sort((a, b) => {
      const getPriority = (calc: Calculation) => {
        if (calc.status === 'completed') return 0;
        if (calc.status === 'pending') return 1;
        if (calc.status === 'processing') return 2;
        if (calc.is_draft) return 3;
        return 4;
      };
      const priorityDiff = getPriority(a) - getPriority(b);
      if (priorityDiff !== 0) return priorityDiff;
      return new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime();
    });

    for (const calc of sorted) {
      const key = calc.forest_name || 'Unnamed Forest';
      if (!forestMap.has(key)) {
        forestMap.set(key, calc);
      }
    }
    return Array.from(forestMap.values());
  }, [calculations]);

  const getStatusBadge = (calc: Calculation) => {
    if (calc.is_draft) return { class: 'bg-blue-100 text-blue-800', text: 'Draft' };
    const styles: Record<string, { class: string; text: string }> = {
      processing: { class: 'bg-yellow-100 text-yellow-800', text: 'Processing' },
      completed: { class: 'bg-green-100 text-green-800', text: 'Completed' },
      failed: { class: 'bg-red-100 text-red-800', text: 'Failed' },
      pending: { class: 'bg-gray-100 text-gray-800', text: 'Pending' },
    };
    return styles[calc.status] || { class: 'bg-gray-100 text-gray-800', text: calc.status };
  };

  const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

  const supportedFormats = ['.shp', '.zip', '.geojson', '.json', '.kml'];

  return (
    <div className="max-w-7xl mx-auto py-8 px-4">
      {/* Header */}
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">My CFOPs</h1>
          <p className="mt-2 text-gray-600">Community Forest Operational Plans</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 font-medium transition-colors"
        >
          + Create New
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
          <button onClick={() => setError(null)} className="float-right font-bold">&times;</button>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      ) : uniqueForests.length === 0 ? (
        /* Empty State */
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-4 text-lg font-medium text-gray-900">No CFOPs yet</h3>
          <p className="mt-2 text-gray-500">Get started by creating your first community forest</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-6 inline-block bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 font-medium"
          >
            Create Your First CFOP
          </button>
        </div>
      ) : (
        /* CFOPs Table */
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Forest Name</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Source</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Updated</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {uniqueForests.map((calc) => {
                const statusInfo = getStatusBadge(calc);
                return (
                  <tr key={calc.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {calc.forest_name || 'Unnamed Forest'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {calc.is_draft ? 'Map Creation' : (calc.uploaded_filename?.replace(/\.(kml|geojson|shp)$/i, '') || 'Imported')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${statusInfo.class}`}>
                        {statusInfo.text}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(calc.updated_at || calc.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-4">
                        {calc.is_draft && (
                          <Link to={`/drafts/${calc.id}/resume`} className="text-purple-600 hover:text-purple-900">
                            Resume
                          </Link>
                        )}
                        {calc.status === 'completed' && (
                          <Link to={`/calculations/${calc.id}`} className="text-green-600 hover:text-green-900">
                            View
                          </Link>
                        )}
                        {calc.status === 'pending' && (
                          <>
                            <button onClick={() => navigate(`/calculations/${calc.id}/block-naming`)} className="text-blue-600 hover:text-blue-900">
                              Analyze
                            </button>
                            <Link to={`/calculations/${calc.id}`} className="text-gray-600 hover:text-gray-900">
                              View
                            </Link>
                          </>
                        )}
                        {calc.status === 'processing' && (
                          <span className="text-yellow-600">Processing...</span>
                        )}
                        <button onClick={() => handleDelete(calc.id, calc.forest_name || 'Unnamed Forest')} className="text-red-600 hover:text-red-900">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Create New Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h2 className="text-xl font-bold">Create New CFOP</h2>
              <button onClick={handleCloseModal} className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
            </div>

            {/* Modal Body */}
            <div className="p-6">
              {/* Step 1: Forest Name (always shown) */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Forest Name <span className="text-red-600">*</span>
                </label>
                <input
                  type="text"
                  value={forestName}
                  onChange={(e) => setForestName(e.target.value)}
                  className="w-full rounded-md border-gray-300 shadow-sm px-4 py-2 border focus:border-green-500 focus:ring-green-500"
                  placeholder="e.g., Shivapuri Community Forest"
                />
              </div>

              {/* Step 2: Mode Selection (if no mode selected) */}
              {!createMode && (
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <button
                    onClick={() => setCreateMode('upload')}
                    className="p-6 rounded-lg border-2 border-gray-300 hover:border-green-500 text-left transition-colors"
                  >
                    <div className="text-2xl mb-2">📁</div>
                    <div className="font-semibold text-lg">Upload File</div>
                    <div className="text-sm text-gray-500">KML, GeoJSON, or Shapefile</div>
                  </button>
                  <button
                    onClick={() => setCreateMode('digitize')}
                    className="p-6 rounded-lg border-2 border-gray-300 hover:border-green-500 text-left transition-colors"
                  >
                    <div className="text-2xl mb-2">🗺️</div>
                    <div className="font-semibold text-lg">Digitize Map</div>
                    <div className="text-sm text-gray-500">Draw boundary on satellite map</div>
                  </button>
                </div>
              )}

              {/* Step 3: Upload Mode */}
              {createMode === 'upload' && (
                <form onSubmit={handleUploadSubmit} className="space-y-6">
                  {/* File Drop Zone */}
                  <div
                    className={`border-2 border-dashed rounded-lg p-8 text-center ${dragActive ? 'border-green-500 bg-green-50' : 'border-gray-300'}`}
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                  >
                    <input
                      type="file"
                      id="file-upload"
                      accept={supportedFormats.join(',')}
                      onChange={handleFileChange}
                      className="hidden"
                    />
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <svg className="mx-auto h-10 w-10 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      {file ? (
                        <p className="text-green-600 font-medium">{file.name}</p>
                      ) : (
                        <>
                          <p className="text-gray-600">Click or drag file to upload</p>
                          <p className="text-xs text-gray-400 mt-1">{supportedFormats.join(', ')}</p>
                        </>
                      )}
                    </label>
                  </div>

                  <AnalysisOptionsPanel options={analysisOptions} onChange={setAnalysisOptions} disabled={uploading} />
                  <MapOptionsPanel options={mapOptions} onChange={setMapOptions} disabled={uploading} />

                  <div className="flex gap-4">
                    <button
                      type="submit"
                      disabled={uploading || !file || !forestName.trim()}
                      className="flex-1 bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 disabled:bg-gray-400 font-medium"
                    >
                      {uploading ? 'Uploading...' : 'Upload & Continue'}
                    </button>
                    <button type="button" onClick={() => setCreateMode(null)} className="px-6 py-3 border border-gray-300 rounded-md">
                      Back
                    </button>
                  </div>
                </form>
              )}

              {/* Step 3: Digitize Mode */}
              {createMode === 'digitize' && (
                <div>
                  {forestName.trim() ? (
                    <MapCreationWizard
                      forestName={forestName}
                      onComplete={handleDigitizeComplete}
                      onCancel={() => setCreateMode(null)}
                      isProcessing={uploading}
                    />
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      Please enter a forest name above to start digitizing
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
