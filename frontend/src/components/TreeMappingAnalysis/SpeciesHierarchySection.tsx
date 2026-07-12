import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { getHierarchyPath, truncateLabel } from './hierarchyUtils';
import CopyTag from '../DetailDescription/CopyTag';

interface Props {
  speciesData: any[];
  diversityData: any[];
  hierRemarkData?: any[];
  collapsed?: boolean;
  onToggle?: () => void;
}

export function SpeciesHierarchySection({ speciesData, diversityData, hierRemarkData, collapsed, onToggle }: Props) {
  if (!speciesData || speciesData.length === 0) return null;

  // Build lookup from hierRemarkData: key = hierarchy+species -> { mother, felling }
  const remarkLookup: Record<string, { mother: number; felling: number }> = {};
  (hierRemarkData || []).forEach((row: any) => {
    const key = `${getHierarchyPath(row)}|${row.species}`;
    if (!remarkLookup[key]) remarkLookup[key] = { mother: 0, felling: 0 };
    if (row.remark === 'Mother Tree') remarkLookup[key].mother = row.tree_count;
    else if (row.remark === 'Felling Tree') remarkLookup[key].felling = row.tree_count;
  });

  // Group by compartment for chart
  const blockGroups: Record<string, Record<string, number>> = {};
  speciesData.forEach(row => {
    const key = row.compartment !== '-' ? row.compartment : row.block_name;
    if (!blockGroups[key]) blockGroups[key] = {};
    blockGroups[key][row.species] = (blockGroups[key][row.species] || 0) + row.tree_count;
  });

  const allSpecies = [...new Set(speciesData.map(r => r.species))];

  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div
        className="flex justify-between items-center px-6 py-4 border-b cursor-pointer hover:bg-gray-50"
        onClick={onToggle}
      >
        <h3 className="text-lg font-semibold">स्थानिक स्तर अनुसार प्रजाति विश्लेषण / Species by Spatial Level
          <CopyTag label="{{section:sm_species_narration}}" value="{{section:sm_species_narration}}" variant="section" />
        </h3>
        <span className="text-gray-400">{collapsed ? '▶' : '▼'}</span>
      </div>
      {!collapsed && (
        <div className="p-6">
          {/* Species Table */}
          <div className="mb-1">
            <CopyTag label="{{sm_species_by_hierarchy}}" value="{{sm_species_by_hierarchy}}" variant="variable" />
          </div>
          <div className="overflow-x-auto mb-6">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left">स्तर पथ / Hierarchy</th>
                  <th className="px-3 py-2 text-left">प्रजाति</th>
                  <th className="px-3 py-2 text-left">स्थानीय नाम</th>
                  <th className="px-3 py-2 text-right">जम्मा रूख</th>
                  <th className="px-3 py-2 text-right bg-green-50">माँउ रूख</th>
                  <th className="px-3 py-2 text-right bg-red-50">कटानी रूख</th>
                  <th className="px-3 py-2 text-right">स्तर प्रतिशत</th>
                  <th className="px-3 py-2 text-right">काठ (m³)</th>
                  <th className="px-3 py-2 text-right">दाउरा (m³)</th>
                  <th className="px-3 py-2 text-right">कुल आयतन (m³)</th>
                  <th className="px-3 py-2 text-right">आयतन प्रतिशत</th>
                  <th className="px-3 py-2 text-right">औसत डीबीएच</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {speciesData.map((row, idx) => {
                  const key = `${getHierarchyPath(row)}|${row.species}`;
                  const rk = remarkLookup[key];
                  return (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2">{getHierarchyPath(row)}</td>
                      <td className="px-3 py-2 font-medium">{row.species}</td>
                      <td className="px-3 py-2">{row.local_name}</td>
                      <td className="px-3 py-2 text-right font-medium">{row.tree_count}</td>
                      <td className="px-3 py-2 text-right text-green-600 bg-green-50">{rk?.mother || 0}</td>
                      <td className="px-3 py-2 text-right text-red-600 bg-red-50">{rk?.felling || 0}</td>
                      <td className="px-3 py-2 text-right">{row.hierarchy_percent}%</td>
                      <td className="px-3 py-2 text-right">{row.timber_m3}</td>
                      <td className="px-3 py-2 text-right">{row.firewood_m3}</td>
                      <td className="px-3 py-2 text-right">{row.gross_volume_m3}</td>
                      <td className="px-3 py-2 text-right">{row.volume_percent}%</td>
                      <td className="px-3 py-2 text-right">{row.avg_dbh_cm}</td>
                    </tr>
                  );
                })}
                <tr className="bg-gray-100 font-semibold">
                  <td className="px-3 py-2" colSpan={3}>जम्मा / Total</td>
                  <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + r.tree_count, 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right text-green-700 bg-green-50">{Object.values(remarkLookup).reduce((s, r) => s + r.mother, 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right text-red-700 bg-red-50">{Object.values(remarkLookup).reduce((s, r) => s + r.felling, 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + (r.timber_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + (r.firewood_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">{speciesData.reduce((s, r) => s + (r.gross_volume_m3 || 0), 0).toFixed(2)}</td>
                  <td className="px-3 py-2 text-right">-</td>
                  <td className="px-3 py-2 text-right">-</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Diversity Table */}
          {diversityData && diversityData.length > 0 && (
            <div>
              <h4 className="font-semibold mb-3">ब्लक अनुसार प्रजाति विविधता / Species Diversity by Block
                <CopyTag label="{{sm_species_diversity}}" value="{{sm_species_diversity}}" variant="variable" />
              </h4>
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left">ब्लकको नाम</th>
                    <th className="px-3 py-2 text-right">प्रजाति समृद्धि</th>
                    <th className="px-3 py-2 text-right">श्यानन सूचकांक</th>
                    <th className="px-3 py-2 text-right">समानता</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {diversityData.map((row, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-3 py-2 font-medium">{row.block_name}</td>
                      <td className="px-3 py-2 text-right">{row.species_richness}</td>
                      <td className="px-3 py-2 text-right">{row.shannon_index}</td>
                      <td className="px-3 py-2 text-right">{row.evenness}</td>
                    </tr>
                  ))}
                  <tr className="bg-gray-100 font-semibold">
                    <td className="px-3 py-2">जम्मा / Total</td>
                    <td className="px-3 py-2 text-right">{diversityData.reduce((s, r) => s + (r.species_richness || 0), 0)}</td>
                    <td className="px-3 py-2 text-right">-</td>
                    <td className="px-3 py-2 text-right">-</td>
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
