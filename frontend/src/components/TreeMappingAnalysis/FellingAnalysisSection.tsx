import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { getHierarchyPath } from './hierarchyUtils';
import CopyTag from '../DetailDescription/CopyTag';

const COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1'];

interface Props {
  totals?: any;
  dbhData: any[];
  speciesData: any[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export function FellingAnalysisSection({ totals, dbhData, speciesData, collapsed, onToggle }: Props) {
  if (!dbhData || dbhData.length === 0) return null;

  // DBH class pie chart
  const dbhPieData = dbhData.map(r => ({
    name: r.dbh_class,
    value: r.tree_count,
  }));

  // Species bar chart (top 10)
  const spChartData = speciesData.slice(0, 10).map(r => ({
    species: r.species.length > 15 ? r.species.substring(0, 12) + '...' : r.species,
    रूख: r.tree_count,
    काठ: r.timber_m3,
  }));

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden border-2 border-red-200">
      <div
        className="flex justify-between items-center px-6 py-4 border-b cursor-pointer hover:bg-red-50"
        onClick={onToggle}
      >
        <h3 className="text-lg font-semibold text-red-800">कटानी रूख विश्लेषण / Felling Tree Analysis (DBH ≥ 30cm)
          <CopyTag label="{{section:sm_felling_narration}}" value="{{section:sm_felling_narration}}" variant="section" />
        </h3>
        <span className="text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="p-6">
          {/* Totals Summary Cards */}
          {totals && (
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-6">
              <div className="bg-red-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">कुल रूख</p>
                <p className="text-xl font-bold text-red-700">{totals.tree_count.toLocaleString()}</p>
              </div>
              <div className="bg-green-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">काठ m³</p>
                <p className="text-xl font-bold text-green-700">{totals.timber_m3.toLocaleString()}</p>
              </div>
              <div className="bg-blue-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">दाउरा m³</p>
                <p className="text-xl font-bold text-blue-700">{totals.firewood_m3.toLocaleString()}</p>
              </div>
              <div className="bg-amber-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">स्थूल m³</p>
                <p className="text-xl font-bold text-amber-700">{totals.gross_volume_m3.toLocaleString()}</p>
              </div>
              <div className="bg-purple-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">नेट m³</p>
                <p className="text-xl font-bold text-purple-700">{totals.net_volume_m3.toLocaleString()}</p>
              </div>
              <div className="bg-teal-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">इन्धन m³</p>
                <p className="text-xl font-bold text-teal-700">{totals.fuelwood_m3.toLocaleString()}</p>
              </div>
              <div className="bg-orange-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500">चट्टा m³</p>
                <p className="text-xl font-bold text-orange-700">{totals.fuelwood_chatta.toLocaleString()}</p>
              </div>
            </div>
          )}

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* DBH Pie Chart */}
            <div>
              <h4 className="font-medium mb-3 text-center">DBH वर्ग अनुसार / By DBH Class
                <CopyTag label="{{chart:sm_felling_dbh_pie}}" value="{{chart:sm_felling_dbh_pie}}" variant="variable" />
              </h4>
              <ResponsiveContainer width="100%" height={280}>
                <PieChart>
                  <Pie
                    data={dbhPieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {dbhPieData.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Species Bar Chart */}
            <div>
              <h4 className="font-medium mb-3 text-center">प्रजाति अनुसार / By Species (Top 10)
                <CopyTag label="{{chart:sm_felling_species_bar}}" value="{{chart:sm_felling_species_bar}}" variant="variable" />
              </h4>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={spChartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="species" type="category" width={110} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="रूख" fill="#ef4444" name="रूख सङ्ख्या" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* DBH Class Table */}
          <div className="mb-6">
            <h4 className="font-medium mb-3">DBH वर्ग अनुसार कटानी रूख / Felling by DBH Class
              <CopyTag label="{{sm_felling_dbh_analysis}}" value="{{sm_felling_dbh_analysis}}" variant="variable" />
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-red-50">
                  <tr>
                    <th className="px-3 py-2 text-left">DBH वर्ग</th>
                    <th className="px-3 py-2 text-right">रूख सङ्ख्या</th>
                    <th className="px-3 py-2 text-right">प्रतिशत</th>
                    <th className="px-3 py-2 text-right">काठ (m³)</th>
                    <th className="px-3 py-2 text-right">दाउरा (m³)</th>
                    <th className="px-3 py-2 text-right">स्थूल (m³)</th>
                    <th className="px-3 py-2 text-right">नेट (m³)</th>
                    <th className="px-3 py-2 text-right">इन्धन (m³)</th>
                    <th className="px-3 py-2 text-right">चट्टा (m³)</th>
                    <th className="px-3 py-2 text-right">औसत DBH</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {dbhData.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{row.dbh_class}</td>
                      <td className="px-3 py-2 text-right font-medium">{row.tree_count.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right">{row.percent}%</td>
                      <td className="px-3 py-2 text-right text-green-700 font-medium">{row.timber_m3}</td>
                      <td className="px-3 py-2 text-right text-blue-700">{row.firewood_m3}</td>
                      <td className="px-3 py-2 text-right font-medium">{row.gross_volume_m3}</td>
                      <td className="px-3 py-2 text-right text-purple-700">{row.net_volume_m3}</td>
                      <td className="px-3 py-2 text-right text-teal-700">{row.fuelwood_m3}</td>
                      <td className="px-3 py-2 text-right text-orange-700">{row.fuelwood_chatta}</td>
                      <td className="px-3 py-2 text-right">{row.avg_dbh_cm}</td>
                    </tr>
                  ))}
                  {totals && (
                    <tr className="bg-gray-100 font-semibold">
                      <td className="px-3 py-2">जम्मा / Total</td>
                      <td className="px-3 py-2 text-right">{totals.tree_count.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right">100%</td>
                      <td className="px-3 py-2 text-right text-green-700">{totals.timber_m3}</td>
                      <td className="px-3 py-2 text-right text-blue-700">{totals.firewood_m3}</td>
                      <td className="px-3 py-2 text-right">{totals.gross_volume_m3}</td>
                      <td className="px-3 py-2 text-right text-purple-700">{totals.net_volume_m3}</td>
                      <td className="px-3 py-2 text-right text-teal-700">{totals.fuelwood_m3}</td>
                      <td className="px-3 py-2 text-right text-orange-700">{totals.fuelwood_chatta}</td>
                      <td className="px-3 py-2 text-right">-</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Species Table */}
          <div>
            <h4 className="font-medium mb-3">प्रजाति अनुसार कटानी रूख / Felling by Species
              <CopyTag label="{{sm_felling_species_analysis}}" value="{{sm_felling_species_analysis}}" variant="variable" />
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-red-50">
                  <tr>
                    <th className="px-3 py-2 text-left">प्रजाति</th>
                    <th className="px-3 py-2 text-left">स्थानीय नाम</th>
                    <th className="px-3 py-2 text-right">रूख सङ्ख्या</th>
                    <th className="px-3 py-2 text-right">प्रतिशत</th>
                    <th className="px-3 py-2 text-right">काठ (m³)</th>
                    <th className="px-3 py-2 text-right">दाउरा (m³)</th>
                    <th className="px-3 py-2 text-right">स्थूल (m³)</th>
                    <th className="px-3 py-2 text-right">नेट (m³)</th>
                    <th className="px-3 py-2 text-right">औसत DBH</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {speciesData.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{row.species}</td>
                      <td className="px-3 py-2">{row.local_name}</td>
                      <td className="px-3 py-2 text-right font-medium">{row.tree_count.toLocaleString()}</td>
                      <td className="px-3 py-2 text-right">{row.percent}%</td>
                      <td className="px-3 py-2 text-right text-green-700 font-medium">{row.timber_m3}</td>
                      <td className="px-3 py-2 text-right text-blue-700">{row.firewood_m3}</td>
                      <td className="px-3 py-2 text-right font-medium">{row.gross_volume_m3}</td>
                      <td className="px-3 py-2 text-right text-purple-700">{row.net_volume_m3}</td>
                      <td className="px-3 py-2 text-right">{row.avg_dbh_cm}</td>
                    </tr>
                  ))}
                  <tr className="bg-red-50 font-semibold">
                    <td className="px-3 py-2" colSpan={2}>जम्मा / Total</td>
                    <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + r.tree_count, 0).toLocaleString()}</td>
                    <td className="px-3 py-2 text-right">100%</td>
                    <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + (r.timber_m3 || 0), 0).toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + (r.firewood_m3 || 0), 0).toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + (r.gross_volume_m3 || 0), 0).toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + (r.net_volume_m3 || 0), 0).toFixed(2)}</td>
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
