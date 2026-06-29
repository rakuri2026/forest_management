import React, { useState, useEffect } from 'react';
import { Card, Input, Tag, Typography, Space, Spin, Empty, Row, Col, Button, message, Modal, Descriptions, Collapse, Select, List, Alert } from 'antd';
import { SearchOutlined, FileTextOutlined, EyeOutlined, TagsOutlined, AppstoreOutlined, CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { operationalPlanApi, forestApi } from '../services/api';

const { Text, Title } = Typography;
const { Panel } = Collapse;

interface PublicTemplate {
  id: string;
  name: string;
  description: string;
  tags: string[];
  sections_summary: string[];
  variables_summary: string[];
  created_by?: string | null;
  updated_at: string;
  template_category?: string | null;
}

interface Calculation {
  id: string;
  forest_name?: string;
  status: string;
  created_at: string;
}

const CATEGORIES = [
  { value: '', label: 'All Categories' },
  { value: 'normal_forest', label: 'Normal Forest' },
  { value: 'leasehold', label: 'Leasehold Forest' },
  { value: 'religious_forest', label: 'Religious Forest' },
  { value: 'community_forest', label: 'Community Forest' },
  { value: 'collaborative_forest', label: 'Collaborative Forest' },
];

const PublicTemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<PublicTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeTag, setActiveTag] = useState<string | undefined>(undefined);
  const [category, setCategory] = useState<string>('');
  const [allTags, setAllTags] = useState<string[]>([]);
  const [detailTemplate, setDetailTemplate] = useState<PublicTemplate | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [calcModalOpen, setCalcModalOpen] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<PublicTemplate | null>(null);
  const [calculations, setCalculations] = useState<Calculation[]>([]);
  const [loadingCalcs, setLoadingCalcs] = useState(false);
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTemplates();
  }, [activeTag, category]);

  const fetchTemplates = async (searchTerm?: string) => {
    setLoading(true);
    try {
      const res = await operationalPlanApi.listPublicTemplates(activeTag, searchTerm || search || undefined);
      const items = res.templates || [];
      if (category) {
        const filtered = items.filter((t: any) => t.tags?.includes(category));
        setTemplates(filtered);
      } else {
        setTemplates(items);
      }
      const tags = new Set<string>();
      items.forEach((t: PublicTemplate) => (t.tags || []).forEach((tag: string) => tags.add(tag)));
      setAllTags(Array.from(tags).sort());
    } catch {
      message.error('Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    fetchTemplates(search);
  };

  const handleUseTemplate = async (tmpl: PublicTemplate) => {
    setSelectedTemplate(tmpl);
    setLoadingCalcs(true);
    setCalcModalOpen(true);
    try {
      const calcs = await forestApi.listCalculations();
      const completed = calcs.filter((c: Calculation) => c.status === 'completed' || c.status === 'processing');
      setCalculations(completed);
    } catch {
      message.error('Failed to load forests');
      setCalculations([]);
    } finally {
      setLoadingCalcs(false);
    }
  };

  const handleCreatePlan = async (calcId: string) => {
    if (!selectedTemplate) return;
    setCreating(true);
    try {
      const plan = await operationalPlanApi.create(calcId, undefined, selectedTemplate.id);
      setCalcModalOpen(false);
      setCreating(false);
      message.success('Operational plan created from template');
      navigate(`/calculations/${calcId}/operational-plan`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to create plan');
      setCreating(false);
    }
  };

  const handleShowDetail = (tmpl: PublicTemplate) => {
    setDetailTemplate(tmpl);
    setDetailOpen(true);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3}><FileTextOutlined /> Template Gallery</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Choose a template for your Operational Plan. Select one and then choose which forest to apply it to.
      </Text>

      <Space style={{ marginBottom: 16, width: '100%' }} direction="vertical">
        <Space wrap>
          <Input
            placeholder="Search templates..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 250 }}
            allowClear
          />
          <Button type="primary" onClick={handleSearch} icon={<SearchOutlined />}>Search</Button>
          <Select
            value={category}
            onChange={(val) => setCategory(val)}
            style={{ width: 200 }}
            options={CATEGORIES}
            placeholder="Filter by category"
          />
        </Space>

        {allTags.length > 0 && (
          <Space wrap>
            <TagsOutlined />
            <Tag
              color={!activeTag ? 'blue' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => setActiveTag(undefined)}
            >
              All
            </Tag>
            {allTags.map(tag => (
              <Tag
                key={tag}
                color={activeTag === tag ? 'blue' : 'default'}
                style={{ cursor: 'pointer' }}
                onClick={() => setActiveTag(tag)}
              >
                {tag}
              </Tag>
            ))}
          </Space>
        )}
      </Space>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
      ) : templates.length === 0 ? (
        <Empty description="No templates found. Check back later or adjust your filters." />
      ) : (
        <Row gutter={[16, 16]}>
          {templates.map(tmpl => (
            <Col key={tmpl.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                actions={[
                  <Button key="use" type="primary" size="small" onClick={() => handleUseTemplate(tmpl)}>
                    Use Template
                  </Button>,
                  <Button key="detail" type="link" size="small" icon={<EyeOutlined />} onClick={() => handleShowDetail(tmpl)}>
                    Details
                  </Button>,
                ]}
              >
                <Card.Meta
                  title={
                    <Space wrap>
                      <Text strong ellipsis style={{ maxWidth: 160 }}>{tmpl.name}</Text>
                    </Space>
                  }
                  description={
                    <div>
                      <Text type="secondary" style={{ fontSize: 12, display: 'block' }} ellipsis>
                        {tmpl.description || 'No description'}
                      </Text>
                      {tmpl.template_category && (
                        <Tag color="purple" style={{ fontSize: 10, marginTop: 4 }}>
                          {CATEGORIES.find(c => c.value === tmpl.template_category)?.label || tmpl.template_category}
                        </Tag>
                      )}
                      {tmpl.tags?.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          {tmpl.tags.slice(0, 3).map(t => <Tag key={t} style={{ fontSize: 10, marginBottom: 2 }}>{t}</Tag>)}
                        </div>
                      )}
                      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
                        {(tmpl.sections_summary?.length || 0)} sections &middot; {(tmpl.variables_summary?.length || 0)} variables
                      </Text>
                      <Text type="secondary" style={{ fontSize: 10 }}>
                        Updated: {new Date(tmpl.updated_at).toLocaleDateString()}
                      </Text>
                    </div>
                  }
                />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="Template Detail"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={[
          <Button key="close" onClick={() => setDetailOpen(false)}>Close</Button>,
          detailTemplate && (
            <Button key="use" type="primary" onClick={() => { setDetailOpen(false); handleUseTemplate(detailTemplate); }}>
              Use This Template
            </Button>
          ),
        ]}
        width={640}
      >
        {detailTemplate && (
          <div>
            <Title level={4}>{detailTemplate.name}</Title>
            <Text style={{ display: 'block', marginBottom: 12 }}>{detailTemplate.description || 'No description'}</Text>
            <Space wrap style={{ marginBottom: 12 }}>
              {detailTemplate.template_category && (
                <Tag color="purple">{CATEGORIES.find(c => c.value === detailTemplate.template_category)?.label}</Tag>
              )}
              {detailTemplate.tags?.map(t => <Tag key={t}>{t}</Tag>)}
            </Space>
            <Collapse ghost>
              <Panel header={`Sections (${detailTemplate.sections_summary?.length || 0})`} key="sections">
                {detailTemplate.sections_summary?.length > 0 ? (
                  <ol style={{ fontSize: 13, maxHeight: 250, overflow: 'auto' }}>
                    {detailTemplate.sections_summary.map((s, i) => <li key={i}>{s}</li>)}
                  </ol>
                ) : <Text type="secondary">No sections recorded</Text>}
              </Panel>
              <Panel header={`Variables used (${detailTemplate.variables_summary?.length || 0})`} key="vars">
                {detailTemplate.variables_summary?.length > 0 ? (
                  <ul style={{ fontSize: 13, maxHeight: 250, overflow: 'auto' }}>
                    {detailTemplate.variables_summary.map((v, i) => <li key={i}>{v}</li>)}
                  </ul>
                ) : <Text type="secondary">No variables used</Text>}
              </Panel>
            </Collapse>
          </div>
        )}
      </Modal>

      <Modal
        title="Select Forest"
        open={calcModalOpen}
        onCancel={() => { if (!creating) setCalcModalOpen(false); }}
        footer={null}
        width={520}
      >
        {loadingCalcs ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : calculations.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Empty description="No completed forests found. Upload a CSV file first to create a forest." />
            <Button type="primary" onClick={() => navigate('/my-uploads')} style={{ marginTop: 12 }}>
              Go to My Uploads
            </Button>
          </div>
        ) : (
          <>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              Choose which forest to apply "<strong>{selectedTemplate?.name}</strong>" to:
            </Text>
            <List
              dataSource={calculations}
              loading={creating}
              renderItem={(calc) => (
                <List.Item
                  actions={[
                    <Button
                      key="select"
                      type="primary"
                      size="small"
                      onClick={() => handleCreatePlan(calc.id)}
                      loading={creating}
                      icon={<CheckCircleOutlined />}
                    >
                      Select
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={calc.forest_name || 'Unnamed Forest'}
                    description={
                      <span>
                        Status: <Tag color={calc.status === 'completed' ? 'green' : 'orange'}>{calc.status}</Tag>
                        &nbsp; Created: {new Date(calc.created_at).toLocaleDateString()}
                      </span>
                    }
                  />
                </List.Item>
              )}
            />
          </>
        )}
      </Modal>
    </div>
  );
};

export default PublicTemplatesPage;