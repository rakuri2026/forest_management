import React, { useEffect, useState } from 'react';
import { useMapEvents, Popup } from 'react-leaflet';
import { userGroupApi } from '../../services/api';
import { Loader2 } from 'lucide-react';

interface RasterClickHandlerProps {
  calculationId: string;
  enabled: boolean;
}

interface QueryResult {
  location: { lat: number; lon: number };
  land_cover: { class_code: number; class_name: string } | null;
  biomass: { value_mg_ha: number; volume_m3_ha: number } | null;
}

export function RasterClickHandler({ calculationId, enabled }: RasterClickHandlerProps) {
  const [popupPosition, setPopupPosition] = useState<[number, number] | null>(null);
  const [queryData, setQueryData] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const map = useMapEvents({
    click: async (e) => {
      if (!enabled) return;

      const { lat, lng } = e.latlng;
      setPopupPosition([lat, lng]);
      setLoading(true);
      setError(null);
      setQueryData(null);

      try {
        const data = await userGroupApi.queryPoint(calculationId, lat, lng);
        setQueryData(data);
      } catch (err: any) {
        console.error('Query error:', err);
        const errorDetail = err.response?.data?.detail || 'Failed to query data at this location';

        // Check if error is about being outside effective area
        if (errorDetail.includes('outside effective area')) {
          setError('This location is outside the user group extent or within the forest overlap area.');
        } else {
          setError(errorDetail);
        }
      } finally {
        setLoading(false);
      }
    },
  });

  // Close popup when handler is disabled
  useEffect(() => {
    if (!enabled) {
      setPopupPosition(null);
      setQueryData(null);
    }
  }, [enabled]);

  if (!popupPosition) return null;

  return (
    <Popup position={popupPosition} onClose={() => setPopupPosition(null)}>
      <div className="p-2 min-w-[200px]">
        {/* Header */}
        <div className="mb-2 pb-2 border-b border-gray-200">
          <h4 className="font-semibold text-gray-800 text-sm">Raster Data Query</h4>
          <p className="text-xs text-gray-500 mt-0.5">
            {popupPosition[0].toFixed(5)}°, {popupPosition[1].toFixed(5)}°
          </p>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-4">
            <Loader2 className="w-5 h-5 animate-spin text-blue-600" />
            <span className="ml-2 text-sm text-gray-600">Querying...</span>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="text-sm text-red-600 py-2">
            <p className="font-medium">Error</p>
            <p className="text-xs mt-1">{error}</p>
          </div>
        )}

        {/* Results */}
        {queryData && !loading && (
          <div className="space-y-3">
            {/* Land Cover */}
            {queryData.land_cover ? (
              <div>
                <p className="text-xs font-semibold text-gray-600 mb-1">Land Cover</p>
                <div className="bg-gray-50 rounded p-2">
                  <p className="text-sm font-medium text-gray-800">
                    {queryData.land_cover.class_name}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Class {queryData.land_cover.class_code}
                  </p>
                </div>
              </div>
            ) : (
              <div>
                <p className="text-xs font-semibold text-gray-600 mb-1">Land Cover</p>
                <p className="text-xs text-gray-500 italic">No data at this location</p>
              </div>
            )}

            {/* Biomass */}
            {queryData.biomass && queryData.biomass.value_mg_ha !== null && queryData.biomass.value_mg_ha > 0 ? (
              <div>
                <p className="text-xs font-semibold text-gray-600 mb-1">Biomass</p>
                <div className="bg-gray-50 rounded p-2 space-y-1">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600">Biomass:</span>
                    <span className="text-sm font-medium text-emerald-700">
                      {queryData.biomass.value_mg_ha.toFixed(2)} Mg/ha
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600">Timber Volume:</span>
                    <span className="text-sm font-medium text-amber-700">
                      {queryData.biomass.volume_m3_ha.toFixed(2)} m³/ha
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div>
                <p className="text-xs font-semibold text-gray-600 mb-1">Biomass</p>
                <p className="text-xs text-gray-500 italic">No data at this location</p>
              </div>
            )}

            {/* Show message if neither data available */}
            {!queryData.land_cover && (!queryData.biomass || !queryData.biomass.value_mg_ha) && (
              <p className="text-xs text-orange-600 italic py-1">
                No raster data available at this location
              </p>
            )}
          </div>
        )}
      </div>
    </Popup>
  );
}
