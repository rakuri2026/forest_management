import React, { useState, useEffect } from 'react';
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
    { key: '10_20', label: '10-20 Sm.Pole' },
    { key: '20_30', label: '20-30 Lg.Pole' },
    { key: '30_40', label: '30-40 Sm.Tree' },
    { key: '40_50', label: '40-50 Med.Tree' },
    { key: '50_60', label: '50-60 Lg.Tree' },
  ];

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
        <h3 className="text-xl font-bold text-blue-900 mb-2">Total Inventory - Absolute Quantities</h3>
        <p className="text-sm text-gray-600">
          Block areas auto-populated from effective forest cover (excludes barren land, water bodies, etc.).
        </p>
      </div>

      {/* Block Areas Input */}
      <div className="bg-white rounded-lg shadow p-6">
        <h4 className="text-lg font-semibold text-gray-900 mb-4">
          Step 1: Block Areas - Effective Forest Cover
        </h4>

        {treeCoverLoading ? (
          <div className="text-center py-8">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="text-sm text-gray-600 mt-2">Calculating tree cover areas...</p>
          </div>
        ) : treeCoverError ? (
          <div className="p-4 bg-red-50 rounded-md border border-red-200">
            <p className="text-sm text-red-800 font-medium">Error calculating tree cover areas:</p>
            <p className="text-sm text-red-700 mt-1">{treeCoverError}</p>
            <button
              onClick={loadTreeCoverAreas}
              className="mt-3 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm"
            >
              Retry Calculation
            </button>
          </div>
        ) : (
          <>
            <div className="mb-4 p-3 bg-blue-50 rounded-md text-sm text-blue-800">
              <p className="font-medium">Tree Cover Areas Auto-Populated</p>
              <p className="text-xs mt-1">
                Areas below show effective forest cover (excludes barren land, water bodies, etc.).
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
                    <span className="text-sm font-medium text-gray-600">ha</span>
                  </div>

                  <div className="text-xs text-gray-600 space-y-1 bg-white p-2 rounded border border-gray-200">
                    <div className="flex justify-between">
                      <span>Total Boundary:</span>
                      <span className="font-medium">{treeCoverInfo.total_area_ha.toFixed(2)} ha</span>
                    </div>
                    <div className="flex justify-between text-green-700 font-medium">
                      <span>Forest Cover:</span>
                      <span>{treeCoverInfo.effective_area_ha.toFixed(2)} ha ({treeCoverInfo.tree_cover_percentage.toFixed(1)}%)</span>
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
            {loading ? 'Calculating...' : 'Calculate Total Inventory'}
          </button>
        </div>
      )}

      {/* Loading indicator */}
      {loading && !totalData && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="text-sm text-gray-600 mt-2">Calculating total inventory...</p>
        </div>
      )}

      {/* No matching blocks warning */}
      {totalData && (!totalData.forest_totals || Object.keys(totalData.forest_totals).length === 0) && (
        <div className="p-4 bg-red-50 rounded-md border border-red-200">
          <p className="text-sm text-red-800 font-medium">No matching blocks found</p>
          <p className="text-xs text-red-700 mt-1">
            Block names from tree cover ({Object.keys(blockAreas).join(', ')}) do not match block names in field inventory data.
          </p>
          <p className="text-xs text-red-600 mt-1">
            Try re-uploading the field inventory CSV with matching block names.
          </p>
        </div>
      )}

      {/* Total Inventory Results */}
      {totalData && totalData.forest_totals && Object.keys(totalData.forest_totals).length > 0 && (
        <>
          {/* Forest-Wide Totals Summary */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border-2 border-green-400 p-6 shadow-lg">
            <h3 className="text-xl font-bold text-green-800 mb-4">Community Forest Totals</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Total Area</div>
                <div className="text-2xl font-bold text-green-700">{(totalData.forest_totals.total_area_ha || 0).toLocaleString()} ha</div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Total Trees</div>
                <div className="text-2xl font-bold text-blue-700">
                  {((totalData.forest_totals.total_pole || 0) + (totalData.forest_totals.total_tree || 0)).toLocaleString()}
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Growing Stock</div>
                <div className="text-xl font-bold text-amber-700">
                  {(totalData.forest_totals.total_growing_stock_m3 || 0).toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">MAI/Year</div>
                <div className="text-xl font-bold text-purple-700">
                  {(totalData.forest_totals.total_mai_m3_per_year || 0).toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md bg-amber-50">
                <div className="text-xs text-gray-600 mb-1 font-medium">AAH/Year</div>
                <div className="text-2xl font-bold text-amber-800">
                  {(totalData.forest_totals.total_aah_m3_per_year || 0).toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Total Biomass</div>
                <div className="text-xl font-bold text-teal-700">
                  {(totalData.forest_totals.total_biomass_tonnes || 0).toLocaleString()} t
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Carbon Stock</div>
                <div className="text-xl font-bold text-teal-700">
                  {(totalData.forest_totals.total_carbon_tc || 0).toLocaleString()} tC
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md bg-teal-50">
                <div className="text-xs text-gray-600 mb-1 font-medium">CO₂ Equivalent</div>
                <div className="text-xl font-bold text-teal-800">
                  {(totalData.forest_totals.total_co2_tco2 || 0).toLocaleString()} tCO₂
                </div>
              </div>
            </div>
          </div>

          {/* Block-wise Totals Table */}
          {totalData.blocks && totalData.blocks.length > 0 && (
          <div className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">Block-wise Total Inventory</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Block</th>
                    <th rowSpan={2} className="px-3 py-3 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Area (ha)</th>
                    <th colSpan={4} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-blue-50">Total Trees</th>
                    <th colSpan={3} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300 bg-amber-50">Total Volumes (m³)</th>
                    <th colSpan={2} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-teal-50">Total Carbon</th>
                  </tr>
                  <tr>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Seedling</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Sapling</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Pole</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Tree</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Stock</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">MAI/yr</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase border-r border-gray-300">AAH/yr</th>
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Biomass (t)</th>
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
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">Total Forest</td>
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

          {/* DBH Class-wise Growing Stock per Hectare (Table 1 - Per-ha reference) */}
          {totalData.blocks && totalData.blocks.length > 0 && totalData.blocks[0].dbh_class_per_ha && (
          <div className="bg-white rounded-lg shadow p-6">
            <h4 className="text-lg font-semibold text-gray-900 mb-4">DBH Class-wise Growing Stock per Hectare</h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Block</th>
                    <th rowSpan={2} className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase border-r border-gray-300">DBH Class</th>
                    <th colSpan={4} className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase bg-blue-50 border-r border-gray-300">Per Hectare</th>
                  </tr>
                  <tr>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">Count</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">Timber (m&sup3;)</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase">Firewood (m&sup3;)</th>
                    <th className="px-2 py-2 text-right text-xs font-medium text-gray-500 uppercase border-r border-gray-300">Volume (m&sup3;)</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {totalData.blocks.map((block: any, bi: number) => {
                    const perHa = block.dbh_class_per_ha || {};
                    const rows = DBH_CLASS_CONFIG.flatMap(({ key, label }) => {
                      const d = perHa[key];
                      if (!d) return [];
                      return [{
                        key, label,
                        isSubtotal: false,
                        count: d.count_per_ha,
                        timber: d.timber_m3_per_ha,
                        firewood: d.firewood_m3_per_ha,
                        volume: d.tree_volume_m3_per_ha,
                      }];
                    });
                    if (rows.length === 0) return null;
                    const subtotal = {
                      count: computeBlockSubtotal(block, 'count_per_ha', true),
                      timber: computeBlockSubtotal(block, 'timber_m3_per_ha', true),
                      firewood: computeBlockSubtotal(block, 'firewood_m3_per_ha', true),
                      volume: computeBlockSubtotal(block, 'tree_volume_m3_per_ha', true),
                    };
                    return [
                      ...rows.map((r, ri) => (
                        <tr key={`${bi}_${ri}`} className={ri === 0 ? 'border-t border-gray-200' : ''}>
                          {ri === 0 && (
                            <td rowSpan={rows.length + 1} className="px-3 py-2 text-sm font-medium text-gray-900 border-r border-gray-200 align-top">{block.block_name}</td>
                          )}
                          <td className="px-3 py-2 text-sm text-gray-700 border-r border-gray-200">{r.label}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmt(r.count, 2)}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmt(r.timber, 2)}</td>
                          <td className="px-2 py-2 text-sm text-right">{fmt(r.firewood, 2)}</td>
                          <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(r.volume, 2)}</td>
                        </tr>
                      )),
                      <tr key={`${bi}_sub`} className="bg-blue-50 font-semibold">
                        <td className="px-3 py-2 text-sm text-gray-900 border-r border-gray-200">{block.block_name} Total</td>
                        <td className="px-2 py-2 text-sm text-right">{fmt(subtotal.count, 2)}</td>
                        <td className="px-2 py-2 text-sm text-right">{fmt(subtotal.timber, 2)}</td>
                        <td className="px-2 py-2 text-sm text-right">{fmt(subtotal.firewood, 2)}</td>
                        <td className="px-2 py-2 text-sm text-right border-r border-gray-300">{fmt(subtotal.volume, 2)}</td>
                      </tr>,
                    ];
                  })}
                  <tr className="bg-green-100 font-bold">
                    <td colSpan={2} className="px-3 py-3 text-sm text-gray-900 border-r border-gray-200">Grand Total</td>
                    <td className="px-2 py-3 text-sm text-right">
                      {fmt(totalData.blocks.reduce((s: number, b: any) => s + computeBlockSubtotal(b, 'count_per_ha', true), 0), 2)}
                    </td>
                    <td className="px-2 py-3 text-sm text-right">
                      {fmt(totalData.blocks.reduce((s: number, b: any) => s + computeBlockSubtotal(b, 'timber_m3_per_ha', true), 0), 2)}
                    </td>
                    <td className="px-2 py-3 text-sm text-right">
                      {fmt(totalData.blocks.reduce((s: number, b: any) => s + computeBlockSubtotal(b, 'firewood_m3_per_ha', true), 0), 2)}
                    </td>
                    <td className="px-2 py-3 text-sm text-right border-r border-gray-300">
                      {fmt(totalData.blocks.reduce((s: number, b: any) => s + computeBlockSubtotal(b, 'tree_volume_m3_per_ha', true), 0), 2)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          )}

          {/* Show warning if some blocks couldn't be matched */}
          {totalData.missing_areas && totalData.missing_areas.length > 0 && (
            <div className="p-4 bg-amber-50 rounded-md border border-amber-200">
              <p className="text-sm text-amber-800 font-medium">Blocks with missing area data:</p>
              <p className="text-xs text-amber-700 mt-1">{totalData.missing_areas.join(', ')}</p>
              <p className="text-xs text-amber-600 mt-1">Block names in field inventory may not match current calculation blocks.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
};
