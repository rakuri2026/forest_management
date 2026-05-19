import React, { useState, useEffect } from 'react';
import { Input, Tabs, List, Tag, Spin, Empty } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { operationalPlanApi } from '../../services/api';

interface VariableDef {
  key: string;
  category: string;
  label_ne: string;
  label_en: string;
  var_type: string;
  source: string;
  auto_populate: boolean;
  description: string;
}

interface VariablePickerProps {
  onSelect: (variableKey: string) => void;
  usedVariables?: string[];
}

const CATEGORY_TABS = [
  { key: '', label: 'All' },
  { key: 'A', label: 'A: System' },
  { key: 'B', label: 'B: Hybrid' },
  { key: 'C', label: 'C: User Input' },
  { key: 'D', label: 'D: Computed' },
  { key: 'E', label: 'E: Section' },
  { key: 'F', label: 'F: Template' },
  { key: '_charts', label: '📊 Charts' },
  { key: '_maps', label: '🗺️ Maps' },
];

const CHART_MAP_TABS = new Set(['_charts', '_maps']);

const typeColors: Record<string, string> = {
  string: 'blue',
  number: 'green',
  boolean: 'orange',
  dict: 'purple',
  list: 'cyan',
};

const VariablePicker: React.FC<VariablePickerProps> = ({ onSelect, usedVariables = [] }) => {
  const [variables, setVariables] = useState<VariableDef[]>([]);
  const [filtered, setFiltered] = useState<VariableDef[]>([]);
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
      const data = await operationalPlanApi.listVariables(params);
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

  const handleSearch = (val: string) => {
    setSearch(val);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 14 }}>
        Variable Picker
      </div>
      <div style={{ padding: '8px 12px' }}>
        <Input
          prefix={<SearchOutlined />}
          placeholder="Search variables..."
          value={search}
          onChange={e => handleSearch(e.target.value)}
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
                <div style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      {usedVariables.includes(v.key) && <span style={{ color: '#52c41a', fontSize: 12 }}>✓</span>}
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
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );
};

export default VariablePicker;
