import React, { useState, useRef } from 'react';
import { MapContainer, GeoJSON, Marker } from 'react-leaflet';
import L from 'leaflet';
import GPSPointInput from './GPSPointInput';
import PolygonCreator from './PolygonCreator';
import BlockSplitterPro from './BlockSplitterPro';
import SubAreaManager from './SubAreaManager';
import BaseMapSelector from './BaseMapSelector';
import LocationSearch from './LocationSearch';
import { GPSPoint } from '../../utils/gpsUtils';
import { formatArea, calculateAreaHectares, cleanAndValidateBlocks } from '../../utils/geometryValidation';

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
    runAnalysis?: boolean;
  }) => void;
  onCancel: () => void;
  isProcessing?: boolean;
}

const MapCreationWizard: React.FC<MapCreationWizardProps> = ({
  forestName,
  onComplete,
  onCancel,
  isProcessing = false,
}) => {
  const [currentStep, setCurrentStep] = useState<number>(1);

  // Step 1: GPS Points (optional)
  const [gpsPoints, setGpsPoints] = useState<GPSPoint[]>([]);

  // Step 2: Outer Boundary
  const [outerBoundary, setOuterBoundary] = useState<any>(null);

  // Step 3: Blocks
  const [blocks, setBlocks] = useState<Block[]>([]);

  // Step 4: Sub-areas (optional)
  const [subAreas, setSubAreas] = useState<SubArea[]>([]);

  // Location search state
  const polygonCreatorRef = useRef<any>(null);
  const [wardBoundaryGeometry, setWardBoundaryGeometry] = useState<any>(null);
  const [showWardBoundary, setShowWardBoundary] = useState(false);

  const steps = [
    { number: 1, name: 'GPS Points', optional: true },
    { number: 2, name: 'Outer Boundary', optional: false },
    { number: 3, name: 'Forest Blocks', optional: false },
    { number: 4, name: 'Sub-areas', optional: true },
    { number: 5, name: 'Review', optional: false },
  ];

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return true; // GPS points are optional
      case 2:
        return outerBoundary !== null;
      case 3:
        return blocks.length > 0;
      case 4:
        return true; // Sub-areas are optional
      case 5:
        return outerBoundary !== null && blocks.length > 0;
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

  const handleFinish = (runAnalysis: boolean = true) => {
    console.log('[MapCreationWizard] handleFinish called, runAnalysis:', runAnalysis);
    console.log('[MapCreationWizard] Data being sent:', {
      outerBoundary,
      gpsPoints,
      blocks: blocks.length,
      subAreas: subAreas.length
    });

    // Clean and validate blocks before sending to backend
    console.log('[MapCreationWizard] Cleaning and validating blocks...');
    const cleanedBlocks = cleanAndValidateBlocks(blocks, outerBoundary);
    console.log('[MapCreationWizard] Cleaned blocks:', cleanedBlocks.length);

    onComplete({
      outerBoundary,
      gpsPoints,
      blocks: cleanedBlocks,
      subAreas,
      runAnalysis,
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
                  <h4 className="font-semibold text-blue-900 text-sm mb-2">💡 Tip</h4>
                  <p className="text-xs text-blue-800">
                    Use the location search to find your area, then draw the forest boundary on the map.
                    Toggle to satellite view for better visibility of natural features.
                  </p>
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
            <BlockSplitterPro
              outerBoundary={outerBoundary}
              gpsPoints={gpsPoints}
              onBlocksChange={setBlocks}
              initialBlocks={blocks}
            />
          )}

          {currentStep === 4 && blocks.length > 0 && (
            <SubAreaManager
              blocks={blocks}
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
                    center={
                      outerBoundary && outerBoundary.coordinates && outerBoundary.coordinates[0]
                        ? [
                            (outerBoundary.coordinates[0][0][1] + outerBoundary.coordinates[0][2][1]) / 2,
                            (outerBoundary.coordinates[0][0][0] + outerBoundary.coordinates[0][2][0]) / 2,
                          ]
                        : [27.7172, 85.324]
                    }
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

                    {/* Blocks - Blue */}
                    {blocks.map((block) => (
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
                          position={[
                            block.geometry.coordinates[0].reduce((sum: number, coord: number[]) => sum + coord[1], 0) / block.geometry.coordinates[0].length,
                            block.geometry.coordinates[0].reduce((sum: number, coord: number[]) => sum + coord[0], 0) / block.geometry.coordinates[0].length,
                          ]}
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
                            position={[
                              subArea.geometry.coordinates[0].reduce((sum: number, coord: number[]) => sum + coord[1], 0) / subArea.geometry.coordinates[0].length,
                              subArea.geometry.coordinates[0].reduce((sum: number, coord: number[]) => sum + coord[0], 0) / subArea.geometry.coordinates[0].length,
                            ]}
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
                    <h3 className="font-semibold mb-2">Forest Blocks ({blocks.length})</h3>
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
                          {blocks.map((block) => (
                            <tr key={block.id}>
                              <td className="px-3 py-2">{block.name}</td>
                              <td className="px-3 py-2">{formatArea(block.area)}</td>
                            </tr>
                          ))}
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
                      Review the map and details above, then click "Finish & Analyze" to create the calculation and run the forest analysis.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Navigation Buttons */}
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex justify-between items-center">
            <div>
              {currentStep > 1 && (
                <button
                  onClick={handleBack}
                  className="px-6 py-2 text-gray-700 bg-gray-200 rounded-md hover:bg-gray-300 transition-colors"
                >
                  Back
                </button>
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
                <button
                  onClick={() => handleFinish(false)}
                  disabled={!canProceed() || isProcessing}
                  className="px-8 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed font-semibold"
                >
                  {isProcessing ? 'Processing...' : 'Save'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapCreationWizard;
