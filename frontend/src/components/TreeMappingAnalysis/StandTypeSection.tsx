import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { getHierarchyPath, truncateLabel } from './hierarchyUtils';
import CopyTag from '../DetailDescription/CopyTag';

interface Props {
  hierarchyData: any[];
  statusData?: any;
  collapsed?: boolean;
  onToggle?: () => void;
}

export function StandTypeSection({ hierarchyData, statusData, collapsed, onToggle }: Props) {
  if (!hierarchyData || hierarchyData.length === 0) return null;

  const chartData = hierarchyData.map(row => ({
    name: truncateLabel(getHierarchyPath(row)),
    पुनरुत्पादन: row.regeneration,
    लाथ्रा: row.sapling,
    पोल: row.pole,
    रूख: row.tree,
  }));

  const getStatusColor = (status: string) => {
    if (status === 'राम्रो') return 'text-green-600 bg-green-100';
    if (status === 'मध्यम') return 'text-amber-600 bg-amber-100';
    return 'text-red-600 bg-red-100';
  };

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div
        className="flex justify-between items-center px-6 py-4 border-b cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <h3 className="text-lg font-semibold">स्थानिक स्तर अनुसार स्ट्यान्ड प्रकार / Stand Type by Spatial Level
          <CopyTag label="{{section:sm_stand_type_narration}}" value="{{section:sm_stand_type_narration}}" variant="section" />
        </h3>
        <span className="text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="p-6">
          {statusData && (
            <div className="mb-6 p-4 rounded-lg bg-gray-50">
              <div className="flex items-center gap-4 flex-wrap">
                <span className="text-sm font-medium">समग्र अवस्था / Overall Status:</span>
                <span className={`px-3 py-1 rounded-full text-sm font-semibold ${getStatusColor(statusData.overall_status)}`}>
                  {statusData.overall_status}
                </span>
                <span className="text-sm text-gray-500">
                  पुनरुत्पादन: {statusData.overall_regeneration_percent}% | 
                  राम्रो: {statusData.good_structure_blocks} | 
                  मध्यम: {statusData.moderate_structure_blocks} | 
                  कमजोर: {statusData.weak_structure_blocks}
                </span>
              </div>
            </div>
          )}

          <div className="mb-6">
            <h4 className="text-sm font-medium text-gray-600 mb-2">स्तर अनुसार स्ट्यान्ड प्रकार / Stand Type by Hierarchy
              <CopyTag label="{{chart:sm_stand_type_bar}}" value="{{chart:sm_stand_type_bar}}" variant="variable" />
            </h4>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="पुनरुत्पादन" stackId="a" fill="#22c55e" />
                <Bar dataKey="लाथ्रा" stackId="a" fill="#3b82f6" />
                <Bar dataKey="पोल" stackId="a" fill="#f59e0b" />
                <Bar dataKey="रूख" stackId="a" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mb-1">
            <CopyTag label="{{sm_stand_type_by_hierarchy}}" value="{{sm_stand_type_by_hierarchy}}" variant="variable" />
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">स्तर पथ / Hierarchy</th>
                  <th className="px-3 py-2 text-right">पुनरुत्पादन</th>
                  <th className="px-3 py-2 text-right">लाथ्रा</th>
                  <th className="px-3 py-2 text-right">पोल</th>
                  <th className="px-3 py-2 text-right">रूख</th>
                  <th className="px-3 py-2 text-right">जम्मा</th>
                  <th className="px-3 py-2 text-right">पुनरुत्पादन %</th>
                  <th className="px-3 py-2 text-left">अवस्था</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {hierarchyData.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{getHierarchyPath(row)}</td>
                    <td className="px-3 py-2 text-right">{row.regeneration}</td>
                    <td className="px-3 py-2 text-right">{row.sapling}</td>
                    <td className="px-3 py-2 text-right">{row.pole}</td>
                    <td className="px-3 py-2 text-right">{row.tree}</td>
                    <td className="px-3 py-2 text-right font-medium">{row.total}</td>
                    <td className="px-3 py-2 text-right">{row.regeneration_percent}%</td>
                    <td className="px-3 py-2">
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${getStatusColor(row.structure_status)}`}>
                        {row.structure_status}
                      </span>
                    </td>
                  </tr>
                ))}
                <tr className="bg-gray-100 font-semibold">
                  <td className="px-3 py-2">जम्मा / Total</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.regeneration || 0), 0)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.sapling || 0), 0)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.pole || 0), 0)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.tree || 0), 0)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.total || 0), 0)}</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2">-</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
