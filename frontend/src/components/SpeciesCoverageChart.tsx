import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

interface SpeciesData {
  scientific_name: string;
  local_name: string;
  present_in_blocks: number;
  total_blocks: number;
  coverage_percentage: number;
  confirmed: boolean;
  roles: string[];
}

interface SpeciesCoverageChartProps {
  speciesData: SpeciesData[];
  totalBlocks: number;
}

const SpeciesCoverageChart: React.FC<SpeciesCoverageChartProps> = ({ speciesData, totalBlocks }) => {
  // Prepare data for the chart - show top 15 species by coverage
  const chartData = speciesData
    .slice(0, 15)
    .map(species => ({
      name: species.local_name || species.scientific_name,
      blocks: species.present_in_blocks,
      coverage: species.coverage_percentage,
      confirmed: species.confirmed
    }));

  // Color based on confirmation status
  const getBarColor = (confirmed: boolean) => {
    return confirmed ? '#10b981' : '#9ca3af'; // Green if confirmed, gray if not
  };

  return (
    <div className="w-full">
      <h3 className="text-lg font-semibold mb-4 text-gray-900">
        Species Distribution Across Blocks (Top 15)
      </h3>
      <ResponsiveContainer width="100%" height={400}>
        <BarChart
          data={chartData}
          margin={{ top: 20, right: 30, left: 20, bottom: 100 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="name"
            angle={-45}
            textAnchor="end"
            height={120}
            interval={0}
            tick={{ fontSize: 11 }}
          />
          <YAxis
            label={{ value: 'Number of Blocks', angle: -90, position: 'insideLeft' }}
            domain={[0, totalBlocks]}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <div className="bg-white p-3 border border-gray-300 rounded shadow-lg">
                    <p className="font-semibold text-gray-900">{data.name}</p>
                    <p className="text-sm text-gray-600">
                      Present in: <span className="font-semibold">{data.blocks}</span> / {totalBlocks} blocks
                    </p>
                    <p className="text-sm text-gray-600">
                      Coverage: <span className="font-semibold">{data.coverage}%</span>
                    </p>
                    <p className="text-sm">
                      Status: <span className={`font-semibold ${data.confirmed ? 'text-green-600' : 'text-gray-600'}`}>
                        {data.confirmed ? 'Confirmed' : 'Unconfirmed'}
                      </span>
                    </p>
                  </div>
                );
              }
              return null;
            }}
          />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            content={() => (
              <div className="flex justify-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-green-500 rounded"></div>
                  <span>Confirmed</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 bg-gray-400 rounded"></div>
                  <span>Unconfirmed</span>
                </div>
              </div>
            )}
          />
          <Bar dataKey="blocks" radius={[8, 8, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getBarColor(entry.confirmed)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="text-xs text-gray-500 mt-2 text-center">
        Showing top 15 species by block coverage. Confirmed species shown in green.
      </p>
    </div>
  );
};

export default SpeciesCoverageChart;
