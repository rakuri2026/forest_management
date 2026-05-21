import React, { useState, useEffect } from 'react';
import { Modal, List, Button, Input, Form, message, Popconfirm, Tag, Typography, Space, Empty, Spin, Select, Tooltip, Collapse } from 'antd';
import {
  SaveOutlined,
  DeleteOutlined,
  FileTextOutlined,
  StarOutlined,
  StarFilled,
  PlusOutlined,
  SendOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { operationalPlanApi } from '../../services/api';

const { TextArea } = Input;
const { Text } = Typography;
const { Panel } = Collapse;

interface TemplateData {
  id: string;
  name: string;
  description: string;
  is_system: boolean;
  is_default: boolean;
  visibility: string;
  approval_status: string;
  approval_note?: string;
  tags: string[];
  sections_summary: string[];
  variables_summary: string[];
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

interface TemplateManagerProps {
  planId: string | null;
  tree: any[];
  visible: boolean;
  onClose: () => void;
  onLoadTemplate: (templateId: string) => void;
}

const VISIBILITY_LABELS: Record<string, { label: string; color: string }> = {
  private: { label: 'Private', color: 'default' },
  shared: { label: 'Shared', color: 'blue' },
  global: { label: 'Global', color: 'green' },
};

const APPROVAL_LABELS: Record<string, { label: string; color: string }> = {
  none: { label: '—', color: 'default' },
  pending: { label: 'Pending', color: 'orange' },
  approved: { label: 'Approved', color: 'green' },
  rejected: { label: 'Rejected', color: 'red' },
};

const TemplateManager: React.FC<TemplateManagerProps> = ({
  planId,
  tree,
  visible,
  onClose,
  onLoadTemplate,
}) => {
  const [templates, setTemplates] = useState<TemplateData[]>([]);
  const [loading, setLoading] = useState(false);
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [saveDesc, setSaveDesc] = useState('');
  const [saveVisibility, setSaveVisibility] = useState('private');
  const [saveTags, setSaveTags] = useState('');
  const [saveAsDefault, setSaveAsDefault] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateData | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  useEffect(() => {
    if (visible) fetchTemplates();
  }, [visible]);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const res = await operationalPlanApi.listTemplates('all');
      setTemplates(res.templates || []);
    } catch {
      message.error('Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    try {
      await operationalPlanApi.deleteTemplate(id);
      message.success('Template deleted');
      fetchTemplates();
    } catch {
      message.error('Failed to delete template');
    }
  };

  const handleSaveTemplate = async () => {
    if (!saveName.trim()) {
      message.warning('Please enter a template name');
      return;
    }
    if (!planId || !tree.length) {
      message.warning('No document tree to save');
      return;
    }
    setSaving(true);
    try {
      const tags = saveTags.split(',').map(t => t.trim()).filter(Boolean);
      await operationalPlanApi.savePlanAsTemplate(planId, {
        name: saveName.trim(),
        description: saveDesc.trim(),
        tree,
        is_default: saveAsDefault,
        visibility: saveVisibility,
        tags,
      });
      message.success('Template saved successfully');
      setSaveModalOpen(false);
      setSaveName('');
      setSaveDesc('');
      setSaveTags('');
      setSaveVisibility('private');
      setSaveAsDefault(false);
      fetchTemplates();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const handleUseTemplate = (tmpl: TemplateData) => {
    onLoadTemplate(tmpl.id);
    onClose();
  };

  const handleShowDetail = async (tmpl: TemplateData) => {
    try {
      const full = await operationalPlanApi.getTemplate(tmpl.id);
      setSelectedTemplate(full);
    } catch {
      setSelectedTemplate(tmpl);
    }
    setDetailOpen(true);
  };

  const handleSubmitForApproval = async (tmpl: TemplateData) => {
    try {
      await operationalPlanApi.submitTemplateForApproval(tmpl.id);
      message.success('Template submitted for approval');
      fetchTemplates();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to submit');
    }
  };

  return (
    <>
      <Modal
        title={<span><FileTextOutlined /> Template Manager</span>}
        open={visible}
        onCancel={onClose}
        footer={null}
        width={720}
      >
        <div style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={() => setSaveModalOpen(true)}
            disabled={!planId || !tree.length}
          >
            Save Current Plan as Template
          </Button>
          <Button icon={<PlusOutlined />} onClick={fetchTemplates} loading={loading}>
            Refresh
          </Button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : templates.length === 0 ? (
          <Empty description="No templates yet. Save your current plan as a template." />
        ) : (
          <List
            dataSource={templates}
            renderItem={(tmpl) => (
              <List.Item
                actions={[
                  <Button key="use" size="small" type="link" onClick={() => handleUseTemplate(tmpl)}>
                    Use Template
                  </Button>,
                  <Tooltip key="detail" title="View details">
                    <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => handleShowDetail(tmpl)} />
                  </Tooltip>,
                  tmpl.visibility === 'private' && tmpl.approval_status === 'none' && !tmpl.is_system ? (
                    <Tooltip key="submit" title="Submit for global approval">
                      <Button size="small" type="link" icon={<SendOutlined />} onClick={() => handleSubmitForApproval(tmpl)} />
                    </Tooltip>
                  ) : null,
                  !tmpl.is_system && (
                    <Popconfirm key="del" title="Delete this template?" onConfirm={() => handleDeleteTemplate(tmpl.id)}>
                      <Button size="small" danger type="link" icon={<DeleteOutlined />} />
                    </Popconfirm>
                  ),
                ].filter(Boolean)}
              >
                <List.Item.Meta
                  avatar={
                    tmpl.is_system ? <StarFilled style={{ color: '#faad14', fontSize: 20 }} /> :
                    tmpl.is_default ? <StarOutlined style={{ color: '#1890ff', fontSize: 20 }} /> :
                    <FileTextOutlined style={{ fontSize: 20, color: '#999' }} />
                  }
                  title={
                    <Space wrap>
                      <Text strong>{tmpl.name}</Text>
                      {tmpl.is_system && <Tag color="gold" style={{ fontSize: 11 }}>System</Tag>}
                      {tmpl.is_default && <Tag color="blue" style={{ fontSize: 11 }}>Default</Tag>}
                      <Tag color={VISIBILITY_LABELS[tmpl.visibility]?.color || 'default'} style={{ fontSize: 11 }}>
                        {VISIBILITY_LABELS[tmpl.visibility]?.label || tmpl.visibility}
                      </Tag>
                      {tmpl.approval_status !== 'none' && (
                        <Tag color={APPROVAL_LABELS[tmpl.approval_status]?.color || 'default'} style={{ fontSize: 11 }}>
                          {APPROVAL_LABELS[tmpl.approval_status]?.label || tmpl.approval_status}
                        </Tag>
                      )}
                    </Space>
                  }
                  description={
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>{tmpl.description || 'No description'}</Text>
                      {tmpl.tags?.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          {tmpl.tags.map(t => <Tag key={t} style={{ fontSize: 10 }}>{t}</Tag>)}
                        </div>
                      )}
                      <div style={{ marginTop: 2 }}>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          Updated: {new Date(tmpl.updated_at).toLocaleDateString()}
                          {tmpl.approval_status === 'rejected' && tmpl.approval_note && (
                            <> &middot; Note: {tmpl.approval_note}</>
                          )}
                        </Text>
                      </div>
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Modal>

      <Modal
        title="Template Detail"
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={640}
      >
        {selectedTemplate && (
          <div>
            <h3>{selectedTemplate.name}</h3>
            <p style={{ color: '#666' }}>{selectedTemplate.description || 'No description'}</p>
            <Space wrap style={{ marginBottom: 12 }}>
              <Tag color={VISIBILITY_LABELS[selectedTemplate.visibility]?.color}>{selectedTemplate.visibility}</Tag>
              {selectedTemplate.tags?.map(t => <Tag key={t}>{t}</Tag>)}
            </Space>

            <Collapse ghost>
              <Panel header={`Sections (${selectedTemplate.sections_summary?.length || 0})`} key="sections">
                {selectedTemplate.sections_summary?.length > 0 ? (
                  <ol style={{ fontSize: 12, maxHeight: 200, overflow: 'auto' }}>
                    {selectedTemplate.sections_summary.map((s, i) => <li key={i}>{s}</li>)}
                  </ol>
                ) : <Text type="secondary">No sections recorded</Text>}
              </Panel>
              <Panel header={`Variables used (${selectedTemplate.variables_summary?.length || 0})`} key="vars">
                {selectedTemplate.variables_summary?.length > 0 ? (
                  <ul style={{ fontSize: 12, maxHeight: 200, overflow: 'auto' }}>
                    {selectedTemplate.variables_summary.map((v, i) => <li key={i}>{v}</li>)}
                  </ul>
                ) : <Text type="secondary">No variables used</Text>}
              </Panel>
            </Collapse>
          </div>
        )}
      </Modal>

      <Modal
        title="Save as Template"
        open={saveModalOpen}
        onCancel={() => setSaveModalOpen(false)}
        onOk={handleSaveTemplate}
        confirmLoading={saving}
        okText="Save Template"
        width={480}
      >
        <Form layout="vertical">
          <Form.Item label="Template Name" required>
            <Input value={saveName} onChange={(e) => setSaveName(e.target.value)} placeholder="e.g. My Custom OP Template" />
          </Form.Item>
          <Form.Item label="Description">
            <TextArea value={saveDesc} onChange={(e) => setSaveDesc(e.target.value)} rows={2} placeholder="What does this template include?" />
          </Form.Item>
          <Form.Item label="Visibility">
            <Select value={saveVisibility} onChange={setSaveVisibility}>
              <Select.Option value="private">Private — only you</Select.Option>
              <Select.Option value="shared">Shared — visible to everyone</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="Tags (comma-separated)">
            <Input value={saveTags} onChange={(e) => setSaveTags(e.target.value)} placeholder="e.g. normal_forest, hills, leasehold" />
          </Form.Item>
          <Form.Item>
            <Button
              type={saveAsDefault ? 'primary' : 'default'}
              icon={saveAsDefault ? <StarFilled /> : <StarOutlined />}
              onClick={() => setSaveAsDefault(!saveAsDefault)}
              size="small"
            >
              {saveAsDefault ? 'Default Template' : 'Set as Default'}
            </Button>
            <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
              Default is auto-selected when creating new plans
            </Text>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default TemplateManager;
