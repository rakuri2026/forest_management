import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Button, message, Spin, Tag, Tabs, Modal } from 'antd';
import {
  SaveOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  DownloadOutlined,
  PlusOutlined,
  BranchesOutlined,
  EyeOutlined,
  PieChartOutlined,
  EnvironmentOutlined,
} from '@ant-design/icons';
import { operationalPlanApi } from '../services/api';
import TreeSidebar from '../components/OperationalPlan/TreeSidebar';
import ContentPane from '../components/OperationalPlan/ContentPane';
import MetadataForm from '../components/OperationalPlan/MetadataForm';
import TableEditor from '../components/OperationalPlan/TableEditor';
import ChartEditor from '../components/OperationalPlan/ChartEditor';
import MapPreview from '../components/OperationalPlan/MapPreview';
import PreviewDrawer from '../components/OperationalPlan/PreviewDrawer';

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
  children: TreeNodeData[];
  is_locked: boolean;
  hidden_in_export: boolean;
  last_modified?: string | null;
}

type EditorTab = 'editor' | 'tables' | 'charts' | 'maps';

interface OperationalPlanPageProps {
  calculationId?: string;
}

const OperationalPlanPage: React.FC<OperationalPlanPageProps> = (props) => {
  const { id: routeId } = useParams<{ id: string }>();
  const calculationId = props.calculationId || routeId;
  const [plan, setPlan] = useState<any>(null);
  const [planId, setPlanId] = useState<string | null>(null);
  const [tree, setTree] = useState<TreeNodeData[]>([]);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);
  const [activeTab, setActiveTab] = useState<EditorTab>('editor');

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
        try {
          const newPlan = await operationalPlanApi.create(calcId);
          setPlan(newPlan);
          setPlanId(newPlan.id);
          setTree(newPlan.tree || []);
          if ((newPlan.tree || []).length > 0) {
            setActiveNodeId(newPlan.tree[0].id);
          }
          message.success('New operational plan created');
        } catch {
          message.error('Failed to create operational plan');
        }
      } else {
        message.error('Failed to load operational plan');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!planId) return;
    setSaving(true);
    try {
      await operationalPlanApi.update(planId, { tree });
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
    const chartTypes = ['forest_type_pie', 'species_pie', 'block_area_bar', 'slope_pie', 'canopy_pie', 'landcover_pie', 'biomass_bar', 'dbh_histogram'];
    const typeStr = window.prompt(`Enter chart type (leave blank for default):\n${chartTypes.join(', ')}`);
    const chartType = typeStr && chartTypes.includes(typeStr) ? typeStr : 'forest_type_pie';
    await handleAddChild(parentId, 'chart', chartType);
  };

  const handleAddMapNode = async (parentId: string | null) => {
    const mapTypes = ['boundary', 'forest_type', 'forest_health', 'slope', 'biomass', 'landcover', 'soil_texture', 'dem', 'aspect', 'canopy'];
    const typeStr = window.prompt(`Enter map type (leave blank for default):\n${mapTypes.join(', ')}`);
    const mapType = typeStr && mapTypes.includes(typeStr) ? typeStr : 'boundary';
    await handleAddChild(parentId, 'map', undefined, mapType);
  };

  const handleDeleteNode = async (nodeId: string) => {
    if (!planId) return;
    try {
      const result = await operationalPlanApi.deleteNode(planId, nodeId);
      setTree(result.tree || []);
      if (activeNodeId === nodeId) {
        setActiveNodeId(null);
      }
      message.success('Section deleted');
    } catch {
      message.error('Failed to delete section');
    }
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
        <Spin size="large" tip="Loading plan..." />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#fff' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid #f0f0f0', background: '#fafafa' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
            Operational Plan Editor
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
          <Button icon={<SettingOutlined />} onClick={() => setShowMetadata(true)} size="small">
            Metadata
          </Button>
          <Button icon={<ThunderboltOutlined />} onClick={handleAutoPopulate} size="small" loading={loading}>
            Auto-Populate
          </Button>
          <Button icon={<SaveOutlined />} onClick={handleSave} size="small" type="primary" loading={saving}>
            Save All
          </Button>
          <Button icon={<DownloadOutlined />} size="small" onClick={handleExport}>
            Export DOCX
          </Button>
          {planId && <PreviewDrawer planId={planId} forestName={plan?.forest_name} />}
        </div>
      </div>

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
              onDeleteNode={handleDeleteNode}
              onToggleHidden={handleToggleHidden}
              onUpdateTitle={handleUpdateTitle}
              onReorderNode={handleReorderNode}
            />
          </div>
          <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {planId && <ContentPane node={activeNode} planId={planId} />}
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

      {planId && (
        <MetadataForm
          planId={planId}
          visible={showMetadata}
          onClose={() => setShowMetadata(false)}
        />
      )}
    </div>
  );
};

export default OperationalPlanPage;
