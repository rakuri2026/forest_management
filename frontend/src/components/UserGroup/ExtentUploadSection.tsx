import React, { useState } from 'react';
import { Upload } from 'lucide-react';
import api from '../../services/api';

interface ExtentUploadSectionProps {
  calculationId: string;
  onExtentCreated: (extentId: number) => void;
}

export function ExtentUploadSection({ calculationId, onExtentCreated }: ExtentUploadSectionProps) {
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setFileName(file.name);
    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // Don't set Content-Type - let browser set it with correct boundary for FormData
      const response = await api.post(
        `/api/calculations/${calculationId}/user-group/upload`,
        formData
      );

      onExtentCreated(response.data.extent_id);
      alert('Extent boundary uploaded successfully!');
    } catch (error: any) {
      console.error('Upload failed:', error);
      console.error('Error response:', error.response);
      console.error('Error data:', error.response?.data);

      let errorMsg = 'Upload failed. Please check file format and try again.';

      if (error.response?.data?.detail) {
        errorMsg = error.response.data.detail;
      } else if (error.response?.data) {
        errorMsg = JSON.stringify(error.response.data);
      } else if (error.message) {
        errorMsg = error.message;
      }

      alert(errorMsg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="extent-upload-section border border-gray-300 rounded p-4 bg-white">
      <h3 className="text-lg font-semibold mb-3">Upload Extent Boundary</h3>

      <div className="upload-area border-2 border-dashed border-gray-400 rounded p-6 text-center hover:border-blue-500 transition-colors">
        <Upload className="mx-auto mb-3 text-gray-500" size={48} />

        <input
          type="file"
          accept=".kml,.kmz,.shp,.zip,.gpx,.geojson,.json,.csv"
          onChange={handleFileUpload}
          disabled={uploading}
          className="hidden"
          id="extent-upload"
        />

        <label
          htmlFor="extent-upload"
          className={`${
            uploading ? 'bg-gray-400' : 'bg-blue-600 hover:bg-blue-700'
          } text-white px-6 py-2 rounded cursor-pointer inline-block transition-colors`}
        >
          {uploading ? 'Uploading...' : 'Choose File'}
        </label>

        {fileName && (
          <p className="mt-3 text-sm text-gray-600">
            Selected: <strong>{fileName}</strong>
          </p>
        )}

        <p className="mt-3 text-sm text-gray-500">
          Supported formats: KML, KMZ, Shapefile (ZIP), GPX, GeoJSON, CSV
        </p>
      </div>
    </div>
  );
}
