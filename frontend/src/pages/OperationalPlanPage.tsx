import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button, message, Spin, Tag, Tabs, Tooltip, Popconfirm } from 'antd';
import {
  SaveOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  DownloadOutlined,
  BranchesOutlined,
  PieChartOutlined,
  EnvironmentOutlined,
  FileTextOutlined,
  PlusOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import { operationalPlanApi } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import TreeSidebar from '../components/OperationalPlan/TreeSidebar';
import ContentPane from '../components/OperationalPlan/ContentPane';
import DocumentOutline from '../components/OperationalPlan/DocumentOutline';
import MetadataForm from '../components/OperationalPlan/MetadataForm';
import TableEditor from '../components/OperationalPlan/TableEditor';
import ChartEditor from '../components/OperationalPlan/ChartEditor';
import MapPreview from '../components/OperationalPlan/MapPreview';
import PreviewDrawer from '../components/OperationalPlan/PreviewDrawer';
import TemplateManager from '../components/OperationalPlan/TemplateManager';

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
  inline_tables?: { caption?: string; columns: string[]; rows: string[][]; merges?: { row: number; col: number; rowspan: number; colspan: number }[] }[] | null;
  children: TreeNodeData[];
  is_locked: boolean;
  hidden_in_export: boolean;
  deleted: boolean;
  last_modified?: string | null;
}

type EditorTab = 'editor' | 'tables' | 'charts' | 'maps';

interface OperationalPlanPageProps {
  calculationId?: string;
}

const OperationalPlanPage: React.FC<OperationalPlanPageProps> = (props) => {
  const { id: routeId } = useParams<{ id: string }>();
  const calculationId = props.calculationId || routeId;
  const { user } = useAuth();
  const isSuperAdmin = user?.role === 'super_admin';
  const isEditor = isSuperAdmin;
  const navigate = useNavigate();

  const [plan, setPlan] = useState<any>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [tree, setTree] = useState<TreeNodeData[]>([]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);
  const [activeTab, setActiveTab] = useState<EditorTab>('editor');
  const [showTemplateManager, setShowTemplateManager] = useState(false);

  useEffect(() => {
    if (calculationId) {
      loadOrCreatePlan(calculationId);
    }
  }, [calculationId]);

  const loadOrCreatePlan = async (calcId: string) => {
    setLoading(true);
    try {
      let planData = await operationalPlanApi.getByCalculation(calcId);
      setPlan(planData);
      setPlanId(planData.id);
      setTree(planData.tree || []);
      if ((planData.tree || []).length > 0) {
        setActiveNodeId(planData.tree[0].id);
      }
    } catch (err: any) {
      if (err.response?.status === 404) {
        await createWithDefault(calcId);
      } else {
        message.error('Failed to load operational plan');
      }
    } finally {
      setLoading(false);
    }
  };

  const createWithDefault = async (calcId: string) => {
    if (!isSuperAdmin) {
      navigate(`/templates?calculation_id=${calcId}`);
      return;
    }
    try {
      const newPlan = await operationalPlanApi.create(calcId);
      setPlan(newPlan);
      setPlanId(newPlan.id);
      setTree(newPlan.tree || []);
      if ((newPlan.tree || []).length > 0) {
        setActiveNodeId(newPlan.tree[0].id);
      }
    } catch {
      message.error('Failed to create operational plan');
    }
  };

  const handleSave = async () => {
    if (!planId) return;
    setSaving(true);
    try {
      const payload: any = { tree };
      const updated = await operationalPlanApi.update(planId, payload);
      setPlan(updated);
      message.success('Plan saved');
    } catch {
      message.error('Failed to save plan');
    } finally {
      setSaving(false);
    }
  };

  const handleAutoPopulate = async () => {
    if (!planId) return;
    setLoading(true);
    try {
      const updated = await operationalPlanApi.autoPopulate(planId);
      setTree(updated.tree || []);
      message.success('Variables resolved');
    } catch {
      message.error('Auto-populate failed');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    if (!planId) return;
    try {
      await operationalPlanApi.exportDocx(planId, plan?.forest_name || 'CF');
      message.success('DOCX exported');
    } catch (err: any) {
      message.error(err.message || 'Export failed');
    }
  };

  const handleUpdateDefaultTemplate = async () => {
    if (!planId) return;
    try {
      await operationalPlanApi.updateDefaultTemplate(planId);
      message.success('Global template updated. New users will see this version.');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to update global template');
    }
  };

  const handleHardDelete = async (nodeId: string) => {
    if (!planId) return;
    try {
      const result = await operationalPlanApi.deleteNode(planId, nodeId);
      setTree(result.tree || []);
      if (activeNodeId === nodeId) setActiveNodeId(null);
      message.success('Section permanently deleted');
    } catch {
      message.error('Failed to delete section');
    }
  };

  const handleAddStaticTable = async (parentId: string | null) => {
    if (!planId) return;

    if (activeNode && activeNode.content_type === 'richtext') {
      const newTable = {
        caption: '',
        columns: ['Column 1', 'Column 2', 'Column 3'],
        rows: [['', '', ''], ['', '', ''], ['', '', '']],
        merges: [],
      };
      const existing = activeNode.inline_tables || [];
      const updated = [...existing, newTable];
      try {
        await operationalPlanApi.updateNode(planId, activeNode.id, { inline_tables: updated });
        setTree(prev => {
          const update = (nodes: TreeNodeData[]): TreeNodeData[] =>
            nodes.map(n => {
              if (n.id === activeNode.id) return { ...n, inline_tables: updated };
              return { ...n, children: update(n.children || []) };
            });
          return update(prev);
        });
        message.success('Table added to section');
      } catch {
        message.error('Failed to add table');
      }
      return;
    }

    const val = window.prompt('Enter table title (Nepali):');
    if (!val) return;
    try {
      const result = await operationalPlanApi.addNode(planId, {
        parent_id: parentId,
        type: parentId ? 'subsection' : 'section',
        title_ne: val,
        content: '',
        content_type: 'static_table',
        static_table: {
          columns: ['Column 1', 'Column 2', 'Column 3'],
          rows: [['', '', ''], ['', '', ''], ['', '', '']],
        },
      });
      setTree(result.tree || []);
      message.success('Static table added');
    } catch {
      message.error('Failed to add static table');
    }
  };

  const handleAddChild = async (parentId: string | null, contentType: string = 'richtext', chartType?: string, mapType?: string) => {
    if (!planId) return;
    const val = window.prompt(`Enter ${contentType === 'chart' ? 'chart' : contentType === 'map' ? 'map' : 'section'} title (Nepali):`);
    if (!val) return;
    try {
      const result = await operationalPlanApi.addNode(planId, {
        parent_id: parentId,
        type: parentId ? 'subsection' : 'section',
        title_ne: val,
        content: '',
        content_type: contentType,
        chart_type: contentType === 'chart' ? (chartType || 'forest_type_pie') : null,
        map_type: contentType === 'map' ? (mapType || 'boundary') : null,
      });
      setTree(result.tree || []);
      message.success(`${contentType === 'chart' ? 'Chart' : contentType === 'map' ? 'Map' : 'Section'} added`);
    } catch {
      message.error('Failed to add section');
    }
  };

  const handleAddChartNode = async (parentId: string | null) => {
    if (!planId) return;
    const chartTypes = ['forest_type_pie', 'species_pie', 'block_area_bar', 'slope_pie', 'canopy_pie', 'landcover_pie', 'biomass_bar', 'dbh_histogram'];
    const typeStr = window.prompt(`Enter chart type (leave blank for default):\n${chartTypes.join(', ')}`);
    const chartType = typeStr && chartTypes.includes(typeStr) ? typeStr : 'forest_type_pie';
    await handleAddChild(parentId, 'chart', chartType);
  };

  const handleAddMapNode = async (parentId: string | null) => {
    if (!planId) return;
    const mapTypes = ['boundary', 'forest_type', 'forest_health', 'slope', 'biomass', 'landcover', 'soil_texture', 'dem', 'aspect', 'canopy'];
    const typeStr = window.prompt(`Enter map type (leave blank for default):\n${mapTypes.join(', ')}`);
    const mapType = typeStr && mapTypes.includes(typeStr) ? typeStr : 'boundary';
    await handleAddChild(parentId, 'map', undefined, mapType);
  };

  const handleToggleDelete = (nodeId: string) => {
    const toggleNode = (nodes: TreeNodeData[]): TreeNodeData[] =>
      nodes.map(n => {
        if (n.id === nodeId) {
          const newDeleted = !n.deleted;
          const cascade = (children: TreeNodeData[]): TreeNodeData[] =>
            children.map(c => ({ ...c, deleted: newDeleted, children: cascade(c.children) }));
          return { ...n, deleted: newDeleted, children: cascade(n.children) };
        }
        return { ...n, children: toggleNode(n.children) };
      });
    setTree(prev => toggleNode(prev));
  };

  const handleReorderNode = async (nodeId: string, newParentId: string | null, newPosition: number) => {
    if (!planId) return;
    try {
      const result = await operationalPlanApi.reorderTree(planId, {
        node_id: nodeId,
        new_parent_id: newParentId,
        new_position: newPosition,
      });
      setTree(result.tree || []);
      message.success('Section moved');
    } catch { message.error('Failed to move section'); }
  };

  const handleUpdateTitle = async (nodeId: string, title_ne: string) => {
    if (!planId) return;
    try {
      await operationalPlanApi.updateNode(planId, nodeId, { title_ne });
      setTree(prev => {
        const update = (nodes: TreeNodeData[]): TreeNodeData[] =>
          nodes.map(n => {
            if (n.id === nodeId) return { ...n, title_ne };
            return { ...n, children: update(n.children || []) };
          });
        return update(prev);
      });
    } catch { message.error('Failed to update title'); }
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

  const handleToggleHidden = async (nodeId: string) => {
    if (!planId) return;
    const findNode = (nodes: TreeNodeData[]): TreeNodeData | null => {
      for (const n of nodes) {
        if (n.id === nodeId) return n;
        const found = findNode(n.children || []);
        if (found) return found;
      }
      return null;
    };
    const node = findNode(tree);
    if (!node) return;
    try {
      await operationalPlanApi.updateNode(planId, nodeId, {
        hidden_in_export: !node.hidden_in_export,
      });
      setTree(prev => {
        const update = (nodes: TreeNodeData[]): TreeNodeData[] =>
          nodes.map(n => {
            if (n.id === nodeId) return { ...n, hidden_in_export: !n.hidden_in_export };
            return { ...n, children: update(n.children || []) };
          });
        return update(prev);
      });
    } catch {
      message.error('Failed to update node');
    }
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
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
            {isEditor ? 'Operational Plan Editor' : 'Operational Plan'}
          </h2>
          {plan && (
            <Tag color={plan.status === 'draft' ? 'blue' : plan.status === 'submitted' ? 'orange' : 'green'}>
              {plan.status}
            </Tag>
          )}
          {plan?.forest_name && (
            <span style={{ color: '#666', fontSize: 13 }}>{plan.forest_name}</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {isEditor && (
            <>
              {isSuperAdmin && (
                <Button icon={<FileTextOutlined />} onClick={() => setShowTemplateManager(true)} size="small">
                  Templates
                </Button>
              )}
              {isSuperAdmin && planId && (
                <Popconfirm
                  title="Update the global template?"
                  description="All new users will see this version when they create their operational plan."
                  onConfirm={handleUpdateDefaultTemplate}
                  okText="Update"
                  cancelText="Cancel"
                >
                  <Button icon={<GlobalOutlined />} size="small">
                    Update Global Template
                  </Button>
                </Popconfirm>
              )}
              <Button icon={<SettingOutlined />} onClick={() => setShowMetadata(true)} size="small">
                Metadata
              </Button>
              <Button icon={<ThunderboltOutlined />} onClick={handleAutoPopulate} size="small" loading={loading}>
                Auto-Populate
              </Button>
              <Button icon={<SaveOutlined />} onClick={handleSave} size="small" type="primary" loading={saving}>
                Save All
              </Button>
            </>
          )}
          {planId && (
            <Tooltip title="Preview full document">
              <PreviewDrawer planId={planId} forestName={plan?.forest_name} />
            </Tooltip>
          )}
          <Button icon={<DownloadOutlined />} size="small" type={isEditor ? 'default' : 'primary'} onClick={handleExport}>
            Export DOCX
          </Button>
        </div>
      </div>

      {isEditor ? (
        <>
          <Tabs
            activeKey={activeTab}
            onChange={(k) => setActiveTab(k as EditorTab)}
            items={[
              { key: 'editor', label: <span><BranchesOutlined /> Document Editor</span> },
              { key: 'tables', label: <span><PlusOutlined /> Tables 1-32</span> },
              { key: 'charts', label: <span><PieChartOutlined /> Charts</span> },
              { key: 'maps', label: <span><EnvironmentOutlined /> Maps</span> },
            ]}
            style={{ marginBottom: 0, padding: '0 16px' }}
            tabBarStyle={{ marginBottom: 0 }}
          />
          {activeTab === 'editor' ? (
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
              <div style={{ width: 320, borderRight: '1px solid #f0f0f0', overflow: 'hidden', flexShrink: 0 }}>
                <TreeSidebar
                  tree={tree}
                  activeNodeId={activeNodeId}
                  onSelectNode={setActiveNodeId}
                  onAddChild={handleAddChild}
                  onAddChartNode={handleAddChartNode}
                  onAddMapNode={handleAddMapNode}
                  onAddStaticTable={handleAddStaticTable}
                  onToggleDelete={handleToggleDelete}
                  onToggleHidden={handleToggleHidden}
                  onHardDelete={handleHardDelete}
                  onUpdateTitle={handleUpdateTitle}
                  onReorderNode={handleReorderNode}
                />
              </div>
              <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                {planId && <ContentPane node={activeNode} planId={planId} calculationId={calculationId} onContentChange={handleContentChange} />}
              </div>
            </div>
          ) : activeTab === 'tables' ? (
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {calculationId && <TableEditor calculationId={calculationId} />}
            </div>
          ) : activeTab === 'charts' ? (
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {planId && <ChartEditor planId={planId} />}
            </div>
          ) : (
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {planId && <MapPreview planId={planId} calculationId={calculationId} />}
            </div>
          )}
        </>
      ) : (
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          <div style={{ width: 280, borderRight: '1px solid #f0f0f0', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '12px 14px', borderBottom: '1px solid #f0f0f0', fontWeight: 600, fontSize: 13 }}>
              <FileTextOutlined style={{ marginRight: 6 }} />Contents
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <DocumentOutline
                tree={tree}
                activeNodeId={activeNodeId}
                onSelectNode={setActiveNodeId}
              />
            </div>
          </div>
          <div style={{ flex: 1, overflow: 'auto', padding: '32px 48px' }}>
            {activeNode ? (
              <div style={{ maxWidth: 720 }}>
                {activeNode.number && (
                  <div style={{ color: '#1677ff', fontSize: 12, fontWeight: 500, marginBottom: 4, letterSpacing: '0.5px' }}>
                    SECTION {activeNode.number}
                  </div>
                )}
                <h2 style={{ margin: '0 0 4px 0', fontSize: 22, fontWeight: 700, color: '#1a1a1a' }}>
                  {activeNode.title_ne || activeNode.title_en}
                </h2>
                {activeNode.title_ne && activeNode.title_en && activeNode.title_en !== activeNode.title_ne && (
                  <div style={{ fontSize: 13, color: '#888', marginBottom: 16 }}>{activeNode.title_en}</div>
                )}
                <hr style={{ border: 'none', borderTop: '2px solid #e8e8e8', margin: '16px 0' }} />
                {activeNode.content_type === 'richtext' && (
                  <div style={{
                    fontSize: 15, lineHeight: 1.8, color: '#333',
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                  }}>
                    {activeNode.content || <span style={{ color: '#bbb', fontStyle: 'italic' }}>No content</span>}
                  </div>
                )}
                {activeNode.content_type === 'chart' && (
                  <div style={{ textAlign: 'center', padding: 40, background: '#fafafa', borderRadius: 8, border: '1px solid #f0f0f0' }}>
                    <PieChartOutlined style={{ fontSize: 32, color: '#1677ff' }} />
                    <div style={{ marginTop: 8, color: '#666' }}>Chart visualization</div>
                  </div>
                )}
                {activeNode.content_type === 'map' && (
                  <div style={{ textAlign: 'center', padding: 40, background: '#fafafa', borderRadius: 8, border: '1px solid #f0f0f0' }}>
                    <EnvironmentOutlined style={{ fontSize: 32, color: '#52c41a' }} />
                    <div style={{ marginTop: 8, color: '#666' }}>Map visualization</div>
                  </div>
                )}
                {activeNode.content_type === 'static_table' && activeNode.static_table && (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                    <thead>
                      <tr>
                        {activeNode.static_table.columns.map((col: string, i: number) => (
                          <th key={i} style={{ border: '1px solid #d9d9d9', padding: '8px 12px', background: '#fafafa', fontWeight: 600, textAlign: 'left' }}>{col}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {activeNode.static_table.rows.map((row: string[], ri: number) => (
                        <tr key={ri}>
                          {row.map((cell: string, ci: number) => (
                            <td key={ci} style={{ border: '1px solid #d9d9d9', padding: '6px 12px' }}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div style={{ marginTop: 40, paddingTop: 24, borderTop: '2px solid #e8e8e8', fontSize: 12, color: '#999' }}>
                  Last updated: {plan?.updated_at ? new Date(plan.updated_at).toLocaleString() : 'N/A'}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: 80, color: '#bbb' }}>
                <FileTextOutlined style={{ fontSize: 48, display: 'block', marginBottom: 16 }} />
                <span style={{ fontSize: 16 }}>Select a section from the table of contents</span>
              </div>
            )}
            {plan?.plan_metadata?.custom_notes && (
              <div style={{ maxWidth: 720, marginTop: 32, padding: 20, background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 8 }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: 14, fontWeight: 600, color: '#ad6800' }}>Custom Notes</h4>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.6, color: '#666' }}>
                  {plan.plan_metadata.custom_notes}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {planId && (
        <MetadataForm
          planId={planId}
          visible={showMetadata}
          onClose={() => setShowMetadata(false)}
        />
      )}

      {isSuperAdmin && (
        <TemplateManager
          planId={planId}
          tree={tree}
          visible={showTemplateManager}
          onClose={() => setShowTemplateManager(false)}
          onLoadTemplate={() => {}}
        />
      )}
    </div>
  );
};

export default OperationalPlanPage;