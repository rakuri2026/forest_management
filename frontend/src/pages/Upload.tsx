import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { forestApi } from '../services/api';

export default function Upload() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [forestName, setForestName] = useState('');
  const [blockName, setBlockName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

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
      const result = await forestApi.uploadBoundary(file, forestName, blockName);
      navigate(`/calculations/${result.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const supportedFormats = ['.shp', '.zip', '.geojson', '.json', '.kml'];

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Upload Forest Boundary</h1>
        <p className="mt-2 text-gray-600">
          Upload your forest boundary file to analyze and generate management reports
        </p>
      </div>

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

          <div>
            <label htmlFor="block-name" className="block text-sm font-medium text-gray-700">
              Block Name (Optional)
            </label>
            <input
              type="text"
              id="block-name"
              value={blockName}
              onChange={(e) => setBlockName(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm px-4 py-2 border"
              placeholder="e.g., Block 1"
            />
          </div>
        </div>

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
    </div>
  );
}
