import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../services/api';

interface MapsTabProps {
  calculationId: string;
  forestName?: string;
}

interface MapCardProps {
  title: string;
  description: string;
  mapType: 'boundary' | 'slope' | 'aspect' | 'landcover' | 'topographic' | 'forest_type' | 'canopy_height' | 'soil' | 'forest_health';
  calculationId: string;
  onGenerate?: () => Promise<void>;
  triggerGenerate?: boolean;
}

const MapCard: React.FC<MapCardProps> = ({ title, description, mapType, calculationId, onGenerate, triggerGenerate }) => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [hasGenerated, setHasGenerated] = useState<boolean>(false);

  const mapUrl = `${API_BASE_URL}/api/forests/calculations/${calculationId}/maps/${mapType}`;

  // Fetch image with authentication
  const fetchImage = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await fetch(mapUrl, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to load map: ${response.statusText}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setImageUrl(url);
      setHasGenerated(true);
      setIsLoading(false);

      // Notify parent component
      if (onGenerate) {
        await onGenerate();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load map');
      setIsLoading(false);
    }
  };

  // Trigger generation when triggerGenerate prop changes
  useEffect(() => {
    if (triggerGenerate && !hasGenerated && !isLoading) {
      fetchImage();
    }
  }, [triggerGenerate]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  const handleDownload = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(mapUrl, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to download map');
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${mapType}_map_${calculationId}.png`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert('Failed to download map');
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="bg-gradient-to-r from-green-600 to-green-700 px-4 py-3">
        <h3 className="text-white font-semibold text-lg">{title}</h3>
        <p className="text-green-100 text-sm mt-1">{description}</p>
      </div>

      {/* Map Display */}
      <div className="p-4">
        <div className="relative bg-gray-50 rounded-lg overflow-hidden" style={{ minHeight: '400px' }}>
          {/* Not Generated State */}
          {!hasGenerated && !isLoading && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <svg className="mx-auto h-16 w-16 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
                <p className="text-gray-600 font-medium mb-2">Map not generated yet</p>
                <p className="text-gray-500 text-sm mb-4">Click the button below to generate this map</p>
                <button
                  onClick={fetchImage}
                  className="inline-flex items-center px-5 py-2.5 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm font-medium shadow-sm"
                >
                  <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                  Generate Map
                </button>
              </div>
            </div>
          )}

          {/* Loading State */}
          {isLoading && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-green-600 mb-3"></div>
                <p className="text-gray-600 text-sm font-medium">Generating map...</p>
                <p className="text-gray-500 text-xs mt-1">This may take 1-3 minutes</p>
                <p className="text-gray-400 text-xs mt-2">Processing raster data and rendering...</p>
              </div>
            </div>
          )}

          {/* Error State */}
          {error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-red-600">
                <svg className="mx-auto h-12 w-12 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="font-medium">{error}</p>
                <button
                  onClick={fetchImage}
                  className="mt-3 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {/* Map Image */}
          {imageUrl && !error && (
            <img
              src={imageUrl}
              alt={`${title} - A5 300 DPI map`}
              className="w-full h-auto"
            />
          )}
        </div>

        {/* Download Button */}
        {imageUrl && !error && !isLoading && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={handleDownload}
              className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors text-sm font-medium"
            >
              <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download Map (PNG)
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

const MapsTab: React.FC<MapsTabProps> = ({ calculationId, forestName }) => {
  const [isGeneratingAll, setIsGeneratingAll] = useState<boolean>(false);
  const [currentGeneratingIndex, setCurrentGeneratingIndex] = useState<number>(-1);
  const [generatedCount, setGeneratedCount] = useState<number>(0);

  const maps = [
    {
      title: 'Boundary Map',
      description: 'Forest boundary with schools, roads, rivers, and contextual features',
      mapType: 'boundary' as const,
    },
    {
      title: 'Topographic Map',
      description: 'Elevation contours and terrain visualization',
      mapType: 'topographic' as const,
    },
    {
      title: 'Slope Map',
      description: '5-class slope classification (Flat to Very Steep)',
      mapType: 'slope' as const,
    },
    {
      title: 'Aspect Map',
      description: 'Temperature-based aspect classes (N=cold/blue, S=warm/red)',
      mapType: 'aspect' as const,
    },
    {
      title: 'Forest Type Map',
      description: 'Forest species classification and distribution',
      mapType: 'forest_type' as const,
    },
    {
      title: 'Canopy Height Map',
      description: 'Forest structure showing canopy height classes',
      mapType: 'canopy_height' as const,
    },
    {
      title: 'Land Cover Map',
      description: 'ESA WorldCover classification (10 land cover classes)',
      mapType: 'landcover' as const,
    },
    {
      title: 'Soil Texture Map',
      description: 'SoilGrids ISRIC soil texture classification (12 classes)',
      mapType: 'soil' as const,
    },
    {
      title: 'Forest Health Map',
      description: 'Vegetation health status (Poor to Excellent)',
      mapType: 'forest_health' as const,
    },
  ];

  // Generate all maps sequentially
  const generateAllMaps = async () => {
    setIsGeneratingAll(true);
    setGeneratedCount(0);

    for (let i = 0; i < maps.length; i++) {
      setCurrentGeneratingIndex(i);
      // Wait for map to generate (will be triggered by triggerGenerate prop)
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    setIsGeneratingAll(false);
    setCurrentGeneratingIndex(-1);
  };

  // Callback when individual map finishes generating
  const handleMapGenerated = async (index: number) => {
    setGeneratedCount(prev => prev + 1);

    // If we're in "generate all" mode, wait 1 second before next map
    if (isGeneratingAll && index < maps.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-2">Analysis Maps</h2>
            <p className="text-gray-600">
              Professional A5 maps at 300 DPI for {forestName || 'your forest area'}.
              All maps are print-ready and include legends, north arrows, and scale bars.
            </p>
          </div>
          <button
            onClick={generateAllMaps}
            disabled={isGeneratingAll}
            className={`ml-4 inline-flex items-center px-6 py-3 rounded-lg font-medium text-sm transition-all shadow-md ${
              isGeneratingAll
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-gradient-to-r from-green-600 to-green-700 hover:from-green-700 hover:to-green-800 text-white'
            }`}
          >
            {isGeneratingAll ? (
              <>
                <div className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Generating... ({generatedCount}/{maps.length})
              </>
            ) : (
              <>
                <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Generate All Maps
              </>
            )}
          </button>
        </div>

        <div className="mt-3 flex items-start space-x-2 text-sm text-gray-500">
          <svg className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>
            <strong>Performance tip:</strong> Maps are now generated on-demand to prevent server overload.
            Each map takes 1-3 minutes. Use "Generate All Maps" for sequential generation (total 9-27 minutes),
            or generate individual maps as needed.
          </span>
        </div>
      </div>

      {/* Maps Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {maps.map((map, index) => (
          <MapCard
            key={map.mapType}
            title={map.title}
            description={map.description}
            mapType={map.mapType}
            calculationId={calculationId}
            onGenerate={async () => handleMapGenerated(index)}
            triggerGenerate={isGeneratingAll && currentGeneratingIndex === index}
          />
        ))}
      </div>

      {/* Footer Info */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <svg className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">Map Specifications:</p>
            <ul className="list-disc list-inside space-y-1 text-blue-700">
              <li>Format: PNG image</li>
              <li>Size: A5 (148mm × 210mm portrait or 210mm × 148mm landscape)</li>
              <li>Resolution: 300 DPI (print quality)</li>
              <li>Coordinate System: WGS84 (EPSG:4326)</li>
              <li>Includes: North arrow, scale bar, legend, and metadata</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MapsTab;
