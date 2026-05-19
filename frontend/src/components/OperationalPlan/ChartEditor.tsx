import React, { useState, useEffect } from 'react';
import { Select, Spin, Empty, message, Card, Row, Col, Tag, Statistic } from 'antd';
import { Pie, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
} from 'chart.js';
import { operationalPlanApi } from '../../services/api';

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title);

interface ChartEditorProps {
  planId: string;
}

interface ChartData {
  chart_type: string;
  title: string;
  labels: string[];
  datasets: {
    label: string;
    data: number[];
    backgroundColor: string | string[];
    borderColor?: string | string[];
    borderWidth?: number;
  }[];
}

const CHART_OPTIONS: { value: string; label: string; category: string }[] = [
  { value: 'species_pie', label: 'Species Composition', category: 'Pie' },
  { value: 'forest_type_pie', label: 'Forest Type Distribution', category: 'Pie' },
  { value: 'slope_pie', label: 'Slope Classification', category: 'Pie' },
  { value: 'canopy_pie', label: 'Canopy Cover', category: 'Pie' },
  { value: 'landcover_pie', label: 'Land Cover Distribution', category: 'Pie' },
  { value: 'block_area_bar', label: 'Block-wise Area', category: 'Bar' },
  { value: 'dbh_histogram', label: 'DBH Class Distribution', category: 'Bar' },
  { value: 'biomass_bar', label: 'Biomass & Carbon Stock', category: 'Bar' },
];

const PIE_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom' as const, labels: { font: { size: 12 }, padding: 12 } },
    title: { display: true, text: '', font: { size: 14 } },
  },
};

const BAR_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    title: { display: true, text: '', font: { size: 14 } },
  },
  scales: {
    y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.06)' } },
    x: { grid: { display: false } },
  },
};

const ChartEditor: React.FC<ChartEditorProps> = ({ planId }) => {
  const [selectedType, setSelectedType] = useState<string>('species_pie');
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadChartData(selectedType);
  }, [selectedType, planId]);

  const loadChartData = async (chartType: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await operationalPlanApi.getChartData(planId, chartType);
      setChartData(data);
    } catch (err: any) {
      if (err.response?.status === 404) {
        setError('No data available for this chart type.');
      } else {
        setError('Failed to load chart data.');
      }
      setChartData(null);
    } finally {
      setLoading(false);
    }
  };

  const selectedOption = CHART_OPTIONS.find(o => o.value === selectedType);
  const isPie = selectedOption?.category === 'Pie';
  const total = chartData?.datasets?.[0]?.data?.reduce((a: number, b: number) => a + b, 0) ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Select
          style={{ width: 320 }}
          value={selectedType}
          onChange={setSelectedType}
          options={[
            { label: '— Pie Charts —', value: '', disabled: true },
            ...CHART_OPTIONS.filter(o => o.category === 'Pie').map(o => ({ value: o.value, label: o.label })),
            { label: '— Bar Charts —', value: '', disabled: true },
            ...CHART_OPTIONS.filter(o => o.category === 'Bar').map(o => ({ value: o.value, label: o.label })),
          ]}
        />
        {selectedOption && (
          <Tag color={isPie ? 'blue' : 'geekblue'}>{selectedOption.category}</Tag>
        )}
        {chartData && (
          <Statistic
            title="Data Points"
            value={chartData.labels.length}
            suffix={isPie ? 'categories' : 'items'}
            valueStyle={{ fontSize: 14 }}
          />
        )}
      </div>

      <div style={{ flex: 1, overflow: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {loading ? (
          <Spin size="large" tip="Loading chart data..." />
        ) : error ? (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>{isPie ? '🥧' : '📊'}</div>
            <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>{error}</div>
            <div style={{ fontSize: 13 }}>
              This chart will display once relevant data is available in the system.
            </div>
          </div>
        ) : chartData ? (
          <Row gutter={24} style={{ width: '100%', maxWidth: 900 }}>
            <Col xs={24} md={isPie ? 14 : 24}>
              <Card style={{ minHeight: 400 }}>
                <div style={{ height: isPie ? 380 : 350 }}>
                  {isPie ? (
                    <Pie
                      data={{
                        labels: chartData.labels,
                        datasets: chartData.datasets.map(ds => ({
                          ...ds,
                          backgroundColor: Array.isArray(ds.backgroundColor)
                            ? ds.backgroundColor
                            : [ds.backgroundColor],
                        })),
                      }}
                      options={{
                        ...PIE_OPTIONS,
                        plugins: {
                          ...PIE_OPTIONS.plugins,
                          title: { ...PIE_OPTIONS.plugins.title, text: chartData.title },
                        },
                      }}
                    />
                  ) : (
                    <Bar
                      data={{
                        labels: chartData.labels,
                        datasets: chartData.datasets.map(ds => ({
                          ...ds,
                          backgroundColor: Array.isArray(ds.backgroundColor)
                            ? ds.backgroundColor
                            : [ds.backgroundColor],
                        })),
                      }}
                      options={{
                        ...BAR_OPTIONS,
                        plugins: {
                          ...BAR_OPTIONS.plugins,
                          title: { ...BAR_OPTIONS.plugins.title, text: chartData.title },
                        },
                      }}
                    />
                  )}
                </div>
              </Card>
            </Col>
            {isPie && (
              <Col xs={24} md={10}>
                <Card title="Data Breakdown" size="small">
                  <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid #f0f0f0' }}>
                        <th style={{ textAlign: 'left', padding: '6px 8px' }}>Category</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px' }}>Value</th>
                        <th style={{ textAlign: 'right', padding: '6px 8px' }}>Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {chartData.labels.map((label, i) => {
                        const val = chartData.datasets[0]?.data?.[i] ?? 0;
                        const colors = chartData.datasets[0]?.backgroundColor;
                        const color = Array.isArray(colors) ? colors[i] : '#999';
                        const pct = total > 0 ? ((val / total) * 100).toFixed(1) : '0.0';
                        return (
                          <tr key={i} style={{ borderBottom: '1px solid #f5f5f5' }}>
                            <td style={{ padding: '4px 8px' }}>
                              <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: color as string, marginRight: 8 }} />
                              {label}
                            </td>
                            <td style={{ textAlign: 'right', padding: '4px 8px', fontWeight: 600 }}>{val}</td>
                            <td style={{ textAlign: 'right', padding: '4px 8px', color: '#666' }}>{pct}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </Card>
              </Col>
            )}
          </Row>
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>📊</div>
            <div>Select a chart type to preview</div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChartEditor;
