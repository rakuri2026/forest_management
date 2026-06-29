import React, { useState, useEffect } from 'react';
import { Pie, Bar } from 'react-chartjs-2';
import { fieldInventoryApi, forestApi } from '../services/api';

interface TotalInventoryTabProps {
  calculationId: string;
  refreshKey?: number;
}

interface TreeCoverArea {
  block_name: string;
  total_area_ha: number;
  effective_area_ha: number;
  tree_cover_percentage: number;
  tree_pixels: number;
  total_pixels: number;
  tree_cover_ratio: number;
}

export const TotalInventoryTab: React.FC<TotalInventoryTabProps> = ({ calculationId, refreshKey = 0 }) => {
  const [loading, setLoading] = useState(false);
  const [treeCoverLoading, setTreeCoverLoading] = useState(false);
  const [treeCoverError, setTreeCoverError] = useState<string | null>(null);
  const [fieldInventory, setFieldInventory] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [blockAreas, setBlockAreas] = useState<Record<string, number>>({});
  const [treeCoverAreas, setTreeCoverAreas] = useState<Record<string, TreeCoverArea>>({});
  const [totalData, setTotalData] = useState<any>(null);
  const [customMultipliers, setCustomMultipliers] = useState<Record<string, number>>({});
  const [initialCalculationDone, setInitialCalculationDone] = useState(false);
  const [speciesDbhData, setSpeciesDbhData] = useState<any[] | null>(null);
  const [speciesDbhForestWide, setSpeciesDbhForestWide] = useState<any[] | null>(null);

  useEffect(() => {
    setInitialCalculationDone(false);
    setTotalData(null);

    loadFieldInventory();
    loadTreeCoverAreas();
  }, [calculationId, refreshKey]);

  useEffect(() => {
    if (
      fieldInventory?.id &&
      Object.keys(treeCoverAreas).length > 0 &&
      Object.keys(blockAreas).length > 0 &&
      !initialCalculationDone &&
      !loading
    ) {
      const allAreasPopulated = Object.values(blockAreas).every(area => area > 0);
      if (allAreasPopulated) {
        console.log('Auto-calculating totals with tree cover areas...');
        handleCalculateTotals(false).then(() => {
          setInitialCalculationDone(true);
        });
      }
    }
  }, [fieldInventory, treeCoverAreas, blockAreas, initialCalculationDone, loading]);

  const loadTreeCoverAreas = async () => {
    try {
      setTreeCoverLoading(true);
      setTreeCoverError(null);

      console.log('Calling calculateTreeCoverAreas for calculation:', calculationId);
      const response = await forestApi.calculateTreeCoverAreas(calculationId);
      console.log('Tree cover response:', response);

      if (!response.tree_cover_areas || response.tree_cover_areas.length === 0) {
        setTreeCoverError('No tree cover data returned. Blocks may not have geometry.');
        return;
      }

      const treeCoverMap: Record<string, TreeCoverArea> = {};
      response.tree_cover_areas?.forEach((area: TreeCoverArea) => {
        treeCoverMap[area.block_name] = area;
      });
      setTreeCoverAreas(treeCoverMap);

      let effectiveAreas: Record<string, number> = {};
      try {
        console.log('Fetching block-area-detail for calculation:', calculationId);
        const blockDetail = await forestApi.getBlockAreaDetail(calculationId);
        console.log('Block-area-detail response:', blockDetail);
        if (blockDetail?.block_details && blockDetail.block_details.length > 0) {
          blockDetail.block_details.forEach((bd: any) => {
            effectiveAreas[bd.block_name] = bd.effective_area_ha || 0;
          });
          console.log('Using effective areas from block-area-detail:', effectiveAreas);
        } else {
          console.warn('Block-area-detail returned no block_details');
        }
      } catch (bdErr: any) {
        console.warn('Failed to load block area details:', bdErr?.response?.data || bdErr.message || bdErr);
      }

      if (Object.keys(effectiveAreas).length === 0) {
        console.log('Falling back to tree_cover_areas effective_area_ha');
        response.tree_cover_areas?.forEach((area: TreeCoverArea) => {
          effectiveAreas[area.block_name] = area.effective_area_ha;
        });
      }

      console.log('Setting blockAreas to:', effectiveAreas);
      setBlockAreas(effectiveAreas);

    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      console.error('Error loading tree cover areas:', err);
      console.error('Error details:', errorMsg);
      setTreeCoverError(`Failed to calculate tree cover areas: ${errorMsg}`);
    } finally {
      setTreeCoverLoading(false);
    }
  };

  const loadFieldInventory = async () => {
    try {
      setLoading(true);
      const inventory = await fieldInventoryApi.getByCalculation(calculationId);
      setFieldInventory(inventory);

      if (inventory?.id) {
        const summaryData = await fieldInventoryApi.getSummary(inventory.id);
        setSummary(summaryData);
        try {
          const sdbh = await fieldInventoryApi.getSpeciesDbhBreakdown(inventory.id);
          setSpeciesDbhData(sdbh.species_dbh_breakdown || []);
          setSpeciesDbhForestWide(sdbh.species_dbh_forest_wide || []);
        } catch { /* optional data */ }
      }
    } catch (err: any) {
      if (err.response?.status !== 404) {
        console.error('Error loading field inventory:', err);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCalculateTotals = async (showAlerts: boolean = true) => {
    if (!fieldInventory?.id) {
      if (showAlerts) {
        console.log('No field inventory available yet');
      }
      return;
    }

    const missingAreas = Object.entries(blockAreas).filter(([_, area]) => area === 0);
    if (missingAreas.length > 0) {
      if (showAlerts) {
        alert(`Please enter areas for all blocks: ${missingAreas.map(([name]) => name).join(', ')}`);
      }
      return;
    }

    try {
      setLoading(true);
      console.log('Calculating total inventory with areas:', blockAreas);
      const result = await fieldInventoryApi.getTotalInventory(
        fieldInventory.id,
        blockAreas,
        customMultipliers
      );
      setTotalData(result);
      if (result?.blocks) {
        setBlockRates((prev) => {
          const updated = { ...prev };
          result.blocks.forEach((b: any) => {
            if (!updated[b.block_name]) {
              updated[b.block_name] = { timber: 5000, fuelwood: 1500, carbon: 1500 };
            }
          });
          return updated;
        });
      }
      console.log('Total inventory calculated successfully:', result);
    } catch (err) {
      console.error('Error calculating total inventory:', err);
      if (showAlerts) {
        alert('Error calculating total inventory. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const DBH_CLASS_CONFIG = [
    { key: '0_4', label: '०-४ से.मि.' },
    { key: '4_10', label: '४-१० से.मि.' },
    { key: '10_20', label: '१०-२० पोल' },
    { key: '20_30', label: '२०-३० पोल' },
    { key: '30_40', label: '३०-४० रूख' },
    { key: '40_50', label: '४०-५० रूख' },
    { key: '50_60', label: '५०-६० रूख' },
    { key: '60_plus', label: '६०+ रूख' },
  ];

  const sortDbhClasses = (items: any[]): any[] =>
    [...items].sort((a, b) => {
      const getNum = (s: string): number => {
        const m = s.match(/(\d+)/);
        return m ? parseInt(m[1], 10) : 999;
      };
      return getNum(a.dbh_class) - getNum(b.dbh_class);
    });

  const computeBlockSubtotal = (block: any, field: string, isPerHa: boolean): number => {
    const data = isPerHa ? block.dbh_class_per_ha : block.dbh_class_totals;
    if (!data) return 0;
    return DBH_CLASS_CONFIG.reduce((sum, { key }) => {
      const d = data[key];
      return sum + (d ? Number(d[field] || 0) : 0);
    }, 0);
  };

  const fmt = (v: any, decimals: number = 2): string => {
    const n = Number(v || 0);
    return n.toFixed(decimals);
  };

  const fmtPH = (v: any): string => {
    const n = Number(v || 0);
    return n.toFixed(1);
  };

  const CHART_COLORS = [
    '#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336',
    '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63',
    '#3F51B5', '#009688', '#FF5722', '#CDDC39', '#03A9F4',
  ];

  const buildSpeciesChartData = (speciesList: any[]) => {
    if (!speciesList || speciesList.length === 0) return null;
    const topSpecies = speciesList.slice(0, 10);
    const otherVolume = speciesList.slice(10).reduce((s: number, sp: any) => s + (sp.volume_m3 || 0), 0);
    const labels = topSpecies.map((sp: any) => sp.species_local || sp.species_scientific || '—');
    const data = topSpecies.map((sp: any) => Math.round(sp.volume_m3 || 0));
    if (otherVolume > 0) { labels.push('अन्य'); data.push(Math.round(otherVolume)); }
    return { labels, datasets: [{ data, backgroundColor: CHART_COLORS.slice(0, labels.length), borderWidth: 1 }] };
  };

  const buildBlockBarChartData = (blocks: any[]) => {
    if (!blocks || blocks.length === 0) return null;
    const labels = blocks.map((b: any) => b.block_name);
    const growingStock = blocks.map((b: any) => b.total_growing_stock_m3 || 0);
    const mai = blocks.map((b: any) => b.total_mai_m3 || 0);
    const aah = blocks.map((b: any) => b.total_aah_m3 || 0);
    return {
      labels,
      datasets: [
        { label: 'उत्पादनसिल संचिती (m³)', data: growingStock, backgroundColor: '#4CAF50', borderColor: '#388E3C', borderWidth: 1 },
        { label: 'MAI (m³/वर्ष)', data: mai, backgroundColor: '#2196F3', borderColor: '#1976D2', borderWidth: 1 },
        { label: 'AAH (m³/वर्ष)', data: aah, backgroundColor: '#FF9800', borderColor: '#F57C00', borderWidth: 1 },
      ],
    };
  };

  const [blockRates, setBlockRates] = useState<Record<string, { timber: number; fuelwood: number; carbon: number }>>({});
  const getBlockRate = (blockName: string) => blockRates[blockName] || { timber: 5000, fuelwood: 1500, carbon: 1500 };

  if (!fieldInventory) {
    return (
      <div className="p-6 bg-yellow-50 rounded-lg border border-yellow-200">
        <p className="text-yellow-800">
          No field inventory data available. Please upload field inventory data first in the "Field Inventory" tab.
        </p>
      </div>
    );
  }

  const treeCoverList = Object.values(treeCoverAreas);

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border-2 border-blue-300 p-6">
        <h3 className="text-xl font-bold text-blue-900 mb-2">कुल मौज्दात - निरपेक्ष परिमाण</h3>
        <p className="text-sm text-gray-600">
          ब्लक क्षेत्रफल प्रभावकारी वन आवरणबाट स्वतः भरिएको (बाँझो जमिन, जलाशय, आदि बाहेक).
        </p>
      </div>

      {/* Block Areas Input */}
      <div className="bg-white rounded-lg shadow p-6">
        <h4 className="text-lg font-semibold text-gray-900 mb-4">
          चरण १: ब्लक क्षेत्रफल - प्रभावकारी वन आवरण
          <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_block_area_table}}'}</code>
        </h4>

        {treeCoverLoading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="text-sm text-gray-600 mt-2">रूख आवरण क्षेत्रफल गणना हुँदै...</p>
          </div>
        ) : treeCoverError ? (
          <div className="p-4 bg-red-50 rounded-md border border-red-200">
            <p className="text-sm text-red-800 font-medium">रूख आवरण क्षेत्रफल गणना त्रुटि:</p>
            <p className="text-sm text-red-700 mt-1">{treeCoverError}</p>
            <button
              onClick={loadTreeCoverAreas}
              className="mt-3 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
            >
              पुन: गणना गर्नुहोस्
            </button>
          </div>
        ) : (
          <>
            <div className="mb-4 p-3 bg-blue-50 rounded-md text-sm text-blue-800">
              <p className="font-medium">रूख आवरण क्षेत्रफल स्वतः भरियो</p>
              <p className="text-xs mt-1">
                तलको क्षेत्रफल प्रभावकारी वन आवरण देखाउँदछ (बाँझो जमिन, जलाशय, आदि बाहेक).
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {treeCoverList.map((treeCoverInfo) => {
                const effectiveArea = blockAreas[treeCoverInfo.block_name] ?? treeCoverInfo.effective_area_ha;
                return (
                <div key={treeCoverInfo.block_name} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                  <label className="font-semibold text-gray-900 mb-2 block">{treeCoverInfo.block_name}</label>

                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex-1 px-3 py-2 bg-gray-100 border border-gray-300 rounded-md text-gray-700 font-medium">
                      {effectiveArea.toFixed(2)}
                    </div>
                    <span className="text-sm font-medium text-gray-600">हे.</span>
                  </div>

                  <div className="text-xs text-gray-600 space-y-1 bg-white p-2 rounded border border-gray-200">
                    <div className="flex justify-between">
                      <span>जम्मा सिमाना:</span>
                      <span className="font-medium">{treeCoverInfo.total_area_ha.toFixed(2)} हे.</span>
                    </div>
                    <div className="flex justify-between text-green-700 font-medium">
                      <span>वन आवरण:</span>
                      <span>{treeCoverInfo.effective_area_ha.toFixed(2)} हे. ({treeCoverInfo.tree_cover_percentage.toFixed(1)}%)</span>
                    </div>
                  </div>
                </div>
              ); })}
            </div>
          </>
        )}
      </div>

      {/* Manual calculate trigger (fallback if auto-calc didn't run) */}
      {treeCoverList.length > 0 && !totalData && !loading && (
        <div className="text-center">
          <button
            onClick={() => handleCalculateTotals(true)}
            disabled={loading}
            className="px-6 py-3 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 font-medium"
          >
            {loading ? 'गणना हुँदै...' : 'कुल मौज्दात गणना गर्नुहोस्'}
          </button>
        </div>
      )}

      {/* Loading indicator */}
      {loading && !totalData && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="text-sm text-gray-600 mt-2">कुल मौज्दात गणना हुँदै...</p>
        </div>
      )}

      {/* No matching blocks warning */}
      {totalData && (!totalData.forest_totals || Object.keys(totalData.forest_totals).length === 0) && (
        <div className="p-4 bg-red-50 rounded-md border border-red-200">
          <p className="text-sm text-red-800 font-medium">कुनै पनि ब्लक भेटिएन</p>
          <p className="text-xs text-red-700 mt-1">
            रूख आवरण ब्लक नामहरू ({Object.keys(blockAreas).join(', ')}) फिल्ड इन्भेन्ट्री डाटाका ब्लक नामहरूसँग मेल खाएनन्।
          </p>
          <p className="text-xs text-red-600 mt-1">
            कृपया मिल्ने ब्लक नाम भएको फिल्ड इन्भेन्ट्री CSV पुन: अपलोड गर्नुहोस्।
          </p>
        </div>
      )}

      {/* Total Inventory Results */}
      {totalData && totalData.forest_totals && Object.keys(totalData.forest_totals).length > 0 && (
        <>
          {/* Forest-Wide Totals Summary */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border-2 border-green-400 p-6 shadow-lg">
            <h3 className="text-xl font-bold text-green-800 mb-4">
              सामुदायिक वन कुल योग
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_forest_total_narration}}'}</code>
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">जम्मा क्षेत्रफल</div>
                <div className="text-2xl font-bold text-green-700">{(totalData.forest_totals.total_area_ha || 0).toLocaleString()} हे.</div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">जम्मा रूख</div>
                <div className="text-2xl font-bold text-blue-700">
                  {((totalData.forest_totals.total_pole || 0) + (totalData.forest_totals.total_tree || 0)).toLocaleString()}
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">उत्पादनसिल संचिती</div>
                <div className="text-xl font-bold text-amber-700">
                  {(totalData.forest_totals.total_growing_stock_m3 || 0).toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">MAI/वर्ष</div>
                <div className="text-xl font-bold text-purple-700">
                  {(totalData.forest_totals.total_mai_m3_per_year || 0).toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md bg-amber-50">
                <div className="text-xs text-gray-600 mb-1 font-medium">AAH/वर्ष</div>
                <div className="text-2xl font-bold text-amber-800">
                  {(totalData.forest_totals.total_aah_m3_per_year || 0).toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">जम्मा जैविक पदार्थ</div>
                <div className="text-xl font-bold text-teal-700">
                  {(totalData.forest_totals.total_biomass_tonnes || 0).toLocaleString()} t
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">कार्बन मौज्दात</div>
                <div className="text-xl font-bold text-teal-700">
                  {(totalData.forest_totals.total_carbon_tc || 0).toLocaleString()} tC
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md bg-teal-50">
                <div className="text-xs text-gray-600 mb-1 font-medium">CO₂ बराबर</div>
                <div className="text-xl font-bold text-teal-800">
                  {(totalData.forest_totals.total_co2_tco2 || 0).toLocaleString()} tCO₂
                </div>
              </div>
            </div>
          </div>

          {/* Block-wise Totals Table */}
          {totalData.blocks && totalData.blocks.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">
              ब्लक अनुसार कुल मौज्दात
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_block_growing_stock}}'}</code>
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_block_growing_stock_narration}}'}</code>
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">ब्लक</th>
                    <th rowSpan={2} className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">क्षेत्रफल (हे.)</th>
                    <th colSpan={4} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-blue-50">जम्मा रूख</th>
                    <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-amber-50">जम्मा आयतन (m³)</th>
                    <th colSpan={2} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-teal-50">जम्मा कार्बन</th>
                  </tr>
                  <tr>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">बिरुवा</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">लाथ्रा</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">पोल</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">रूख</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">मौज्दात</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">MAI/वर्ष</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">AAH/वर्ष</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">जैविक (ट.)</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">CO₂ (tCO₂)</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {totalData.blocks.map((block: any, index: number) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-3 py-3 text-sm font-medium text-gray-900 border-r border-gray-200">{block.block_name}</td>
                      <td className="px-3 py-3 text-sm text-center border-r border-gray-200">{(block.area_ha || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{(block.total_regeneration || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{(block.total_sapling || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{(block.total_pole || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{(block.total_tree || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{(block.total_growing_stock_m3 || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{(block.total_mai_m3 || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right border-r border-gray-200 font-semibold text-amber-700">{(block.total_aah_m3 || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{(block.total_biomass_tonnes || 0).toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{(block.total_co2_tco2 || 0).toLocaleString()}</td>
                    </tr>
                  ))}
                  <tr className="bg-green-100 font-bold">
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन</td>
                    <td className="px-3 py-3 text-sm text-center border-r border-gray-200">{(totalData.forest_totals.total_area_ha || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{(totalData.forest_totals.total_regeneration || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{(totalData.forest_totals.total_sapling || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{(totalData.forest_totals.total_pole || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{(totalData.forest_totals.total_tree || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{(totalData.forest_totals.total_growing_stock_m3 || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{(totalData.forest_totals.total_mai_m3_per_year || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right border-r border-gray-200 text-amber-900">{(totalData.forest_totals.total_aah_m3_per_year || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{(totalData.forest_totals.total_biomass_tonnes || 0).toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{(totalData.forest_totals.total_co2_tco2 || 0).toLocaleString()}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          )}

          {/* Species Breakdown Table */}
          {totalData.species_breakdown && totalData.species_breakdown.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-2">
                प्रजाति अनुसार कुल मौज्दात
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_species_block_growing_stock}}'}</code>
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_species_stock_narration}}'}</code>
              </h4>
              <p className="text-xs text-gray-500 mb-4">सबै ब्लकहरूमा प्रजाति अनुसार निरपेक्ष गणना र आयतन</p>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">वैज्ञानिक नाम</th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">स्थानीय नाम</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">गणना</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">काठ (m³)</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">दाउरा (m³)</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">आयतन (m³)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {totalData.species_breakdown.map((sp: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-sm text-gray-900 italic">{sp.species_scientific || '—'}</td>
                        <td className="px-3 py-2 text-sm text-gray-700">{sp.species_local || '—'}</td>
                        <td className="px-3 py-2 text-sm text-right">{(sp.count || 0).toLocaleString()}</td>
                        <td className="px-3 py-2 text-sm text-right">{fmt(sp.timber_m3)}</td>
                        <td className="px-3 py-2 text-sm text-right">{fmt(sp.fuelwood_m3)}</td>
                        <td className="px-3 py-2 text-sm text-right font-medium">{fmt(sp.volume_m3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Species × DBH Class Breakdown Table */}
          {speciesDbhData && speciesDbhData.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-2">
                प्रजाति अनुसार DBH क्लास मौज्दात
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_species_dbh_class_table}}'}</code>
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_species_dbh_narration}}'}</code>
              </h4>
              <p className="text-xs text-gray-500 mb-4">प्रजाति र DBH क्लास अनुसार प्रति हेक्टर गणना र आयतन</p>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">ब्लक</th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">स्थानीय नाम</th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">DBH क्लास</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">गणना/हे.</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">काठ (m³/हे.)</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">दाउरा (m³/हे.)</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">आयतन (m³/हे.)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {(() => {
                      const blockGroups: Record<string, any[]> = {};
                      speciesDbhData.forEach((item: any) => {
                        if (!blockGroups[item.block_name]) blockGroups[item.block_name] = [];
                        blockGroups[item.block_name].push(item);
                      });
                      const blockNames = Object.keys(blockGroups);
                      const rows: JSX.Element[] = [];
                      let grandCount = 0, grandTimber = 0, grandFuel = 0, grandVol = 0;
                      blockNames.forEach((bn, bi) => {
                        const items = blockGroups[bn];
                        // Group by species within block
                        const spGroups: Record<string, any[]> = {};
                        items.forEach((item: any) => {
                          const sk = item.species_local || item.species_scientific || '—';
                          if (!spGroups[sk]) spGroups[sk] = [];
                          spGroups[sk].push(item);
                        });
                        let blkCount = 0, blkTimber = 0, blkFuel = 0, blkVol = 0;
                        Object.keys(spGroups).forEach((sk) => {
                          const spItems = sortDbhClasses(spGroups[sk]);
                          let spCount = 0, spTimber = 0, spFuel = 0, spVol = 0;
                          spItems.forEach((item: any) => {
                            spCount += item.count_per_ha || 0;
                            spTimber += item.timber_m3_per_ha || 0;
                            spFuel += item.fuelwood_m3_per_ha || 0;
                            spVol += item.volume_m3_per_ha || 0;
                            rows.push(
                              <tr key={`${bi}-${sk}-${item.dbh_class}`} className="hover:bg-gray-50">
                                <td className="px-3 py-2 text-sm text-gray-900">{item.block_name}</td>
                                <td className="px-3 py-2 text-sm text-gray-700">{sk}</td>
                                <td className="px-3 py-2 text-sm text-gray-600">{DBH_CLASS_CONFIG.find((c: any) => c.key === item.dbh_class)?.label || item.dbh_class}</td>
                                <td className="px-3 py-2 text-sm text-right">{item.count_per_ha?.toFixed(1) || '—'}</td>
                                <td className="px-3 py-2 text-sm text-right">{item.timber_m3_per_ha?.toFixed(2) || '—'}</td>
                                <td className="px-3 py-2 text-sm text-right">{item.fuelwood_m3_per_ha?.toFixed(2) || '—'}</td>
                                <td className="px-3 py-2 text-sm text-right font-medium">{item.volume_m3_per_ha?.toFixed(2) || '—'}</td>
                              </tr>
                            );
                          });
                          // Species subtotal within block
                          rows.push(
                            <tr key={`${bi}-sp-sub-${sk}`} className="bg-yellow-50 font-semibold text-yellow-800">
                              <td className="px-3 py-2 text-sm" colSpan={3}>प्रजाति जम्मा — {sk}</td>
                              <td className="px-3 py-2 text-sm text-right">{spCount.toFixed(1)}</td>
                              <td className="px-3 py-2 text-sm text-right">{spTimber.toFixed(2)}</td>
                              <td className="px-3 py-2 text-sm text-right">{spFuel.toFixed(2)}</td>
                              <td className="px-3 py-2 text-sm text-right">{spVol.toFixed(2)}</td>
                            </tr>
                          );
                          blkCount += spCount; blkTimber += spTimber; blkFuel += spFuel; blkVol += spVol;
                        });
                        // Block subtotal
                        rows.push(
                          <tr key={`sub-${bi}`} className="bg-green-50 font-semibold">
                            <td className="px-3 py-2 text-sm text-green-800" colSpan={3}>ब्लक जम्मा — {bn}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{blkCount.toFixed(1)}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{blkTimber.toFixed(2)}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{blkFuel.toFixed(2)}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{blkVol.toFixed(2)}</td>
                          </tr>
                        );
                        grandCount += blkCount; grandTimber += blkTimber; grandFuel += blkFuel; grandVol += blkVol;
                      });
                      // Grand total
                      rows.push(
                        <tr key="grand" className="bg-blue-50 font-bold text-blue-900">
                          <td className="px-3 py-2 text-sm" colSpan={3}>पुरै वन क्षेत्र जम्मा</td>
                          <td className="px-3 py-2 text-sm text-right">{grandCount.toFixed(1)}</td>
                          <td className="px-3 py-2 text-sm text-right">{grandTimber.toFixed(2)}</td>
                          <td className="px-3 py-2 text-sm text-right">{grandFuel.toFixed(2)}</td>
                          <td className="px-3 py-2 text-sm text-right">{grandVol.toFixed(2)}</td>
                        </tr>
                      );
                      return rows;
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Species × DBH Class — Forest-Wide */}
          {speciesDbhForestWide && speciesDbhForestWide.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-2">
                पुरै वन क्षेत्र — प्रजाति अनुसार DBH क्लास मौज्दात
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_forest_dbh_class_table}}'}</code>
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_forest_dbh_narration}}'}</code>
              </h4>
              <p className="text-xs text-gray-500 mb-4">सबै ब्लकहरू मिलाएर प्रजाति र DBH क्लास अनुसार प्रति हेक्टर गणना र आयतन</p>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">स्थानीय नाम</th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">DBH क्लास</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">गणना/हे.</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">काठ (m³/हे.)</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">दाउरा (m³/हे.)</th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">आयतन (m³/हे.)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {(() => {
                      const spGroups: Record<string, any[]> = {};
                      speciesDbhForestWide.forEach((item: any) => {
                        const key = item.species_local || item.species_scientific || '—';
                        if (!spGroups[key]) spGroups[key] = [];
                        spGroups[key].push(item);
                      });
                      const spNames = Object.keys(spGroups);
                      const rows: JSX.Element[] = [];
                      let grandCount = 0, grandTimber = 0, grandFuel = 0, grandVol = 0;
                      spNames.forEach((sp, si) => {
                        const items = sortDbhClasses(spGroups[sp]);
                        let spCount = 0, spTimber = 0, spFuel = 0, spVol = 0;
                        items.forEach((item: any) => {
                          spCount += item.count_per_ha || 0;
                          spTimber += item.timber_m3_per_ha || 0;
                          spFuel += item.fuelwood_m3_per_ha || 0;
                          spVol += item.volume_m3_per_ha || 0;
                          rows.push(
                            <tr key={`fw-${si}-${item.dbh_class}`} className="hover:bg-gray-50">
                              <td className="px-3 py-2 text-sm text-gray-700">{sp}</td>
                              <td className="px-3 py-2 text-sm text-gray-600">{DBH_CLASS_CONFIG.find((c: any) => c.key === item.dbh_class)?.label || item.dbh_class}</td>
                              <td className="px-3 py-2 text-sm text-right">{item.count_per_ha?.toFixed(1) || '—'}</td>
                              <td className="px-3 py-2 text-sm text-right">{item.timber_m3_per_ha?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-2 text-sm text-right">{item.fuelwood_m3_per_ha?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-2 text-sm text-right font-medium">{item.volume_m3_per_ha?.toFixed(2) || '—'}</td>
                            </tr>
                          );
                        });
                        // Species subtotal
                        rows.push(
                          <tr key={`fw-sub-${si}`} className="bg-green-50 font-semibold">
                            <td className="px-3 py-2 text-sm text-green-800" colSpan={2}>प्रजाति जम्मा — {sp}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{spCount.toFixed(1)}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{spTimber.toFixed(2)}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{spFuel.toFixed(2)}</td>
                            <td className="px-3 py-2 text-sm text-right text-green-800">{spVol.toFixed(2)}</td>
                          </tr>
                        );
                        grandCount += spCount; grandTimber += spTimber; grandFuel += spFuel; grandVol += spVol;
                      });
                      // Grand total
                      rows.push(
                        <tr key="fw-grand" className="bg-blue-50 font-bold text-blue-900">
                          <td className="px-3 py-2 text-sm" colSpan={2}>पुरै वन क्षेत्र जम्मा</td>
                          <td className="px-3 py-2 text-sm text-right">{grandCount.toFixed(1)}</td>
                          <td className="px-3 py-2 text-sm text-right">{grandTimber.toFixed(2)}</td>
                          <td className="px-3 py-2 text-sm text-right">{grandFuel.toFixed(2)}</td>
                          <td className="px-3 py-2 text-sm text-right">{grandVol.toFixed(2)}</td>
                        </tr>
                      );
                      return rows;
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* DBH Class-wise Total Inventory (Absolute) */}
          {totalData.blocks && totalData.blocks.length > 0 && totalData.blocks[0].dbh_class_totals && (
          <div className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">
              DBH क्लास अनुसार कुल मौज्दात
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_dbh_class_totals_table}}'}</code>
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_dbh_total_narration}}'}</code>
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">ब्लक</th>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">DBH क्लास</th>
                    <th colSpan={4} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-blue-50 border-r border-gray-300">कुल योग</th>
                  </tr>
                  <tr>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">गणना</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">काठ (m³)</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">दाउरा (m³)</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">आयतन (m³)</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {totalData.blocks.map((block: any, bi: number) => {
                    const absData = block.dbh_class_totals || {};
                    const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                      const d = absData[key];
                      if (!d) return [];
                      return [{
                        key, label,
                        count: d.total_count,
                        timber: d.total_timber_m3,
                        firewood: d.total_firewood_m3,
                        volume: d.total_tree_volume_m3,
                      }];
                    });
                    if (rows.length === 0) return null;
                    const subtotal = {
                      count: computeBlockSubtotal(block, 'total_count', false),
                      timber: computeBlockSubtotal(block, 'total_timber_m3', false),
                      firewood: computeBlockSubtotal(block, 'total_firewood_m3', false),
                      volume: computeBlockSubtotal(block, 'total_tree_volume_m3', false),
                    };
                    return [
                      ...rows.map((r, ri) => (
                        <tr key={`${bi}_abs_${ri}`} className={ri === 0 ? 'border-t border-gray-200' : ''}>
                          {ri === 0 && (
                            <td rowSpan={rows.length + 1} className="px-3 py-2 text-sm font-medium text-gray-900 border-r border-gray-200 align-top">{block.block_name}</td>
                          )}
                          <td className="px-3 py-2 text-sm text-gray-700 border-r border-gray-200">{r.label}</td>
                          <td className="px-2 py-2 text-sm text-right">{(r.count || 0).toLocaleString()}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmt(r.timber)}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmt(r.firewood)}</td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(r.volume)}</td>
                        </tr>
                      )),
                      <tr key={`${bi}_abs_sub`} className="bg-blue-50 font-semibold">
                        <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{block.block_name} जम्मा</td>
                        <td className="px-2 py-2 text-sm text-right">{(Math.round(subtotal.count)).toLocaleString()}</td>
                        <td className="px-2 py-2 text-sm text-right">{fmt(subtotal.timber)}</td>
                        <td className="px-2 py-2 text-sm text-right">{fmt(subtotal.firewood)}</td>
                        <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(subtotal.volume)}</td>
                      </tr>,
                    ];
                  })}
                  {/* Forest-wide DBH class totals */}
                  {totalData.forest_totals?.dbh_class_totals && (
                    <>
                      {(() => {
                        const ftDBH = totalData.forest_totals.dbh_class_totals;
                        const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                          const d = ftDBH[key];
                          if (!d) return [];
                          return [{
                            key, label,
                            count: d.total_count,
                            timber: d.total_timber_m3,
                            firewood: d.total_firewood_m3,
                            volume: d.total_tree_volume_m3,
                          }];
                        });
                        const fsub = {
                          count: rows.reduce((s: number, r: any) => s + (r.count || 0), 0),
                          timber: rows.reduce((s: number, r: any) => s + (r.timber || 0), 0),
                          firewood: rows.reduce((s: number, r: any) => s + (r.firewood || 0), 0),
                          volume: rows.reduce((s: number, r: any) => s + (r.volume || 0), 0),
                        };
                        return [
                          ...rows.map((r, ri) => (
                            <tr key={`ft_abs_${ri}`} className="bg-green-100 font-bold">
                              {ri === 0 && (
                                <td rowSpan={rows.length + 1} className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन</td>
                              )}
                              <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{r.label}</td>
                              <td className="px-2 py-2 text-sm text-right">{(r.count || 0).toLocaleString()}</td>
                              <td className="px-2 py-2 text-sm text-right">{fmt(r.timber)}</td>
                              <td className="px-2 py-2 text-sm text-right">{fmt(r.firewood)}</td>
                              <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(r.volume)}</td>
                            </tr>
                          )),
                          <tr key="ft_abs_sub" className="bg-green-100 font-bold border-t-2 border-green-400">
                            <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन कुल</td>
                            <td className="px-2 py-3 text-sm text-right">{(Math.round(fsub.count)).toLocaleString()}</td>
                            <td className="px-2 py-3 text-sm text-right">{fmt(fsub.timber)}</td>
                            <td className="px-2 py-3 text-sm text-right">{fmt(fsub.firewood)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-300">{fmt(fsub.volume)}</td>
                          </tr>,
                        ];
                      })()}
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </div>
          )}

          {/* DBH Class-wise Total Inventory (Growing Stock) */}
          {totalData.blocks && totalData.blocks.length > 0 && totalData.blocks[0].dbh_class_totals && (
          <div className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">
              DBH क्लास अनुसार कुल मौज्दात (प्रति हे.)
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_dbh_class_perha_table}}'}</code>
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_dbh_perha_narration}}'}</code>
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">ब्लक</th>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">DBH क्लास</th>
                    <th colSpan={4} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-amber-50 border-r border-gray-300">प्रति हेक्टर</th>
                  </tr>
                  <tr>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">गणना/हे.</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">काठ (m³/हे.)</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">दाउरा (m³/हे.)</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">आयतन (m³/हे.)</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {totalData.blocks.map((block: any, bi: number) => {
                    const gsData = block.dbh_class_per_ha || block.dbh_class_totals || {};
                    const absData = block.dbh_class_totals || {};
                    const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                      const d = gsData[key];
                      const abs = absData[key];
                      if (!d && !abs) return [];
                      return [{
                        key, label,
                        count: abs?.total_count || 0,
                        timber: abs?.total_timber_m3 || 0,
                        firewood: abs?.total_firewood_m3 || 0,
                        volume: abs?.total_tree_volume_m3 || 0,
                        ph_count: d?.count_per_ha ?? d?.per_ha_count ?? 0,
                        ph_timber: d?.timber_m3_per_ha ?? d?.per_ha_timber_m3 ?? 0,
                        ph_firewood: d?.firewood_m3_per_ha ?? d?.per_ha_firewood_m3 ?? 0,
                        ph_volume: d?.tree_volume_m3_per_ha ?? d?.per_ha_tree_volume_m3 ?? 0,
                      }];
                    });
                    if (rows.length === 0) return null;
                    const ha = block.area_ha || 1;
                    const subtotalPH = {
                      count: rows.reduce((s: number, r: any) => s + (r.ph_count || 0), 0),
                      timber: rows.reduce((s: number, r: any) => s + (r.ph_timber || 0), 0),
                      firewood: rows.reduce((s: number, r: any) => s + (r.ph_firewood || 0), 0),
                      volume: rows.reduce((s: number, r: any) => s + (r.ph_volume || 0), 0),
                    };
                    return [
                      ...rows.map((r, ri) => (
                        <tr key={`${bi}_gs_${ri}`} className={ri === 0 ? 'border-t border-gray-200' : ''}>
                          {ri === 0 && (
                            <td rowSpan={rows.length + 1} className="px-3 py-2 text-sm font-medium text-gray-900 border-r border-gray-200 align-top">{block.block_name}</td>
                          )}
                          <td className="px-3 py-2 text-sm text-gray-700 border-r border-gray-200">{r.label}</td>
                          <td className="px-2 py-2 text-sm text-right">{(r.ph_count || 0).toFixed(1)}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmtPH(r.ph_timber)}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmtPH(r.ph_firewood)}</td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmtPH(r.ph_volume)}</td>
                        </tr>
                      )),
                      <tr key={`${bi}_gs_sub`} className="bg-amber-50 font-semibold">
                        <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{block.block_name} जम्मा/हे.</td>
                        <td className="px-2 py-2 text-sm text-right">{subtotalPH.count.toFixed(1)}</td>
                        <td className="px-2 py-2 text-sm text-right">{fmtPH(subtotalPH.timber)}</td>
                        <td className="px-2 py-2 text-sm text-right">{fmtPH(subtotalPH.firewood)}</td>
                        <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmtPH(subtotalPH.volume)}</td>
                      </tr>,
                    ];
                  })}
                  {/* Forest-wide DBH class per-hectare totals */}
                  {totalData.forest_totals?.dbh_class_totals && (() => {
                    const ftArea = totalData.forest_totals.total_area_ha || 1;
                    const ftDBH = totalData.forest_totals.dbh_class_totals;
                    const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                      const d = ftDBH[key];
                      if (!d) return [];
                      return [{
                        key, label,
                        ph_count: (d.total_count || 0) / ftArea,
                        ph_timber: (d.total_timber_m3 || 0) / ftArea,
                        ph_firewood: (d.total_firewood_m3 || 0) / ftArea,
                        ph_volume: (d.total_tree_volume_m3 || 0) / ftArea,
                      }];
                    });
                    const fsubPH = {
                      count: rows.reduce((s: number, r: any) => s + r.ph_count, 0),
                      timber: rows.reduce((s: number, r: any) => s + r.ph_timber, 0),
                      firewood: rows.reduce((s: number, r: any) => s + r.ph_firewood, 0),
                      volume: rows.reduce((s: number, r: any) => s + r.ph_volume, 0),
                    };
                    return (
                      <>
                        {rows.map((r, ri) => (
                          <tr key={`ft_gs_${ri}`} className="bg-green-100 font-bold">
                            {ri === 0 && (
                              <td rowSpan={rows.length + 1} className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन</td>
                            )}
                            <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{r.label}</td>
                            <td className="px-2 py-2 text-sm text-right">{r.ph_count.toFixed(1)}</td>
                            <td className="px-2 py-2 text-sm text-right">{fmtPH(r.ph_timber)}</td>
                            <td className="px-2 py-2 text-sm text-right">{fmtPH(r.ph_firewood)}</td>
                            <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmtPH(r.ph_volume)}</td>
                          </tr>
                        ))}
                        <tr key="ft_gs_sub" className="bg-green-100 font-bold border-t-2 border-green-400">
                          <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन कुल/हे.</td>
                          <td className="px-2 py-3 text-sm text-right">{fsubPH.count.toFixed(1)}</td>
                          <td className="px-2 py-3 text-sm text-right">{fmtPH(fsubPH.timber)}</td>
                          <td className="px-2 py-3 text-sm text-right">{fmtPH(fsubPH.firewood)}</td>
                          <td className="px-2 py-3 text-sm text-right border-r border-gray-300">{fmtPH(fsubPH.volume)}</td>
                        </tr>
                      </>
                    );
                  })()}
                </tbody>
              </table>
            </div>
          </div>
          )}

          {/* MAI (Mean Annual Increment) */}
          {totalData.blocks && totalData.blocks.some((b: any) => b.mai_by_species && b.mai_by_species.length > 0) && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-2">
                प्रजाति अनुसार MAI
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_mai_table}}'}</code>
              </h4>
              <p className="text-xs text-gray-500 mb-4">प्रजाति अनुसार मध्यम वार्षिक वृद्धि (m³/वर्ष)</p>
              <div className="overflow-x-auto">
                {totalData.blocks.map((block: any, bi: number) => {
                  const species = block.mai_by_species || [];
                  if (species.length === 0) return null;
                  return (
                    <div key={bi} className="mb-4">
                      <h5 className="text-sm font-semibold text-gray-800 mb-2">{block.block_name}</h5>
                      <table className="min-w-full divide-y divide-gray-200 text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">प्रजाति</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">गणना/हे.</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">आयतन/हे. (m³)</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">MAI/हे. (m³)</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">जम्मा MAI (m³)</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {species.map((sp: any, si: number) => (
                            <tr key={si} className="hover:bg-gray-50">
                              <td className="px-3 py-1.5 text-sm">{sp.species_local || sp.species_scientific || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right">{sp.count_per_ha?.toFixed(1) || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right">{sp.volume_per_ha?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right">{sp.mai_per_ha?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right font-medium">{sp.mai_total?.toFixed(2) || '—'}</td>
                            </tr>
                          ))}
                          <tr className="bg-purple-50 font-semibold">
                            <td className="px-3 py-1.5 text-sm">{block.block_name} जम्मा</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.count_per_ha || 0), 0).toFixed(1)}</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.volume_per_ha || 0), 0).toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.mai_per_ha || 0), 0).toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.mai_total || 0), 0).toFixed(2)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* DBH Class-wise MAI */}
          {totalData.blocks && totalData.blocks.some((b: any) => b.dbh_class_totals) && (
            <div className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">
              DBH क्लास अनुसार MAI
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_dbh_mai_table}}'}</code>
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_dbh_mai_narration}}'}</code>
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">ब्लक</th>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">DBH क्लास</th>
                    <th colSpan={2} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-purple-50 border-r border-gray-300">MAI</th>
                    </tr>
                    <tr>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">MAI/हे. (m³/वर्ष)</th>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">जम्मा MAI (m³/वर्ष)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {totalData.blocks.map((block: any, bi: number) => {
                      const dbhData = block.dbh_class_totals || {};
                      const blockMaiTotal = block.total_mai_m3 || 0;
                      const blockVolume = (Object.values(dbhData) as any[]).reduce((s: number, d: any) => s + (d.total_tree_volume_m3 || 0), 0);
                      const ha = block.area_ha || 1;
                      const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                        const d = dbhData[key];
                        if (!d) return [];
                        const classVol = d.total_tree_volume_m3 || 0;
                        const maiTotal = blockVolume > 0 ? (classVol / blockVolume) * blockMaiTotal : 0;
                        return { key, label, mai_per_ha: maiTotal / ha, mai_total: maiTotal };
                      });
                      if (rows.length === 0) return null;
                      const subtotal = {
                        per_ha: rows.reduce((s, r) => s + r.mai_per_ha, 0),
                        total: rows.reduce((s, r) => s + r.mai_total, 0),
                      };
                      return [
                        ...rows.map((r, ri) => (
                          <tr key={`${bi}_mai_${ri}`} className={ri === 0 ? 'border-t border-gray-200' : ''}>
                            {ri === 0 && (
                              <td rowSpan={rows.length + 1} className="px-3 py-2 text-sm font-medium text-gray-900 border-r border-gray-200 align-top">{block.block_name}</td>
                            )}
                            <td className="px-3 py-2 text-sm text-gray-700 border-r border-gray-200">{r.label}</td>
                            <td className="px-2 py-2 text-sm text-right">{fmtPH(r.mai_per_ha)}</td>
                            <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(r.mai_total)}</td>
                          </tr>
                        )),
                        <tr key={`${bi}_mai_sub`} className="bg-purple-50 font-semibold">
                          <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{block.block_name} जम्मा</td>
                          <td className="px-2 py-2 text-sm text-right">{fmtPH(subtotal.per_ha)}</td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(subtotal.total)}</td>
                        </tr>,
                      ];
                    })}
                    {totalData.forest_totals?.dbh_class_totals && (() => {
                      const ftArea = totalData.forest_totals.total_area_ha || 1;
                      const ftMai = totalData.forest_totals.total_mai_m3_per_year || 0;
                      const ftDBH = totalData.forest_totals.dbh_class_totals;
                      const ftVolume = (Object.values(ftDBH) as any[]).reduce((s: number, d: any) => s + (d.total_tree_volume_m3 || 0), 0);
                      const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                        const d = ftDBH[key];
                        if (!d) return [];
                        const classVol = d.total_tree_volume_m3 || 0;
                        const maiTotal = ftVolume > 0 ? (classVol / ftVolume) * ftMai : 0;
                        return { key, label, mai_per_ha: maiTotal / ftArea, mai_total: maiTotal };
                      });
                      const fsub = { per_ha: rows.reduce((s, r) => s + r.mai_per_ha, 0), total: rows.reduce((s, r) => s + r.mai_total, 0) };
                      return (
                        <>
                          {rows.map((r, ri) => (
                            <tr key={`ft_mai_${ri}`} className="bg-green-100 font-bold">
                              {ri === 0 && <td rowSpan={rows.length + 1} className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन</td>}
                              <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{r.label}</td>
                              <td className="px-2 py-2 text-sm text-right">{fmtPH(r.mai_per_ha)}</td>
                              <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(r.mai_total)}</td>
                            </tr>
                          ))}
                          <tr key="ft_mai_sub" className="bg-green-100 font-bold border-t-2 border-green-400">
                            <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन कुल</td>
                              <td className="px-2 py-3 text-sm text-right">{fmtPH(fsub.per_ha)}</td>
                              <td className="px-2 py-3 text-sm text-right border-r border-gray-300">{fmt(fsub.total)}</td>
                            </tr>
                        </>
                      );
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* AAH (Allowable Annual Harvest) */}
          {totalData.blocks && totalData.blocks.some((b: any) => b.aah_by_species && b.aah_by_species.length > 0) && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-2">
                प्रजाति अनुसार AAH
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_aah_table}}'}</code>
              </h4>
              <p className="text-xs text-gray-500 mb-4">प्रजाति अनुसार वार्षिक स्वीकार्य फँडानी (m³/वर्ष)</p>
              <div className="overflow-x-auto">
                {totalData.blocks.map((block: any, bi: number) => {
                  const species = block.aah_by_species || [];
                  if (species.length === 0) return null;
                  return (
                    <div key={bi} className="mb-4">
                      <h5 className="text-sm font-semibold text-gray-800 mb-2">{block.block_name}</h5>
                      <table className="min-w-full divide-y divide-gray-200 text-sm">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">प्रजाति</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">MAI (m³)</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">उत्पादनसिल संचिती (m³)</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">AAH (m³)</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">काठ (m³)</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">दाउरा (m³)</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {species.map((sp: any, si: number) => (
                            <tr key={si} className="hover:bg-gray-50">
                              <td className="px-3 py-1.5 text-sm">{sp.species_local || sp.species_scientific || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right">{sp.mai_m3?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right">{sp.growing_stock_m3?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right font-semibold text-amber-700">{sp.aah_m3?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right">{sp.timber_m3?.toFixed(2) || '—'}</td>
                              <td className="px-3 py-1.5 text-sm text-right">{sp.fuelwood_m3?.toFixed(2) || '—'}</td>
                            </tr>
                          ))}
                          <tr className="bg-amber-50 font-semibold">
                            <td className="px-3 py-1.5 text-sm">{block.block_name} जम्मा</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.mai_m3 || 0), 0).toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.growing_stock_m3 || 0), 0).toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.aah_m3 || 0), 0).toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.timber_m3 || 0), 0).toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-sm text-right">{species.reduce((s: number, sp: any) => s + (sp.fuelwood_m3 || 0), 0).toFixed(2)}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* DBH Class-wise AAH */}
          {totalData.blocks && totalData.blocks.some((b: any) => b.dbh_class_totals) && (
            <div className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">
              DBH क्लास अनुसार AAH
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_dbh_aah_table}}'}</code>
              <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_dbh_aah_narration}}'}</code>
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">ब्लक</th>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">DBH क्लास</th>
                    <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-amber-50 border-r border-gray-300">AAH</th>
                    </tr>
                    <tr>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">AAH/हे. (m³/वर्ष)</th>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">काठ (m³)</th>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">जम्मा AAH (m³/वर्ष)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {totalData.blocks.map((block: any, bi: number) => {
                      const dbhData = block.dbh_class_totals || {};
                      const blockAahTotal = block.total_aah_m3 || 0;
                      const ha = block.area_ha || 1;
                      const blockVolume = (Object.values(dbhData) as any[]).reduce((s: number, d: any) => s + (d.total_tree_volume_m3 || 0), 0);
                      const blockTimberVol = (Object.values(dbhData) as any[]).reduce((s: number, d: any) => s + (d.total_timber_m3 || 0), 0);
                      const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                        const d = dbhData[key];
                        if (!d) return [];
                        const classVol = d.total_tree_volume_m3 || 0;
                        const classTimber = d.total_timber_m3 || 0;
                        const aahTotal = blockVolume > 0 ? (classVol / blockVolume) * blockAahTotal : 0;
                        const aahTimber = blockTimberVol > 0 ? (classTimber / blockTimberVol) * blockAahTotal : 0;
                        return { key, label, aah_per_ha: aahTotal / ha, aah_total: aahTotal, aah_timber: aahTimber };
                      });
                      if (rows.length === 0) return null;
                      const subtotal = {
                        per_ha: rows.reduce((s, r) => s + r.aah_per_ha, 0),
                        timber: rows.reduce((s, r) => s + r.aah_timber, 0),
                        total: rows.reduce((s, r) => s + r.aah_total, 0),
                      };
                      return [
                        ...rows.map((r, ri) => (
                          <tr key={`${bi}_aah_${ri}`} className={ri === 0 ? 'border-t border-gray-200' : ''}>
                            {ri === 0 && (
                              <td rowSpan={rows.length + 1} className="px-3 py-2 text-sm font-medium text-gray-900 border-r border-gray-200 align-top">{block.block_name}</td>
                            )}
                            <td className="px-3 py-2 text-sm text-gray-700 border-r border-gray-200">{r.label}</td>
                            <td className="px-2 py-2 text-sm text-right">{fmtPH(r.aah_per_ha)}</td>
                            <td className="px-2 py-2 text-sm text-right">{fmt(r.aah_timber)}</td>
                            <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(r.aah_total)}</td>
                          </tr>
                        )),
                        <tr key={`${bi}_aah_sub`} className="bg-amber-50 font-semibold">
                          <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{block.block_name} जम्मा</td>
                          <td className="px-2 py-2 text-sm text-right">{fmtPH(subtotal.per_ha)}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmt(subtotal.timber)}</td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(subtotal.total)}</td>
                        </tr>,
                      ];
                    })}
                    {totalData.forest_totals?.dbh_class_totals && (() => {
                      const ftArea = totalData.forest_totals.total_area_ha || 1;
                      const ftAah = totalData.forest_totals.total_aah_m3_per_year || 0;
                      const ftDBH = totalData.forest_totals.dbh_class_totals;
                      const ftVolume = (Object.values(ftDBH) as any[]).reduce((s: number, d: any) => s + (d.total_tree_volume_m3 || 0), 0);
                      const ftTimberVol = (Object.values(ftDBH) as any[]).reduce((s: number, d: any) => s + (d.total_timber_m3 || 0), 0);
                      const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                        const d = ftDBH[key];
                        if (!d) return [];
                        const classVol = d.total_tree_volume_m3 || 0;
                        const classTimber = d.total_timber_m3 || 0;
                        const aahTotal = ftVolume > 0 ? (classVol / ftVolume) * ftAah : 0;
                        const aahTimber = ftTimberVol > 0 ? (classTimber / ftTimberVol) * ftAah : 0;
                        return { key, label, aah_per_ha: aahTotal / ftArea, aah_total: aahTotal, aah_timber: aahTimber };
                      });
                      const fsub = { per_ha: rows.reduce((s, r) => s + r.aah_per_ha, 0), timber: rows.reduce((s, r) => s + r.aah_timber, 0), total: rows.reduce((s, r) => s + r.aah_total, 0) };
                      return (
                        <>
                          {rows.map((r, ri) => (
                            <tr key={`ft_aah_${ri}`} className="bg-green-100 font-bold">
                              {ri === 0 && <td rowSpan={rows.length + 1} className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन</td>}
                              <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{r.label}</td>
                              <td className="px-2 py-2 text-sm text-right">{fmtPH(r.aah_per_ha)}</td>
                              <td className="px-2 py-2 text-sm text-right">{fmt(r.aah_timber)}</td>
                              <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(r.aah_total)}</td>
                            </tr>
                          ))}
                          <tr key="ft_aah_sub" className="bg-green-100 font-bold border-t-2 border-green-400">
                            <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">जम्मा वन कुल</td>
                            <td className="px-2 py-3 text-sm text-right">{fmtPH(fsub.per_ha)}</td>
                            <td className="px-2 py-3 text-sm text-right">{fmt(fsub.timber)}</td>
                            <td className="px-2 py-3 text-sm text-right border-r border-gray-300">{fmt(fsub.total)}</td>
                          </tr>
                        </>
                      );
                    })()}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Charts: Species Composition Pie Chart + Block-wise Bar Chart */}
          {totalData.species_breakdown && totalData.species_breakdown.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-4">
                प्रजाति संरचना र ब्लक तुलना
              </h4>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Species Composition Pie Chart */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h5 className="text-sm font-semibold text-gray-700 mb-3 text-center">
                    प्रजाति संरचना (स्थानीय नाम)
                    <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_species_composition_narration}}'}</code>
                  </h5>
                  {(() => {
                    const speciesChartData = buildSpeciesChartData(totalData.species_breakdown);
                    return speciesChartData ? (
                      <Pie
                        data={speciesChartData}
                        options={{
                          responsive: true,
                          plugins: {
                            legend: {
                              position: 'right',
                              labels: { font: { size: 11 }, boxWidth: 12, padding: 8 },
                            },
                            tooltip: {
                              callbacks: {
                                label: (ctx: any) => {
                                  const label = ctx.label || '';
                                  const val = ctx.parsed || 0;
                                  const total = ctx.dataset.data.reduce((a: number, b: number) => a + b, 0);
                                  const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
                                  return `${label}: ${val.toLocaleString()} (${pct}%)`;
                                },
                              },
                            },
                          },
                        }}
                      />
                    ) : (
                      <p className="text-sm text-gray-500 text-center py-8">प्रजाति डाटा उपलब्ध छैन</p>
                    );
                  })()}
                </div>
                {/* Block-wise Growing Stock Bar Chart */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h5 className="text-sm font-semibold text-gray-700 mb-3 text-center">
                    ब्लक अनुसार उत्पादनसिल संचिती
                    <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_productivity_narration}}'}</code>
                  </h5>
                  {(() => {
                    const barChartData = buildBlockBarChartData(totalData.blocks);
                    return barChartData ? (
                      <Bar
                        data={barChartData}
                        options={{
                          responsive: true,
                          indexAxis: 'y',
                          plugins: {
                            legend: { display: false },
                            tooltip: {
                              callbacks: {
                                label: (ctx: any) => `${ctx.parsed.x?.toLocaleString() || 0} m³`,
                              },
                            },
                          },
                          scales: {
                            x: {
                              beginAtZero: true,
                              title: { display: true, text: 'm³', font: { size: 11 } },
                              ticks: { font: { size: 10 } },
                            },
                            y: {
                              ticks: { font: { size: 10 } },
                            },
                          },
                        }}
                      />
                    ) : (
                      <p className="text-sm text-gray-500 text-center py-8">ब्लक डाटा उपलब्ध छैन</p>
                    );
                  })()}
                </div>
              </div>
            </div>
          )}

          {/* Economic Valuation */}
          {totalData.blocks && totalData.blocks.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-4">
                आर्थिक मूल्याङ्कन
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_economic_valuation_table}}'}</code>
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_economic_narration}}'}</code>
              </h4>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th rowSpan={2} className="px-2 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">ब्लक</th>
                      <th rowSpan={2} className="px-2 py-3 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">उत्पादनसिल संचिती (m³)</th>
                      <th colSpan={2} className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-blue-50 border-r border-gray-300">काठ</th>
                      <th colSpan={2} className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-amber-50 border-r border-gray-300">दाउरा</th>
                      <th rowSpan={2} className="px-2 py-3 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">कुल (रु.)</th>
                      <th colSpan={2} className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-teal-50 border-r border-gray-300">कार्बन</th>
                      <th rowSpan={2} className="px-2 py-3 text-right text-xs font-medium text-gray-500 uppercase">जम्मा (रु.)</th>
                    </tr>
                    <tr>
                      <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">दर (रु./m³)</th>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">मूल्य</th>
                      <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">दर (रु./m³)</th>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">मूल्य</th>
                      <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">दर (रु./tCO₂)</th>
                      <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">मूल्य</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {totalData.blocks.map((block: any, bi: number) => {
                      const gs = block.total_growing_stock_m3 || 0;
                      const rate = getBlockRate(block.block_name);
                      const timberVol = (block.total_pole_timber_m3 || 0) + (block.total_tree_timber_m3 || 0);
                      const firewoodVol = (block.total_pole_firewood_m3 || 0) + (block.total_tree_firewood_m3 || 0);
                      const co2 = block.total_co2_tco2 || 0;
                      const timberVal = timberVol * rate.timber;
                      const fuelwoodVal = firewoodVol * rate.fuelwood;
                      const carbonVal = co2 * rate.carbon;
                      const totalVal = timberVal + fuelwoodVal + carbonVal;
                      return (
                        <tr key={bi} className="hover:bg-gray-50">
                          <td className="px-2 py-2 text-sm font-medium text-gray-900 border-r border-gray-200">{block.block_name}</td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-200">{gs.toLocaleString()}</td>
                          <td className="px-2 py-2 text-center border-r border-gray-200">
                            <input
                              type="number"
                              value={rate.timber}
                              onChange={(e) => setBlockRates((prev) => ({ ...prev, [block.block_name]: { ...prev[block.block_name], timber: Math.max(0, Number(e.target.value)) } }))}
                              className="w-20 px-1 py-0.5 border border-blue-300 rounded text-xs text-right"
                              min={0}
                            />
                          </td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-200">{timberVal.toLocaleString()}</td>
                          <td className="px-2 py-2 text-center border-r border-gray-200">
                            <input
                              type="number"
                              value={rate.fuelwood}
                              onChange={(e) => setBlockRates((prev) => ({ ...prev, [block.block_name]: { ...prev[block.block_name], fuelwood: Math.max(0, Number(e.target.value)) } }))}
                              className="w-20 px-1 py-0.5 border border-amber-300 rounded text-xs text-right"
                              min={0}
                            />
                          </td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-200">{fuelwoodVal.toLocaleString()}</td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-200 font-medium">{(timberVal + fuelwoodVal).toLocaleString()}</td>
                          <td className="px-2 py-2 text-center border-r border-gray-200">
                            <input
                              type="number"
                              value={rate.carbon}
                              onChange={(e) => setBlockRates((prev) => ({ ...prev, [block.block_name]: { ...prev[block.block_name], carbon: Math.max(0, Number(e.target.value)) } }))}
                              className="w-20 px-1 py-0.5 border border-teal-300 rounded text-xs text-right"
                              min={0}
                            />
                          </td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-200">{carbonVal.toLocaleString()}</td>
                          <td className="px-2 py-2 text-sm text-right font-semibold text-green-700">{totalVal.toLocaleString()}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Sustainability Index */}
          {totalData.blocks && totalData.blocks.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-4">
                दिगोपन सूचकांक
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{ti_sustainability_table}}'}</code>
                <code className="ml-2 text-xs text-blue-600 font-mono bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200 select-all">{'{{section:ti_sustainability_narration}}'}</code>
              </h4>

              {/* Methodology Summary */}
              <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200 text-xs text-blue-900 space-y-2">
                <p className="font-semibold text-sm">गणना विधि (Calculation Methodology):</p>
                <ul className="list-disc pl-5 space-y-1">
                  <li><strong>दिगोपन सूचकांक (SI)</strong> = (AAH / उत्पादनसिल संचिती) × १०० — कुल मौज्दातको कति प्रतिशत वार्षिक फँडानी गर्न सकिन्छ भन्ने मापन। SI &lt; ५% = दिगो, ५-१०% = मध्यम, &gt; १०% = अति दोहन जोखिम।</li>
                  <li><strong>कटान दवाव (HP)</strong> = (AAH / MAI) × १०० — वार्षिक वृद्धिको तुलनामा फँडानी दर। HP &lt; ५०% = कम दबाब, ५०-८०% = मध्यम, &gt; ८०% = उच्च दबाब।</li>
                  <li><strong>उत्पादनसिल संचिती/हे.</strong> = कुल उत्पादनसिल संचिती (m³) ÷ ब्लक क्षेत्रफल (हे.) — प्रति हेक्टर काठको मात्रा।</li>
                </ul>
                <p className="mt-2 pt-2 border-t border-blue-200 text-blue-700">
                  <strong>English:</strong> SI = (AAH / Productive Growing Stock) × 100 — harvest rate against total stock. HP = (AAH / MAI) × 100 — harvest pressure against annual growth. GS/ha = Productive Growing Stock / block area.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {totalData.blocks.map((block: any, bi: number) => {
                  const gs = block.total_growing_stock_m3 || 0;
                  const mai = block.total_mai_m3 || 1;
                  const aah = block.total_aah_m3 || 0;
                  const sustainabilityIndex = gs > 0 ? (aah / gs) * 100 : 0;
                  const harvestingPressure = mai > 0 ? (aah / mai) * 100 : 0;
                  return (
                    <div key={bi} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                      <h5 className="text-sm font-semibold text-gray-900 mb-2">{block.block_name}</h5>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">दिगोपन सूचकांक:</span>
                          <span className={`font-semibold ${sustainabilityIndex < 5 ? 'text-green-600' : sustainabilityIndex < 10 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {sustainabilityIndex.toFixed(2)}%
                            <span className={`ml-1 text-xs ${sustainabilityIndex < 5 ? 'text-green-600' : sustainabilityIndex < 10 ? 'text-yellow-600' : 'text-red-600'}`}>
                              ({sustainabilityIndex < 5 ? 'दिगो' : sustainabilityIndex < 10 ? 'मध्यम' : 'अति दोहन'})
                            </span>
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">कटान दवाव:</span>
                          <span className={`font-semibold ${harvestingPressure < 50 ? 'text-green-600' : harvestingPressure < 80 ? 'text-yellow-600' : 'text-red-600'}`}>
                            {harvestingPressure.toFixed(1)}%
                            <span className={`ml-1 text-xs ${harvestingPressure < 50 ? 'text-green-600' : harvestingPressure < 80 ? 'text-yellow-600' : 'text-red-600'}`}>
                              ({harvestingPressure < 50 ? 'कम' : harvestingPressure < 80 ? 'मध्यम' : 'उच्च'})
                            </span>
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">उत्पादनसिल संचिती/हे.:</span>
                          <span className="font-semibold">{(gs / (block.area_ha || 1)).toFixed(1)} m³
                            <span className={`ml-1 text-xs ${(gs / (block.area_ha || 1)) > 200 ? 'text-green-600' : (gs / (block.area_ha || 1)) >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                              ({(gs / (block.area_ha || 1)) > 200 ? 'राम्रो' : (gs / (block.area_ha || 1)) >= 50 ? 'मध्यम' : 'कमसल'})
                            </span>
                          </span>
                        </div>

                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          </>
          )}

          {/* Missing Area Data Warning */}
          {treeCoverList.length > 0 && !loading && (!totalData || !totalData.forest_totals || Object.keys(totalData.forest_totals).length === 0) && (
            <div className="p-4 bg-yellow-50 rounded-md border border-yellow-200">
              <p className="text-sm text-yellow-800 font-medium">क्षेत्र डाटा भेटिएन</p>
              <p className="text-xs text-yellow-700 mt-1">
                माथिको ब्लक क्षेत्रफलहरू प्रयोग गरेर कुल मौज्दात गणना गर्नको लागि कृपया "गणना गर्नुहोस्" बटन थिच्नुहोस्।
              </p>
            </div>
          )}

    </div>
  );
};

