import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { forestApi } from '../services/api';
import AnalysisOptionsPanel from '../components/AnalysisOptionsPanel';
import MapOptionsPanel from '../components/MapOptionsPanel';
import MapCreationWizard from '../components/MapCreation/MapCreationWizard';
import { DEFAULT_ANALYSIS_OPTIONS, DEFAULT_MAP_OPTIONS } from '../constants/analysisPresets';
import type { AnalysisOptions, MapOptions } from '../constants/analysisPresets';

type UploadMode = 'file' | 'map';

export default function Upload() {
  const navigate = useNavigate();
  const [uploadMode, setUploadMode] = useState<UploadMode>('file');
  const [file, setFile] = useState<File | null>(null);
  const [forestName, setForestName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [showMapWizard, setShowMapWizard] = useState(false);

  // Analysis and map options (default to Complete preset for all options)
  const [analysisOptions, setAnalysisOptions] = useState<AnalysisOptions>(DEFAULT_ANALYSIS_OPTIONS);
  const [mapOptions, setMapOptions] = useState<MapOptions>(DEFAULT_MAP_OPTIONS);

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
      setError(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!file) {
      setError('Please select a file to upload');
      return;
    }

    if (!forestName.trim()) {
      setError('Forest name is mandatory to describe');
      return;
    }

    setUploading(true);

    try {
      // Pass analysis and map options to API for selective analysis
      const result = await forestApi.uploadBoundary(
        file,
        forestName,
        analysisOptions,
        mapOptions
      );
      // Redirect to block naming page for multi-polygon files
      navigate(`/calculations/${result.id}/block-naming`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  // Handle map creation wizard completion
  const handleMapCreationComplete = async (data: {
    outerBoundary: any;
    gpsPoints: any[];
    blocks: any[];
    subAreas: any[];
    runAnalysis?: boolean;
  }) => {
    console.log('[Upload] handleMapCreationComplete called with:', {
      forestName,
      outerBoundary: !!data.outerBoundary,
      gpsPointsCount: data.gpsPoints?.length || 0,
      blocksCount: data.blocks?.length || 0,
      subAreasCount: data.subAreas?.length || 0,
      analysisOptions,
      mapOptions,
      runAnalysis: data.runAnalysis
    });

    setUploading(true);
    setError(null);

    try {
      console.log('[Upload] Calling forestApi.createFromMap...');

      // Call the create-from-map API endpoint
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

      console.log('[Upload] API call successful, result:', result);
      console.log('[Upload] Navigating to /calculations/' + result.id);

      // Navigate to calculation detail - blocks are already created with names from wizard
      navigate(`/calculations/${result.id}`);
    } catch (err: any) {
      console.error('[Upload] API call failed:', err);
      console.error('[Upload] Error response:', err.response?.data);
      const errorMessage = err.response?.data?.detail || 'Map creation failed. Please try again.';
      console.error('[Upload] Setting error message:', errorMessage);
      setError(errorMessage);
      setShowMapWizard(false); // Go back to the form to show the error
    } finally {
      setUploading(false);
      console.log('[Upload] Upload state set to false');
    }
  };

  const handleMapCreationCancel = () => {
    setUploadMode('file');
    setForestName('');
    setShowMapWizard(false);
  };

  const handleStartMapCreation = () => {
    if (!forestName.trim()) {
      setError('Please enter a forest name');
      return;
    }
    setError(null);
    setShowMapWizard(true);
  };

  const supportedFormats = ['.shp', '.zip', '.geojson', '.json', '.kml'];

  // If in map creation mode and user clicked "Start Map Creation", show wizard
  if (uploadMode === 'map' && showMapWizard) {
    return (
      <MapCreationWizard
        forestName={forestName}
        onComplete={handleMapCreationComplete}
        onCancel={handleMapCreationCancel}
        isProcessing={uploading}
      />
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Upload Forest Boundary</h1>
        <p className="mt-2 text-gray-600">
          Upload your forest boundary file or create one interactively on the map
        </p>
      </div>

      {/* Mode Toggle */}
      <div className="mb-6 bg-white rounded-lg shadow p-6">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Choose Input Method
        </label>
        <div className="grid grid-cols-2 gap-4">
          <button
            onClick={() => setUploadMode('file')}
            className={`px-6 py-4 rounded-lg border-2 transition-colors text-left ${
              uploadMode === 'file'
                ? 'border-green-600 bg-green-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <div className="font-semibold text-lg mb-1">Upload File</div>
            <div className="text-sm text-gray-600">
              Upload KML, GeoJSON, or Shapefile
            </div>
          </button>
          <button
            onClick={() => setUploadMode('map')}
            className={`px-6 py-4 rounded-lg border-2 transition-colors text-left ${
              uploadMode === 'map'
                ? 'border-green-600 bg-green-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <div className="font-semibold text-lg mb-1">Create on Map</div>
            <div className="text-sm text-gray-600">
              Draw boundary using GPS points or digitizing
            </div>
          </button>
        </div>
      </div>

      {/* Content based on mode */}
      {uploadMode === 'file' ? (
        <form onSubmit={handleSubmit} className="space-y-6">
          <div
            className={`border-2 border-dashed rounded-lg p-12 text-center ${
              dragActive ? 'border-green-500 bg-green-50' : 'border-gray-300'
            }`}
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
              <div className="space-y-4">
                <svg
                  className="mx-auto h-12 w-12 text-gray-400"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 48 48"
                >
                  <path
                    d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <div className="text-gray-600">
                  <span className="font-medium text-green-600 hover:text-green-500">
                    Click to upload
                  </span>{' '}
                  or drag and drop
                </div>
                <p className="text-xs text-gray-500">
                  Supported formats: {supportedFormats.join(', ')}
                </p>
                {file && (
                  <p className="text-sm text-green-600 font-medium mt-4">
                    Selected: {file.name}
                  </p>
                )}
              </div>
            </label>
          </div>

          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div>
              <label htmlFor="forest-name" className="block text-sm font-medium text-gray-700">
                Forest Name <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                id="forest-name"
                value={forestName}
                onChange={(e) => setForestName(e.target.value)}
                required
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm px-4 py-2 border"
                placeholder="e.g., Shivapuri Community Forest"
              />
            </div>
          </div>

          {/* Analysis Options Panel */}
          <AnalysisOptionsPanel
            options={analysisOptions}
            onChange={setAnalysisOptions}
            disabled={uploading}
          />

          {/* Map Options Panel */}
          <MapOptionsPanel
            options={mapOptions}
            onChange={setMapOptions}
            disabled={uploading}
          />

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
              {error}
            </div>
          )}

          <div className="flex gap-4">
            <button
              type="submit"
              disabled={uploading || !file || !forestName.trim()}
              className="flex-1 bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
            >
              {uploading ? 'Uploading...' : 'Upload and Analyze'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="px-6 py-3 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 font-medium transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        /* Map Creation Mode */
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">Forest Information</h2>
            <div>
              <label htmlFor="map-forest-name" className="block text-sm font-medium text-gray-700 mb-2">
                Forest Name <span className="text-red-600">*</span>
              </label>
              <input
                type="text"
                id="map-forest-name"
                value={forestName}
                onChange={(e) => setForestName(e.target.value)}
                required
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 px-4 py-2 border"
                placeholder="e.g., Shivapuri Community Forest"
              />
              <p className="text-sm text-gray-500 mt-2">
                Enter the forest name before proceeding to map creation.
              </p>
            </div>

            {error && (
              <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
                {error}
              </div>
            )}

            <div className="mt-6 flex gap-4">
              <button
                onClick={handleStartMapCreation}
                disabled={!forestName.trim()}
                className="flex-1 bg-green-600 text-white px-6 py-3 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
              >
                Start Map Creation
              </button>
              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                className="px-6 py-3 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 font-medium transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
            <h3 className="text-lg font-medium text-blue-900 mb-3">Interactive Map Creation</h3>
            <ul className="space-y-2 text-sm text-blue-800">
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span><strong>GPS Points:</strong> Import coordinates from CSV, GPX, or enter manually</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span><strong>Boundary:</strong> Auto-create from GPS points or draw directly on map</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span><strong>Blocks:</strong> Split forest into management blocks</span>
              </li>
              <li className="flex items-start">
                <span className="mr-2">•</span>
                <span><strong>Sub-areas:</strong> Define special zones (protected, plantation, etc.)</span>
              </li>
            </ul>
          </div>
        </div>
      )}

      {uploadMode === 'file' && (
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
          <h3 className="text-lg font-medium text-blue-900 mb-3">File Format Guidelines</h3>
          <ul className="space-y-2 text-sm text-blue-800">
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span><strong>Shapefile (.shp/.zip):</strong> Upload as a ZIP file containing all components (.shp, .shx, .dbf, .prj)</span>
            </li>
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span><strong>GeoJSON (.geojson/.json):</strong> Must contain valid GeoJSON geometry</span>
            </li>
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span><strong>KML (.kml):</strong> Google Earth KML format with polygon or point features</span>
            </li>
            <li className="flex items-start">
              <span className="mr-2">•</span>
              <span>All coordinates will be automatically converted to WGS84 (EPSG:4326)</span>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
