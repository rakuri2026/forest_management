import React, { useState, useEffect, useRef } from 'react';
import { Upload, Settings, Download, Play, Image, Users, Map } from 'lucide-react';
import { Tabs } from 'antd';
import { ExtentUploadSection } from './UserGroup/ExtentUploadSection';
import CopyTag from './DetailDescription/CopyTag';
import { AutoBufferSection } from './UserGroup/AutoBufferSection';
import { downloadFromApi } from '../utils/download';
import { UserGroupMapVisualization } from './UserGroup/UserGroupMapVisualization';
import { SettlementStatistics } from './UserGroup/SettlementStatistics';
import { LandCoverAnalysis } from './UserGroup/LandCoverAnalysis';
import { MapExportPanel } from './UserGroup/MapExportPanel';
import HouseholdInfoTab from './HouseholdInfo/HouseholdInfoTab';
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
  const [activeSubTab, setActiveSubTab] = useState<string>('boundary');
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
      await downloadFromApi(
        `/api/user-group/${extentId}/export`,
        `user_group_map.${format}`,
        { format }
      );
    } catch (error: any) {
      console.error('Export failed:', error);
      alert(error.message || 'Export failed. Please try again.');
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

  const renderBoundaryTab = () => (
    <>
      <div className="method-selector mb-6">
        <div className="grid grid-cols-2 gap-4 mb-4">
          <button
            className={`px-4 py-3 rounded-lg flex items-center justify-center gap-2 border-2 ${
              activeMethod === 'upload' 
                ? 'border-blue-600 bg-blue-50 text-blue-700' 
                : 'border-gray-300 bg-white hover:border-blue-400'
            }`}
            onClick={() => setActiveMethod('upload')}
          >
            <Upload size={18} />
            <span className="font-medium">Upload Boundary</span>
          </button>
          <button
            className={`px-4 py-3 rounded-lg flex items-center justify-center gap-2 border-2 ${
              activeMethod === 'auto' 
                ? 'border-purple-600 bg-purple-50 text-purple-700' 
                : 'border-gray-300 bg-white hover:border-purple-400'
            }`}
            onClick={() => setActiveMethod('auto')}
          >
            <Settings size={18} />
            <span className="font-medium">Auto-Buffer</span>
          </button>
        </div>

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

      {extentId && (
        <div className="analyze-section mb-6 flex gap-3">
          <button
            className={`${
              analyzing ? 'bg-gray-400' : 'bg-green-600 hover:bg-green-700'
            } text-white px-8 py-3 rounded-lg flex items-center gap-2 font-medium text-lg`}
            onClick={handleAnalyze}
            disabled={analyzing}
          >
            <Play size={18} />
            {analyzing ? 'Analyzing...' : 'Analyze'}
          </button>
          <button
            className="bg-red-100 hover:bg-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2"
            onClick={handleDelete}
            disabled={analyzing}
            title="Delete current User Group extent and analysis"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18"></path>
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
            </svg>
            Delete
          </button>
        </div>
      )}

      {results && (
        <>
          <UserGroupMapVisualization
            calculationId={calculationId}
            forestBoundary={results.forest_boundary}
            extentBoundary={results.extent_geometry}
            settlements={results.settlements}
            buildings={results.buildings}
            poiData={poiData}
            ref={mapRef}
          />
          <p className="text-xs text-gray-400 font-mono mb-1">{'{{map:usergroup}}'}</p>

          <SettlementStatistics settlements={results.settlements} />

          <div className="mt-6">
            <LandCoverAnalysis
              calculationId={calculationId}
              forestName={forestName}
            />
          </div>

          {/* OP Document Variables */}
          {results && (
            <div className="mt-6 bg-white border border-emerald-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-emerald-800 text-sm">
                  📋 OP Document Variables — User Group Map
                </h4>
              </div>
              <p className="text-xs text-gray-500 mb-2">
                उपभोक्ता समूह नक्सा — settlement, land cover, biomass variables for the OP document
              </p>

              {/* Narration */}
              <div className="mb-3">
                <p className="text-xs font-medium text-gray-600 mb-1">नेपाली विवरण:</p>
                <CopyTag label="{{section:user_group_narration}}" value="{{section:user_group_narration}}" variant="section" />
              </div>

              {/* Settlement Variables */}
              <details className="mb-2">
                <summary className="text-xs font-semibold text-gray-700 cursor-pointer hover:text-blue-600">
                  🏘️ Settlement Variables
                </summary>
                <div className="flex flex-wrap gap-1 mt-2">
                  <CopyTag label="{{ug_total_settlements}}" value="{{ug_total_settlements}}" variant="section" />
                  <CopyTag label="{{ug_total_buildings}}" value="{{ug_total_buildings}}" variant="section" />
                  <CopyTag label="{{ug_total_building_area_m2}}" value="{{ug_total_building_area_m2}}" variant="section" />
                  <CopyTag label="{{ug_avg_building_size_m2}}" value="{{ug_avg_building_size_m2}}" variant="section" />
                  <CopyTag label="{{ug_small_buildings}}" value="{{ug_small_buildings}}" variant="section" />
                  <CopyTag label="{{ug_medium_buildings}}" value="{{ug_medium_buildings}}" variant="section" />
                  <CopyTag label="{{ug_large_buildings}}" value="{{ug_large_buildings}}" variant="section" />
                  <CopyTag label="{{ug_small_pct}}" value="{{ug_small_pct}}" variant="section" />
                  <CopyTag label="{{ug_medium_pct}}" value="{{ug_medium_pct}}" variant="section" />
                  <CopyTag label="{{ug_large_pct}}" value="{{ug_large_pct}}" variant="section" />
                  <CopyTag label="{{ug_buildings}}" value="{{ug_buildings}}" variant="section" />
                </div>
              </details>

              {/* Land Cover Variables */}
              <details className="mb-2">
                <summary className="text-xs font-semibold text-gray-700 cursor-pointer hover:text-blue-600">
                  🌿 Land Cover & Biomass Variables
                </summary>
                <div className="flex flex-wrap gap-1 mt-2">
                  <CopyTag label="{{ug_user_group_area_ha}}" value="{{ug_user_group_area_ha}}" variant="section" />
                  <CopyTag label="{{ug_forest_overlap_area_ha}}" value="{{ug_forest_overlap_area_ha}}" variant="section" />
                  <CopyTag label="{{ug_net_analysis_area_ha}}" value="{{ug_net_analysis_area_ha}}" variant="section" />
                  <CopyTag label="{{ug_total_biomass_mg}}" value="{{ug_total_biomass_mg}}" variant="section" />
                  <CopyTag label="{{ug_total_volume_m3}}" value="{{ug_total_volume_m3}}" variant="section" />
                  <CopyTag label="{{ug_avg_biomass_mg_per_ha}}" value="{{ug_avg_biomass_mg_per_ha}}" variant="section" />
                  <CopyTag label="{{ug_avg_volume_m3_per_ha}}" value="{{ug_avg_volume_m3_per_ha}}" variant="section" />
                  <CopyTag label="{{ug_land_cover_classes}}" value="{{ug_land_cover_classes}}" variant="section" />
                </div>
              </details>

              {/* Map variable */}
              <div className="mt-2">
                <span className="text-xs text-gray-400 font-mono">{'{{map:usergroup}}'}</span>
              </div>
            </div>
          )}

          <div className="export-section mt-6">
            <h3 className="text-lg font-semibold mb-3">Export</h3>
            <div className="flex gap-3 flex-wrap">
              <button
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 flex items-center gap-2"
                onClick={() => handleExport('csv')}
              >
                <Download size={16} />CSV
              </button>
              <button
                className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 flex items-center gap-2"
                onClick={() => handleExport('geojson')}
              >
                <Download size={16} />GeoJSON
              </button>
              <button
                className="bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700 flex items-center gap-2"
                onClick={() => setShowExportPanel(true)}
              >
                <Image size={16} />PNG
              </button>
            </div>
          </div>
        </>
      )}

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
    </>
  );

  const renderUserListTab = () => (
    <div className="bg-white rounded-lg shadow-lg">
      <HouseholdInfoTab calculationId={calculationId} />
    </div>
  );

  return (
    <div className="user-group-map-tab p-6">
      <h2 className="text-2xl font-bold mb-6">User Group Map</h2>

      <Tabs 
        activeKey={activeSubTab} 
        onChange={setActiveSubTab}
        className="mb-6"
        items={[
          {
            key: 'boundary',
            label: (
              <span className="flex items-center gap-2">
                <Map size={16} />
                User Boundary
              </span>
            ),
            children: renderBoundaryTab(),
          },
          {
            key: 'userlist',
            label: (
              <span className="flex items-center gap-2">
                <Users size={16} />
                User Name List
              </span>
            ),
            children: renderUserListTab(),
          },
        ]}
      />
    </div>
  );
}

export default UserGroupMapTab;
