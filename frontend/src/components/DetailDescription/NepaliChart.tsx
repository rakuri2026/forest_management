import React, { useMemo } from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { GraphicData } from '../../services/sectionGenerators';
import { toNepaliDigit } from '../../constants/nepaliLabels';

interface NepaliChartProps {
  graphic: GraphicData;
  height?: number;
}

const FALLBACK_PALETTE = [
  '#059669', '#dc2626', '#2563eb', '#d97706',
  '#7c3aed', '#db2777', '#0891b2', '#65a30d',
  '#ea580c', '#4f46e5', '#0d9488', '#9333ea',
  '#ca8a04', '#16a34a', '#e11d48', '#0284c7',
  '#a21caf', '#c2410c', '#64748b', '#84cc16',
];

function dedupeColors(data: { label: string; value: number; color: string }[]):
  { label: string; value: number; color: string }[] {
  const used = new Set<string>();
  let paletteIdx = 0;
  return data.map((d) => {
    let color = d.color || FALLBACK_PALETTE[paletteIdx % FALLBACK_PALETTE.length];
    while (used.has(color)) {
      paletteIdx++;
      color = FALLBACK_PALETTE[paletteIdx % FALLBACK_PALETTE.length];
    }
    used.add(color);
    paletteIdx++;
    return { ...d, color };
  });
}

const np = (n: number, d = 1) => toNepaliDigit(n, d);

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="bg-white p-2 border border-gray-300 rounded shadow-lg text-xs">
        <p className="font-semibold">{d.label}</p>
        <p className="text-gray-600">{np(d.value)}%</p>
      </div>
    );
  }
  return null;
};

const PieLegend = ({ data }: { data: { label: string; value: number; color: string }[] }) => {
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 mt-2 text-xs">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-3 rounded-sm" style={{ backgroundColor: d.color }} />
          <span className="text-gray-700">{d.label}</span>
          <span className="text-gray-500 font-medium">{np(d.value, 0)}</span>
        </div>
      ))}
    </div>
  );
};

const NepaliChart: React.FC<NepaliChartProps> = ({ graphic, height = 250 }) => {
  const deduped = useMemo(() => dedupeColors(graphic.data), [graphic.data]);

  if (graphic.type === 'none' || deduped.length === 0) return null;

  const total = deduped.reduce((s, d) => s + d.value, 0);

  if (graphic.type === 'pie') {
    return (
      <div>
        <ResponsiveContainer width="100%" height={height}>
          <PieChart>
            <Pie
              data={deduped}
              cx="50%"
              cy="50%"
              labelLine={false}
              outerRadius={90}
              dataKey="value"
            >
              {deduped.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <PieLegend data={deduped} />
      </div>
    );
  }

  if (graphic.type === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={deduped} margin={{ top: 10, right: 20, left: 0, bottom: 50 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" angle={-35} textAnchor="end" height={90} tick={{ fontSize: 11 }} interval={0} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => toNepaliDigit(v, 0)} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {deduped.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (graphic.type === 'horizontal_bar') {
    return (
      <ResponsiveContainer width="100%" height={Math.max(height, deduped.length * 35)}>
        <BarChart
          data={deduped}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" tick={{ fontSize: 11 }} domain={[0, 'auto']} tickFormatter={(v: number) => toNepaliDigit(v, 0)} />
          <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={100} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {deduped.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (graphic.type === 'stacked_bar') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={[{
          name: 'क्षेत्रफल',
          ...Object.fromEntries(deduped.map(d => [d.label, d.value]))
        }]} margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => toNepaliDigit(v, 0)} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: '11px' }} />
          {deduped.map((entry, i) => (
            <Bar key={i} dataKey={entry.label} stackId="a" fill={entry.color} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  return null;
};

export default NepaliChart;
