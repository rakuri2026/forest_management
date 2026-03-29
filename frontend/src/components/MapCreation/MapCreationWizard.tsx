import React, { useState, useRef } from 'react';
import { MapContainer, GeoJSON, Marker } from 'react-leaflet';
import L from 'leaflet';
import GPSPointInput from './GPSPointInput';
import PolygonCreator from './PolygonCreator';
import BlockSplitterPro from './BlockSplitterPro';
import SubAreaManager from './SubAreaManager';
import BaseMapSelector from './BaseMapSelector';
import LocationSearch from './LocationSearch';
import HelpTooltip, { helpTexts } from '../HelpTooltip';
import { GPSPoint } from '../../utils/gpsUtils';
import { formatArea, calculateAreaHectares, cleanAndValidateBlocks } from '../../utils/geometryValidation';
import { getGeometryCenter } from '../../utils/geometryHelpers';

interface Block {
  id: string;
  name: string;
  geometry: any;
  area: number;
}

interface SubArea {
  id: string;
  name: string;
  category: string;
  geometry: any;
  area: number;
  blockId?: string;
  blockName?: string;
}

interface MapCreationWizardProps {
  forestName: string;
  onComplete: (data: {
    outerBoundary: any;
    gpsPoints: GPSPoint[];
    blocks: Block[];
    subAreas: SubArea[];
  }) => void;
  onCancel: () => void;
  isProcessing?: boolean;
  initialPolygon?: any;  // For resuming drafts
  initialDraftId?: string;  // Draft ID to update when saving
  isDraft?: boolean;    // For drafts
}

const MapCreationWizard: React.FC<MapCreationWizardProps> = ({
  forestName,
  onComplete,
  onCancel,
  isProcessing = false,
  initialPolygon,
  initialDraftId,
  isDraft = false,
}) => {
  const [currentStep, setCurrentStep] = useState<number>(isDraft ? 2 : 1);  // Skip GPS points for drafts

  // Step 1: GPS Points (optional)
  const [gpsPoints, setGpsPoints] = useState<GPSPoint[]>([]);

  // Step 2: Outer Boundary - initialize from draft if available
  const [outerBoundary, setOuterBoundary] = useState<any>(initialPolygon || null);

  // Step 3: Blocks
  const [blocks, setBlocks] = useState<Block[]>([]);

  // Step 4: Sub-areas (optional)
  const [subAreas, setSubAreas] = useState<SubArea[]>([]);

  // Draft state - initialize from initialDraftId if resuming
  const [draftId, setDraftId] = useState<string | null>(initialDraftId || null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  
  // Edited block names (for review step renaming)
  const [editedBlockNames, setEditedBlockNames] = useState<Record<string, string>>({});

  // Location search state
  const polygonCreatorRef = useRef<any>(null);
  const [wardBoundaryGeometry, setWardBoundaryGeometry] = useState<any>(null);
  const [showWardBoundary, setShowWardBoundary] = useState(false);

  const steps = [
    { number: 1, name: 'GPS Points', optional: true },
    { number: 2, name: 'Outer Boundary', optional: false },
    { number: 3, name: 'Forest Blocks', optional: true }, // Now optional!
    { number: 4, name: 'Sub-areas', optional: true },
    { number: 5, name: 'Review', optional: false },
  ];

  // Auto-create default blocks from islands if no blocks defined manually
  const getEffectiveBlocks = (): Block[] => {
    if (blocks.length > 0) {
      return blocks;
    }
    
    // Auto-create blocks from islands (one block per island)
    if (outerBoundary) {
      // Check if it's a MultiPolygon (multiple islands)
      if (outerBoundary.type === 'MultiPolygon' && outerBoundary.coordinates) {
        // Create one block for each island
        return outerBoundary.coordinates.map((coords: any, index: number) => {
          const polygonGeom = {
            type: 'Polygon',
            coordinates: coords
          };
          const area = calculateAreaHectares(polygonGeom);
          return {
            id: `block-${Date.now()}-${index}`,
            name: `${forestName} - Block ${index + 1}`,
            geometry: polygonGeom,
            area: area,
          };
        });
      } else {
        // Single polygon - create one block
        const area = calculateAreaHectares(outerBoundary);
        return [{
          id: `block-${Date.now()}`,
          name: `${forestName} - Block 1`,
          geometry: outerBoundary,
          area: area,
        }];
      }
    }
    return [];
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return true; // GPS points are optional
      case 2:
        return outerBoundary !== null;
      case 3:
        return true; // Blocks now optional - auto-creates default
      case 4:
        return true; // Sub-areas are optional
      case 5:
        return outerBoundary !== null;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < steps.length) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    if (steps[currentStep - 1].optional) {
      handleNext();
    }
  };

  // Save draft to server
  const handleSaveDraft = async () => {
    if (!outerBoundary) {
      setSaveMessage('Please draw the boundary first');
      return;
    }

    const token = localStorage.getItem('access_token');
    if (!token) {
      setSaveMessage('Please login first to save draft');
      return;
    }

    // Prevent multiple saves while one is in progress
    if (isSaving) {
      setSaveMessage('Saving in progress...');
      return;
    }

    setIsSaving(true);
    setSaveMessage(null);

    try {
      // Convert islands to the format expected by the API
      const islands = [{
        id: `island-${Date.now()}`,
        geometry: outerBoundary,
        area: calculateAreaHectares(outerBoundary),
      }];

      // Capture current draftId to avoid closure issues
      const currentDraftId = draftId;
      
      console.log('[MapCreationWizard] Saving draft...', {
        forest_name: forestName,
        islands_count: islands.length,
        mode: 'manual',
        draft_id: currentDraftId,
      });

      const response = await fetch('http://localhost:8001/api/forests/save-draft', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          forest_name: forestName,
          islands: islands,
          mode: 'manual',
          draft_id: currentDraftId,  // Use captured value
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save draft');
      }

      const result = await response.json();
      console.log('[MapCreationWizard] Draft saved:', result);
      
      // Only update draftId if this was a new draft (currentDraftId was null)
      if (!currentDraftId) {
        setDraftId(result.id);
      }
      
      setSaveMessage('Draft saved! You can close this page and resume later.');
      setTimeout(() => setSaveMessage(null), 5000);
    } catch (error: any) {
      console.error('[MapCreationWizard] Error saving draft:', error);
      const errorMsg = error.message || 'Failed to save draft. Please try again.';
      setSaveMessage(errorMsg);
    } finally {
      setIsSaving(false);
    }
  };

  const handleFinish = () => {
    console.log('[MapCreationWizard] handleFinish called - saving without analysis');

    // Use effective blocks (auto-create default if none defined)
    let finalBlocks = getEffectiveBlocks();
    
    // Apply edited block names if user renamed any
    if (Object.keys(editedBlockNames).length > 0) {
      finalBlocks = finalBlocks.map(block => ({
        ...block,
        name: editedBlockNames[block.id] || block.name
      }));
    }
    
    console.log('[MapCreationWizard] Data being sent:', {
      outerBoundary,
      gpsPoints,
      blocks: finalBlocks.length,
      subAreas: subAreas.length
    });

    // Clean and validate blocks before sending to backend
    console.log('[MapCreationWizard] Cleaning and validating blocks...');
    const cleanedBlocks = cleanAndValidateBlocks(finalBlocks, outerBoundary);
    console.log('[MapCreationWizard] Cleaned blocks:', cleanedBlocks.length);

    // Clear polygon creator draft since we're completing the wizard
    try {
      localStorage.removeItem('polygon_creator_draft');
      console.log('[MapCreationWizard] Cleared polygon creator draft');
    } catch (error) {
      console.error('[MapCreationWizard] Error clearing draft:', error);
    }

    onComplete({
      outerBoundary,
      gpsPoints,
      blocks: cleanedBlocks,
      subAreas,
    });
  };

  // Location search handlers
  const handleLocationSelected = (bounds: [number, number, number, number]) => {
    console.log('[MapCreationWizard] Location selected, bounds:', bounds);
    // Pass to PolygonCreator to zoom map
    if (polygonCreatorRef.current && polygonCreatorRef.current.zoomToBounds) {
      polygonCreatorRef.current.zoomToBounds(bounds);
    }
  };

  const handleBoundaryToggle = (show: boolean, geometry: any) => {
    console.log('[MapCreationWizard] Ward boundary toggle:', show);
    setShowWardBoundary(show);
    setWardBoundaryGeometry(geometry);
    // Pass to PolygonCreator to show/hide boundary
    if (polygonCreatorRef.current && polygonCreatorRef.current.setWardBoundary) {
      polygonCreatorRef.current.setWardBoundary(show ? geometry : null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 relative">
      {/* Loading Overlay */}
      {isProcessing && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg p-8 max-w-md mx-4">
            <div className="flex flex-col items-center">
              <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-green-600 mb-4"></div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Creating Forest...</h3>
              <p className="text-gray-600 text-center">
                Running analysis on your forest boundary. This may take a few moments.
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-800">
                Create Forest Map: {forestName}
              </h1>
              <p className="text-gray-600 mt-1">
                Create your community forest boundary through interactive mapping
              </p>
            </div>
            <button
              onClick={onCancel}
              className="px-4 py-2 text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
          </div>

          {/* Progress Steps */}
          <div className="flex items-center justify-between">
            {steps.map((step, index) => (
              <React.Fragment key={step.number}>
                <div className="flex flex-col items-center flex-1">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                      currentStep === step.number
                        ? 'bg-green-600 text-white'
                        : currentStep > step.number
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-300 text-gray-600'
                    }`}
                  >
                    {currentStep > step.number ? '✓' : step.number}
                  </div>
                  <div className="text-sm mt-2 text-center">
                    <div className="font-medium">{step.name}</div>
                    {step.optional && (
                      <div className="text-xs text-gray-500">(Optional)</div>
                    )}
                  </div>
                </div>
                {index < steps.length - 1 && (
                  <div
                    className={`flex-1 h-1 mx-2 ${
                      currentStep > step.number ? 'bg-green-500' : 'bg-gray-300'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="mb-6">
          {currentStep === 1 && (
            <GPSPointInput
              onPointsChange={setGpsPoints}
              initialPoints={gpsPoints}
            />
          )}

          {currentStep === 2 && (
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
              {/* Left Sidebar - Location Search */}
              <div className="lg:col-span-1 space-y-4">
                <LocationSearch
                  onLocationSelected={handleLocationSelected}
                  onBoundaryToggle={handleBoundaryToggle}
                />
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <div className="flex-1">
                      <h4 className="font-semibold text-blue-900 text-sm mb-2">💡 सुझाव</h4>
                      <p className="text-xs text-blue-800">
                        तपाईंको क्षेत्र फेला पार्न location search प्रयोग गर्नुहोस्, त्यसपछि नक्शामा वन सीमाना कोर्नुहोस्।
                        प्राकृतिक विशेषताहरू राम्रोसँग देख्न satellite view मा टगल गर्नुहोस्।
                      </p>
                    </div>
                    <HelpTooltip helpText={helpTexts.drawPolygon.text} position="left" />
                  </div>
                </div>
              </div>

              {/* Main Content - Polygon Creator */}
              <div className="lg:col-span-3">
                <PolygonCreator
                  ref={polygonCreatorRef}
                  gpsPoints={gpsPoints}
                  onPolygonChange={setOuterBoundary}
                  initialPolygon={outerBoundary}
                />
              </div>
            </div>
          )}

          {currentStep === 3 && outerBoundary && (
            <div>
              {/* Info banner - blocks are now optional */}
              <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-md">
                <p className="text-sm text-blue-800">
                  <strong>Optional:</strong> Blocks are optional. If you don't create blocks, the entire forest boundary will be treated as one block. 
                  Use "Save Draft" to save your progress and resume later.
                </p>
              </div>
              <BlockSplitterPro
                outerBoundary={outerBoundary}
                gpsPoints={gpsPoints}
                onBlocksChange={setBlocks}
                initialBlocks={blocks}
              />
            </div>
          )}

          {currentStep === 4 && (
            <SubAreaManager
              blocks={getEffectiveBlocks()}
              outerBoundary={outerBoundary}
              onSubAreasChange={setSubAreas}
              initialSubAreas={subAreas}
            />
          )}

          {currentStep === 5 && (
            <div className="space-y-6">
              {/* Visual Map Review */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h2 className="text-xl font-bold mb-4">Visual Review</h2>
                <div style={{ height: '500px', width: '100%' }} className="border border-gray-300 rounded-lg overflow-hidden">
                  <MapContainer
                    center={getGeometryCenter(outerBoundary, [27.7172, 85.324])}
                    zoom={14}
                    style={{ height: '100%', width: '100%' }}
                  >
                    <BaseMapSelector />

                    {/* Outer Boundary - Green */}
                    {outerBoundary && (
                      <GeoJSON
                        data={outerBoundary}
                        style={{
                          color: '#10b981',
                          weight: 3,
                          fillOpacity: 0.05,
                        }}
                      />
                    )}

                    {/* Blocks - Blue (use effective blocks - auto-creates default if none defined) */}
                    {getEffectiveBlocks().map((block) => (
                      <React.Fragment key={block.id}>
                        <GeoJSON
                          data={block.geometry}
                          style={{
                            color: '#3b82f6',
                            weight: 2,
                            fillOpacity: 0.15,
                          }}
                        />
                        {/* Block label */}
                        <Marker
                          position={getGeometryCenter(block.geometry, [27.7172, 85.324])}
                          icon={L.divIcon({
                            className: 'block-label-review',
                            html: `<div style="background: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; border: 2px solid #3b82f6; white-space: nowrap;">${block.name}</div>`,
                          })}
                        />
                      </React.Fragment>
                    ))}

                    {/* Sub-areas - Colored by category */}
                    {subAreas.map((subArea) => {
                      const colors: Record<string, string> = {
                        'protected': '#ef4444',
                        'plantation': '#10b981',
                        'pro-poor': '#f59e0b',
                        'religious': '#8b5cf6',
                        'biodiversity': '#06b6d4',
                        'tourist': '#ec4899',
                        'office': '#6b7280',
                      };
                      const color = colors[subArea.category] || '#9ca3af';

                      return (
                        <React.Fragment key={subArea.id}>
                          <GeoJSON
                            data={subArea.geometry}
                            style={{
                              color: color,
                              weight: 2,
                              fillOpacity: 0.3,
                            }}
                          />
                          {/* Sub-area label */}
                          <Marker
                            position={getGeometryCenter(subArea.geometry, [27.7172, 85.324])}
                            icon={L.divIcon({
                              className: 'subarea-label-review',
                              html: `<div style="background: ${color}; color: white; padding: 3px 6px; border-radius: 3px; font-size: 11px; font-weight: bold; white-space: nowrap;">${subArea.name}</div>`,
                            })}
                          />
                        </React.Fragment>
                      );
                    })}
                  </MapContainer>
                </div>

                {/* Legend */}
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <h4 className="font-semibold mb-2 text-sm">Legend</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-green-500 bg-green-100"></div>
                      <span>Outer Boundary</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-blue-500 bg-blue-100"></div>
                      <span>Forest Blocks</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-red-500"></div>
                      <span>Protected</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 bg-orange-500"></div>
                      <span>Pro-Poor</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Detailed Summary */}
              <div className="bg-white p-6 rounded-lg shadow">
                <h2 className="text-xl font-bold mb-4">Detailed Summary</h2>

                <div className="space-y-4">
                  {/* Forest Info */}
                  <div className="border-b pb-4">
                    <h3 className="font-semibold mb-2">Forest Information</h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-600">Forest Name:</span>
                        <div className="font-medium">{forestName}</div>
                      </div>
                      <div>
                        <span className="text-gray-600">Total Area:</span>
                        <div className="font-medium">{formatArea(calculateAreaHectares(outerBoundary))}</div>
                      </div>
                    </div>
                  </div>

                  {/* Blocks */}
                  <div className="border-b pb-4">
                    <h3 className="font-semibold mb-2">
                      Forest Blocks ({getEffectiveBlocks().length})
                      {blocks.length === 0 && <span className="ml-2 text-xs text-gray-500">(auto-created from boundary)</span>}
                    </h3>
                    <div className="max-h-48 overflow-y-auto">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left font-medium text-gray-700">
                              Block Name
                            </th>
                            <th className="px-3 py-2 text-left font-medium text-gray-700">
                              Area
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200">
                          {getEffectiveBlocks().map((block, index) => {
                            // Check if user has edited this block name
                            const editedName = editedBlockNames[block.id] !== undefined 
                              ? editedBlockNames[block.id] 
                              : block.name;
                            return (
                              <tr key={block.id}>
                                <td className="px-3 py-2">
                                  <input
                                    type="text"
                                    value={editedName}
                                    onChange={(e) => {
                                      setEditedBlockNames(prev => ({
                                        ...prev,
                                        [block.id]: e.target.value
                                      }));
                                    }}
                                    className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                                    placeholder="Enter block name"
                                  />
                                </td>
                                <td className="px-3 py-2">{formatArea(block.area)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Sub-areas with Block Distribution */}
                  {subAreas.length > 0 && (
                    <div className="border-b pb-4">
                      <h3 className="font-semibold mb-2">Sub-areas ({subAreas.length})</h3>
                      <div className="space-y-4">
                        {subAreas.map((subArea) => (
                          <div key={subArea.id} className="p-4 bg-gray-50 rounded-lg">
                            <div className="flex justify-between items-start mb-2">
                              <div>
                                <h4 className="font-semibold">{subArea.name}</h4>
                                <p className="text-sm text-gray-600 capitalize">
                                  {subArea.category.replace('-', ' ')}
                                </p>
                              </div>
                              <div className="text-right">
                                <div className="font-semibold">{formatArea(subArea.area)}</div>
                                <div className="text-xs text-gray-500">Total Area</div>
                              </div>
                            </div>

                            {/* Block-wise breakdown */}
                            {subArea.blockBreakdown && subArea.blockBreakdown.length > 0 ? (
                              <div className="mt-2">
                                <div className="text-xs font-medium text-gray-600 mb-1">
                                  Spans {subArea.blockBreakdown.length} block(s):
                                </div>
                                <div className="space-y-1">
                                  {subArea.blockBreakdown.map((breakdown, idx) => (
                                    <div
                                      key={idx}
                                      className="flex justify-between text-xs bg-white px-2 py-1 rounded"
                                    >
                                      <span>{breakdown.blockName}</span>
                                      <span className="font-medium">
                                        {formatArea(breakdown.area)} ({breakdown.percentage.toFixed(1)}%)
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : (
                              <div className="text-xs text-gray-500 mt-2">
                                Within: {subArea.blockName}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Confirmation */}
                  <div className="p-4 bg-green-50 border border-green-200 rounded-md">
                    <p className="text-sm text-green-800">
                      <strong>Ready to proceed!</strong>
                      <br />
                      Review the map and details above, then click "Save" to create the forest. You can run analysis from the Analysis page when ready.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="bg-white p-6 rounded-lg shadow">
          {/* Save Draft Message */}
          {saveMessage && (
            <div className={`mb-4 p-3 rounded-md ${saveMessage.includes('Failed') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
              {saveMessage}
            </div>
          )}

          <div className="flex justify-between items-center">
            <div className="flex gap-3">
              {currentStep > 1 && (
                <button
                  onClick={handleBack}
                  className="px-6 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors"
                >
                  Back
                </button>
              )}
              
              {/* Save Draft Button - available after step 2 */}
              {currentStep >= 2 && outerBoundary && (
                <div className="flex items-center">
                  <HelpTooltip helpText={helpTexts.saveDraft.text} position="top">
                    <button
                      onClick={handleSaveDraft}
                      disabled={isSaving}
                      className="px-4 py-2 text-blue-700 bg-blue-100 border border-blue-300 rounded-md hover:bg-blue-200 transition-colors disabled:bg-gray-100 disabled:cursor-not-allowed"
                    >
                      {isSaving ? 'Saving...' : (draftId ? 'Update Draft' : 'Save Draft')}
                    </button>
                  </HelpTooltip>
                </div>
              )}
            </div>

            <div className="flex gap-3">
              {steps[currentStep - 1].optional && currentStep < steps.length && (
                <button
                  onClick={handleSkip}
                  className="px-6 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors"
                >
                  Skip
                </button>
              )}

              {currentStep < steps.length && (
                <button
                  onClick={handleNext}
                  disabled={!canProceed()}
                  className="px-6 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              )}

              {currentStep === steps.length && (
                <div className="flex items-center">
                  <HelpTooltip helpText={helpTexts.saveAndNext.text} position="top">
                    <button
                      onClick={handleFinish}
                      disabled={!canProceed() || isProcessing}
                      className="px-8 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed font-semibold"
                    >
                      {isProcessing ? 'Processing...' : 'Save'}
                    </button>
                  </HelpTooltip>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapCreationWizard;
