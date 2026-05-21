import React, { useState, useEffect } from 'react';
import { Card, Input, Tag, Typography, Space, Spin, Empty, Row, Col, Button, message, Modal, Descriptions, Collapse } from 'antd';
import { SearchOutlined, FileTextOutlined, EyeOutlined, TagsOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { operationalPlanApi } from '../services/api';

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
}

const PublicTemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<PublicTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeTag, setActiveTag] = useState<string | undefined>(undefined);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [detailTemplate, setDetailTemplate] = useState<PublicTemplate | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTemplates();
  }, [activeTag]);

  const fetchTemplates = async (searchTerm?: string) => {
    setLoading(true);
    try {
      const res = await operationalPlanApi.listPublicTemplates(activeTag, searchTerm || search || undefined);
      const items = res.templates || [];
      setTemplates(items);
      const tags = new Set<string>();
      items.forEach((t: PublicTemplate) => (t.tags || []).forEach((tag: string) => tags.add(tag)));
      setAllTags(Array.from(tags).sort());
    } catch {
      message.error('Failed to load public templates');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    fetchTemplates(search);
  };

  const handleUseTemplate = (tmpl: PublicTemplate) => {
    navigate(`/calculations/0/operational-plan?template_id=${tmpl.id}`);
  };

  const handleShowDetail = (tmpl: PublicTemplate) => {
    setDetailTemplate(tmpl);
    setDetailOpen(true);
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <Title level={3}><FileTextOutlined /> Public Templates</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Browse shared and approved templates from the community. Use them as starting points for your operational plans.
      </Text>

      <Space style={{ marginBottom: 16, width: '100%' }} direction="vertical">
        <Space>
          <Input
            placeholder="Search templates..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 300 }}
            allowClear
          />
          <Button type="primary" onClick={handleSearch} icon={<SearchOutlined />}>Search</Button>
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
        <Empty description="No public templates found. Check back later or adjust your filters." />
      ) : (
        <Row gutter={[16, 16]}>
          {templates.map(tmpl => (
            <Col key={tmpl.id} xs={24} sm={12} md={8} lg={6}>
              <Card
                hoverable
                actions={[
                  <Button key="use" type="link" size="small" onClick={() => handleUseTemplate(tmpl)}>
                    Use Template
                  </Button>,
                  <Button key="detail" type="link" size="small" icon={<EyeOutlined />} onClick={() => handleShowDetail(tmpl)}>
                    Details
                  </Button>,
                ]}
              >
                <Card.Meta
                  title={<Text strong ellipsis>{tmpl.name}</Text>}
                  description={
                    <div>
                      <Text type="secondary" style={{ fontSize: 12, display: 'block' }} ellipsis>
                        {tmpl.description || 'No description'}
                      </Text>
                      {tmpl.tags?.length > 0 && (
                        <div style={{ marginTop: 6 }}>
                          {tmpl.tags.map(t => <Tag key={t} style={{ fontSize: 10, marginBottom: 2 }}>{t}</Tag>)}
                        </div>
                      )}
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {(tmpl.sections_summary?.length || 0)} sections &middot; {(tmpl.variables_summary?.length || 0)} variables
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
    </div>
  );
};

export default PublicTemplatesPage;
