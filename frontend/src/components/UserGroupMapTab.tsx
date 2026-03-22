import React, { useState, useEffect, useRef } from 'react';
import { Upload, Map, Settings, Download, Play, Image } from 'lucide-react';
import { ExtentUploadSection } from './UserGroup/ExtentUploadSection';
import { AutoBufferSection } from './UserGroup/AutoBufferSection';
import { UserGroupMapVisualization } from './UserGroup/UserGroupMapVisualization';
import { SettlementStatistics } from './UserGroup/SettlementStatistics';
import { MapExportPanel } from './UserGroup/MapExportPanel';
import api from '../services/api';

interface UserGroupMapTabProps {
  calculationId: string;
  forestBoundary: any;
  forestName?: string;
}

export function UserGroupMapTab({ calculationId, forestBoundary, forestName: propForestName }: UserGroupMapTabProps) {
  const [activeMethod, setActiveMethod] = useState<'upload' | 'manual' | 'auto'>('upload');
  const [extentId, setExtentId] = useState<number | null>(null);
  const [results, setResults] = useState<any>(null);
  const [poiData, setPoiData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [showExportPanel, setShowExportPanel] = useState(false);
  const [forestName, setForestName] = useState<string>(propForestName || '');
  const mapRef = useRef<any>(null);

  // Fetch forest name from calculation if not provided
  useEffect(() => {
    if (!propForestName && calculationId) {
      const fetchForestName = async () => {
        try {
          const response = await api.get(`/api/calculations/${calculationId}`);
          if (response.data?.forest_name) {
            setForestName(response.data.forest_name);
          }
        } catch (error) {
          console.warn('Could not fetch forest name:', error);
        }
      };
      fetchForestName();
    }
  }, [calculationId, propForestName]);

  // Check for existing extent on component mount
  useEffect(() => {
    const loadExistingExtent = async () => {
      try {
        setLoading(true);
        const response = await api.get(`/api/calculations/${calculationId}/user-group/results`);

        if (response.data) {
          // Extent exists! Load it
          setResults(response.data);

          // Extract extent_id from the results
          if (response.data.extent_id) {
            setExtentId(response.data.extent_id);
          }

          // Try to fetch POI data too
          try {
            const poiResponse = await api.get(`/api/calculations/${calculationId}/user-group/poi`, {
              params: { layer_type: 'all' }
            });
            setPoiData(poiResponse.data);
          } catch (poiError) {
            console.warn('POI layers not available:', poiError);
          }
        }
      } catch (error: any) {
        // No existing extent - this is fine
        console.log('No existing user group extent');
      } finally {
        setLoading(false);
      }
    };

    loadExistingExtent();
  }, [calculationId]);

  const handleAnalyze = async () => {
    if (!extentId) {
      alert('Please create an extent first');
      return;
    }

    setAnalyzing(true);
    try {
      await api.post(`/api/calculations/${calculationId}/user-group/analyze`, null, {
        params: { extent_id: extentId }
      });

      // Fetch results
      const response = await api.get(`/api/calculations/${calculationId}/user-group/results`);
      setResults(response.data);

      // Fetch POI layers
      try {
        const poiResponse = await api.get(`/api/calculations/${calculationId}/user-group/poi`, {
          params: { layer_type: 'all' }
        });
        setPoiData(poiResponse.data);
      } catch (poiError) {
        console.warn('POI layers not available:', poiError);
        setPoiData(null);
      }
    } catch (error: any) {
      console.error('Analysis failed:', error);
      const errorMsg = error.response?.data?.detail || 'Analysis failed. Please try again.';
      alert(errorMsg);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleExport = async (format: string) => {
    if (!extentId) {
      alert('No extent to export');
      return;
    }

    try {
      const response = await api.get(`/api/user-group/${extentId}/export`, {
        params: { format },
        responseType: 'blob'
      });

      // Download file
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `user_group_map.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error: any) {
      console.error('Export failed:', error);
      const errorMsg = error.response?.data?.detail || 'Export failed. Please try again.';
      alert(errorMsg);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete the current User Group extent and analysis? This cannot be undone.')) {
      return;
    }

    try {
      await api.delete(`/api/calculations/${calculationId}/user-group`);

      // Clear state
      setExtentId(null);
      setResults(null);
      setPoiData(null);

      alert('User Group extent deleted successfully');
    } catch (error: any) {
      console.error('Delete failed:', error);
      const errorMsg = error.response?.data?.detail || 'Delete failed. Please try again.';
      alert(errorMsg);
    }
  };

  return (
    <div className="user-group-map-tab p-6">
      <h2 className="text-2xl font-bold mb-6">User Group Map</h2>

      {/* Method Selection */}
      <div className="method-selector mb-6">
        <div className="flex gap-4 mb-4">
          <button
            className={`px-4 py-2 rounded flex items-center gap-2 ${
              activeMethod === 'upload' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
            onClick={() => setActiveMethod('upload')}
          >
            <Upload size={16} />
            Upload Boundary
          </button>
          <button
            className={`px-4 py-2 rounded flex items-center gap-2 ${
              activeMethod === 'auto' ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
            onClick={() => setActiveMethod('auto')}
          >
            <Settings size={16} />
            Auto-Buffer
          </button>
        </div>

        {/* Render selected method component */}
        {activeMethod === 'upload' && (
          <ExtentUploadSection
            calculationId={calculationId}
            onExtentCreated={(id) => setExtentId(id)}
          />
        )}
        {activeMethod === 'auto' && (
          <AutoBufferSection
            calculationId={calculationId}
            defaultDistance={1000}
            onExtentCreated={(id) => setExtentId(id)}
          />
        )}
      </div>

      {/* Analyze and Delete Buttons */}
      {extentId && (
        <div className="analyze-section mb-6 flex gap-3">
          <button
            className={`${
              analyzing ? 'bg-gray-400' : 'bg-green-600 hover:bg-green-700'
            } text-white px-6 py-3 rounded transition-colors flex items-center gap-2`}
            onClick={handleAnalyze}
            disabled={analyzing}
          >
            <Play size={16} />
            {analyzing ? 'Analyzing...' : 'Analyze User Group'}
          </button>

          <button
            className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded transition-colors flex items-center gap-2"
            onClick={handleDelete}
            disabled={analyzing}
            title="Delete current User Group extent and analysis"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18"></path>
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
            </svg>
            Delete Extent
          </button>
        </div>
      )}

      {/* Results Section */}
      {results && (
        <>
          {/* Map Visualization */}
          <UserGroupMapVisualization
            calculationId={calculationId}
            forestBoundary={results.forest_boundary}
            extentBoundary={results.extent_geometry}
            settlements={results.settlements}
            buildings={results.buildings}
            poiData={poiData}
            ref={mapRef}
          />

          {/* Statistics Dashboard */}
          <SettlementStatistics settlements={results.settlements} />

          {/* Export Options */}
          <div className="export-section mt-6">
            <h3 className="text-xl font-semibold mb-3">Export Results</h3>
            <div className="flex gap-3 flex-wrap">
              <button
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition-colors flex items-center gap-2"
                onClick={() => handleExport('csv')}
              >
                <Download size={16} />
                Export CSV
              </button>
              <button
                className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition-colors flex items-center gap-2"
                onClick={() => handleExport('geojson')}
              >
                <Download size={16} />
                Export GeoJSON
              </button>
              <button
                className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 transition-colors flex items-center gap-2"
                onClick={() => setShowExportPanel(true)}
              >
                <Image size={16} />
                Export PNG (A5)
              </button>
            </div>
          </div>
        </>
      )}

      {/* Map Export Panel Modal */}
      {showExportPanel && results && (
        <MapExportPanel
          forestBoundary={results.forest_boundary}
          extentBoundary={results.extent_geometry}
          settlements={results.settlements}
          buildings={results.buildings}
          poiData={poiData}
          mapRef={mapRef}
          forestName={forestName}
          onClose={() => setShowExportPanel(false)}
        />
      )}
    </div>
  );
}

export default UserGroupMapTab;
