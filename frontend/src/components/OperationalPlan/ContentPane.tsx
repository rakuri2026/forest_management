import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Input, Button, message, Tag, Spin, Tooltip, Alert, InputNumber } from 'antd';
import { SaveOutlined, CodeOutlined, EyeOutlined, EditOutlined, WarningOutlined, PlusOutlined, MinusOutlined, DeleteOutlined, ColumnHeightOutlined, ColumnWidthOutlined } from '@ant-design/icons';
import { operationalPlanApi } from '../../services/api';
import VariablePicker from './VariablePicker';

interface MergeEntry {
  row: number;
  col: number;
  rowspan: number;
  colspan: number;
}

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
  static_table?: { columns: string[]; rows: string[][]; merges?: MergeEntry[] } | null;
  children: TreeNodeData[];
  is_locked: boolean;
  hidden_in_export: boolean;
  deleted: boolean;
  last_modified?: string | null;
}

interface ContentPaneProps {
  node: TreeNodeData | null;
  planId: string;
  calculationId?: string;
  onContentChange?: (nodeId: string, content: string, updates?: Record<string, any>) => void;
}

const typeLabels: Record<string, string> = {
  preamble: 'Preamble',
  toc: 'TOC',
  section: 'Section',
  subsection: 'Subsection',
  appendix: 'Appendix',
};

const ContentPane: React.FC<ContentPaneProps> = ({ node, planId, calculationId, onContentChange }) => {
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<'edit' | 'preview'>('edit');
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [tableColumns, setTableColumns] = useState<string[]>([]);
  const [tableRows, setTableRows] = useState<string[][]>([]);
  const [merges, setMerges] = useState<MergeEntry[]>([]);
  const [activeCell, setActiveCell] = useState<{ row: number; col: number } | null>(null);
  const [selectionStart, setSelectionStart] = useState<{ row: number; col: number } | null>(null);
  const [selectionEnd, setSelectionEnd] = useState<{ row: number; col: number } | null>(null);
  const tableColsRef = useRef(tableColumns);
  const tableRowsRef = useRef(tableRows);
  const mergesRef = useRef(merges);
  tableColsRef.current = tableColumns;
  tableRowsRef.current = tableRows;
  mergesRef.current = merges;

  const isCellMerged = useCallback((ri: number, ci: number): { master: boolean; entry?: MergeEntry } => {
    for (const m of merges) {
      if (ri >= m.row && ri < m.row + m.rowspan && ci >= m.col && ci < m.col + m.colspan) {
        return { master: ri === m.row && ci === m.col, entry: m };
      }
    }
    return { master: true };
  }, [merges]);

  const isInMergeRange = useCallback((ri: number, ci: number): boolean => {
    for (const m of merges) {
      if (ri >= m.row && ri < m.row + m.rowspan && ci >= m.col && ci < m.col + m.colspan) {
        return true;
      }
    }
    return false;
  }, [merges]);

  const rangesOverlap = (r1: number, c1: number, rs1: number, cs1: number,
                          r2: number, c2: number, rs2: number, cs2: number): boolean => {
    return !(r1 + rs1 <= r2 || r2 + rs2 <= r1 || c1 + cs1 <= c2 || c2 + cs2 <= c1);
  };

  const fetchPreview = useCallback(async () => {
    if (!node || !planId) return;
    setPreviewLoading(true);
    try {
      const html = await operationalPlanApi.previewOperationalPlanSection(planId, node.id);
      setPreviewHtml(html);
    } catch {
      setPreviewHtml('<div style="padding:24px;color:red">Failed to load preview</div>');
    } finally {
      setPreviewLoading(false);
    }
  }, [node?.id, planId]);

  useEffect(() => {
    setContent(node?.content || '');
    if (node?.content_type === 'static_table' && node?.static_table) {
      setTableColumns(node.static_table.columns || ['Column 1']);
      setTableRows(node.static_table.rows || [['']]);
      setMerges(node.static_table.merges || []);
    } else {
      setMerges([]);
    }
    setActiveCell(null);
    setSelectionStart(null);
    setSelectionEnd(null);
    setDirty(false);
    setMode('edit');
    setPreviewHtml('');
  }, [node?.id]);

  const propagateToParent = (content?: string, extra?: Record<string, any>) => {
    if (!planId && onContentChange && node) {
      onContentChange(node.id, content ?? '', extra);
    }
  };

  useEffect(() => {
    if (!dirty || planId) return;
    if (node?.content_type === 'static_table') {
      propagateToParent('', {
        static_table: {
          columns: tableColsRef.current,
          rows: tableRowsRef.current,
          merges: mergesRef.current,
        }
      });
    } else {
      propagateToParent(content);
    }
  }, [content, tableColumns, tableRows, merges]);

  const handleSave = useCallback(async () => {
    if (!node || !planId || !dirty) return;
    setSaving(true);
    try {
      if (node.content_type === 'static_table') {
        const staticTableData = { static_table: { columns: tableColumns, rows: tableRows, merges } };
        await operationalPlanApi.updateNode(planId, node.id, staticTableData);
        setDirty(false);
        onContentChange?.(node.id, '', staticTableData);
      } else {
        await operationalPlanApi.updateNode(planId, node.id, { content });
        setDirty(false);
        onContentChange?.(node.id, content);
      }
    } catch {
      message.error('Failed to save');
    } finally {
      setSaving(false);
    }
  }, [node, planId, content, dirty, onContentChange, tableColumns, tableRows, merges]);

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

  const handleTableHeaderChange = (colIndex: number, val: string) => {
    setTableColumns(prev => { const c = [...prev]; c[colIndex] = val; return c; });
    setDirty(true);
  };

  const handleTableCellChange = (rowIndex: number, colIndex: number, val: string) => {
    const { master, entry } = isCellMerged(rowIndex, colIndex);
    if (!master && entry) {
      setTableRows(prev => {
        const r = prev.map(row => [...row]);
        r[entry.row][entry.col] = val;
        return r;
      });
    } else {
      setTableRows(prev => {
        const r = prev.map(row => [...row]);
        r[rowIndex][colIndex] = val;
        return r;
      });
    }
    setDirty(true);
  };

  const handleCellClick = (ri: number, ci: number, shiftKey: boolean) => {
    const { master, entry } = isCellMerged(ri, ci);
    const targetRow = master && entry ? entry.row : ri;
    const targetCol = master && entry ? entry.col : ci;
    setActiveCell({ row: targetRow, col: targetCol });
    if (shiftKey && selectionStart) {
      setSelectionEnd({ row: targetRow, col: targetCol });
    } else {
      setSelectionStart({ row: targetRow, col: targetCol });
      setSelectionEnd({ row: targetRow, col: targetCol });
    }
  };

  const getMergeRect = () => {
    if (!selectionStart || !selectionEnd) return null;
    const topRow = Math.min(selectionStart.row, selectionEnd.row);
    const bottomRow = Math.max(selectionStart.row, selectionEnd.row);
    const leftCol = Math.min(selectionStart.col, selectionEnd.col);
    const rightCol = Math.max(selectionStart.col, selectionEnd.col);
    return { row: topRow, col: leftCol, rowspan: bottomRow - topRow + 1, colspan: rightCol - leftCol + 1 };
  };

  const isCellSelected = (ri: number, ci: number): boolean => {
    if (!selectionStart || !selectionEnd) return false;
    const topRow = Math.min(selectionStart.row, selectionEnd.row);
    const bottomRow = Math.max(selectionStart.row, selectionEnd.row);
    const leftCol = Math.min(selectionStart.col, selectionEnd.col);
    const rightCol = Math.max(selectionStart.col, selectionEnd.col);
    return ri >= topRow && ri <= bottomRow && ci >= leftCol && ci <= rightCol;
  };

  const handleMerge = () => {
    const rect = getMergeRect();
    if (!rect) {
      message.warning('Select cells first: click a cell, then shift-click another cell');
      return;
    }
    if (rect.rowspan === 1 && rect.colspan === 1) {
      message.warning('Select at least 2 cells to merge');
      return;
    }
    for (const m of merges) {
      if (rangesOverlap(rect.row, rect.col, rect.rowspan, rect.colspan, m.row, m.col, m.rowspan, m.colspan)) {
        message.warning('Selection overlaps an existing merged region');
        return;
      }
    }
    setMerges(prev => [...prev, rect]);
    setDirty(true);
    message.success(`Merged ${rect.rowspan}×${rect.colspan} cells`);
  };

  const handleUnmerge = () => {
    if (!activeCell) {
      message.warning('Click a merged cell first');
      return;
    }
    const { master, entry } = isCellMerged(activeCell.row, activeCell.col);
    if (!entry) {
      message.warning('This cell is not part of a merged region');
      return;
    }
    const masterValue = tableRows[entry.row]?.[entry.col] || '';
    setTableRows(prev => {
      const r = prev.map(row => [...row]);
      for (let ri = entry.row; ri < entry.row + entry.rowspan; ri++) {
        for (let ci = entry.col; ci < entry.col + entry.colspan; ci++) {
          r[ri][ci] = masterValue;
        }
      }
      return r;
    });
    setMerges(prev => prev.filter(m => m !== entry));
    setDirty(true);
    message.success('Unmerged cells');
  };

  const adjustMergesOnRowRemove = (rowIndex: number) => {
    setMerges(prev => {
      const updated: MergeEntry[] = [];
      for (const m of prev) {
        const mc = { ...m };
        if (mc.row === rowIndex || (mc.row < rowIndex && rowIndex < mc.row + mc.rowspan)) {
          mc.rowspan -= 1;
        } else if (mc.row > rowIndex) {
          mc.row -= 1;
        }
        if (mc.rowspan >= 1) updated.push(mc);
      }
      return updated;
    });
  };

  const adjustMergesOnColRemove = (colIndex: number) => {
    setMerges(prev => {
      const updated: MergeEntry[] = [];
      for (const m of prev) {
        const mc = { ...m };
        if (mc.col === colIndex || (mc.col < colIndex && colIndex < mc.col + mc.colspan)) {
          mc.colspan -= 1;
        } else if (mc.col > colIndex) {
          mc.col -= 1;
        }
        if (mc.colspan >= 1) updated.push(mc);
      }
      return updated;
    });
  };

  const addColumn = () => {
    setTableColumns(prev => [...prev, `Column ${prev.length + 1}`]);
    setTableRows(prev => prev.map(row => [...row, '']));
    setDirty(true);
  };

  const removeColumn = (colIndex: number) => {
    if (tableColumns.length <= 1) return;
    setTableColumns(prev => prev.filter((_, i) => i !== colIndex));
    setTableRows(prev => prev.map(row => row.filter((_, i) => i !== colIndex)));
    adjustMergesOnColRemove(colIndex);
    setDirty(true);
  };

  const addRow = () => {
    setTableRows(prev => [...prev, tableColumns.map(() => '')]);
    setDirty(true);
  };

  const removeRow = (rowIndex: number) => {
    if (tableRows.length <= 1) return;
    setTableRows(prev => prev.filter((_, i) => i !== rowIndex));
    adjustMergesOnRowRemove(rowIndex);
    setDirty(true);
  };

  const handleVariableSelect = (varKey: string) => {
    if (node?.content_type === 'static_table') {
      if (!activeCell) {
        message.warning('Click a cell first, then insert variable');
        return;
      }
      const targetRow = activeCell.row;
      const targetCol = activeCell.col;
      setTableRows(prev => {
        const r = prev.map(row => [...row]);
        r[targetRow][targetCol] = `{{${varKey}}}`;
        return r;
      });
      setDirty(true);
    } else {
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
    }
  };

  const renderTableCells = (ri: number, row: string[]) => {
    const cells: React.ReactNode[] = [];
    for (let ci = 0; ci < row.length; ci++) {
      const { master, entry } = isCellMerged(ri, ci);
      if (!master) continue;
      const visualRow = entry ? entry.row : ri;
      const visualCol = entry ? entry.col : ci;
      const isActive = activeCell?.row === visualRow && activeCell?.col === visualCol;
      const isSelected = isCellSelected(ri, ci);
      const rs = entry?.rowspan || 1;
      const cs = entry?.colspan || 1;
      const value = tableRows[visualRow]?.[visualCol] || '';
      cells.push(
        <td
          key={ci}
          rowSpan={rs}
          colSpan={cs}
          style={{
            border: '1px solid #d9d9d9',
            padding: 4,
            background: isSelected ? '#d6e4ff' : isActive ? '#e6f7ff' : undefined,
            verticalAlign: 'top',
          }}
        >
          <input
            value={value}
            onChange={e => handleTableCellChange(visualRow, visualCol, e.target.value)}
            onFocus={() => {
              setActiveCell({ row: visualRow, col: visualCol });
            }}
            onMouseDown={(e) => {
              e.stopPropagation();
              handleCellClick(visualRow, visualCol, e.shiftKey);
            }}
            onClick={(e) => {
              e.stopPropagation();
            }}
            style={{ width: '100%', border: 'none', outline: 'none', fontSize: 13, background: 'transparent' }}
          />
        </td>
      );
    }
    return cells;
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
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <Button
              size="small"
              type={mode === 'edit' ? 'primary' : 'default'}
              icon={<EditOutlined />}
              onClick={() => setMode('edit')}
            >
              Edit
            </Button>
            <Button
              size="small"
              type={mode === 'preview' ? 'primary' : 'default'}
              icon={<EyeOutlined />}
              onClick={() => { setMode('preview'); fetchPreview(); }}
              disabled={!node?.content && !['chart', 'table', 'map', 'static_table'].includes(node?.content_type || '')}
            >
              Preview
            </Button>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <Tooltip title={node?.content_type === 'static_table' ? 'Select a cell, then pick a variable' : 'Insert variable'}>
              <Button
                icon={<CodeOutlined />}
                size="small"
                onClick={() => setShowPicker(!showPicker)}
                type={showPicker ? 'primary' : 'default'}
              >
                {node?.content_type === 'static_table' ? 'Cell Variables' : 'Variables'}
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

      {node.deleted && (
        <Alert
          message="This section is marked as removed. It will NOT appear in the DOCX export or HTML preview. Click the undo button in the tree sidebar to restore it."
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          style={{ margin: '8px 16px', borderRadius: 6 }}
        />
      )}

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {mode === 'preview' ? (
            <div style={{ flex: 1, overflow: 'auto', background: '#f5f5f5' }}>
              {previewLoading ? (
                <div style={{ textAlign: 'center', paddingTop: 80 }}>
                  <Spin size="large" tip="Loading preview..." />
                </div>
              ) : (
                <iframe
                  srcDoc={previewHtml}
                  style={{ width: '100%', height: '100%', border: 'none', background: 'white' }}
                  title="Section Preview"
                />
              )}
            </div>
          ) : node.content_type === 'richtext' ? (
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
          ) : node.content_type === 'static_table' ? (
            <div style={{ padding: 16, overflow: 'auto', flex: 1 }}>
              <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <Button size="small" icon={<PlusOutlined />} onClick={addRow}>Add Row</Button>
                <Button size="small" icon={<PlusOutlined />} onClick={addColumn}>Add Column</Button>
                <span style={{ width: 1, height: 20, background: '#d9d9d9', margin: '0 4px' }} />
                <Button size="small" icon={<ColumnWidthOutlined />} onClick={handleMerge}>Merge Cells</Button>
                <Button size="small" icon={<ColumnHeightOutlined />} onClick={handleUnmerge}>Unmerge</Button>
                <div style={{ flex: 1 }} />
                {activeCell && (
                  <span style={{ fontSize: 12, color: '#1890ff', background: '#e6f7ff', padding: '2px 8px', borderRadius: 4 }}>
                    Cell: {activeCell.row + 1}×{activeCell.col + 1}
                    {(() => {
                      const { entry } = isCellMerged(activeCell.row, activeCell.col);
                      return entry ? ` (merged ${entry.rowspan}×${entry.colspan})` : '';
                    })()}
                  </span>
                )}
                {!activeCell && node?.content_type === 'static_table' && showPicker && (
                  <span style={{ fontSize: 12, color: '#999' }}>Click a cell to select it</span>
                )}
                {dirty && <span style={{ color: '#ff4d4f', fontSize: 12 }}>Unsaved changes</span>}
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ width: 30, padding: 4 }}></th>
                    {tableColumns.map((col, ci) => {
                      const { master, entry } = isCellMerged(0, ci);
                      if (!master) return null;
                      const cs = entry?.colspan || 1;
                      return (
                        <th key={ci} colSpan={cs} style={{ border: '1px solid #d9d9d9', padding: 4, background: '#fafafa', position: 'relative' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <input
                              value={col}
                              onChange={e => handleTableHeaderChange(ci, e.target.value)}
                              style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontWeight: 600, textAlign: 'center', fontSize: 13 }}
                            />
                            <DeleteOutlined
                              style={{ color: '#ff4d4f', fontSize: 11, cursor: tableColumns.length > 1 ? 'pointer' : 'not-allowed', opacity: tableColumns.length > 1 ? 1 : 0.3 }}
                              onClick={() => removeColumn(ci)}
                            />
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row, ri) => {
                    const rowHasMaster = (() => {
                      for (let c = 0; c < row.length; c++) {
                        const { master } = isCellMerged(ri, c);
                        if (master) return true;
                      }
                      return false;
                    })();
                    if (!rowHasMaster) return null;
                    return (
                      <tr key={ri}>
                        <td style={{ textAlign: 'center', verticalAlign: 'top', paddingTop: 8 }}>
                          <DeleteOutlined
                            style={{ color: '#ff4d4f', fontSize: 11, cursor: tableRows.length > 1 ? 'pointer' : 'not-allowed', opacity: tableRows.length > 1 ? 1 : 0.3 }}
                            onClick={() => removeRow(ri)}
                          />
                        </td>
                        {renderTableCells(ri, row)}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div style={{ marginTop: 8, color: '#999', fontSize: 11 }}>
                Tip: Click a cell then Shift+click another to select a range, then click <strong>Merge Cells</strong>. Use <code>{'{{variable_name}}'}</code> in cells to auto-populate data.
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
              usedVariables={
                node?.content_type === 'static_table'
                  ? Array.from(tableRows.flat().join(' ').matchAll(/\{\{(\w+:?\w+)\}\}/g)).map(m => m[1])
                  : Array.from(content.matchAll(/\{\{(\w+:?\w+)\}\}/g)).map(m => m[1])
              }
              calculationId={calculationId}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default ContentPane;
