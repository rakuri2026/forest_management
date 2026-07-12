import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { getHierarchyPath } from './hierarchyUtils';
import CopyTag from '../DetailDescription/CopyTag';

const COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1'];

interface Props {
  coverageData?: any;
  hierarchyData: any[];
  remarkBreakdown?: Record<string, any>;
  motherBySpecies?: any[];
  fellingBySpecies?: any[];
  summary?: any;
  collapsed?: boolean;
  onToggle?: () => void;
}

export function MotherTreeCoverageSection({
  coverageData,
  hierarchyData,
  remarkBreakdown,
  motherBySpecies,
  fellingBySpecies,
  summary,
  collapsed,
  onToggle,
}: Props) {
  if (!hierarchyData || hierarchyData.length === 0) return null;

  // Pie chart data for mother vs felling
  const pieData = summary ? [
    { name: 'माँउ रूख (Mother)', value: summary.total_mother_trees },
    { name: 'कटानी रूख (Felling)', value: summary.total_felling_trees },
  ] : [];

  // Species bar chart data
  const speciesChartData = motherBySpecies && fellingBySpecies ? (() => {
    const speciesMap: Record<string, { mother: number; felling: number }> = {};
    motherBySpecies.forEach((r: any) => {
      if (!speciesMap[r.species]) speciesMap[r.species] = { mother: 0, felling: 0 };
      speciesMap[r.species].mother = r.tree_count;
    });
    fellingBySpecies.forEach((r: any) => {
      if (!speciesMap[r.species]) speciesMap[r.species] = { mother: 0, felling: 0 };
      speciesMap[r.species].felling = r.tree_count;
    });
    return Object.entries(speciesMap)
      .sort((a, b) => (b[1].mother + b[1].felling) - (a[1].mother + a[1].felling))
      .slice(0, 10)
      .map(([species, counts]) => ({
        species: species.length > 15 ? species.substring(0, 12) + '...' : species,
        माँउ: counts.mother,
        कटानी: counts.felling,
      }));
  })() : [];

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div
        className="flex justify-between items-center px-6 py-4 border-b cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <h3 className="text-lg font-semibold">माँउ रूख विश्लेषण / Mother Tree Analysis
          <CopyTag label="{{section:sm_mother_tree_narration}}" value="{{section:sm_mother_tree_narration}}" variant="section" />
        </h3>
        <span className="text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="p-6">
          {/* Coverage Summary Cards */}
          {coverageData && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-green-50 rounded-lg p-4 text-center">
                <p className="text-sm text-gray-500">ग्रिड दूरी (मि.)</p>
                <p className="text-2xl font-bold text-green-600">{coverageData.grid_spacing_m}</p>
              </div>
              <div className="bg-blue-50 rounded-lg p-4 text-center">
                <p className="text-sm text-gray-500">कुल ग्रिड सेल</p>
                <p className="text-2xl font-bold text-blue-600">{coverageData.total_grid_cells}</p>
              </div>
              <div className="bg-amber-50 rounded-lg p-4 text-center">
                <p className="text-sm text-gray-500">माँउ रूख भएको सेल</p>
                <p className="text-2xl font-bold text-amber-600">{coverageData.cells_with_mother}</p>
              </div>
              <div className="bg-purple-50 rounded-lg p-4 text-center">
                <p className="text-sm text-gray-500">कभरेज प्रतिशत</p>
                <p className="text-2xl font-bold text-purple-600">{coverageData.coverage_percent}%</p>
              </div>
            </div>
          )}

          {/* Mother vs Felling Summary */}
          {summary && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {/* Pie Chart */}
              <div>
                <h4 className="font-medium mb-3 text-center">माँउ रूख बनाम कटानी रूख / Mother vs Felling
                  <CopyTag label="{{chart:sm_mother_felling_pie}}" value="{{chart:sm_mother_felling_pie}}" variant="variable" />
                </h4>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {pieData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={index === 0 ? '#22c55e' : '#ef4444'} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Summary Stats */}
              <div className="flex flex-col justify-center">
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                    <span className="font-medium text-green-800">माँउ रूख (Mother Trees)</span>
                    <span className="text-2xl font-bold text-green-600">{summary.total_mother_trees.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                    <span className="font-medium text-red-800">कटानी रूख (Felling Trees)</span>
                    <span className="text-2xl font-bold text-red-600">{summary.total_felling_trees.toLocaleString()}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-gray-100 rounded-lg">
                    <span className="font-medium text-gray-800">जम्मा (Total)</span>
                    <span className="text-2xl font-bold text-gray-600">{summary.total_trees.toLocaleString()}</span>
                  </div>
                  <div className="text-sm text-gray-500 text-center">
                    माँउ: {summary.mother_percent}% | कटानी: {summary.felling_percent}%
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Species-wise Mother vs Felling Chart */}
          {speciesChartData.length > 0 && (
            <div className="mb-6">
              <h4 className="font-medium mb-3">प्रजाति अनुसार माँउ बनाम कटानी रूख / Species-wise Mother vs Felling
                <CopyTag label="{{chart:sm_mother_felling_species_bar}}" value="{{chart:sm_mother_felling_species_bar}}" variant="variable" />
              </h4>
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={speciesChartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="species" type="category" width={120} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="माँउ" fill="#22c55e" name="माँउ रूख" />
                  <Bar dataKey="कटानी" fill="#ef4444" name="कटानी रूख" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Species Tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* Mother Tree by Species */}
            {motherBySpecies && motherBySpecies.length > 0 && (
              <div>
                <h4 className="font-medium mb-3 text-green-700">प्रजाति अनुसार माँउ रूख / Mother Tree by Species
                  <CopyTag label="{{sm_mother_tree_by_species}}" value="{{sm_mother_tree_by_species}}" variant="variable" />
                </h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-green-50">
                      <tr>
                        <th className="px-3 py-2 text-left">प्रजाति</th>
                        <th className="px-3 py-2 text-left">स्थानीय नाम</th>
                        <th className="px-3 py-2 text-right">सङ्ख्या</th>
                        <th className="px-3 py-2 text-right">प्रतिशत</th>
                        <th className="px-3 py-2 text-right">काठ (m³)</th>
                        <th className="px-3 py-2 text-right">DBH (cm)</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {motherBySpecies.map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium">{row.species}</td>
                          <td className="px-3 py-2">{row.local_name}</td>
                          <td className="px-3 py-2 text-right font-medium">{row.tree_count}</td>
                          <td className="px-3 py-2 text-right">{row.percent}%</td>
                          <td className="px-3 py-2 text-right">{row.timber_m3}</td>
                          <td className="px-3 py-2 text-right">{row.avg_dbh_cm}</td>
                        </tr>
                      ))}
                      <tr className="bg-green-50 font-semibold">
                        <td className="px-3 py-2" colSpan={2}>जम्मा / Total</td>
                        <td className="px-3 py-2 text-right">{motherBySpecies.reduce((s, r) => s + r.tree_count, 0).toLocaleString()}</td>
                        <td className="px-3 py-2 text-right">100%</td>
                        <td className="px-3 py-2 text-right">{motherBySpecies.reduce((s, r) => s + r.timber_m3, 0).toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">-</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Felling Tree by Species */}
            {fellingBySpecies && fellingBySpecies.length > 0 && (
              <div>
                <h4 className="font-medium mb-3 text-red-700">प्रजाति अनुसार कटानी रूख / Felling Tree by Species
                  <CopyTag label="{{sm_felling_tree_by_species}}" value="{{sm_felling_tree_by_species}}" variant="variable" />
                </h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-red-50">
                      <tr>
                        <th className="px-3 py-2 text-left">प्रजाति</th>
                        <th className="px-3 py-2 text-left">स्थानीय नाम</th>
                        <th className="px-3 py-2 text-right">सङ्ख्या</th>
                        <th className="px-3 py-2 text-right">प्रतिशत</th>
                        <th className="px-3 py-2 text-right">काठ (m³)</th>
                        <th className="px-3 py-2 text-right">DBH (cm)</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {fellingBySpecies.map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-50">
                          <td className="px-3 py-2 font-medium">{row.species}</td>
                          <td className="px-3 py-2">{row.local_name}</td>
                          <td className="px-3 py-2 text-right font-medium">{row.tree_count}</td>
                          <td className="px-3 py-2 text-right">{row.percent}%</td>
                          <td className="px-3 py-2 text-right">{row.timber_m3}</td>
                          <td className="px-3 py-2 text-right">{row.avg_dbh_cm}</td>
                        </tr>
                      ))}
                      <tr className="bg-red-50 font-semibold">
                        <td className="px-3 py-2" colSpan={2}>जम्मा / Total</td>
                        <td className="px-3 py-2 text-right">{fellingBySpecies.reduce((s, r) => s + r.tree_count, 0).toLocaleString()}</td>
                        <td className="px-3 py-2 text-right">100%</td>
                        <td className="px-3 py-2 text-right">{fellingBySpecies.reduce((s, r) => s + r.timber_m3, 0).toFixed(2)}</td>
                        <td className="px-3 py-2 text-right">-</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Hierarchy Table */}
          <div>
            <h4 className="font-medium mb-3">स्तर अनुसार माँउ/कटानी रूख / Mother/Felling by Hierarchy
              <CopyTag label="{{sm_mother_tree_by_hierarchy}}" value="{{sm_mother_tree_by_hierarchy}}" variant="variable" />
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">स्तर पथ / Hierarchy</th>
                    <th className="px-3 py-2 text-right">ग्रिड सेल</th>
                    <th className="px-3 py-2 text-right bg-green-50">माँउ रूख</th>
                    <th className="px-3 py-2 text-right bg-red-50">कटानी रूख</th>
                    <th className="px-3 py-2 text-right">कभरेज अनुपात</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {hierarchyData.map((row, idx) => {
                    const rk = remarkBreakdown?.[`${row.sub_compartment}|${row.compartment}|${row.block_name}|${row.sub_area_name}`];
                    const motherCount = rk?.mother_trees ?? row.mother_trees ?? 0;
                    const fellingCount = rk?.felling_trees ?? 0;
                    return (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-3 py-2 font-medium">{getHierarchyPath(row)}</td>
                        <td className="px-3 py-2 text-right">{row.grid_cells}</td>
                        <td className="px-3 py-2 text-right text-green-600 font-medium bg-green-50">{motherCount.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right text-red-600 font-medium bg-red-50">{fellingCount.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right">
                          <span className={`px-2 py-1 rounded text-xs font-semibold ${
                            row.coverage_ratio >= 0.7 ? 'bg-green-100 text-green-700' :
                            row.coverage_ratio >= 0.5 ? 'bg-amber-100 text-amber-700' :
                            'bg-red-100 text-red-700'
                          }`}>
                            {(row.coverage_ratio * 100).toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                      );
                    })}
                    <tr className="bg-gray-100 font-semibold">
                      <td className="px-3 py-2">जम्मा / Total</td>
                      <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.grid_cells || 0), 0)}</td>
                      <td className="px-3 py-2 text-right text-green-700 bg-green-50">{hierarchyData.reduce((s, r) => {
                        const rk = remarkBreakdown?.[`${r.sub_compartment}|${r.compartment}|${r.block_name}|${r.sub_area_name}`];
                        return s + (rk?.mother_trees ?? r.mother_trees ?? 0);
                      }, 0).toLocaleString()}</td>
                      <td className="px-3 py-2 text-right text-red-700 bg-red-50">{hierarchyData.reduce((s, r) => {
                        const rk = remarkBreakdown?.[`${r.sub_compartment}|${r.compartment}|${r.block_name}|${r.sub_area_name}`];
                        return s + (rk?.felling_trees ?? 0);
                      }, 0).toLocaleString()}</td>
                      <td className="px-3 py-2 text-right">-</td>
                    </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
