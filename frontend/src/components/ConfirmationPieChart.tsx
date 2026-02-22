import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

interface ConfirmationPieChartProps {
  confirmedCount: number;
  unconfirmedCount: number;
}

const ConfirmationPieChart: React.FC<ConfirmationPieChartProps> = ({ confirmedCount, unconfirmedCount }) => {
  const data = [
    { name: 'Confirmed', value: confirmedCount, color: '#10b981' },
    { name: 'Unconfirmed', value: unconfirmedCount, color: '#9ca3af' }
  ];

  const totalSpecies = confirmedCount + unconfirmedCount;
  const confirmedPercentage = totalSpecies > 0 ? ((confirmedCount / totalSpecies) * 100).toFixed(1) : '0.0';

  // Custom label to show percentage
  const renderLabel = (entry: any) => {
    const percent = totalSpecies > 0 ? ((entry.value / totalSpecies) * 100).toFixed(1) : '0.0';
    return `${percent}%`;
  };

  return (
    <div className="w-full">
      <h3 className="text-lg font-semibold mb-4 text-gray-900">
        Species Confirmation Status
      </h3>
      <div className="flex flex-col items-center">
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={renderLabel}
              outerRadius={100}
              fill="#8884d8"
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const data = payload[0];
                  const percent = totalSpecies > 0 ? ((data.value as number / totalSpecies) * 100).toFixed(1) : '0.0';
                  return (
                    <div className="bg-white p-3 border border-gray-300 rounded shadow-lg">
                      <p className="font-semibold text-gray-900">{data.name}</p>
                      <p className="text-sm text-gray-600">
                        Count: <span className="font-semibold">{data.value}</span> species
                      </p>
                      <p className="text-sm text-gray-600">
                        Percentage: <span className="font-semibold">{percent}%</span>
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Legend
              verticalAlign="bottom"
              height={36}
              content={() => (
                <div className="flex justify-center gap-4 text-sm mt-4">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-green-500 rounded"></div>
                    <span>Confirmed ({confirmedCount})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-gray-400 rounded"></div>
                    <span>Unconfirmed ({unconfirmedCount})</span>
                  </div>
                </div>
              )}
            />
          </PieChart>
        </ResponsiveContainer>

        <div className="mt-6 grid grid-cols-3 gap-4 w-full max-w-md">
          <div className="bg-gray-50 p-3 rounded-lg text-center">
            <p className="text-2xl font-bold text-gray-900">{totalSpecies}</p>
            <p className="text-xs text-gray-600 mt-1">Total Species</p>
          </div>
          <div className="bg-green-50 p-3 rounded-lg text-center">
            <p className="text-2xl font-bold text-green-600">{confirmedCount}</p>
            <p className="text-xs text-gray-600 mt-1">Confirmed</p>
          </div>
          <div className="bg-gray-100 p-3 rounded-lg text-center">
            <p className="text-2xl font-bold text-gray-600">{unconfirmedCount}</p>
            <p className="text-xs text-gray-600 mt-1">Unconfirmed</p>
          </div>
        </div>

        <div className="mt-4 text-center">
          <p className="text-sm text-gray-600">
            Confirmation Progress: <span className="font-semibold text-green-600">{confirmedPercentage}%</span> complete
          </p>
        </div>
      </div>
    </div>
  );
};

export default ConfirmationPieChart;
