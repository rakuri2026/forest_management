import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Input, Button, message, Tag, Spin, Tooltip } from 'antd';
import { SaveOutlined, CodeOutlined, EyeOutlined } from '@ant-design/icons';
import { operationalPlanApi } from '../../services/api';
import VariablePicker from './VariablePicker';

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
  children: TreeNodeData[];
  is_locked: boolean;
  hidden_in_export: boolean;
  last_modified?: string | null;
}

interface ContentPaneProps {
  node: TreeNodeData | null;
  planId: string;
}

const typeLabels: Record<string, string> = {
  preamble: 'Preamble',
  toc: 'TOC',
  section: 'Section',
  subsection: 'Subsection',
  appendix: 'Appendix',
};

const ContentPane: React.FC<ContentPaneProps> = ({ node, planId }) => {
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [dirty, setDirty] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setContent(node?.content || '');
    setDirty(false);
  }, [node?.id]);

  const handleSave = useCallback(async () => {
    if (!node || !planId || !dirty) return;
    setSaving(true);
    try {
      await operationalPlanApi.updateNode(planId, node.id, { content });
      setDirty(false);
    } catch {
      message.error('Failed to save');
    } finally {
      setSaving(false);
    }
  }, [node, planId, content, dirty]);

  useEffect(() => {
    if (!dirty) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(handleSave, 2000);
    return () => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
    };
  }, [content, dirty, handleSave]);

  const handleChange = (val: string) => {
    setContent(val);
    setDirty(true);
  };

  const handleVariableSelect = (varKey: string) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const before = content.substring(0, start);
    const after = content.substring(end);
    const newContent = `${before}{{${varKey}}}${after}`;
    handleChange(newContent);
    setTimeout(() => {
      ta.selectionStart = ta.selectionEnd = start + varKey.length + 4;
      ta.focus();
    }, 0);
  };

  if (!node) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
        Select a section from the tree to edit
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <Tag color="blue">{typeLabels[node.type] || node.type}</Tag>
              {node.content_type !== 'richtext' && (
                <Tag color="geekblue">{node.content_type}</Tag>
              )}
              {node.hidden_in_export && <Tag color="orange">Hidden</Tag>}
              {dirty && <Tag color="red">Unsaved</Tag>}
            </div>
            <div style={{ fontWeight: 600, fontSize: 16 }}>
              {node.number ? `${node.number}. ` : ''}{node.title_ne}
            </div>
            <div style={{ fontSize: 12, color: '#999' }}>{node.title_en}</div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <Tooltip title="Insert variable">
              <Button
                icon={<CodeOutlined />}
                size="small"
                onClick={() => setShowPicker(!showPicker)}
                type={showPicker ? 'primary' : 'default'}
              >
                Variables
              </Button>
            </Tooltip>
            <Button
              icon={<SaveOutlined />}
              size="small"
              onClick={handleSave}
              loading={saving}
              disabled={!dirty}
            >
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {node.content_type === 'richtext' ? (
            <textarea
              ref={textareaRef}
              value={content}
              onChange={e => handleChange(e.target.value)}
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                padding: 16,
                fontSize: 14,
                lineHeight: 1.7,
                resize: 'none',
                fontFamily: "'Noto Sans', 'Segoe UI', sans-serif",
                width: '100%',
              }}
              placeholder="Type content here... Use the Variable Picker to insert {{variable_name}} placeholders."
            />
          ) : node.content_type === 'chart' ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📊</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{node.chart_type || node.title_en}</div>
              <div style={{ background: '#f9f9f9', borderRadius: 8, padding: 16, display: 'inline-block', textAlign: 'left', minWidth: 300 }}>
                <div style={{ marginBottom: 8 }}><strong>Chart Type:</strong> {node.chart_type}</div>
                <div style={{ marginBottom: 8 }}><strong>Source:</strong> {
                  {species_pie: 'Species data', forest_type_pie: 'Raster analysis', block_area_bar: 'Block areas',
                   dbh_histogram: 'Tree inventory', biomass_bar: 'Biomass/carbon', slope_pie: 'Slope analysis',
                   canopy_pie: 'Canopy cover', landcover_pie: 'Landcover analysis'
                  }[node.chart_type || ''] || 'System data'
                }</div>
                <div style={{ color: '#999', fontSize: 12 }}>Rendered as PNG in DOCX export via matplotlib.</div>
                <div style={{ color: '#999', fontSize: 12 }}>Live Chart.js preview coming soon.</div>
              </div>
            </div>
          ) : node.content_type === 'table' ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>📋</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{node.table_id || node.title_en}</div>
              <div style={{ background: '#f9f9f9', borderRadius: 8, padding: 16, display: 'inline-block', textAlign: 'left', minWidth: 300 }}>
                <div style={{ marginBottom: 8 }}><strong>Table ID:</strong> {node.table_id}</div>
                <div style={{ color: '#999', fontSize: 12 }}>Edit data in the "Tables 1-32" tab above.</div>
              </div>
            </div>
          ) : node.content_type === 'map' ? (
            <div style={{ padding: 24, textAlign: 'center' }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>🗺️</div>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>{node.title_en || 'Forest Boundary Map'}</div>
              <div style={{ background: '#f9f9f9', borderRadius: 8, padding: 16, display: 'inline-block', textAlign: 'left', minWidth: 300 }}>
                <div style={{ marginBottom: 8 }}><strong>Type:</strong> Boundary Map</div>
                <div style={{ marginBottom: 8 }}><strong>Source:</strong> Forest boundary & block geometry</div>
                <div style={{ color: '#999', fontSize: 12 }}>Preview in the "Maps" tab above.</div>
                <div style={{ color: '#999', fontSize: 12 }}>Rendered as PNG in DOCX export via matplotlib.</div>
              </div>
            </div>
          ) : (
            <textarea
              value={content}
              onChange={e => handleChange(e.target.value)}
              style={{ flex: 1, border: 'none', outline: 'none', padding: 16, fontSize: 14, resize: 'none' }}
            />
          )}
        </div>

        {showPicker && (
          <div style={{ width: 320, borderLeft: '1px solid #f0f0f0', overflow: 'hidden' }}>
            <VariablePicker
              onSelect={handleVariableSelect}
              usedVariables={Array.from(content.matchAll(/\{\{(\w+:?\w+)\}\}/g)).map(m => m[1])}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default ContentPane;
