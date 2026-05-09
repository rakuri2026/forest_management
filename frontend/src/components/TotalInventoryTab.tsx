import React, { useState, useEffect } from 'react';
import { fieldInventoryApi, forestApi } from '../services/api';

interface TotalInventoryTabProps {
  calculationId: string;
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

export const TotalInventoryTab: React.FC<TotalInventoryTabProps> = ({ calculationId }) => {
  const [loading, setLoading] = useState(false);
  const [treeCoverLoading, setTreeCoverLoading] = useState(false);
  const [treeCoverError, setTreeCoverError] = useState<string | null>(null);
  const [fieldInventory, setFieldInventory] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [blockAreas, setBlockAreas] = useState<Record<string, number>>({});
  const [treeCoverAreas, setTreeCoverAreas] = useState<Record<string, TreeCoverArea>>({});
  const [totalData, setTotalData] = useState<any>(null);
  const [customMultipliers, setCustomMultipliers] = useState<Record<string, number>>({});
  const [areasManuallyChanged, setAreasManuallyChanged] = useState(false);
  const [initialCalculationDone, setInitialCalculationDone] = useState(false);

  useEffect(() => {
    // Reset states when calculation changes
    setInitialCalculationDone(false);
    setAreasManuallyChanged(false);
    setTotalData(null);

    loadFieldInventory();
    loadTreeCoverAreas();
  }, [calculationId]);

  // Auto-calculate totals immediately when both field inventory and tree cover areas are loaded
  useEffect(() => {
    if (
      fieldInventory?.id &&
      Object.keys(treeCoverAreas).length > 0 &&
      Object.keys(blockAreas).length > 0 &&
      !initialCalculationDone &&
      !loading
    ) {
      // Check if all areas are populated (non-zero)
      const allAreasPopulated = Object.values(blockAreas).every(area => area > 0);
      if (allAreasPopulated) {
        console.log('Auto-calculating totals with tree cover areas...');
        handleCalculateTotals(false); // Silent auto-calculation (no alerts)
        setInitialCalculationDone(true);
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

      // Convert array to map for easy lookup
      const treeCoverMap: Record<string, TreeCoverArea> = {};
      response.tree_cover_areas?.forEach((area: TreeCoverArea) => {
        treeCoverMap[area.block_name] = area;
      });

      setTreeCoverAreas(treeCoverMap);

      // Auto-populate block areas with effective tree cover areas
      const areas: Record<string, number> = {};
      response.tree_cover_areas?.forEach((area: TreeCoverArea) => {
        areas[area.block_name] = area.effective_area_ha;
      });
      setBlockAreas(areas);

      console.log('Tree cover areas loaded successfully:', treeCoverMap);

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

  const handleBlockAreaChange = (blockName: string, value: string) => {
    const numValue = parseFloat(value);
    setBlockAreas({
      ...blockAreas,
      [blockName]: isNaN(numValue) ? 0 : numValue
    });
    // Mark that user has manually changed areas
    setAreasManuallyChanged(true);
  };

  const handleCalculateTotals = async (showAlerts: boolean = true) => {
    if (!fieldInventory?.id) {
      if (showAlerts) {
        console.log('No field inventory available yet');
      }
      return;
    }

    // Check if all areas are entered
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
      console.log('Total inventory calculated successfully');
    } catch (err) {
      console.error('Error calculating total inventory:', err);
      if (showAlerts) {
        alert('Error calculating total inventory. Please try again.');
      }
    } finally {
      setLoading(false);
    }
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

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border-2 border-blue-300 p-6">
        <h3 className="text-xl font-bold text-blue-900 mb-2">Total Inventory - Absolute Quantities</h3>
        <p className="text-sm text-gray-600">
          Enter block areas to calculate total quantities (trees, volumes, biomass) for your forest.
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
                You can manually adjust if needed.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {summary?.blocks?.map((block: any) => {
                const treeCoverInfo = treeCoverAreas[block.block_name];
                return (
                  <div key={block.block_name} className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <label className="font-semibold text-gray-900 mb-2 block">{block.block_name}</label>

                    <div className="flex items-center gap-2 mb-2">
                      <input
                        type="number"
                        value={blockAreas[block.block_name] || ''}
                        onChange={(e) => handleBlockAreaChange(block.block_name, e.target.value)}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="0.00"
                        min="0"
                        step="0.01"
                      />
                      <span className="text-sm font-medium text-gray-600">ha</span>
                    </div>

                    {treeCoverInfo && (
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
                    )}
                  </div>
                );
              })}
            </div>

            {areasManuallyChanged && (
              <div className="mt-4 p-3 bg-amber-50 rounded-md border border-amber-200">
                <p className="text-sm text-amber-800 mb-2">
                  You have modified area values. Click the button below to recalculate.
                </p>
                <button
                  onClick={() => {
                    handleCalculateTotals();
                    setAreasManuallyChanged(false);
                  }}
                  disabled={loading}
                  className="px-6 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 disabled:bg-gray-400 font-medium"
                >
                  {loading ? 'Recalculating...' : 'Recalculate Total Inventory'}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Total Inventory Results */}
      {totalData && (
        <>
          {/* Forest-Wide Totals Summary */}
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border-2 border-green-400 p-6 shadow-lg">
            <h3 className="text-xl font-bold text-green-800 mb-4">Community Forest Totals</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Total Area</div>
                <div className="text-2xl font-bold text-green-700">{totalData.forest_totals.total_area_ha.toLocaleString()} ha</div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Total Trees</div>
                <div className="text-2xl font-bold text-blue-700">
                  {(totalData.forest_totals.total_pole + totalData.forest_totals.total_tree).toLocaleString()}
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Growing Stock</div>
                <div className="text-xl font-bold text-amber-700">
                  {totalData.forest_totals.total_growing_stock_m3.toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">MAI/Year</div>
                <div className="text-xl font-bold text-purple-700">
                  {totalData.forest_totals.total_mai_m3_per_year.toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md bg-amber-50">
                <div className="text-xs text-gray-600 mb-1 font-medium">AAH/Year</div>
                <div className="text-2xl font-bold text-amber-800">
                  {totalData.forest_totals.total_aah_m3_per_year.toLocaleString()} m³
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Total Biomass</div>
                <div className="text-xl font-bold text-teal-700">
                  {totalData.forest_totals.total_biomass_tonnes.toLocaleString()} t
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md">
                <div className="text-xs text-gray-500 mb-1">Carbon Stock</div>
                <div className="text-xl font-bold text-teal-700">
                  {totalData.forest_totals.total_carbon_tc.toLocaleString()} tC
                </div>
              </div>
              <div className="bg-white rounded-lg p-4 shadow-md bg-teal-50">
                <div className="text-xs text-gray-600 mb-1 font-medium">CO₂ Equivalent</div>
                <div className="text-xl font-bold text-teal-800">
                  {totalData.forest_totals.total_co2_tco2.toLocaleString()} tCO₂
                </div>
              </div>
            </div>
          </div>

          {/* Block-wise Totals Table */}
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
                    <th className="px-2 py-2 text-center text-xs font-medium text-gray-500 uppercase">Regen</th>
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
                      <td className="px-3 py-3 text-sm text-center border-r border-gray-200">{block.area_ha.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{block.total_regeneration.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{block.total_sapling.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{block.total_pole.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{block.total_tree.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{block.total_growing_stock_m3.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{block.total_mai_m3.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right border-r border-gray-200 font-semibold text-amber-700">{block.total_aah_m3.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{block.total_biomass_tonnes.toLocaleString()}</td>
                      <td className="px-2 py-3 text-sm text-right">{block.total_co2_tco2.toLocaleString()}</td>
                    </tr>
                  ))}
                  {/* Totals Row */}
                  <tr className="bg-green-100 font-bold">
                    <td className="px-3 py-3 text-sm font-bold text-gray-900 border-r border-gray-200">Total Forest</td>
                    <td className="px-3 py-3 text-sm text-center border-r border-gray-200">{totalData.forest_totals.total_area_ha.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{totalData.forest_totals.total_regeneration.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{totalData.forest_totals.total_sapling.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{totalData.forest_totals.total_pole.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right border-r border-gray-200">{totalData.forest_totals.total_tree.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{totalData.forest_totals.total_growing_stock_m3.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{totalData.forest_totals.total_mai_m3_per_year.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right border-r border-gray-200 text-amber-900">{totalData.forest_totals.total_aah_m3_per_year.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{totalData.forest_totals.total_biomass_tonnes.toLocaleString()}</td>
                    <td className="px-2 py-3 text-sm text-right">{totalData.forest_totals.total_co2_tco2.toLocaleString()}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
