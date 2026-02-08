import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { forestApi } from '../services/api';
import type { Calculation } from '../types';
import { EditableCell } from '../components/EditableCell';
import { FieldbookTab } from '../components/FieldbookTab';
import { SamplingTab } from '../components/SamplingTab';
import { TreeMappingTab } from '../components/TreeMappingTab';
import BiodiversityTab from '../components/BiodiversityTab';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Import leaflet scale control (built-in)
import 'leaflet/dist/leaflet.css';

// Component to handle auto-zoom to layer and add scale control
function ZoomToLayer({
  geometry,
  setMapInstance,
  orientation
}: {
  geometry: any;
  setMapInstance: (map: L.Map) => void;
  orientation: 'portrait' | 'landscape';
}) {
  const map = useMap();

  useEffect(() => {
    // Store map instance for external use
    setMapInstance(map);

    // Remove any existing scale controls first
    map.eachLayer((layer: any) => {
      if (layer instanceof L.Control.Scale) {
        map.removeControl(layer);
      }
    });

    // Add single scale control (bottom-left)
    const scaleControl = L.control.scale({
      position: 'bottomleft',
      metric: true,
      imperial: false,
      maxWidth: 150
    });
    scaleControl.addTo(map);

    // Auto-zoom to layer on initial load - same behavior for both orientations
    if (geometry) {
      const geoJsonLayer = L.geoJSON(geometry);
      const bounds = geoJsonLayer.getBounds();
      if (bounds.isValid()) {
        // Use same padding for both portrait and landscape for consistent zoom behavior
        const padding = [50, 50] as [number, number];

        map.fitBounds(bounds, { padding });
      }
    }

    // Cleanup function
    return () => {
      if (map && scaleControl) {
        map.removeControl(scaleControl);
      }
    };
  }, [geometry, map, setMapInstance, orientation]);

  return null;
}

// North Arrow Component - Points upward (North)
function NorthArrow() {
  return (
    <div className="absolute top-4 right-4 z-[1000] bg-white rounded-lg shadow-lg p-2 border border-gray-300">
      <div className="flex flex-col items-center">
        <div className="text-sm font-bold text-gray-800 mb-1">N</div>
        <svg width="30" height="50" viewBox="0 0 30 60">
          {/* Arrow shaft */}
          <line x1="15" y1="10" x2="15" y2="50" stroke="#333" strokeWidth="2"/>
          {/* North half (dark/filled) pointing UP */}
          <polygon points="15,5 10,20 15,18 20,20" fill="#1a1a1a" stroke="#000" strokeWidth="1"/>
          {/* South half (white/outline) pointing DOWN */}
          <polygon points="15,18 10,20 15,50 20,20" fill="#ffffff" stroke="#000" strokeWidth="1"/>
        </svg>
      </div>
    </div>
  );
}

export default function CalculationDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [calculation, setCalculation] = useState<Calculation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mapInstance, setMapInstance] = useState<L.Map | null>(null);
  const [mapOrientation, setMapOrientation] = useState<'portrait' | 'landscape'>('portrait');
  const [activeTab, setActiveTab] = useState<'analysis' | 'fieldbook' | 'sampling' | 'treemapping'>('analysis');

  useEffect(() => {
    if (id) {
      loadCalculation();
    }
  }, [id]);

  // Calculate optimal map orientation based on geometry extent
  useEffect(() => {
    if (calculation?.geometry) {
      const geoJsonLayer = L.geoJSON(calculation.geometry);
      const bounds = geoJsonLayer.getBounds();

      if (bounds.isValid()) {
        const width = bounds.getEast() - bounds.getWest();
        const height = bounds.getNorth() - bounds.getSouth();

        // If width > height, use landscape; otherwise portrait
        const orientation = width > height ? 'landscape' : 'portrait';
        setMapOrientation(orientation);
      }
    }
  }, [calculation]);

  const loadCalculation = async () => {
    try {
      setLoading(true);
      console.log('Loading calculation:', id);
      const data = await forestApi.getCalculation(id!);
      console.log('Calculation data loaded:', data);
      console.log('Result data keys:', data.result_data ? Object.keys(data.result_data) : 'null');
      console.log('Blocks:', data.result_data?.blocks);
      setCalculation(data);
    } catch (err: any) {
      console.error('Error loading calculation:', err);
      setError(err.response?.data?.detail || 'Failed to load calculation');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      processing: 'bg-yellow-100 text-yellow-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return styles[status as keyof typeof styles] || 'bg-gray-100 text-gray-800';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const handleZoomToLayer = () => {
    if (calculation?.geometry && mapInstance) {
      const geoJsonLayer = L.geoJSON(calculation.geometry);
      const bounds = geoJsonLayer.getBounds();
      if (bounds.isValid()) {
        // Use same padding for both portrait and landscape for consistent zoom behavior
        const padding = [50, 50] as [number, number];

        mapInstance.fitBounds(bounds, { padding });
      }
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading calculation details...</p>
        </div>
      </div>
    );
  }

  if (error || !calculation) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error || 'Calculation not found'}
        </div>
        <button
          onClick={() => navigate('/my-uploads')}
          className="mt-4 text-green-600 hover:text-green-700"
        >
          ← Back to My Uploads
        </button>
      </div>
    );
  }

  // Handler to save a whole-forest field
  const handleSaveWholeForest = async (key: string, newValue: string) => {
    const numericKeys = [
      'elevation_mean_m', 'elevation_min_m', 'elevation_max_m',
      'temperature_mean_c', 'temperature_min_c',
      'precipitation_mean_mm',
      'agb_total_mg', 'agb_mean_mg_ha', 'carbon_stock_mg',
      'forest_loss_hectares', 'forest_gain_hectares', 'fire_loss_hectares',
      'canopy_mean_m', 'area_hectares', 'area_sqm'
    ];
    const val: any = numericKeys.includes(key) ? parseFloat(newValue) : newValue;
    await forestApi.updateResultData(calculation.id, { [key]: val });
    setCalculation(prev => prev ? {
      ...prev,
      result_data: { ...prev.result_data, [key]: val }
    } : prev);
  };

  // Handler to save a block-level field
  const handleSaveBlock = async (blockIndex: number, key: string, newValue: string) => {
    const numericKeys = [
      'elevation_mean_m', 'elevation_min_m', 'elevation_max_m',
      'temperature_mean_c', 'temperature_min_c',
      'precipitation_mean_mm',
      'agb_total_mg', 'agb_mean_mg_ha', 'carbon_stock_mg',
      'forest_loss_hectares', 'forest_gain_hectares', 'fire_loss_hectares',
      'canopy_mean_m', 'area_hectares', 'area_sqm'
    ];
    const val: any = numericKeys.includes(key) ? parseFloat(newValue) : newValue;
    const updatedBlocks = [...(calculation.result_data?.blocks || [])];
    updatedBlocks[blockIndex] = { ...updatedBlocks[blockIndex], [key]: val };
    await forestApi.updateResultData(calculation.id, { blocks: updatedBlocks });
    setCalculation(prev => prev ? {
      ...prev,
      result_data: { ...prev.result_data, blocks: updatedBlocks }
    } : prev);
  };

  // Handler to save a block extent field
  const handleSaveBlockExtent = async (blockIndex: number, direction: string, newValue: string) => {
    const val = parseFloat(newValue);
    const updatedBlocks = [...(calculation.result_data?.blocks || [])];
    updatedBlocks[blockIndex] = {
      ...updatedBlocks[blockIndex],
      extent: { ...updatedBlocks[blockIndex].extent, [direction]: val }
    };
    await forestApi.updateResultData(calculation.id, { blocks: updatedBlocks });
    setCalculation(prev => prev ? {
      ...prev,
      result_data: { ...prev.result_data, blocks: updatedBlocks }
    } : prev);
  };

  // Handler to save whole forest extent field
  const handleSaveWholeExtent = async (direction: string, newValue: string) => {
    const val = parseFloat(newValue);
    const updatedExtent = { ...calculation.result_data?.whole_forest_extent, [direction]: val };
    await forestApi.updateResultData(calculation.id, { whole_forest_extent: updatedExtent });
    setCalculation(prev => prev ? {
      ...prev,
      result_data: { ...prev.result_data, whole_forest_extent: updatedExtent }
    } : prev);
  };

  // Handler to save whole forest percentages
  const handleSaveWholePercentages = async (key: string, className: string, newValue: string) => {
    const val = parseFloat(newValue);
    const updatedPercentages = { ...calculation.result_data?.[key], [className]: val };
    await forestApi.updateResultData(calculation.id, { [key]: updatedPercentages });
    setCalculation(prev => prev ? {
      ...prev,
      result_data: { ...prev.result_data, [key]: updatedPercentages }
    } : prev);
  };

  // Handler to save block percentages
  const handleSaveBlockPercentages = async (blockIndex: number, key: string, className: string, newValue: string) => {
    const val = parseFloat(newValue);
    const updatedBlocks = [...(calculation.result_data?.blocks || [])];
    updatedBlocks[blockIndex] = {
      ...updatedBlocks[blockIndex],
      [key]: { ...updatedBlocks[blockIndex][key], [className]: val }
    };
    await forestApi.updateResultData(calculation.id, { blocks: updatedBlocks });
    setCalculation(prev => prev ? {
      ...prev,
      result_data: { ...prev.result_data, blocks: updatedBlocks }
    } : prev);
  };

  // Extract blocks from result_data
  const blocks = calculation.result_data?.blocks || [];
  const totalBlocks = calculation.result_data?.total_blocks || 1;
  const processingInfo = calculation.result_data?.processing_info || {};

  // Debug logging
  console.log('Rendering CalculationDetail:', {
    calculationId: calculation.id,
    forestName: calculation.forest_name,
    hasResultData: !!calculation.result_data,
    blocksCount: blocks.length,
    totalBlocks,
    resultDataKeys: calculation.result_data ? Object.keys(calculation.result_data) : []
  });

  return (
    <div className="max-w-7xl mx-auto py-8 px-4">
      <div className="mb-6">
        <button
          onClick={() => navigate('/my-uploads')}
          className="text-green-600 hover:text-green-700 flex items-center"
        >
          <svg className="w-5 h-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to My Uploads
        </button>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {/* Header Section */}
        <div className="px-6 py-5 border-b border-gray-200 bg-gradient-to-r from-green-50 to-green-100">
          <h1 className="text-3xl font-bold text-gray-900">{calculation.forest_name}</h1>
          <div className="mt-2 flex items-center text-sm text-gray-600">
            <svg className="w-4 h-4 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span>Uploaded: {formatDate(calculation.created_at)}</span>
            <span className="mx-2">•</span>
            <span className="font-medium">{calculation.uploaded_filename}</span>
          </div>
          {totalBlocks > 1 && (
            <div className="mt-2 text-sm text-green-700 font-medium">
              {totalBlocks} Blocks {processingInfo.partitioned && '(Partitioned using division lines)'}
            </div>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px">
            <button
              onClick={() => setActiveTab('analysis')}
              className={`px-6 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'analysis'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Analysis
            </button>
            <button
              onClick={() => setActiveTab('fieldbook')}
              className={`px-6 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'fieldbook'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Fieldbook
            </button>
            <button
              onClick={() => setActiveTab('sampling')}
              className={`px-6 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'sampling'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Sampling
            </button>
            <button
              onClick={() => setActiveTab('treemapping')}
              className={`px-6 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'treemapping'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Tree Mapping
            </button>
            <button
              onClick={() => setActiveTab('biodiversity')}
              className={`px-6 py-3 border-b-2 font-medium text-sm ${
                activeTab === 'biodiversity'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Biodiversity
            </button>
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'fieldbook' && (
          <div className="p-6">
            <FieldbookTab calculationId={calculation.id} />
          </div>
        )}

        {activeTab === 'sampling' && (
          <div className="p-6">
            <SamplingTab calculationId={calculation.id} />
          </div>
        )}

        {activeTab === 'treemapping' && (
          <div className="p-6">
            <TreeMappingTab calculationId={calculation.id} />
          </div>
        )}

        {activeTab === 'biodiversity' && (
          <div className="p-6">
            <BiodiversityTab calculationId={calculation.id} />
          </div>
        )}

        {/* Whole Forest Analysis Section */}
        {activeTab === 'analysis' && (
          <div className="p-6 border-t border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Whole Forest Analysis</h2>
          <div className="border border-gray-300 rounded-lg bg-white shadow-sm">
            {/* Forest Header */}
            <div className="bg-gradient-to-r from-blue-50 to-blue-100 px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-bold text-gray-900">
                {calculation.forest_name} - Complete Forest Summary
              </h3>
              <p className="text-sm text-gray-600 mt-1">
                Total Area: {calculation.result_data?.area_hectares?.toFixed(2)} hectares
                {totalBlocks > 1 && ` (${totalBlocks} blocks)`}
              </p>
            </div>

            {/* Forest Analysis Table */}
            <div className="p-6">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Parameter</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {/* Area */}
                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Total Area</td>
                    <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                      {calculation.result_data?.area_hectares?.toFixed(2)} ha
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {(calculation.result_data?.area_sqm || 0).toLocaleString()} m²
                    </td>
                  </tr>

                  {/* Extent */}
                  {calculation.result_data?.whole_forest_extent && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Extent</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.whole_forest_extent.N} displayValue={"N: " + calculation.result_data.whole_forest_extent.N.toFixed(7)} onSave={(v) => handleSaveWholeExtent('N', v)} className="font-mono" />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600 font-mono">
                        <EditableCell value={calculation.result_data.whole_forest_extent.S} displayValue={"S: " + calculation.result_data.whole_forest_extent.S.toFixed(7)} onSave={(v) => handleSaveWholeExtent('S', v)} className="font-mono" />{", "}
                        <EditableCell value={calculation.result_data.whole_forest_extent.E} displayValue={"E: " + calculation.result_data.whole_forest_extent.E.toFixed(7)} onSave={(v) => handleSaveWholeExtent('E', v)} className="font-mono" />{", "}
                        <EditableCell value={calculation.result_data.whole_forest_extent.W} displayValue={"W: " + calculation.result_data.whole_forest_extent.W.toFixed(7)} onSave={(v) => handleSaveWholeExtent('W', v)} className="font-mono" />
                      </td>
                    </tr>
                  )}

                  {/* Elevation */}
                  {calculation.result_data?.elevation_mean_m !== undefined && calculation.result_data?.elevation_mean_m !== null && calculation.result_data?.elevation_mean_m > -32000 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Elevation</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.elevation_mean_m} displayValue={calculation.result_data.elevation_mean_m.toFixed(1) + " m (mean)"} onSave={(v) => handleSaveWholeForest('elevation_mean_m', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        Min: <EditableCell value={calculation.result_data.elevation_min_m} displayValue={calculation.result_data.elevation_min_m?.toFixed(0)} onSave={(v) => handleSaveWholeForest('elevation_min_m', v)} />{" m, Max: "}
                        <EditableCell value={calculation.result_data.elevation_max_m} displayValue={calculation.result_data.elevation_max_m?.toFixed(0)} onSave={(v) => handleSaveWholeForest('elevation_max_m', v)} />{" m"}
                      </td>
                    </tr>
                  )}

                  {/* Slope */}
                  {calculation.result_data?.slope_dominant_class && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Slope</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                        <EditableCell value={calculation.result_data.slope_dominant_class} onSave={(v) => handleSaveWholeForest('slope_dominant_class', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.slope_percentages &&
                          Object.entries(calculation.result_data.slope_percentages).map(([cls, pct]: [string, any], idx: number) => (
                            <span key={cls}>
                              {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('slope_percentages', cls, v)} className="inline" />
                              {idx < Object.keys(calculation.result_data.slope_percentages).length - 1 && ', '}
                            </span>
                          ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Aspect */}
                  {calculation.result_data?.aspect_dominant && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Aspect (Orientation)</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize font-semibold">
                        <EditableCell value={calculation.result_data.aspect_dominant} onSave={(v) => handleSaveWholeForest('aspect_dominant', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.aspect_percentages &&
                          Object.entries(calculation.result_data.aspect_percentages).map(([dir, pct]: [string, any], idx: number) => (
                            <span key={dir}>
                              {dir}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('aspect_percentages', dir, v)} className="inline" />
                              {idx < Object.keys(calculation.result_data.aspect_percentages).length - 1 && ', '}
                            </span>
                          ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Canopy Height */}
                  {calculation.result_data?.canopy_dominant_class && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Canopy Structure</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                        <EditableCell value={calculation.result_data.canopy_dominant_class} onSave={(v) => handleSaveWholeForest('canopy_dominant_class', v)} />
                        {calculation.result_data?.canopy_mean_m !== undefined && (
                          <span className="text-xs text-gray-500 ml-2">
                            (<EditableCell value={calculation.result_data.canopy_mean_m} displayValue={calculation.result_data.canopy_mean_m.toFixed(1)} onSave={(v) => handleSaveWholeForest('canopy_mean_m', v)} />m avg)
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.canopy_percentages &&
                          Object.entries(calculation.result_data.canopy_percentages).map(([cls, pct]: [string, any], idx: number) => (
                            <span key={cls}>
                              {cls.replace('_', ' ')}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('canopy_percentages', cls, v)} className="inline" />
                              {idx < Object.keys(calculation.result_data.canopy_percentages).length - 1 && ', '}
                            </span>
                          ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Above Ground Biomass */}
                  {calculation.result_data?.agb_total_mg !== undefined && calculation.result_data?.agb_total_mg !== null && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Above Ground Biomass (AGB)</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.agb_total_mg} displayValue={calculation.result_data.agb_total_mg.toLocaleString() + " Mg"} onSave={(v) => handleSaveWholeForest('agb_total_mg', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        <EditableCell value={calculation.result_data.agb_mean_mg_ha} displayValue={calculation.result_data.agb_mean_mg_ha?.toFixed(2)} onSave={(v) => handleSaveWholeForest('agb_mean_mg_ha', v)} /> Mg/ha (mean per hectare)
                      </td>
                    </tr>
                  )}

                  {/* Carbon Stock */}
                  {calculation.result_data?.carbon_stock_mg !== undefined && calculation.result_data?.carbon_stock_mg !== null && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Carbon Stock</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.carbon_stock_mg} displayValue={calculation.result_data.carbon_stock_mg.toLocaleString() + " Mg"} onSave={(v) => handleSaveWholeForest('carbon_stock_mg', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        50% of total biomass
                      </td>
                    </tr>
                  )}

                  {/* Forest Health */}
                  {calculation.result_data?.forest_health_dominant && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Health</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                        <EditableCell value={calculation.result_data.forest_health_dominant} onSave={(v) => handleSaveWholeForest('forest_health_dominant', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.forest_health_percentages &&
                          Object.entries(calculation.result_data.forest_health_percentages).map(([cls, pct]: [string, any], idx: number) => (
                            <span key={cls}>
                              {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('forest_health_percentages', cls, v)} className="inline" />
                              {idx < Object.keys(calculation.result_data.forest_health_percentages).length - 1 && ', '}
                            </span>
                          ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Forest Type */}
                  {calculation.result_data?.forest_type_dominant && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Type</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                        <EditableCell value={calculation.result_data.forest_type_dominant} onSave={(v) => handleSaveWholeForest('forest_type_dominant', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.forest_type_percentages &&
                          Object.entries(calculation.result_data.forest_type_percentages).map(([type, pct]: [string, any], idx: number) => (
                            <span key={type}>
                              {type}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('forest_type_percentages', type, v)} className="inline" />
                              {idx < Object.keys(calculation.result_data.forest_type_percentages).length - 1 && ', '}
                            </span>
                          ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Land Cover */}
                  {calculation.result_data?.landcover_dominant && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Land Cover</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                        <EditableCell value={calculation.result_data.landcover_dominant} onSave={(v) => handleSaveWholeForest('landcover_dominant', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.landcover_percentages &&
                          Object.entries(calculation.result_data.landcover_percentages).map(([cover, pct]: [string, any], idx: number) => (
                            <span key={cover}>
                              {cover}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('landcover_percentages', cover, v)} className="inline" />
                              {idx < Object.keys(calculation.result_data.landcover_percentages).length - 1 && ', '}
                            </span>
                          ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Forest Loss */}
                  {calculation.result_data?.forest_loss_hectares !== undefined && calculation.result_data?.forest_loss_hectares !== null && calculation.result_data?.forest_loss_hectares >= 0 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Loss (2001-2023)</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.forest_loss_hectares} displayValue={calculation.result_data.forest_loss_hectares.toFixed(2) + " ha"} onSave={(v) => handleSaveWholeForest('forest_loss_hectares', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.forest_loss_by_year &&
                          Object.entries(calculation.result_data.forest_loss_by_year)
                            .sort(([yearA], [yearB]) => parseInt(yearA) - parseInt(yearB))
                            .map(([year, ha]: [string, any], idx: number, arr: any[]) => (
                              <span key={year}>
                                {year}: <EditableCell value={ha} displayValue={ha.toFixed(2) + " ha"} onSave={(v) => handleSaveWholePercentages('forest_loss_by_year', year, v)} className="inline" />
                                {idx < arr.length - 1 && ', '}
                              </span>
                            ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Forest Gain */}
                  {calculation.result_data?.forest_gain_hectares !== undefined && calculation.result_data?.forest_gain_hectares !== null && calculation.result_data?.forest_gain_hectares >= 0 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Gain (2000-2012)</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.forest_gain_hectares} displayValue={calculation.result_data.forest_gain_hectares.toFixed(2) + " ha"} onSave={(v) => handleSaveWholeForest('forest_gain_hectares', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        Net forest gain over 12-year period
                      </td>
                    </tr>
                  )}

                  {/* Fire Loss */}
                  {calculation.result_data?.fire_loss_hectares !== undefined && calculation.result_data?.fire_loss_hectares !== null && calculation.result_data?.fire_loss_hectares >= 0 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Fire Loss (2001-2023)</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.fire_loss_hectares} displayValue={calculation.result_data.fire_loss_hectares.toFixed(2) + " ha"} onSave={(v) => handleSaveWholeForest('fire_loss_hectares', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.fire_loss_by_year &&
                          Object.entries(calculation.result_data.fire_loss_by_year)
                            .sort(([yearA], [yearB]) => parseInt(yearA) - parseInt(yearB))
                            .map(([year, ha]: [string, any], idx: number, arr: any[]) => (
                              <span key={year}>
                                {year}: <EditableCell value={ha} displayValue={ha.toFixed(2) + " ha"} onSave={(v) => handleSaveWholePercentages('fire_loss_by_year', year, v)} className="inline" />
                                {idx < arr.length - 1 && ', '}
                              </span>
                            ))
                        }
                      </td>
                    </tr>
                  )}

                  {/* Temperature */}
                  {calculation.result_data?.temperature_mean_c !== undefined && calculation.result_data?.temperature_mean_c !== null && calculation.result_data?.temperature_mean_c > -100 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Temperature</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.temperature_mean_c} displayValue={calculation.result_data.temperature_mean_c.toFixed(1) + " °C (mean)"} onSave={(v) => handleSaveWholeForest('temperature_mean_c', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        Min (coldest month): <EditableCell value={calculation.result_data.temperature_min_c} displayValue={calculation.result_data.temperature_min_c?.toFixed(1)} onSave={(v) => handleSaveWholeForest('temperature_min_c', v)} />{" °C"}
                      </td>
                    </tr>
                  )}

                  {/* Precipitation */}
                  {calculation.result_data?.precipitation_mean_mm !== undefined && calculation.result_data?.precipitation_mean_mm !== null && calculation.result_data?.precipitation_mean_mm >= 0 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Precipitation</td>
                      <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                        <EditableCell value={calculation.result_data.precipitation_mean_mm} displayValue={calculation.result_data.precipitation_mean_mm.toFixed(0) + " mm/year"} onSave={(v) => handleSaveWholeForest('precipitation_mean_mm', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        Annual total precipitation
                      </td>
                    </tr>
                  )}

                  {/* Soil Texture */}
                  {calculation.result_data?.soil_texture && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Soil Texture</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                        <EditableCell value={calculation.result_data.soil_texture} onSave={(v) => handleSaveWholeForest('soil_texture', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.soil_properties &&
                          Object.entries(calculation.result_data?.soil_properties)
                            .map(([prop, val]: [string, any]) => `${prop}: ${val}`)
                            .join(', ')
                        }
                      </td>
                    </tr>
                  )}

                  {/* Administrative Location */}
                  <tr className="bg-gray-100">
                    <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                      Administrative Location
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Province</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_province} onSave={(v) => handleSaveWholeForest('whole_province', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">District</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_district} onSave={(v) => handleSaveWholeForest('whole_district', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Municipality</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_municipality} onSave={(v) => handleSaveWholeForest('whole_municipality', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Ward</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_ward} onSave={(v) => handleSaveWholeForest('whole_ward', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Watershed</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_watershed} onSave={(v) => handleSaveWholeForest('whole_watershed', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Major River Basin</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_major_river_basin} onSave={(v) => handleSaveWholeForest('whole_major_river_basin', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  {/* Geology */}
                  {calculation.result_data?.whole_geology_percentages && Object.keys(calculation.result_data.whole_geology_percentages).length > 0 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Geology</td>
                      <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                        {Object.entries(calculation.result_data.whole_geology_percentages).map(([cls, pct]: [string, any], idx: number) => (
                          <span key={cls}>
                            {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('whole_geology_percentages', cls, v)} className="inline" />
                            {idx < Object.keys(calculation.result_data.whole_geology_percentages).length - 1 && ', '}
                          </span>
                        ))}
                      </td>
                    </tr>
                  )}

                  {/* Access */}
                  {calculation.result_data?.whole_access_info && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Access</td>
                      <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                        <EditableCell value={calculation.result_data.whole_access_info} onSave={(v) => handleSaveWholeForest('whole_access_info', v)} />
                      </td>
                    </tr>
                  )}

                  {/* Nearby Features */}
                  <tr className="bg-gray-100">
                    <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                      Natural Features (within 100m)
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features North</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_north || ''} onSave={(v) => handleSaveWholeForest('whole_features_north', v)} />
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features East</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_east || ''} onSave={(v) => handleSaveWholeForest('whole_features_east', v)} />
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features South</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_south || ''} onSave={(v) => handleSaveWholeForest('whole_features_south', v)} />
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features West</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_west || ''} onSave={(v) => handleSaveWholeForest('whole_features_west', v)} />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Detailed Block-wise Analysis */}
          {blocks.length > 0 && (
          <div className="p-6 border-t border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Detailed Block-wise Analysis</h2>
            <div className="space-y-6">
              {blocks.map((block: any, index: number) => (
                <div key={index} className="border border-gray-300 rounded-lg bg-white shadow-sm">
                  {/* Block Header */}
                  <div className="bg-gradient-to-r from-green-50 to-green-100 px-6 py-4 border-b border-gray-200">
                    <h3 className="text-lg font-bold text-gray-900">
                      Block #{index + 1}: {block.block_name}
                    </h3>
                    <p className="text-sm text-gray-600 mt-1">
                      Area: {parseFloat(block.area_hectares || 0).toFixed(2)} hectares
                    </p>
                  </div>

                  {/* Block Analysis Table */}
                  <div className="p-6">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Parameter</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Details</th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {/* Extent */}
                        {block.extent && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Extent</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.extent.N} displayValue={"N: " + block.extent.N.toFixed(7)} onSave={(v) => handleSaveBlockExtent(index, 'N', v)} className="font-mono" />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600 font-mono">
                              <div><EditableCell value={block.extent.S} displayValue={"S: " + block.extent.S.toFixed(7)} onSave={(v) => handleSaveBlockExtent(index, 'S', v)} className="font-mono" /></div>
                              <div><EditableCell value={block.extent.E} displayValue={"E: " + block.extent.E.toFixed(7)} onSave={(v) => handleSaveBlockExtent(index, 'E', v)} className="font-mono" /></div>
                              <div><EditableCell value={block.extent.W} displayValue={"W: " + block.extent.W.toFixed(7)} onSave={(v) => handleSaveBlockExtent(index, 'W', v)} className="font-mono" /></div>
                            </td>
                          </tr>
                        )}

                        {/* Elevation */}
                        {block.elevation_mean_m !== undefined && block.elevation_mean_m !== null && block.elevation_mean_m > -32000 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Elevation</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.elevation_mean_m} displayValue={block.elevation_mean_m.toFixed(1) + " m (mean)"} onSave={(v) => handleSaveBlock(index, 'elevation_mean_m', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              Min: <EditableCell value={block.elevation_min_m} displayValue={block.elevation_min_m?.toFixed(0)} onSave={(v) => handleSaveBlock(index, 'elevation_min_m', v)} />{" m, Max: "}
                              <EditableCell value={block.elevation_max_m} displayValue={block.elevation_max_m?.toFixed(0)} onSave={(v) => handleSaveBlock(index, 'elevation_max_m', v)} />{" m"}
                            </td>
                          </tr>
                        )}

                        {/* Slope */}
                        {block.slope_dominant_class && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Slope</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                              <EditableCell value={block.slope_dominant_class} onSave={(v) => handleSaveBlock(index, 'slope_dominant_class', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.slope_percentages &&
                                Object.entries(block.slope_percentages).map(([cls, pct]: [string, any], idx: number) => (
                                  <span key={cls}>
                                    {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'slope_percentages', cls, v)} className="inline" />
                                    {idx < Object.keys(block.slope_percentages).length - 1 && ', '}
                                  </span>
                                ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Aspect */}
                        {block.aspect_dominant && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Aspect</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize font-semibold">
                              <EditableCell value={block.aspect_dominant} onSave={(v) => handleSaveBlock(index, 'aspect_dominant', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.aspect_percentages &&
                                Object.entries(block.aspect_percentages).map(([dir, pct]: [string, any], idx: number) => (
                                  <span key={dir}>
                                    {dir}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'aspect_percentages', dir, v)} className="inline" />
                                    {idx < Object.keys(block.aspect_percentages).length - 1 && ', '}
                                  </span>
                                ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Canopy Height */}
                        {block.canopy_dominant_class && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Canopy Structure</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                              <EditableCell value={block.canopy_dominant_class} onSave={(v) => handleSaveBlock(index, 'canopy_dominant_class', v)} />
                              {block.canopy_mean_m !== undefined && (
                                <span className="text-xs text-gray-500 ml-2">
                                  (<EditableCell value={block.canopy_mean_m} displayValue={block.canopy_mean_m.toFixed(1)} onSave={(v) => handleSaveBlock(index, 'canopy_mean_m', v)} />m avg)
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.canopy_percentages &&
                                Object.entries(block.canopy_percentages).map(([cls, pct]: [string, any], idx: number) => (
                                  <span key={cls}>
                                    {cls.replace('_', ' ')}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'canopy_percentages', cls, v)} className="inline" />
                                    {idx < Object.keys(block.canopy_percentages).length - 1 && ', '}
                                  </span>
                                ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Above Ground Biomass */}
                        {block.agb_total_mg !== undefined && block.agb_total_mg !== null && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Above Ground Biomass</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.agb_total_mg} displayValue={block.agb_total_mg.toLocaleString() + " Mg"} onSave={(v) => handleSaveBlock(index, 'agb_total_mg', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              <EditableCell value={block.agb_mean_mg_ha} displayValue={block.agb_mean_mg_ha?.toFixed(2)} onSave={(v) => handleSaveBlock(index, 'agb_mean_mg_ha', v)} /> Mg/ha (mean per hectare)
                            </td>
                          </tr>
                        )}

                        {/* Carbon Stock */}
                        {block.carbon_stock_mg !== undefined && block.carbon_stock_mg !== null && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Carbon Stock</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.carbon_stock_mg} displayValue={block.carbon_stock_mg.toLocaleString() + " Mg"} onSave={(v) => handleSaveBlock(index, 'carbon_stock_mg', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              50% of total biomass
                            </td>
                          </tr>
                        )}

                        {/* Forest Health */}
                        {block.forest_health_dominant && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Health</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                              <EditableCell value={block.forest_health_dominant} onSave={(v) => handleSaveBlock(index, 'forest_health_dominant', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.forest_health_percentages &&
                                Object.entries(block.forest_health_percentages).map(([cls, pct]: [string, any], idx: number) => (
                                  <span key={cls}>
                                    {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'forest_health_percentages', cls, v)} className="inline" />
                                    {idx < Object.keys(block.forest_health_percentages).length - 1 && ', '}
                                  </span>
                                ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Forest Type */}
                        {block.forest_type_dominant && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Type</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                              <EditableCell value={block.forest_type_dominant} onSave={(v) => handleSaveBlock(index, 'forest_type_dominant', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.forest_type_percentages &&
                                Object.entries(block.forest_type_percentages).map(([type, pct]: [string, any], idx: number) => (
                                  <span key={type}>
                                    {type}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'forest_type_percentages', type, v)} className="inline" />
                                    {idx < Object.keys(block.forest_type_percentages).length - 1 && ', '}
                                  </span>
                                ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Land Cover */}
                        {block.landcover_dominant && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Land Cover</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                              <EditableCell value={block.landcover_dominant} onSave={(v) => handleSaveBlock(index, 'landcover_dominant', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.landcover_percentages &&
                                Object.entries(block.landcover_percentages).map(([cover, pct]: [string, any], idx: number) => (
                                  <span key={cover}>
                                    {cover}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'landcover_percentages', cover, v)} className="inline" />
                                    {idx < Object.keys(block.landcover_percentages).length - 1 && ', '}
                                  </span>
                                ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Forest Loss */}
                        {block.forest_loss_hectares !== undefined && block.forest_loss_hectares !== null && block.forest_loss_hectares >= 0 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Loss (2001-2023)</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.forest_loss_hectares} displayValue={block.forest_loss_hectares.toFixed(2) + " ha"} onSave={(v) => handleSaveBlock(index, 'forest_loss_hectares', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.forest_loss_by_year &&
                                Object.entries(block.forest_loss_by_year)
                                  .sort(([yearA], [yearB]) => parseInt(yearA) - parseInt(yearB))
                                  .map(([year, ha]: [string, any], idx: number, arr: any[]) => (
                                    <span key={year}>
                                      {year}: <EditableCell value={ha} displayValue={ha.toFixed(2) + " ha"} onSave={(v) => handleSaveBlockPercentages(index, 'forest_loss_by_year', year, v)} className="inline" />
                                      {idx < arr.length - 1 && ', '}
                                    </span>
                                  ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Forest Gain */}
                        {block.forest_gain_hectares !== undefined && block.forest_gain_hectares !== null && block.forest_gain_hectares >= 0 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Forest Gain (2000-2012)</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.forest_gain_hectares} displayValue={block.forest_gain_hectares.toFixed(2) + " ha"} onSave={(v) => handleSaveBlock(index, 'forest_gain_hectares', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              Net forest gain over 12-year period
                            </td>
                          </tr>
                        )}

                        {/* Fire Loss */}
                        {block.fire_loss_hectares !== undefined && block.fire_loss_hectares !== null && block.fire_loss_hectares >= 0 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Fire Loss (2001-2023)</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.fire_loss_hectares} displayValue={block.fire_loss_hectares.toFixed(2) + " ha"} onSave={(v) => handleSaveBlock(index, 'fire_loss_hectares', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.fire_loss_by_year &&
                                Object.entries(block.fire_loss_by_year)
                                  .sort(([yearA], [yearB]) => parseInt(yearA) - parseInt(yearB))
                                  .map(([year, ha]: [string, any], idx: number, arr: any[]) => (
                                    <span key={year}>
                                      {year}: <EditableCell value={ha} displayValue={ha.toFixed(2) + " ha"} onSave={(v) => handleSaveBlockPercentages(index, 'fire_loss_by_year', year, v)} className="inline" />
                                      {idx < arr.length - 1 && ', '}
                                    </span>
                                  ))
                              }
                            </td>
                          </tr>
                        )}

                        {/* Temperature */}
                        {block.temperature_mean_c !== undefined && block.temperature_mean_c !== null && block.temperature_mean_c > -100 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Temperature</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.temperature_mean_c} displayValue={block.temperature_mean_c.toFixed(1) + " °C (mean)"} onSave={(v) => handleSaveBlock(index, 'temperature_mean_c', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              Min (coldest month): <EditableCell value={block.temperature_min_c} displayValue={block.temperature_min_c?.toFixed(1)} onSave={(v) => handleSaveBlock(index, 'temperature_min_c', v)} />{" °C"}
                            </td>
                          </tr>
                        )}

                        {/* Precipitation */}
                        {block.precipitation_mean_mm !== undefined && block.precipitation_mean_mm !== null && block.precipitation_mean_mm >= 0 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Precipitation</td>
                            <td className="px-4 py-3 text-sm text-gray-900 font-mono">
                              <EditableCell value={block.precipitation_mean_mm} displayValue={block.precipitation_mean_mm.toFixed(0) + " mm/year"} onSave={(v) => handleSaveBlock(index, 'precipitation_mean_mm', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              Annual total precipitation
                            </td>
                          </tr>
                        )}

                        {/* Soil Texture */}
                        {block.soil_texture && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Soil Texture</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                              <EditableCell value={block.soil_texture} onSave={(v) => handleSaveBlock(index, 'soil_texture', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.soil_properties &&
                                Object.entries(block.soil_properties)
                                  .map(([prop, val]: [string, any]) => `${prop}: ${val}`)
                                  .join(', ')
                              }
                            </td>
                          </tr>
                        )}

                        {/* Administrative Location */}
                        <tr className="bg-gray-100">
                          <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                            Administrative Location
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Province</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.province} onSave={(v) => handleSaveBlock(index, 'province', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">District</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.district} onSave={(v) => handleSaveBlock(index, 'district', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Municipality</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.municipality} onSave={(v) => handleSaveBlock(index, 'municipality', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Ward</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.ward} onSave={(v) => handleSaveBlock(index, 'ward', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Watershed</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.watershed} onSave={(v) => handleSaveBlock(index, 'watershed', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Major River Basin</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.major_river_basin} onSave={(v) => handleSaveBlock(index, 'major_river_basin', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        {/* Geology */}
                        {block.geology_percentages && Object.keys(block.geology_percentages).length > 0 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Geology</td>
                            <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                              {Object.entries(block.geology_percentages).map(([cls, pct]: [string, any], idx: number) => (
                                <span key={cls}>
                                  {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'geology_percentages', cls, v)} className="inline" />
                                  {idx < Object.keys(block.geology_percentages).length - 1 && ', '}
                                </span>
                              ))}
                            </td>
                          </tr>
                        )}

                        {/* Access */}
                        {block.access_info && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Access</td>
                            <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                              <EditableCell value={block.access_info} onSave={(v) => handleSaveBlock(index, 'access_info', v)} />
                            </td>
                          </tr>
                        )}

                        {/* Nearby Features */}
                        <tr className="bg-gray-100">
                          <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                            Natural Features (within 100m)
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features North</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_north || ''} onSave={(v) => handleSaveBlock(index, 'features_north', v)} />
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features East</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_east || ''} onSave={(v) => handleSaveBlock(index, 'features_east', v)} />
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features South</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_south || ''} onSave={(v) => handleSaveBlock(index, 'features_south', v)} />
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features West</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_west || ''} onSave={(v) => handleSaveBlock(index, 'features_west', v)} />
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </div>
          )}

          {/* Additional Information */}
          <div className="px-6 pb-6">
          <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-3">
            <div>
              <dt className="text-sm font-medium text-gray-500">Status</dt>
              <dd className="mt-1">
                <span
                  className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadge(
                    calculation.status
                  )}`}
                >
                  {calculation.status}
                </span>
              </dd>
            </div>

            {calculation.processing_time_seconds && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Processing Time</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {calculation.processing_time_seconds} seconds
                </dd>
              </div>
            )}

            {calculation.completed_at && (
              <div>
                <dt className="text-sm font-medium text-gray-500">Completed At</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDate(calculation.completed_at)}
                </dd>
              </div>
            )}

            {calculation.error_message && (
              <div className="sm:col-span-3">
                <dt className="text-sm font-medium text-gray-500">Error Message</dt>
                <dd className="mt-1 text-sm text-red-600">{calculation.error_message}</dd>
              </div>
            )}
          </dl>
          </div>

          {/* Map Section */}
          {calculation.geometry && (
          <div className="px-6 pb-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold text-gray-900">
                Boundary Map (A5 - {mapOrientation === 'portrait' ? 'Portrait' : 'Landscape'})
              </h2>
              <button
                onClick={handleZoomToLayer}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors shadow-sm"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                </svg>
                Zoom to Layer
              </button>
            </div>
            <div
              className="rounded-lg overflow-hidden border-2 border-gray-400 shadow-lg mx-auto relative"
              style={{
                width: mapOrientation === 'portrait' ? '560px' : '794px',
                height: mapOrientation === 'portrait' ? '794px' : '560px'
              }}
            >
              <MapContainer
                center={[27.7, 85.3]}
                zoom={7}
                style={{ height: '100%', width: '100%' }}
                zoomControl={true}
                attributionControl={true}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <GeoJSON
                  data={calculation.geometry}
                  style={{
                    color: '#059669',
                    weight: 3,
                    fillColor: '#34d399',
                    fillOpacity: 0.3
                  }}
                />
                <ZoomToLayer
                  geometry={calculation.geometry}
                  setMapInstance={setMapInstance}
                  orientation={mapOrientation}
                />
              </MapContainer>
              <NorthArrow />
            </div>
            <div className="mt-3 text-center">
              <p className="text-sm text-gray-500">
                A5 Map Size: {mapOrientation === 'portrait' ? '560px × 794px (148mm × 210mm)' : '794px × 560px (210mm × 148mm)'} at 96 DPI
                {totalBlocks > 1 && (
                  <span className="block mt-1 italic">
                    Map shows all {totalBlocks} blocks combined
                  </span>
                )}
              </p>
            </div>
          </div>
          )}

          {/* Processing Info Section - Only show if partitioned */}
          {processingInfo.partitioned && (
          <div className="px-6 pb-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">Processing Information</h2>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-3" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <div className="flex-1">
                  <p className="text-sm text-blue-800 font-medium">Compartment Boundary Partitioning Applied</p>
                  <p className="mt-1 text-sm text-blue-700">
                    The outer boundary was partitioned using {processingInfo.partition_info?.division_lines_used || 0} division lines,
                    creating {processingInfo.partition_info?.blocks_created || 0} separate forest blocks.
                  </p>
                </div>
              </div>
            </div>
          </div>
          )}
        </div>
        )}
      </div>
    </div>
  );
}
