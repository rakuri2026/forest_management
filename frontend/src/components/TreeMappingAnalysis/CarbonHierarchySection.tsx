import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getHierarchyPath, truncateLabel } from './hierarchyUtils';
import CopyTag from '../DetailDescription/CopyTag';

interface Props {
  data: any[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export function CarbonHierarchySection({ data, collapsed, onToggle }: Props) {
  if (!data || data.length === 0) return null;

  const chartData = data.map(row => ({
    name: truncateLabel(getHierarchyPath(row)),
    carbon: row.carbon_tc,
    co2: row.co2_tco2,
  }));

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div
        className="flex justify-between items-center px-6 py-4 border-b cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <h3 className="text-lg font-semibold">स्थानिक स्तर अनुसार कार्बन मौज्दात / Carbon Stock by Spatial Level
          <CopyTag label="{{section:sm_carbon_narration}}" value="{{section:sm_carbon_narration}}" variant="section" />
        </h3>
        <span className="text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="p-6">
          <div className="mb-6">
            <h4 className="text-sm font-medium text-gray-600 mb-2">स्तर अनुसार कार्बन / Carbon by Hierarchy
              <CopyTag label="{{chart:sm_carbon_bar}}" value="{{chart:sm_carbon_bar}}" variant="variable" />
            </h4>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="carbon" fill="#22c55e" name="Carbon (tC)" />
                <Bar dataKey="co2" fill="#3b82f6" name="CO₂e (tCO₂)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mb-1">
            <CopyTag label="{{sm_carbon_by_hierarchy}}" value="{{sm_carbon_by_hierarchy}}" variant="variable" />
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">स्तर पथ / Hierarchy</th>
                  <th className="px-3 py-2 text-right">स्थूल आयतन (m³)</th>
                  <th className="px-3 py-2 text-right">भारित काठ घनत्व</th>
                  <th className="px-3 py-2 text-right">AGB (टन)</th>
                  <th className="px-3 py-2 text-right">BGB (टन)</th>
                  <th className="px-3 py-2 text-right">जैविक पदार्थ (टन)</th>
                  <th className="px-3 py-2 text-right">कार्बन (tC)</th>
                  <th className="px-3 py-2 text-right">CO₂e (tCO₂)</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{getHierarchyPath(row)}</td>
                    <td className="px-3 py-2 text-right">{row.gross_volume_m3}</td>
                    <td className="px-3 py-2 text-right">{row.wood_density}</td>
                    <td className="px-3 py-2 text-right">{row.agb_t}</td>
                    <td className="px-3 py-2 text-right">{row.bgb_t}</td>
                    <td className="px-3 py-2 text-right">{row.biomass_t}</td>
                    <td className="px-3 py-2 text-right font-medium">{row.carbon_tc}</td>
                    <td className="px-3 py-2 text-right font-medium">{row.co2_tco2}</td>
                  </tr>
                ))}
                <tr className="bg-gray-100 font-semibold">
                  <td className="px-3 py-2">जम्मा / Total</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + (r.gross_volume_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + (r.agb_t || 0), 0).toFixed(3)}</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + (r.bgb_t || 0), 0).toFixed(3)}</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + (r.biomass_t || 0), 0).toFixed(3)}</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + (r.carbon_tc || 0), 0).toFixed(3)}</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + (r.co2_tco2 || 0), 0).toFixed(3)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
