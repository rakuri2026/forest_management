import React, { useState } from 'react';
import { BarChart3, Leaf, TreePine, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { userGroupApi } from '../../services/api';

interface LandCoverAnalysisProps {
  calculationId: string;
  forestName?: string;
}

interface LandCoverClass {
  class_code: number;
  class_name: string;
  area_ha: number;
  percentage: number;
  avg_biomass_mg_per_ha: number;
  total_biomass_mg: number;
  avg_volume_m3_per_ha: number;
  total_volume_m3: number;
}

interface LandCoverResults {
  user_group_area_ha: number;
  forest_overlap_area_ha: number;
  net_analysis_area_ha: number;
  land_cover_classes: LandCoverClass[];
  total_biomass_mg: number;
  total_volume_m3: number;
  avg_biomass_mg_per_ha: number;
  avg_volume_m3_per_ha: number;
  has_forest_overlap: boolean;
}

export function LandCoverAnalysis({ calculationId, forestName }: LandCoverAnalysisProps) {
  const [results, setResults] = useState<LandCoverResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fromCache, setFromCache] = useState(false);
  const [initialLoadDone, setInitialLoadDone] = useState(false);
  const [cacheInfo, setCacheInfo] = useState<{ size: number; age: string } | null>(null);

  // Get cache info
  const getCacheInfo = () => {
    const localCacheKey = `land_cover_${calculationId}`;
    const cached = localStorage.getItem(localCacheKey);
    if (cached) {
      try {
        const parsed = JSON.parse(cached);
        const sizeKB = new Blob([cached]).size / 1024;
        const ageMs = Date.now() - new Date(parsed.cached_at).getTime();
        const ageHours = Math.floor(ageMs / (1000 * 60 * 60));
        const ageMinutes = Math.floor((ageMs % (1000 * 60 * 60)) / (1000 * 60));
        const ageStr = ageHours > 0 ? `${ageHours}h ${ageMinutes}m ago` : `${ageMinutes}m ago`;
        setCacheInfo({ size: sizeKB, age: ageStr });
      } catch (e) {
        setCacheInfo(null);
      }
    } else {
      setCacheInfo(null);
    }
  };

  // Auto-load cached results on component mount
  React.useEffect(() => {
    const loadCachedResults = async () => {
      try {
        setLoading(true);

        // LAYER 1: Try LocalStorage first (instant, <5ms)
        const localCacheKey = `land_cover_${calculationId}`;
        const localCached = localStorage.getItem(localCacheKey);

        if (localCached) {
          try {
            const parsedData = JSON.parse(localCached);
            // Check if cache is fresh (< 24 hours old)
            const cacheAge = Date.now() - new Date(parsedData.cached_at).getTime();
            const isStale = cacheAge > 24 * 60 * 60 * 1000; // 24 hours

            if (!isStale) {
              console.log('✅ Loaded from LocalStorage (instant!)', parsedData);
              setResults(parsedData.data);
              setFromCache(true);
              setInitialLoadDone(true);
              setLoading(false);
              getCacheInfo();
              return; // Exit early - no need to hit server
            } else {
              console.log('⚠️ LocalStorage cache is stale, refreshing from server...');
              localStorage.removeItem(localCacheKey);
            }
          } catch (e) {
            console.error('LocalStorage parse error:', e);
            localStorage.removeItem(localCacheKey);
          }
        }

        // LAYER 2: Load from database (slower, 50-200ms)
        console.log('📡 Loading from database...');
        const data = await userGroupApi.analyzeLandCover(calculationId, false);
        setResults(data);
        setFromCache(data.from_cache === true);

        // Save to LocalStorage for next time
        try {
          localStorage.setItem(localCacheKey, JSON.stringify({
            data: data,
            cached_at: new Date().toISOString(),
            calculation_id: calculationId
          }));
          console.log('💾 Saved to LocalStorage for instant future access');
          getCacheInfo(); // Update cache info display
        } catch (storageError) {
          console.warn('LocalStorage save failed (quota exceeded?):', storageError);
        }

        setInitialLoadDone(true);
      } catch (err: any) {
        // If no cached results or error, just show the button
        console.log('No cached results available');
        setInitialLoadDone(true);
      } finally {
        setLoading(false);
      }
    };

    loadCachedResults();
  }, [calculationId]);

  const handleAnalyze = async (forceRefresh: boolean = false) => {
    setLoading(true);
    setError(null);

    try {
      const data = await userGroupApi.analyzeLandCover(calculationId, forceRefresh);
      setResults(data);
      setFromCache(data.from_cache === true);

      // Save to LocalStorage for instant future access
      const localCacheKey = `land_cover_${calculationId}`;
      try {
        localStorage.setItem(localCacheKey, JSON.stringify({
          data: data,
          cached_at: new Date().toISOString(),
          calculation_id: calculationId
        }));
        console.log('💾 Saved fresh analysis to LocalStorage');
        getCacheInfo(); // Update cache info display
      } catch (storageError) {
        console.warn('LocalStorage save failed:', storageError);
      }
    } catch (err: any) {
      const errorMessage = err.response?.data?.detail || err.message || 'Analysis failed';
      setError(errorMessage);
      console.error('Land cover analysis error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Get color for land cover class
  const getLandCoverColor = (classCode: number): string => {
    const colors: Record<number, string> = {
      10: '#006400', // Tree cover - Dark green
      20: '#8B4513', // Shrubland - Saddle brown
      30: '#90EE90', // Grassland - Light green
      40: '#FFD700', // Cropland - Gold
      50: '#FF6347', // Built-up - Tomato
      60: '#D2B48C', // Bare/sparse - Tan
      70: '#FFFFFF', // Snow and ice - White
      80: '#4169E1', // Water - Royal blue
      90: '#00CED1', // Wetland - Dark turquoise
      95: '#2E8B57', // Mangroves - Sea green
      100: '#98FB98', // Moss and lichen - Pale green
    };
    return colors[classCode] || '#999999';
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-green-50 rounded-lg">
            <Leaf className="w-6 h-6 text-green-600" />
          </div>
          <div>
            <h3 className="text-xl font-semibold text-gray-800">Land Cover & Biomass Analysis</h3>
            <p className="text-sm text-gray-500">
              Comprehensive land use and biomass assessment for {forestName || 'User Group'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {results && (
            <div className="flex items-center gap-2">
              {fromCache && (
                <span className="text-xs px-2 py-1 bg-green-50 text-green-700 border border-green-200 rounded flex items-center gap-1">
                  <CheckCircle className="w-3 h-3" />
                  ⚡ Instant load (LocalStorage)
                </span>
              )}
              {cacheInfo && (
                <span className="text-xs px-2 py-1 bg-gray-50 text-gray-600 border border-gray-200 rounded">
                  {cacheInfo.size.toFixed(1)} KB · {cacheInfo.age}
                </span>
              )}
              <button
                onClick={() => {
                  // Clear LocalStorage cache
                  const localCacheKey = `land_cover_${calculationId}`;
                  localStorage.removeItem(localCacheKey);
                  setCacheInfo(null);
                  setFromCache(false);
                  console.log('🗑️ Cleared LocalStorage cache');
                  alert('Local cache cleared! Next load will fetch from database.');
                }}
                className="text-xs px-2 py-1 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded border border-gray-200 hover:border-red-200 transition-colors"
                title="Clear local cache and reload from database"
              >
                🗑️ Clear Local Cache
              </button>
            </div>
          )}
          <button
            onClick={() => handleAnalyze(results !== null)}
            disabled={loading}
            className="px-6 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700
                     disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors
                     flex items-center gap-2 font-medium"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {results ? 'Re-analyzing...' : 'Analyzing...'}
              </>
            ) : (
              <>
                <BarChart3 className="w-4 h-4" />
                {results ? 'Re-run Analysis' : 'Run Analysis'}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium text-red-800">Analysis Failed</p>
            <p className="text-sm text-red-600 mt-1">{error}</p>
            {error.includes('not found') && (
              <p className="text-xs text-red-500 mt-2">
                Make sure you have:
                <br />• Uploaded a community forest boundary (Analysis tab)
                <br />• Created a user group extent (Forest User Map tab)
              </p>
            )}
          </div>
        </div>
      )}

      {/* Results */}
      {results && (
        <div className="space-y-6">
          {/* Area Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-sm text-blue-600 font-medium mb-1">User Group Area</p>
              <p className="text-2xl font-bold text-blue-800">
                {results.user_group_area_ha.toFixed(2)} ha
              </p>
            </div>

            <div className="p-4 bg-orange-50 rounded-lg border border-orange-200">
              <p className="text-sm text-orange-600 font-medium mb-1">Forest Overlap</p>
              <p className="text-2xl font-bold text-orange-800">
                {results.forest_overlap_area_ha.toFixed(2)} ha
              </p>
              {results.has_forest_overlap && (
                <p className="text-xs text-orange-600 mt-1">Excluded from analysis</p>
              )}
            </div>

            <div className="p-4 bg-green-50 rounded-lg border border-green-200">
              <p className="text-sm text-green-600 font-medium mb-1">Net Analysis Area</p>
              <p className="text-2xl font-bold text-green-800">
                {results.net_analysis_area_ha.toFixed(2)} ha
              </p>
              <p className="text-xs text-green-600 mt-1">After overlap exclusion</p>
            </div>
          </div>

          {/* Biomass & Volume Summary */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-5 bg-gradient-to-br from-emerald-50 to-green-50 rounded-lg border border-emerald-200">
              <div className="flex items-center gap-2 mb-3">
                <TreePine className="w-5 h-5 text-emerald-600" />
                <p className="text-sm font-semibold text-emerald-700">Total Biomass</p>
              </div>
              <p className="text-3xl font-bold text-emerald-800">
                {results.total_biomass_mg.toFixed(2)} Mg
              </p>
              <p className="text-sm text-emerald-600 mt-2">
                Average: {results.avg_biomass_mg_per_ha.toFixed(2)} Mg/ha
              </p>
            </div>

            <div className="p-5 bg-gradient-to-br from-amber-50 to-yellow-50 rounded-lg border border-amber-200">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-5 h-5 text-amber-600" />
                <p className="text-sm font-semibold text-amber-700">Total Timber Volume</p>
              </div>
              <p className="text-3xl font-bold text-amber-800">
                {results.total_volume_m3.toFixed(2)} m³
              </p>
              <p className="text-sm text-amber-600 mt-2">
                Average: {results.avg_volume_m3_per_ha.toFixed(2)} m³/ha
              </p>
            </div>
          </div>

          {/* Land Cover Breakdown */}
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            <div className="bg-gray-50 px-6 py-3 border-b border-gray-200">
              <h4 className="font-semibold text-gray-800">Land Cover Classification</h4>
              <p className="text-xs text-gray-500 mt-1">
                Based on ESA World Cover (10m resolution) and AGB 2022 Nepal (100m resolution)
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Land Cover Type
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Area (ha)
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Percentage
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Biomass (Mg/ha)
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Volume (m³/ha)
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Total Biomass (Mg)
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wider">
                      Total Volume (m³)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {results.land_cover_classes.map((cls) => (
                    <tr key={cls.class_code} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-4 h-4 rounded border border-gray-300"
                            style={{ backgroundColor: getLandCoverColor(cls.class_code) }}
                          />
                          <span className="text-sm font-medium text-gray-800">
                            {cls.class_name}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-gray-700">
                        {cls.area_ha.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-gray-700">
                        <span className="font-medium">{cls.percentage.toFixed(1)}%</span>
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-gray-700">
                        {cls.avg_biomass_mg_per_ha.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-gray-700">
                        {cls.avg_volume_m3_per_ha.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-right text-sm font-medium text-emerald-700">
                        {cls.total_biomass_mg.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-right text-sm font-medium text-amber-700">
                        {cls.total_volume_m3.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot className="bg-gray-50 border-t-2 border-gray-300">
                  <tr className="font-semibold">
                    <td className="px-6 py-4 text-sm text-gray-800">TOTAL</td>
                    <td className="px-6 py-4 text-right text-sm text-gray-800">
                      {results.net_analysis_area_ha.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-right text-sm text-gray-800">100.0%</td>
                    <td className="px-6 py-4 text-right text-sm text-gray-800">
                      {results.avg_biomass_mg_per_ha.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-right text-sm text-gray-800">
                      {results.avg_volume_m3_per_ha.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-right text-sm font-bold text-emerald-700">
                      {results.total_biomass_mg.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 text-right text-sm font-bold text-amber-700">
                      {results.total_volume_m3.toFixed(2)}
                    </td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {/* Analysis Info */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-blue-800">
              <p className="font-medium">Analysis Methodology:</p>
              <ul className="mt-2 space-y-1 text-blue-700">
                <li>• Land cover classification: ESA World Cover 2020 (10m resolution)</li>
                <li>• Above-ground biomass: ESA CCI AGB 2022 Nepal (100m resolution)</li>
                <li>
                  • Timber volume conversion factor: 0.67 (wood density)
                </li>
                {results.has_forest_overlap && (
                  <li className="text-orange-700 font-medium">
                    • Community forest overlap ({results.forest_overlap_area_ha.toFixed(2)} ha) excluded from calculations
                  </li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Instructions (when no results) */}
      {!results && !loading && !error && (
        <div className="text-center py-12 text-gray-500">
          <Leaf className="w-16 h-16 mx-auto mb-4 text-gray-300" />
          <p className="text-lg font-medium text-gray-600 mb-2">
            Ready to Analyze Land Cover & Biomass
          </p>
          <p className="text-sm max-w-md mx-auto">
            Click "Run Analysis" to perform comprehensive land use classification and biomass
            estimation for your user group area. The analysis will automatically exclude any
            overlapping community forest areas.
          </p>
        </div>
      )}
    </div>
  );
}
