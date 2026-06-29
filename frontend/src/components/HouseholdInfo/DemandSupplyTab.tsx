import React, { useState, useEffect } from 'react';
import { Table, Card, Alert, Spin, Typography, Divider } from 'antd';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from 'recharts';
import { userGroupApi } from '../../services/api';
import { toNepaliDigit } from '../../constants/nepaliLabels';
import type { DemandSupplyResponse } from '../../types/demand_supply';
import HouseholdVariablePanel from './HouseholdVariablePanel';

const { Paragraph } = Typography;

interface DemandSupplyTabProps {
  calculationId: string;
}

const PRODUCT_LABELS: Record<string, string> = {
  firewood_bhari: 'दाउरा भारी',
  grass_bhari: 'घाँस भारी',
  bedding_bhari: 'सोतर भारी',
  timber_cft: 'काठ क्यू.फि.',
  poles_count: 'खाँवा संख्या',
};

const np = (v: any, d = 2) => {
  if (v === '-' || v === null || v === undefined) return '-';
  return toNepaliDigit(Number(v), d);
};

const DemandSupplyTab: React.FC<DemandSupplyTabProps> = ({ calculationId }) => {
  const [data, setData] = useState<DemandSupplyResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const result = await userGroupApi.getDemandSupply(calculationId);
        setData(result);
      } catch (err) {
        console.error('Failed to load demand-supply:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [calculationId]);

  const tableData = data
    ? Object.keys(PRODUCT_LABELS).map((key) => ({
        key,
        product: PRODUCT_LABELS[key],
        demand: np(data.demand[key]),
        cf_regular: np(data.supply_cf_regular[key]),
        cf_aah: np(data.supply_cf_aah[key]),
        private: np(data.supply_private[key]),
        total_supply: np(data.total_supply[key]),
        deficit: data.deficit[key],
        deficit_display: data.deficit[key] === '-' || data.deficit[key] === null || data.deficit[key] === undefined
          ? '-' : toNepaliDigit(Math.abs(Number(data.deficit[key])), 2),
        deficit_sign: data.deficit[key] === '-' || data.deficit[key] === null || data.deficit[key] === undefined
          ? '' : Number(data.deficit[key]) >= 0 ? 'बचत' : 'कमी',
      }))
    : [];

  const chartData = data
    ? Object.keys(PRODUCT_LABELS).map((key) => ({
        name: PRODUCT_LABELS[key],
        माग: data.demand[key] ?? 0,
        आपूर्ति: data.total_supply[key] ?? 0,
      }))
    : [];

  return (
    <Spin spinning={loading}>
      {data?.nepali_description && (
        <Card style={{ marginBottom: 16 }}>
          <Paragraph style={{ fontSize: 16, lineHeight: 1.8 }}>
            {data.nepali_description.replace(/\d/g, d => '०१२३४५६७८९'[parseInt(d)])}
          </Paragraph>
        </Card>
      )}

      <Card title="माग र आपूर्तिको अवस्था" style={{ marginBottom: 16 }}>
        <Table
          dataSource={tableData}
          columns={[
            { title: 'उत्पादन किसिम', dataIndex: 'product', key: 'product', width: 140 },
            { title: 'माग', dataIndex: 'demand', key: 'demand', align: 'right' },
            { title: 'झिँजा दाउरा तथा घाँस संकलन', dataIndex: 'cf_regular', key: 'cf_regular', align: 'right' },
            { title: 'वार्षिक संकलन परिमाण', dataIndex: 'cf_aah', key: 'cf_aah', align: 'right' },
            { title: 'निजि क्षेत्रबाट उत्पादन', dataIndex: 'private', key: 'private', align: 'right' },
            { title: 'जम्मा आपूर्ति', dataIndex: 'total_supply', key: 'total_supply', align: 'right', render: (v: any) => <strong>{v}</strong> },
            { title: 'बचत तथा कमी', dataIndex: 'deficit', key: 'deficit', align: 'right', render: (_: any, record: any) => {
              if (record.deficit === '-' || record.deficit === null) return '-';
              return (
                <span style={{ color: Number(record.deficit) >= 0 ? '#059669' : '#dc2626', fontWeight: 600 }}>
                  {record.deficit_sign} {record.deficit_display}
                </span>
              );
            }},
          ]}
          pagination={false}
          bordered
          size="middle"
        />
      </Card>

      {chartData.length > 0 && (
        <Card title="माग र आपूर्ति तुलना">
          <ResponsiveContainer width="100%" height={350}>
            <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => toNepaliDigit(v, 0)} />
              <Tooltip formatter={(v: number) => toNepaliDigit(v, 2)} />
              <Legend />
              <Bar dataKey="माग" fill="#dc2626" radius={[4, 4, 0, 0]} />
              <Bar dataKey="आपूर्ति" fill="#059669" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {!data && !loading && (
        <Alert message="माग र आपूर्ति डाटा उपलब्ध छैन" type="info" showIcon />
      )}

      {calculationId && (
        <div style={{ marginTop: 24 }}>
          <Divider>माग/आपूर्ति चरहरू</Divider>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 60%', minWidth: 300 }}>
              <div style={{
                border: '1px solid #d9d9d9',
                borderRadius: 6,
                padding: 12,
                background: '#fafafa',
              }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: 13 }}>
                  अतिरिक्त विवरण / नोट (Additional Notes)
                </h4>
                <textarea
                  id="demand-notes"
                  rows={4}
                  style={{
                    width: '100%',
                    border: '1px solid #d9d9d9',
                    borderRadius: 4,
                    padding: '8px 12px',
                    fontSize: 13,
                    lineHeight: 1.6,
                    fontFamily: 'inherit',
                    resize: 'vertical',
                  }}
                  placeholder="चर सम्मिलित गर्न दायाँ प्यानलको 'सम्मिलित' बटन प्रयोग गर्नुहोस्।"
                />
              </div>
            </div>
            <div style={{ flex: '0 0 340px' }}>
              <HouseholdVariablePanel
                calculationId={calculationId}
                tabKey="demand"
                onInsert={(varStr) => {
                  const ta = document.getElementById('demand-notes') as HTMLTextAreaElement;
                  if (ta) {
                    const start = ta.selectionStart;
                    const end = ta.selectionEnd;
                    ta.value = ta.value.substring(0, start) + varStr + ta.value.substring(end);
                    ta.focus();
                    ta.selectionStart = ta.selectionEnd = start + varStr.length;
                  }
                }}
              />
            </div>
          </div>
        </div>
      )}
    </Spin>
  );
};

export default DemandSupplyTab;
