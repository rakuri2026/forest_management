import React, { useState, useEffect } from 'react';
import { Input, Tabs, List, Tag, Spin, Empty, Tooltip, Badge, Space } from 'antd';
import { SearchOutlined, CheckCircleOutlined, CloseCircleOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import { operationalPlanApi } from '../../services/api';

interface CatalogVariable {
  key: string;
  category: string;
  label_ne: string;
  label_en: string;
  var_type: string;
  source: string;
  auto_populate: boolean;
  data_status: string;
  sample_value: any;
}

interface VariablePickerProps {
  onSelect: (variableKey: string) => void;
  usedVariables?: string[];
  calculationId?: string;
}

const CATEGORY_TABS = [
  { key: '', label: 'All' },
  { key: 'A', label: 'A: System' },
  { key: 'B', label: 'B: Hybrid' },
  { key: 'C', label: 'C: User Input' },
  { key: 'D', label: 'D: Computed' },
  { key: 'E', label: 'E: Section' },
  { key: 'F', label: 'F: Template' },
  { key: '_charts', label: 'Charts' },
  { key: '_maps', label: 'Maps' },
];

const CHART_MAP_TABS = new Set(['_charts', '_maps']);

const typeColors: Record<string, string> = {
  string: 'blue',
  number: 'green',
  boolean: 'orange',
  dict: 'purple',
  list: 'cyan',
};

const VariablePicker: React.FC<VariablePickerProps> = ({ onSelect, usedVariables = [], calculationId }) => {
  const [variables, setVariables] = useState<CatalogVariable[]>([]);
  const [filtered, setFiltered] = useState<CatalogVariable[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');

  useEffect(() => {
    loadVariables();
  }, [category]);

  useEffect(() => {
    filterVariables();
  }, [search, variables, category]);

  const loadVariables = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (category && !CHART_MAP_TABS.has(category)) {
        params.category = category;
      }
      let data;
      if (calculationId) {
        data = await operationalPlanApi.getVariableCatalog(calculationId, params);
      } else {
        const basicData = await operationalPlanApi.listVariables(params);
        data = {
          total: (basicData.variables || []).length,
          variables: (basicData.variables || []).map((v: any) => ({
            ...v,
            data_status: 'unknown',
            sample_value: null,
          })),
        };
      }
      setVariables(data.variables || []);
    } catch {
      setVariables([]);
    } finally {
      setLoading(false);
    }
  };

  const filterVariables = () => {
    let result = variables;

    if (category === '_charts') {
      result = result.filter(v => v.key.startsWith('chart:'));
    } else if (category === '_maps') {
      result = result.filter(v => v.key.startsWith('map:'));
    }

    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        v => v.key.toLowerCase().includes(q)
          || v.label_ne.toLowerCase().includes(q)
          || v.label_en.toLowerCase().includes(q)
      );
    }

    setFiltered(result);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'available': return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 12 }} />;
      case 'empty': return <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 12 }} />;
      default: return <QuestionCircleOutlined style={{ color: '#d9d9d9', fontSize: 12 }} />;
    }
  };

  const availableCount = variables.filter(v => v.data_status === 'available').length;
  const totalCount = variables.length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>Variable Picker</span>
        <Badge count={`${availableCount}/${totalCount}`} style={{ backgroundColor: '#52c41a', fontSize: 10 }} />
      </div>
      <div style={{ padding: '8px 12px' }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Search variables..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          allowClear
          size="small"
        />
      </div>
      <Tabs
        size="small"
        activeKey={category}
        onChange={setCategory}
        items={CATEGORY_TABS.map(t => ({ key: t.key, label: t.label }))}
        style={{ padding: '0 12px' }}
        tabBarStyle={{ marginBottom: 0 }}
      />
      <div style={{ flex: 1, overflow: 'auto', padding: '0 12px 12px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 20 }}><Spin /></div>
        ) : filtered.length === 0 ? (
          <Empty description="No variables found" />
        ) : (
          <List
            size="small"
            dataSource={filtered}
            renderItem={(v) => (
              <List.Item
                onClick={() => onSelect(v.key)}
                style={{
                  cursor: 'pointer', padding: '6px 8px', borderRadius: 4,
                  background: usedVariables.includes(v.key) ? '#f6ffed' : 'transparent',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = usedVariables.includes(v.key) ? '#d9f7be' : '#f5f5f5'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = usedVariables.includes(v.key) ? '#f6ffed' : 'transparent'; }}
              >
                <Tooltip
                  title={
                    <div style={{ maxWidth: 300 }}>
                      <div><strong>{v.key}</strong> <Tag color={typeColors[v.var_type]}>{v.var_type}</Tag></div>
                      <div style={{ fontSize: 11, margin: '4px 0' }}>{v.label_ne} / {v.label_en}</div>
                      <div style={{ fontSize: 11 }}>Source: {v.source}</div>
                      <div style={{ fontSize: 11 }}>Auto-populate: {v.auto_populate ? 'Yes' : 'No'}</div>
                      <div style={{ fontSize: 11 }}>Status: {v.data_status}</div>
                      {v.sample_value !== null && v.sample_value !== undefined && (
                        <div style={{ fontSize: 11, marginTop: 4, background: '#1a1a1a', padding: '4px 6px', borderRadius: 3, color: '#a0d8a0', wordBreak: 'break-all' }}>
                          <strong>Sample:</strong> {String(v.sample_value)}
                        </div>
                      )}
                    </div>
                  }
                  placement="right"
                  overlayStyle={{ fontSize: 12 }}
                >
                  <div style={{ width: '100%' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        {usedVariables.includes(v.key) && <span style={{ color: '#52c41a', fontSize: 12 }}>✓</span>}
                        {getStatusIcon(v.data_status)}
                        <code style={{ fontSize: 12, fontWeight: 600 }}>{v.key}</code>
                      </div>
                      <Tag color={typeColors[v.var_type] || 'default'} style={{ fontSize: 10, lineHeight: '16px' }}>
                        {v.var_type}
                      </Tag>
                    </div>
                    <div style={{ fontSize: 12, color: '#666' }}>
                      {v.label_ne} / {v.label_en}
                    </div>
                  </div>
                </Tooltip>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );
};

export default VariablePicker;