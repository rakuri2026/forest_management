import React from 'react';
import { Home, Users, MapPin } from 'lucide-react';

interface Settlement {
  settlement_id?: number;
  settlement_name: string;
  building_count: number;
  total_area_m2: number;
  direction_from_forest: string;
  lat?: number;
  lon?: number;
}

interface SettlementStatisticsProps {
  settlements: Settlement[];
}

export function SettlementStatistics({ settlements }: SettlementStatisticsProps) {
  const totalBuildings = settlements.reduce((sum, s) => sum + s.building_count, 0);
  const totalArea = settlements.reduce((sum, s) => sum + s.total_area_m2, 0);

  return (
    <div className="settlement-statistics mt-6">
      <h3 className="text-xl font-semibold mb-4">Settlement Analysis</h3>

      {/* Summary Cards */}
      <div className="summary-cards grid grid-cols-3 gap-4 mb-6">
        <div className="card bg-blue-100 p-4 rounded shadow">
          <div className="flex items-center">
            <MapPin className="text-blue-600 mr-3" size={32} />
            <div>
              <p className="text-sm text-gray-600">Total Settlements</p>
              <p className="text-2xl font-bold">{settlements.length}</p>
            </div>
          </div>
        </div>

        <div className="card bg-green-100 p-4 rounded shadow">
          <div className="flex items-center">
            <Home className="text-green-600 mr-3" size={32} />
            <div>
              <p className="text-sm text-gray-600">Total Buildings</p>
              <p className="text-2xl font-bold">{totalBuildings}</p>
            </div>
          </div>
        </div>

        <div className="card bg-yellow-100 p-4 rounded shadow">
          <div className="flex items-center">
            <Users className="text-yellow-600 mr-3" size={32} />
            <div>
              <p className="text-sm text-gray-600">Total Building Area</p>
              <p className="text-2xl font-bold">{totalArea.toFixed(0)} m²</p>
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full bg-white border border-gray-300">
          <thead className="bg-gray-100">
            <tr>
              <th className="px-4 py-2 border text-left">Settlement Name</th>
              <th className="px-4 py-2 border text-center">Number of Buildings</th>
              <th className="px-4 py-2 border text-center">Total Building Area (m²)</th>
              <th className="px-4 py-2 border text-center">Direction from Forest</th>
            </tr>
          </thead>
          <tbody>
            {settlements.map((settlement, idx) => (
              <tr key={idx} className="hover:bg-gray-50">
                <td className="px-4 py-2 border">{settlement.settlement_name}</td>
                <td className="px-4 py-2 border text-center">{settlement.building_count}</td>
                <td className="px-4 py-2 border text-center">{settlement.total_area_m2.toFixed(2)}</td>
                <td className="px-4 py-2 border text-center">
                  <span className="inline-block bg-blue-200 px-3 py-1 rounded">
                    {settlement.direction_from_forest}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
