import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, message, Spin, Tag, Input, Modal, Typography, Space, List, Tooltip, Descriptions, Divider, Popconfirm, Select } from 'antd';
import {
  SaveOutlined,
  CheckCircleOutlined,
  StopOutlined,
  StarOutlined,
  StarFilled,
  CopyOutlined,
  EyeOutlined,
  ArrowLeftOutlined,
  HistoryOutlined,
  RollbackOutlined,
  CameraOutlined,
} from '@ant-design/icons';
import html2canvas from 'html2canvas';
import { operationalPlanApi } from '../services/api';
import TreeSidebar from '../components/OperationalPlan/TreeSidebar';
import ContentPane from '../components/OperationalPlan/ContentPane';
import VariablePicker from '../components/OperationalPlan/VariablePicker';

const { Text } = Typography;
const { TextArea } = Input;

interface TreeNodeData {
  id: string;
  type: string;
  title_ne: string;
  title_en: string;
  number?: string | null;
  level: number;
  content_type: string;
  content: string;
  chart_type?: string | null;
  table_id?: string | null;
  map_type?: string | null;
  static_table?: { columns: string[]; rows: string[][]; merges?: { row: number; col: number; rowspan: number; colspan: number }[] } | null;
  children: TreeNodeData[];
  is_locked: boolean;
  hidden_in_export: boolean;
  deleted: boolean;
  last_modified?: string | null;
}

const TemplateDesignerPage: React.FC = () => {
  const { templateId } = useParams<{ templateId: string }>();
  const navigate = useNavigate();
  const isNew = templateId === 'new';

  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [template, setTemplate] = useState<any>(null);
  const [tree, setTree] = useState<TreeNodeData[]>([]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [showVariablePicker, setShowVariablePicker] = useState(false);
  const [changelogModal, setChangelogModal] = useState(false);
  const [changelog, setChangelog] = useState('');
  const [versionHistoryOpen, setVersionHistoryOpen] = useState(false);
  const [versions, setVersions] = useState<any[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [rollbacking, setRollbacking] = useState(false);
  const [categories, setCategories] = useState<any[]>([]);
  const [capturing, setCapturing] = useState(false);

  useEffect(() => {
    if (!isNew && templateId) {
      loadTemplate(templateId);
    } else {
      setTree([]);
      setLoading(false);
    }
  }, [templateId]);

  const loadTemplate = async (id: string) => {
    setLoading(true);
    try {
      const [tmpl, cats] = await Promise.all([
        operationalPlanApi.getTemplate(id),
        operationalPlanApi.listTemplateCategories().catch(() => []),
      ]);
      setTemplate(tmpl);
      setTree(tmpl.tree || []);
      setCategories(cats || []);
      if ((tmpl.tree || []).length > 0) {
        setActiveNodeId(tmpl.tree[0].id);
      }
    } catch {
      message.error('Failed to load template');
    } finally {
      setLoading(false);
    }
  };

  const handleCategoryChange = async (categoryKey: string | undefined) => {
    if (!template) return;
    try {
      const updated = await operationalPlanApi.updateTemplate(template.id, { template_category: categoryKey || null });
      setTemplate(updated);
      message.success('Category updated');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to update category');
    }
  };

  const handleSave = async () => {
    let id = templateId;
    setSaving(true);
    try {
      if (isNew) {
        const created = await operationalPlanApi.createTemplate({
          name: 'Untitled Template',
          description: '',
          tree,
          visibility: 'private',
        });
        id = created.id;
        setTemplate(created);
        navigate(`/templates/designer/${created.id}`, { replace: true });
        message.success('Template created');
      } else {
        const payload: any = { tree };
        if (template?.is_active) {
          payload.changelog = changelog || `Updated ${new Date().toLocaleDateString()}`;
        }
        const updated = await operationalPlanApi.updateTemplate(id!, payload);
        setTemplate(updated);
        setChangelog('');
        setChangelogModal(false);
        message.success('Template saved');
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to save template');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveWithVersion = async () => {
    if (template?.is_active) {
      setChangelogModal(true);
    } else {
      await handleSave();
    }
  };

  const handlePublish = async () => {
    if (!template) return;
    setSaving(true);
    try {
      const updated = await operationalPlanApi.publishTemplate(template.id, !template.is_active);
      setTemplate(updated);
      message.success(updated.is_active ? 'Template published' : 'Template unpublished');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to update publish status');
    } finally {
      setSaving(false);
    }
  };

  const handleSetDefault = async () => {
    if (!template) return;
    setSaving(true);
    try {
      const updated = await operationalPlanApi.updateTemplate(template.id, {
        is_default: !template.is_default,
      });
      setTemplate(updated);
      message.success(updated.is_default ? 'Set as default' : 'Default removed');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to update default status');
    } finally {
      setSaving(false);
    }
  };

  const handleClone = async () => {
    if (!template) return;
    setSaving(true);
    try {
      const cloned = await operationalPlanApi.cloneTemplate(template.id);
      navigate(`/templates/designer/${cloned.id}`);
      message.success('Template cloned');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to clone template');
    } finally {
      setSaving(false);
    }
  };

  const handleOpenVersionHistory = async () => {
    if (!template) return;
    setVersionsLoading(true);
    setVersionHistoryOpen(true);
    try {
      const data = await operationalPlanApi.getTemplateVersions(template.id);
      setVersions(data || []);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to load version history');
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleRollback = async (version: number) => {
    if (!template) return;
    setRollbacking(true);
    try {
      const updated = await operationalPlanApi.rollbackTemplate(template.id, version);
      setTemplate(updated);
      setTree(updated.tree || []);
      message.success(`Rolled back to version ${version}`);
      setVersionHistoryOpen(false);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to rollback');
    } finally {
      setRollbacking(false);
    }
  };

  const handleCapturePreview = async () => {
    if (!template) return;
    setCapturing(true);
    try {
      const el = document.querySelector('.template-designer-content');
      if (!el) { message.warning('Content area not found'); return; }
      const canvas = await html2canvas(el as HTMLElement, { background: '#ffffff', scale: 0.5 } as any);
      const dataUrl = canvas.toDataURL('image/png');
      await operationalPlanApi.updateTemplate(template.id, { preview_image_url: dataUrl });
      setTemplate((prev: any) => ({ ...prev, preview_image_url: dataUrl }));
      message.success('Preview image captured');
    } catch {
      message.error('Failed to capture preview');
    } finally {
      setCapturing(false);
    }
  };

  const handleAddChild = async (_parentId: string | null, contentType?: string) => {
    if (!contentType || contentType === 'richtext' || contentType === 'static_table') {
      const val = window.prompt(`Enter ${contentType === 'static_table' ? 'table' : 'section'} title (Nepali):`);
      if (!val) return;
      const newNode: any = {
        id: `node_${Date.now()}`,
        type: _parentId ? 'subsection' : 'section',
        title_ne: val,
        title_en: '',
        content: '',
        content_type: contentType === 'static_table' ? 'static_table' : 'richtext',
        level: 0,
        children: [],
        is_locked: false,
        hidden_in_export: false,
        deleted: false,
      };
      if (contentType === 'static_table') {
        newNode.static_table = {
          columns: ['Column 1', 'Column 2', 'Column 3'],
          rows: [['', '', ''], ['', '', ''], ['', '', '']],
        };
      }
      setTree(prev => {
        const addNode = (nodes: TreeNodeData[]): TreeNodeData[] => {
          if (!_parentId) return [...nodes, newNode];
          return nodes.map(n => {
            if (n.id === _parentId) return { ...n, children: [...(n.children || []), newNode] };
            return { ...n, children: addNode(n.children || []) };
          });
        };
        return addNode(prev);
      });
    }
  };

  const handleAddChartNode = undefined;
  const handleAddMapNode = undefined;
  const handleToggleDelete = (nodeId: string) => {
    setTree(prev => {
      const toggle = (nodes: TreeNodeData[]): TreeNodeData[] =>
        nodes.map(n => {
          if (n.id === nodeId) return { ...n, deleted: !n.deleted };
          return { ...n, children: toggle(n.children || []) };
        });
      return toggle(prev);
    });
  };
  const handleHardDelete = async (nodeId: string) => {
    setTree(prev => {
      const remove = (nodes: TreeNodeData[]): TreeNodeData[] =>
        nodes.filter(n => {
          if (n.id === nodeId) return false;
          return { ...n, children: remove(n.children || []) };
        });
      return remove(prev);
    });
  };
  const handleReorderNode = (nodeId: string, newParentId: string | null, newPosition: number) => {
    setTree(prev => {
      const flat = (nodes: TreeNodeData[]): TreeNodeData[] =>
        nodes.flatMap(n => [n, ...flat(n.children || [])]);
      const all = flat(prev);
      const node = all.find(n => n.id === nodeId);
      if (!node) return prev;
      const without = (nodes: TreeNodeData[]): TreeNodeData[] =>
        nodes.filter(n => {
          if (n.id === nodeId) return false;
          return { ...n, children: without(n.children || []) };
        });
      const cleaned = without(prev);
      const addAt = (nodes: TreeNodeData[]): TreeNodeData[] => {
        if (!newParentId) {
          const pos = Math.min(newPosition, nodes.length);
          return [...nodes.slice(0, pos), node, ...nodes.slice(pos)];
        }
        return nodes.map(n => {
          if (n.id === newParentId) return { ...n, children: addAt(n.children || []) };
          return { ...n, children: addAt(n.children || []) };
        });
      };
      return addAt(cleaned);
    });
  };
  const handleUpdateTitle = (nodeId: string, title_ne: string) => {
    setTree(prev => {
      const update = (nodes: TreeNodeData[]): TreeNodeData[] =>
        nodes.map(n => {
          if (n.id === nodeId) return { ...n, title_ne };
          return { ...n, children: update(n.children || []) };
        });
      return update(prev);
    });
  };
  const handleToggleHidden = (nodeId: string) => {
    setTree(prev => {
      const toggle = (nodes: TreeNodeData[]): TreeNodeData[] =>
        nodes.map(n => {
          if (n.id === nodeId) return { ...n, hidden_in_export: !n.hidden_in_export };
          return { ...n, children: toggle(n.children || []) };
        });
      return toggle(prev);
    });
  };
  const handleContentChange = (nodeId: string, content: string, updates?: Record<string, any>) => {
    setTree(prev => {
      const update = (nodes: TreeNodeData[]): TreeNodeData[] =>
        nodes.map(n => {
          if (n.id === nodeId) return { ...n, content, ...(updates || {}) };
          return { ...n, children: update(n.children || []) };
        });
      return update(prev);
    });
  };

  const activeNode = activeNodeId
    ? (() => {
        const find = (nodes: TreeNodeData[]): TreeNodeData | null => {
          for (const n of nodes) {
            if (n.id === activeNodeId) return n;
            const found = find(n.children || []);
            if (found) return found;
          }
          return null;
        };
        return find(tree);
      })()
    : null;

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid #f0f0f0', background: '#fafafa' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/admin/templates')}
          />
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
            Template Designer
          </h2>
          {template && (
            <>
              {template.is_system && <Tag color="gold">System</Tag>}
              {template.is_default && <Tag color="blue">Default</Tag>}
              {template.is_active ? (
                <Tag color="green">Published v{template.version || 1}</Tag>
              ) : (
                <Tag>Draft</Tag>
              )}
              <Text type="secondary" style={{ fontSize: 13 }}>{template.name}</Text>
              <Select
                allowClear
                placeholder="Category"
                style={{ width: 160 }}
                size="small"
                value={template.template_category || undefined}
                onChange={handleCategoryChange}
                options={categories.map((c: any) => ({ value: c.key, label: c.label_en }))}
              />
            </>
          )}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {!isNew && template && (
            <>
              <Button
                icon={<HistoryOutlined />}
                onClick={handleOpenVersionHistory}
                size="small"
              >
                History
              </Button>
              <Tooltip title="Capture a preview image of the content area for the gallery">
                <Button
                  icon={<CameraOutlined />}
                  onClick={handleCapturePreview}
                  size="small"
                  loading={capturing}
                >
                  Preview
                </Button>
              </Tooltip>
              <Button
                icon={template.is_default ? <StarFilled /> : <StarOutlined />}
                onClick={handleSetDefault}
                size="small"
                loading={saving}
              >
                {template.is_default ? 'Default' : 'Set Default'}
              </Button>
              <Button
                icon={template.is_active ? <StopOutlined /> : <CheckCircleOutlined />}
                onClick={handlePublish}
                size="small"
                loading={saving}
                type={template.is_active ? 'default' : 'primary'}
              >
                {template.is_active ? 'Unpublish' : 'Publish'}
              </Button>
              <Button icon={<CopyOutlined />} onClick={handleClone} size="small" loading={saving}>
                Clone
              </Button>
            </>
          )}
          <Button
            icon={<SaveOutlined />}
            onClick={handleSaveWithVersion}
            size="small"
            type="primary"
            loading={saving}
          >
            {isNew ? 'Create Template' : 'Save Version'}
          </Button>
        </div>
      </div>

      <div className="template-designer-content" style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ width: 320, borderRight: '1px solid #f0f0f0', overflow: 'hidden', flexShrink: 0 }}>
          <TreeSidebar
            tree={tree}
            activeNodeId={activeNodeId}
            onSelectNode={setActiveNodeId}
            onAddChild={(pid) => handleAddChild(pid, 'richtext')}
            onAddChartNode={handleAddChartNode}
            onAddMapNode={handleAddMapNode}
            onAddStaticTable={(pid) => handleAddChild(pid, 'static_table')}
            onToggleDelete={handleToggleDelete}
            onToggleHidden={handleToggleHidden}
            onHardDelete={handleHardDelete}
            onUpdateTitle={handleUpdateTitle}
            onReorderNode={handleReorderNode}
          />
        </div>
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', position: 'relative' }}>
          <div style={{ position: 'absolute', top: 8, right: 8, zIndex: 10 }}>
            <Button
              size="small"
              icon={<EyeOutlined />}
              onClick={() => setShowVariablePicker(!showVariablePicker)}
            >
              {showVariablePicker ? 'Hide Variables' : 'Variables'}
            </Button>
          </div>
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '8px 16px', borderBottom: '1px solid #f0f0f0', fontSize: 13, color: '#666' }}>
                {activeNode ? (
                  <span>
                    <strong>{activeNode.title_ne || activeNode.title_en || 'Untitled'}</strong>
                    {activeNode.content_type === 'richtext' && ' — Rich Text'}
                    {activeNode.content_type === 'static_table' && ' — Static Table'}
                  </span>
                ) : (
                  <span style={{ color: '#bbb' }}>Select a section from the outline</span>
                )}
              </div>
              <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <ContentPane
                  node={activeNode}
                  planId={''}
                  calculationId={template?.source_calculation_id || undefined}
                  onContentChange={handleContentChange}
                />
              </div>
            </div>
            {showVariablePicker && activeNode && (
              <div style={{ width: 300, borderLeft: '1px solid #f0f0f0', overflow: 'auto', flexShrink: 0 }}>
                <VariablePicker
                  calculationId={template?.source_calculation_id || undefined}
                  onSelect={(key) => {
                    const textarea = document.querySelector('.content-pane-textarea') as HTMLTextAreaElement;
                    if (textarea) {
                      const start = textarea.selectionStart;
                      const end = textarea.selectionEnd;
                      const newContent = activeNode.content.slice(0, start) + `{{${key}}}` + activeNode.content.slice(end);
                      handleContentChange(activeNode.id, newContent);
                    } else {
                      handleContentChange(activeNode.id, activeNode.content + `{{${key}}}`);
                    }
                  }}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal
        title={<span><HistoryOutlined /> Version History: {template?.name}</span>}
        open={versionHistoryOpen}
        onCancel={() => setVersionHistoryOpen(false)}
        footer={null}
        width={640}
      >
        {versionsLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
        ) : versions.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>
            <HistoryOutlined style={{ fontSize: 32, marginBottom: 12 }} />
            <p>No version history yet. Versions are created when you save changes to a published template.</p>
          </div>
        ) : (
          <List
            dataSource={versions}
            renderItem={(v: any) => (
              <List.Item
                actions={[
                  <Popconfirm
                    key="rollback"
                    title={`Rollback to v${v.version}? Current unsaved changes will be lost.`}
                    onConfirm={() => handleRollback(v.version)}
                  >
                    <Button size="small" icon={<RollbackOutlined />} loading={rollbacking}>
                      Rollback
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  avatar={
                    <Tag color={v.version === template?.version ? 'green' : 'default'} style={{ fontSize: 14 }}>
                      v{v.version}
                    </Tag>
                  }
                  title={
                    <Space>
                      <Text strong>{v.version === template?.version ? 'Current Version' : v.name}</Text>
                      {v.version === template?.version && <Tag color="green">Active</Tag>}
                    </Space>
                  }
                  description={
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {new Date(v.created_at).toLocaleString()}
                      </Text>
                      {v.changelog && (
                        <>
                          <Divider style={{ margin: '4px 0' }} />
                          <Text style={{ fontSize: 12, fontStyle: 'italic' }}>
                            {v.changelog}
                          </Text>
                        </>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Modal>

      <Modal
        title="Save New Version"
        open={changelogModal}
        onOk={() => { setChangelogModal(false); handleSave(); }}
        onCancel={() => setChangelogModal(false)}
        okText="Save Version"
        confirmLoading={saving}
      >
        <div style={{ marginBottom: 12 }}>
          <Text>Describe what changed in this version (optional):</Text>
        </div>
        <TextArea
          value={changelog}
          onChange={(e) => setChangelog(e.target.value)}
          rows={3}
          placeholder="e.g. Added new sections for fire management, updated species list"
        />
      </Modal>
    </div>
  );
};

export default TemplateDesignerPage;