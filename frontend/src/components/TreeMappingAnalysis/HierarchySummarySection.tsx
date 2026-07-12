import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { getHierarchyPath, truncateLabel } from './hierarchyUtils';
import CopyTag from '../DetailDescription/CopyTag';

interface Props {
  data: any[];
  remarkBreakdown?: Record<string, any>;
  collapsed?: boolean;
  onToggle?: () => void;
}

function getRemarkKey(row: any): string {
  return `${row.sub_compartment}|${row.compartment}|${row.block_name}|${row.sub_area_name}`;
}

export function HierarchySummarySection({ data, remarkBreakdown, collapsed, onToggle }: Props) {
  if (!data || data.length === 0) return null;

  const chartData = data.slice(0, 12).map((row) => {
    const rk = remarkBreakdown?.[getRemarkKey(row)];
    return {
      name: truncateLabel(getHierarchyPath(row)),
      माँउ: rk?.mother_trees || 0,
      कटानी: rk?.felling_trees || 0,
    };
  });

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div
        className="flex justify-between items-center px-6 py-4 border-b cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <h3 className="text-lg font-semibold">स्थानिक स्तर अनुसार रूख सारांश / Spatial Hierarchy Tree Summary
          <CopyTag label="{{section:sm_hierarchy_narration}}" value="{{section:sm_hierarchy_narration}}" variant="section" />
        </h3>
        <span className="text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="p-6">
          {/* Stacked Bar Chart - Mother vs Felling by Hierarchy */}
          <div className="mb-6">
            <h4 className="text-sm font-medium text-gray-600 mb-2">माँउ बनाम कटानी रूख / Mother vs Felling by Hierarchy
              <CopyTag label="{{chart:sm_mother_felling_hierarchy_bar}}" value="{{chart:sm_mother_felling_hierarchy_bar}}" variant="variable" />
            </h4>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="name" type="category" width={140} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="माँउ" stackId="a" fill="#22c55e" />
                <Bar dataKey="कटानी" stackId="a" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-green-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-700">{data.length}</div>
              <div className="text-xs text-green-600">कुल स्तरहरू / Levels</div>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-blue-700">{data.reduce((s, r) => s + r.tree_count, 0).toLocaleString()}</div>
              <div className="text-xs text-blue-600">कुल रूख / Total Trees</div>
            </div>
            <div className="bg-amber-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-amber-700">{data.reduce((s, r) => s + (r.total_volume_m3 || 0), 0).toFixed(0)}</div>
              <div className="text-xs text-amber-600">कुल आयतन m³</div>
            </div>
            <div className="bg-purple-50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-purple-700">{data.filter(r => r.sub_area_name !== '-').length}</div>
              <div className="text-xs text-purple-600">उप-क्षेत्र / Sub-areas</div>
            </div>
          </div>

          {/* Table */}
          <div className="mb-2">
            <CopyTag label="{{sm_hierarchy_summary}}" value="{{sm_hierarchy_summary}}" variant="variable" />
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">स्तर पथ / Hierarchy Path</th>
                  <th className="px-3 py-2 text-left">उप-क्षेत्र</th>
                  <th className="px-3 py-2 text-right">जम्मा रूख</th>
                  <th className="px-3 py-2 text-right bg-green-50">माँउ रूख</th>
                  <th className="px-3 py-2 text-right bg-red-50">कटानी रूख</th>
                  <th className="px-3 py-2 text-right">क्षेत्रफल (हे)</th>
                  <th className="px-3 py-2 text-right">रूख/हे</th>
                  <th className="px-3 py-2 text-right">कुल आयतन (m³)</th>
                  <th className="px-3 py-2 text-right">आयतन/हे</th>
                  <th className="px-3 py-2 text-left">प्रमुख प्रजाति</th>
                  <th className="px-3 py-2 text-right">DBH (cm)</th>
                  <th className="px-3 py-2 text-right">उचाइ (m)</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {data.map((row, idx) => {
                  const rk = remarkBreakdown?.[getRemarkKey(row)];
                  const motherCount = rk?.mother_trees || 0;
                  const fellingCount = rk?.felling_trees || 0;
                  return (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">
                        <span className="text-xs text-gray-400 mr-1">{idx + 1}.</span>
                        {getHierarchyPath(row)}
                      </td>
                      <td className="px-3 py-2 text-xs">{row.sub_area_name !== '-' ? row.sub_area_name : ''}</td>
                      <td className="px-3 py-2 text-right font-medium">{row.tree_count.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right text-green-600 font-medium bg-green-50">{motherCount.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right text-red-600 font-medium bg-red-50">{fellingCount.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right">{row.area_ha}</td>
                      <td className="px-3 py-2 text-right">{row.trees_per_ha}</td>
                      <td className="px-3 py-2 text-right">{row.total_volume_m3.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right">{row.volume_per_ha}</td>
                      <td className="px-3 py-2 text-xs">{row.dominant_species}</td>
                      <td className="px-3 py-2 text-right">{row.avg_dbh_cm}</td>
                      <td className="px-3 py-2 text-right">{row.avg_height_m}</td>
                    </tr>
                  );
                })}
                <tr className="bg-gray-100 font-semibold">
                  <td className="px-3 py-2" colSpan={2}>जम्मा / Total</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + r.tree_count, 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right text-green-700 bg-green-50">{data.reduce((s, r) => {
                    const rk = remarkBreakdown?.[getRemarkKey(r)];
                    return s + (rk?.mother_trees || 0);
                  }, 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right text-red-700 bg-red-50">{data.reduce((s, r) => {
                    const rk = remarkBreakdown?.[getRemarkKey(r)];
                    return s + (rk?.felling_trees || 0);
                  }, 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2 text-right">{data.reduce((s, r) => s + (r.total_volume_m3 || 0), 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2">-</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2 text-right">-</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
