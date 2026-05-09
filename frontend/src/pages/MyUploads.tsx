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

const STAGES = [
  { key: 'draft', num: 1, label: 'Draw Boundary', icon: '🗺️', color: 'bg-blue-500', textColor: 'text-blue-800', bgColor: 'bg-blue-50', barColor: 'bg-blue-400' },
  { key: 'pending', num: 2, label: 'Name Blocks', icon: '📦', color: 'bg-gray-500', textColor: 'text-gray-800', bgColor: 'bg-gray-50', barColor: 'bg-gray-400' },
  { key: 'processing', num: 3, label: 'Running Analysis', icon: '⚙️', color: 'bg-yellow-500', textColor: 'text-yellow-800', bgColor: 'bg-yellow-50', barColor: 'bg-yellow-400' },
  { key: 'completed', num: 4, label: 'Complete', icon: '✅', color: 'bg-green-500', textColor: 'text-green-800', bgColor: 'bg-green-50', barColor: 'bg-green-400' },
];

const FAILED_STAGE = { key: 'failed', num: -1, label: 'Failed', icon: '⚠️', color: 'bg-red-500', textColor: 'text-red-800', bgColor: 'bg-red-50', barColor: 'bg-red-400' };

function getStage(calc: Calculation) {
  if (calc.is_draft) return STAGES[0];
  if (calc.status === 'pending') return STAGES[1];
  if (calc.status === 'processing') return STAGES[2];
  if (calc.status === 'completed') return STAGES[3];
  if (calc.status === 'failed') return FAILED_STAGE;
  return STAGES[0];
}

function getNextAction(calc: Calculation) {
  if (calc.is_draft) return { label: 'Resume Drawing', to: `/drafts/${calc.id}/resume`, color: 'text-purple-700' };
  if (calc.status === 'pending') return { label: 'Name Blocks', to: `/calculations/${calc.id}/block-naming`, color: 'text-blue-700' };
  if (calc.status === 'processing') return null;
  if (calc.status === 'completed') return { label: 'Open CFOP', to: `/calculations/${calc.id}`, color: 'text-green-700' };
  if (calc.status === 'failed') return { label: 'Retry', to: `/calculations/${calc.id}`, color: 'text-red-700' };
  return null;
}

function getNextHint(calc: Calculation) {
  if (calc.is_draft) return 'Finish drawing the forest boundary';
  if (calc.status === 'pending') return 'Name blocks, then run analysis';
  if (calc.status === 'processing') return 'Analysis is running...';
  if (calc.status === 'completed') return 'Set up sampling, inventory & tree model';
  if (calc.status === 'failed') return 'Analysis failed. Check your data & retry.';
  return '';
}

export default function MyUploads() {
  const navigate = useNavigate();
  const [calculations, setCalculations] = useState<Calculation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createMode, setCreateMode] = useState<CreateMode>(null);

  const [file, setFile] = useState<File | null>(null);
  const [forestName, setForestName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);

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
    if (!window.confirm(`Delete "${forestName}"? This cannot be undone.`)) return;
    try {
      await forestApi.deleteCalculation(id);
      await loadCalculations();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete calculation');
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") setDragActive(true);
    else if (e.type === "dragleave") setDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) setFile(e.target.files[0]);
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setError('Please select a file'); return; }
    if (!forestName.trim()) { setError('Please enter a forest name'); return; }
    setUploading(true); setError(null);
    try {
      const result = await forestApi.uploadBoundary(file, forestName, analysisOptions, mapOptions);
      setShowCreateModal(false);
      navigate(`/calculations/${result.id}/block-naming`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally { setUploading(false); }
  };

  const handleDigitizeComplete = async (data: {
    outerBoundary: any; gpsPoints: any[]; blocks: any[]; subAreas: any[]; runAnalysis?: boolean;
  }) => {
    setUploading(true); setError(null);
    try {
      const result = await forestApi.createFromMap({
        forest_name: forestName, outer_boundary: data.outerBoundary,
        gps_points: data.gpsPoints, blocks: data.blocks, sub_areas: data.subAreas,
        analysis_options: analysisOptions, map_options: mapOptions,
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
    if (!forestName.trim()) { setError('Please enter a forest name'); return; }
    setCreateMode('digitize');
  };

  const handleCloseModal = () => {
    setShowCreateModal(false); setCreateMode(null);
    setFile(null); setForestName(''); setError(null);
  };

  const groupedForests = useMemo(() => {
    const groups = STAGES.map(s => ({
      stage: s, forests: [] as Calculation[],
    }));
    groups.push({ stage: FAILED_STAGE, forests: [] as Calculation[] });

    for (const calc of calculations) {
      const stage = getStage(calc);
      const g = groups.find(g => g.stage.key === stage.key);
      if (g) g.forests.push(calc);
    }
    return groups.filter(g => g.forests.length > 0);
  }, [calculations]);

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
          className="bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 font-medium transition-colors shadow-sm"
        >
          + Create New
        </button>
      </div>

      {/* Workflow Guide */}
      <div className="mb-8 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <div className="flex items-center gap-1 sm:gap-3 justify-between flex-wrap">
          {STAGES.map((s, i) => (
            <div key={s.key} className="flex items-center gap-1 sm:gap-2">
              <div className={`w-8 h-8 rounded-full ${s.color} text-white flex items-center justify-center text-sm font-bold shadow-sm`}>
                {s.num}
              </div>
              <div className="text-xs sm:text-sm font-medium text-gray-700">{s.label}</div>
              {i < STAGES.length - 1 && <div className="hidden sm:block text-gray-300 text-lg">→</div>}
            </div>
          ))}
        </div>
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
      ) : calculations.length === 0 ? (
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
        /* CFOPs List grouped by stage */
        <div className="space-y-6">
          {groupedForests.map(({ stage, forests }) => (
            <div key={stage.key} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              {/* Stage Header */}
              <div className={`${stage.bgColor} px-5 py-3 border-b border-gray-200`}>
                <div className="flex items-center gap-3">
                  <span className="text-lg">{stage.icon}</span>
                  <div>
                    <span className={`text-sm font-bold ${stage.textColor}`}>
                      Stage {stage.num > 0 ? stage.num : ''} — {stage.label}
                    </span>
                    <span className="ml-2 text-xs text-gray-500">({forests.length})</span>
                  </div>
                </div>
              </div>

              {/* Forest Cards */}
              <div className="divide-y divide-gray-100">
                {forests.map((calc) => {
                  const action = getNextAction(calc);
                  const hint = getNextHint(calc);
                  return (
                    <div key={calc.id} className="px-5 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors">
                      {/* Left: Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-gray-900 truncate">
                            {calc.forest_name || 'Unnamed Forest'}
                          </span>
                          <span className="text-xs text-gray-400">
                            {calc.is_draft ? 'Map Creation' : (calc.uploaded_filename?.replace(/\.(kml|geojson|shp)$/i, '') || 'Imported')}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <div className={`w-1.5 h-1.5 rounded-full ${stage.color}`}></div>
                          <span className={`text-xs ${stage.textColor} font-medium`}>
                            Stage {stage.num > 0 ? stage.num : ''}
                          </span>
                          <span className="text-xs text-gray-400">|</span>
                          <span className="text-xs text-gray-500">{formatDate(calc.updated_at || calc.created_at)}</span>
                          {hint && (
                            <>
                              <span className="text-xs text-gray-300">|</span>
                              <span className="text-xs text-gray-400 italic">{hint}</span>
                            </>
                          )}
                        </div>
                      </div>

                      {/* Right: Actions */}
                      <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                        {action && (
                          <Link
                            to={action.to}
                            className={`px-4 py-1.5 rounded-md text-sm font-semibold ${action.color} bg-gray-50 hover:bg-gray-100 border border-gray-200 transition-colors`}
                          >
                            {action.label}
                          </Link>
                        )}
                        {calc.status === 'completed' && (
                          <Link
                            to={`/calculations/${calc.id}`}
                            className="px-4 py-1.5 rounded-md text-sm font-semibold text-green-700 bg-green-50 hover:bg-green-100 border border-green-200 transition-colors"
                          >
                            View
                          </Link>
                        )}
                        {calc.status === 'pending' && (
                          <>
                            <button
                              onClick={() => navigate(`/calculations/${calc.id}/block-naming`)}
                              className="px-4 py-1.5 rounded-md text-sm font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 transition-colors"
                            >
                              Analyze
                            </button>
                            <Link
                              to={`/calculations/${calc.id}`}
                              className="px-3 py-1.5 rounded-md text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
                            >
                              View
                            </Link>
                          </>
                        )}
                        {calc.status === 'processing' && (
                          <span className="text-sm text-yellow-600 italic">Processing...</span>
                        )}
                        <button
                          onClick={() => handleDelete(calc.id, calc.forest_name || 'Unnamed Forest')}
                          className="px-3 py-1.5 rounded-md text-sm text-red-600 hover:text-red-800 hover:bg-red-50 transition-colors"
                          title="Delete"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create New Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
              <h2 className="text-xl font-bold">Create New CFOP</h2>
              <button onClick={handleCloseModal} className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
            </div>
            <div className="p-6">
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

              {!createMode && (
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <button onClick={() => setCreateMode('upload')}
                    className="p-6 rounded-lg border-2 border-gray-300 hover:border-green-500 text-left transition-colors">
                    <div className="text-2xl mb-2">📁</div>
                    <div className="font-semibold text-lg">Upload File</div>
                    <div className="text-sm text-gray-500">KML, GeoJSON, or Shapefile</div>
                  </button>
                  <button onClick={() => setCreateMode('digitize')}
                    className="p-6 rounded-lg border-2 border-gray-300 hover:border-green-500 text-left transition-colors">
                    <div className="text-2xl mb-2">🗺️</div>
                    <div className="font-semibold text-lg">Digitize Map</div>
                    <div className="text-sm text-gray-500">Draw boundary on satellite map</div>
                  </button>
                </div>
              )}

              {createMode === 'upload' && (
                <form onSubmit={handleUploadSubmit} className="space-y-6">
                  <div className={`border-2 border-dashed rounded-lg p-8 text-center ${dragActive ? 'border-green-500 bg-green-50' : 'border-gray-300'}`}
                    onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}>
                    <input type="file" id="file-upload" accept={supportedFormats.join(',')} onChange={handleFileChange} className="hidden" />
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <svg className="mx-auto h-10 w-10 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                      {file ? <p className="text-green-600 font-medium">{file.name}</p> : (
                        <><p className="text-gray-600">Click or drag file to upload</p>
                        <p className="text-xs text-gray-400 mt-1">{supportedFormats.join(', ')}</p></>
                      )}
                    </label>
                  </div>
                  <AnalysisOptionsPanel options={analysisOptions} onChange={setAnalysisOptions} disabled={uploading} />
                  <MapOptionsPanel options={mapOptions} onChange={setMapOptions} disabled={uploading} />
                  <div className="flex gap-4">
                    <button type="submit" disabled={uploading || !file || !forestName.trim()}
                      className="flex-1 bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 disabled:bg-gray-400 font-medium">
                      {uploading ? 'Uploading...' : 'Upload & Continue'}
                    </button>
                    <button type="button" onClick={() => setCreateMode(null)} className="px-6 py-3 border border-gray-300 rounded-md">Back</button>
                  </div>
                </form>
              )}

              {createMode === 'digitize' && (
                <div>
                  {forestName.trim() ? (
                    <MapCreationWizard forestName={forestName} onComplete={handleDigitizeComplete}
                      onCancel={() => setCreateMode(null)} isProcessing={uploading} />
                  ) : (
                    <div className="text-center py-8 text-gray-500">Please enter a forest name above to start digitizing</div>
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
