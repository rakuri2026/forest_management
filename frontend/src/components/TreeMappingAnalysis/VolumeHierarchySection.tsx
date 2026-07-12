import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { getHierarchyPath, truncateLabel } from './hierarchyUtils';
import CopyTag from '../DetailDescription/CopyTag';

interface Props {
  hierarchyData: any[];
  topSpeciesData: any[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export function VolumeHierarchySection({ hierarchyData, topSpeciesData, collapsed, onToggle }: Props) {
  if (!hierarchyData || hierarchyData.length === 0) return null;

  const chartData = hierarchyData.map(row => ({
    name: truncateLabel(getHierarchyPath(row)),
    काण्ड: row.stem_volume_m3,
    हाँगा: row.branch_volume_m3,
  }));

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div
        className="flex justify-between items-center px-6 py-4 border-b cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <h3 className="text-lg font-semibold">स्थानिक स्तर अनुसार आयतन विश्लेषण / Volume Analysis by Spatial Level
          <CopyTag label="{{section:sm_volume_narration}}" value="{{section:sm_volume_narration}}" variant="section" />
        </h3>
        <span className="text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="p-6">
          <div className="mb-6">
            <h4 className="font-medium mb-3">आयतन संरचना / Volume Composition
              <CopyTag label="{{chart:sm_volume_bar}}" value="{{chart:sm_volume_bar}}" variant="variable" />
            </h4>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="काण्ड" stackId="a" fill="#22c55e" />
                <Bar dataKey="हाँगा" stackId="a" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mb-1">
            <CopyTag label="{{sm_volume_by_hierarchy}}" value="{{sm_volume_by_hierarchy}}" variant="variable" />
          </div>
          <div className="overflow-x-auto mb-6">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">स्तर पथ / Hierarchy</th>
                  <th className="px-3 py-2 text-right">काण्ड आयतन (m³)</th>
                  <th className="px-3 py-2 text-right">हाँगा आयतन (m³)</th>
                  <th className="px-3 py-2 text-right">कुल आयतन (m³)</th>
                  <th className="px-3 py-2 text-right">नेट आयतन (m³)</th>
                  <th className="px-3 py-2 text-right">दाउरा (m³)</th>
                  <th className="px-3 py-2 text-right">दाउरा (चट्टा)</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {hierarchyData.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{getHierarchyPath(row)}</td>
                    <td className="px-3 py-2 text-right">{row.stem_volume_m3}</td>
                    <td className="px-3 py-2 text-right">{row.branch_volume_m3}</td>
                    <td className="px-3 py-2 text-right font-medium">{row.total_volume_m3}</td>
                    <td className="px-3 py-2 text-right">{row.net_volume_m3}</td>
                    <td className="px-3 py-2 text-right">{row.firewood_m3}</td>
                    <td className="px-3 py-2 text-right">{row.firewood_chatta}</td>
                  </tr>
                ))}
                <tr className="bg-gray-100 font-semibold">
                  <td className="px-3 py-2">जम्मा / Total</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.stem_volume_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.branch_volume_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.total_volume_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.net_volume_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.firewood_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{hierarchyData.reduce((s, r) => s + (r.firewood_chatta || 0), 0).toFixed(2)}</td>
                </tr>
              </tbody>
            </table>
          </div>

          {topSpeciesData && topSpeciesData.length > 0 && (
            <div>
              <h4 className="font-medium mb-3">आयतन अनुसार शीर्ष प्रजाति / Top Species by Volume
                <CopyTag label="{{sm_top_species_by_volume}}" value="{{sm_top_species_by_volume}}" variant="variable" />
              </h4>
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">प्रजाति</th>
                    <th className="px-3 py-2 text-left">स्थानीय नाम</th>
                    <th className="px-3 py-2 text-right">कुल आयतन (m³)</th>
                    <th className="px-3 py-2 text-right">प्रतिशत</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {topSpeciesData.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{row.species}</td>
                      <td className="px-3 py-2">{row.local_name}</td>
                      <td className="px-3 py-2 text-right">{row.total_volume_m3}</td>
                      <td className="px-3 py-2 text-right">{row.percent}%</td>
                    </tr>
                  ))}
                  <tr className="bg-gray-100 font-semibold">
                    <td className="px-3 py-2" colSpan={2}>जम्मा / Total</td>
                    <td className="px-3 py-2 text-right">{topSpeciesData.reduce((s, r) => s + (r.total_volume_m3 || 0), 0).toFixed(2)}</td>
                    <td className="px-3 py-2 text-right">100%</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
