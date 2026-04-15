import React, { useState, useEffect } from 'react';
import { Tabs, Button, message, Space, Spin, Table, InputNumber, Select, Form, Card, Statistic, Row, Col, Modal, Popover } from 'antd';
import type { TabsProps, ColumnsType } from 'antd/es/table';
import { PlusOutlined, ReloadOutlined, CheckCircleOutlined, SaveOutlined, EditOutlined, CalendarOutlined, EnvironmentOutlined } from '@ant-design/icons';
import { yearlyActivitiesApi, forestApi } from '../services/api';
import ActivityMapView from './YearlyActivities/ActivityMapView';
import YearDetailEditor from './YearlyActivities/YearDetailEditor';
import BlockSubAreaSelector from './YearlyActivities/BlockSubAreaSelector';

interface YearlyActivitiesTabProps {
  calculationId: string;
}

const YearlyActivitiesTab: React.FC<YearlyActivitiesTabProps> = ({ calculationId }) => {
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [potentialActivities, setPotentialActivities] = useState<any[]>([]);
  const [groupedActivities, setGroupedActivities] = useState<any[]>([]);
  const [proposedActivities, setProposedActivities] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [blocks, setBlocks] = useState<any[]>([]);
  const [blocksWithSubAreas, setBlocksWithSubAreas] = useState<any[]>([]);
  const [subAreas, setSubAreas] = useState<any[]>([]);
  const [editingKey, setEditingKey] = useState<string>('');
  const [yearDetailVisible, setYearDetailVisible] = useState(false);
  const [selectedActivity, setSelectedActivity] = useState<any>(null);
  const [blockSelectorVisible, setBlockSelectorVisible] = useState(false);
  const [blockSelectorActivity, setBlockSelectorActivity] = useState<any>(null);
  const [selectedAllBlocks, setSelectedAllBlocks] = useState(true);
  const [selectedBlocks, setSelectedBlocks] = useState<string[]>([]);
  const [selectedSubAreas, setSelectedSubAreas] = useState<string[]>([]);
  const [form] = Form.useForm();

  // Load data on mount
  useEffect(() => {
    loadData();
  }, [calculationId, refreshKey]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [potential, proposed, summaryData, calc] = await Promise.all([
        yearlyActivitiesApi.listPotentialActivities({ is_active: true }),
        yearlyActivitiesApi.listProposedActivities(calculationId),
        yearlyActivitiesApi.getSummary(calculationId).catch(() => null),
        forestApi.getCalculation(calculationId)
      ]);

      setPotentialActivities(potential);
      
      // Fetch proposed activities and then get spatial assignments for each
      const proposedWithSpatial = await Promise.all(
        proposed.map(async (pa: any) => {
          try {
            const spatial = await yearlyActivitiesApi.getSpatialAssignments(pa.id);
            return { ...pa, spatial_assignments: spatial };
          } catch {
            return pa;
          }
        })
      );
      
      setProposedActivities(proposedWithSpatial);
      setSummary(summaryData);

      // Group by program for expandable table
      const grouped = groupActivitiesByProgram(potential);
      setGroupedActivities(grouped);

      // Load blocks from result_data
      if (calc.result_data?.blocks) {
        setBlocks(calc.result_data.blocks);
      }

      // Load blocks with sub-areas for selector
      try {
        const blocksWithSub = await yearlyActivitiesApi.getBlocksWithSubareas(calculationId);
        setBlocksWithSubAreas(blocksWithSub);
      } catch (err) {
        console.error('Failed to load blocks with sub-areas', err);
      }

      // Load sub-areas
      try {
        const subAreasData = await forestApi.listSubAreas(calculationId);
        setSubAreas(subAreasData?.sub_areas || subAreasData || []);
      } catch (err) {
        console.error('Failed to load sub-areas', err);
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to load activities');
    } finally {
      setLoading(false);
    }
  };

  // Toggle activity selection
  const handleToggleActivity = async (potentialActivity: any, checked: boolean) => {
    try {
      if (checked) {
        // Add activity - budget entered in thousands, convert to actual value
        const quantity = parseFloat(potentialActivity.quantity) || 1;
        const yearlyBudgetRaw = parseFloat(potentialActivity.yearly_budget) || 5;
        const yearlyBudget = yearlyBudgetRaw * 1000; // Convert to actual NPR

        await yearlyActivitiesApi.createProposedActivity(calculationId, {
          potential_activity_id: potentialActivity.id,
          default_quantity: quantity,
          default_yearly_budget: yearlyBudget
        });
        message.success(`Added: ${potentialActivity.activity}`);
      } else {
        // Find and remove activity
        const proposed = proposedActivities.find(
          pa => pa.potential_activity_id === potentialActivity.id
        );
        if (proposed) {
          await yearlyActivitiesApi.deleteProposedActivity(proposed.id);
          message.success(`Removed: ${potentialActivity.activity}`);
        }
      }
      setRefreshKey(prev => prev + 1);
    } catch (error: any) {
      const errorDetail = error.response?.data?.detail;
      const errorMessage = Array.isArray(errorDetail) 
        ? errorDetail.map((e: any) => e.msg || JSON.stringify(e)).join(', ')
        : errorDetail || 'Failed to update activity';
      message.error(errorMessage);
    }
  };

  // Check if activity is selected
  const isActivitySelected = (potentialActivityId: number) => {
    return proposedActivities.some(pa => pa.potential_activity_id === potentialActivityId);
  };

  // Get proposed activity for a potential activity
  const getProposedActivity = (potentialActivityId: number) => {
    return proposedActivities.find(pa => pa.potential_activity_id === potentialActivityId);
  };

  // Edit mode
  const isEditing = (record: any) => record.id === editingKey;

  const edit = (record: any) => {
    const proposed = getProposedActivity(record.id);
    if (proposed) {
      form.setFieldsValue({
        default_quantity: proposed.default_quantity,
        default_yearly_budget: Math.round((proposed.default_yearly_budget || 5000) / 1000),
        block_id: proposed.block_id,
        sub_area_id: proposed.sub_area_id
      });
      setEditingKey(record.id);
    }
  };

  const cancel = () => {
    setEditingKey('');
  };

  // Block/Sub-Area selector handlers
  const handleBlockSelectorOpen = (record: any) => {
    const proposed = getProposedActivity(record.id);
    if (proposed) {
      setBlockSelectorActivity(proposed);
      // Load current spatial assignments
      yearlyActivitiesApi.getSpatialAssignments(proposed.id).then((assignments: any[]) => {
        if (assignments.length === 0 || assignments.some((a: any) => a.assignment_type === 'all_blocks')) {
          setSelectedAllBlocks(true);
          setSelectedBlocks([]);
          setSelectedSubAreas([]);
        } else {
          setSelectedAllBlocks(false);
          const blockIds: string[] = [];
          const subAreaIds: string[] = [];
          assignments.forEach((a: any) => {
            if (a.sub_area_id) {
              subAreaIds.push(a.sub_area_id);
            } else if (a.block_id) {
              blockIds.push(a.block_id);
            }
          });
          setSelectedBlocks(blockIds);
          setSelectedSubAreas(subAreaIds);
        }
        setBlockSelectorVisible(true);
      }).catch(() => {
        setSelectedAllBlocks(true);
        setSelectedBlocks([]);
        setSelectedSubAreas([]);
        setBlockSelectorVisible(true);
      });
    }
  };

  const handleBlockSelectorChange = (type: 'all' | 'block' | 'sub_area', id?: string, checked?: boolean) => {
    if (type === 'all') {
      setSelectedAllBlocks(checked || false);
      if (checked) {
        setSelectedBlocks([]);
        setSelectedSubAreas([]);
      }
    } else if (type === 'block' && id) {
      setSelectedAllBlocks(false);
      if (checked) {
        setSelectedBlocks(prev => {
          if (prev.includes(id)) return prev;
          return [...prev, id];
        });
      } else {
        setSelectedBlocks(prev => prev.filter(b => b !== id));
        setSelectedSubAreas(prev => {
          const block = blocksWithSubAreas.find(b => b.block_id === id);
          const subAreaIdsInBlock = block?.sub_areas?.map(sa => sa.id) || [];
          return prev.filter(saId => !subAreaIdsInBlock.includes(saId));
        });
      }
    } else if (type === 'sub_area' && id) {
      setSelectedAllBlocks(false);
      
      const subArea = subAreas.find(sa => sa.id === id);
      const blockId = subArea?.block_id;
      
      if (checked) {
        if (blockId && !selectedBlocks.includes(blockId)) {
          setSelectedBlocks(prev => [...prev, blockId]);
        }
        setSelectedSubAreas(prev => {
          if (prev.includes(id)) return prev;
          return [...prev, id];
        });
      } else {
        setSelectedSubAreas(prev => prev.filter(s => s !== id));
        
        if (blockId) {
          const block = blocksWithSubAreas.find(b => b.block_id === blockId);
          const remainingSubAreasInBlock = block?.sub_areas?.filter(
            sa => selectedSubAreas.includes(sa.id) && sa.id !== id
          ) || [];
          
          if (remainingSubAreasInBlock.length === 0) {
            setSelectedBlocks(prev => prev.filter(b => b !== blockId));
          }
        }
      }
    }
  };

  const handleBlockSelectorSave = async () => {
    if (!blockSelectorActivity) return;
    
    try {
      // First, get existing assignments and delete them
      const existingAssignments = await yearlyActivitiesApi.getSpatialAssignments(blockSelectorActivity.id);
      for (const assignment of existingAssignments) {
        await yearlyActivitiesApi.deleteSpatialAssignment(blockSelectorActivity.id, assignment.id);
      }

      if (selectedAllBlocks) {
        // Create single "all blocks" assignment
        await yearlyActivitiesApi.createSpatialAssignment(blockSelectorActivity.id, {
          assignment_type: 'all_blocks'
        });
      } else {
        // Create individual block/sub-area assignments
        // Only create block-level assignment if block is selected AND no sub-areas from that block
        for (const blockId of selectedBlocks) {
          const block = blocksWithSubAreas.find(b => b.block_id === blockId);
          const subAreaIdsInBlock = block?.sub_areas?.map(sa => sa.id) || [];
          const selectedSubAreasInBlock = selectedSubAreas.filter(saId => subAreaIdsInBlock.includes(saId));
          
          if (selectedSubAreasInBlock.length === 0) {
            await yearlyActivitiesApi.createSpatialAssignment(blockSelectorActivity.id, {
              block_id: blockId,
              assignment_type: 'block'
            });
          }
        }
        
        // Create sub-area assignments (which include block_id automatically)
        for (const subAreaId of selectedSubAreas) {
          const subArea = subAreas.find(sa => sa.id === subAreaId);
          if (subArea) {
            await yearlyActivitiesApi.createSpatialAssignment(blockSelectorActivity.id, {
              block_id: subArea.block_id,
              sub_area_id: subAreaId,
              assignment_type: 'sub_area'
            });
          }
        }
      }

      message.success('Block/Sub-Area assignment saved');
      setBlockSelectorVisible(false);
      setRefreshKey(prev => prev + 1);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to save assignments');
    }
  };

  // Group activities by program
  const groupActivitiesByProgram = (activities: any[]) => {
    const groups: Record<string, any[]> = {};
    
    activities.forEach(act => {
      const program = act.program || 'Unassigned';
      if (!groups[program]) {
        groups[program] = [];
      }
      groups[program].push(act);
    });

    // Convert to array with expandable structure - use index to make keys unique
    return Object.entries(groups).map(([program, items], programIndex) => ({
      key: `group-${programIndex}-${program}`,
      program,
      count: items.length,
      children: items.map((item, itemIndex) => ({ 
        ...item, 
        // Ensure unique key by combining program index, item index, and ID
        key: `prog-${programIndex}-item-${itemIndex}-${item.id || item.sn}`,
        // Also ensure unique id for selection checks
        uniqueKey: `${program}-${item.id || item.sn}-${itemIndex}`
      }))
    }));
  };

  const save = async (record: any) => {
    try {
      const row = await form.validateFields();
      const proposed = getProposedActivity(record.id);

      if (proposed) {
        await yearlyActivitiesApi.updateProposedActivity(proposed.id, {
          default_quantity: row.default_quantity,
          default_yearly_budget: row.default_yearly_budget * 1000,
          block_id: row.block_id || null,
          sub_area_id: row.sub_area_id || null
        });
        message.success('Saved successfully');
        setEditingKey('');
        setRefreshKey(prev => prev + 1);
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to save');
    }
  };

  // Activity selection table columns
  const columns: ColumnsType<any> = [
    {
      title: 'SN',
      dataIndex: 'sn',
      key: 'sn',
      width: 40,
      fixed: 'left',
    },
    {
      title: '✓',
      key: 'checkbox',
      width: 50,
      fixed: 'left',
      render: (_, record) => (
        <input
          type="checkbox"
          checked={isActivitySelected(record.id)}
          onChange={(e) => handleToggleActivity(record, e.target.checked)}
        />
      )
    },
    {
      title: 'Program',
      dataIndex: 'program',
      key: 'program',
      width: 150,
      render: (text: string, record: any) => {
        if (record.children) {
          return <strong>{text} ({record.count})</strong>;
        }
        return null;
      },
    },
    {
      title: 'Activity',
      dataIndex: 'activity',
      key: 'activity',
      width: 200,
      render: (text, record) => (
        <>
          {text}
          {record.is_default === 'True' && <span style={{ marginLeft: 8, color: '#1890ff' }}>(Default)</span>}
        </>
      )
    },
    {
      title: 'Unit',
      dataIndex: 'unit',
      key: 'unit',
      width: 80
    },
    {
      title: 'Quantity (per year)',
      key: 'quantity',
      width: 120,
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return '-';

        const proposed = getProposedActivity(record.id);
        const editable = isEditing(record);

        return editable ? (
          <Form.Item
            name="default_quantity"
            style={{ margin: 0 }}
            rules={[{ required: true, message: 'Required' }]}
          >
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
        ) : (
          <span>{proposed ? Number(proposed.default_quantity).toLocaleString() : '-'}</span>
        );
      }
    },
    {
      title: 'Budget',
      key: 'budget',
      width: 100,
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return '-';

        const proposed = getProposedActivity(record.id);
        const editable = isEditing(record);
        const budgetValue = proposed?.default_yearly_budget || 5000;
        const displayInThousands = Math.round(budgetValue / 1000);

        return editable ? (
          <Form.Item
            name="default_yearly_budget"
            style={{ margin: 0 }}
            rules={[{ required: true, message: 'Required' }]}
          >
            <InputNumber
              min={0}
              placeholder="Enter in thousands"
              formatter={value => `${value || 0}ह`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={(value: any) => {
                const parsed = parseFloat(value!.replace(/हs?|(,*)/g, '')) || 0;
                return parsed * 1000;
              }}
              style={{ width: '100%' }}
            />
          </Form.Item>
        ) : (
          <span title={`NPR ${budgetValue.toLocaleString()}`}>{displayInThousands}ह</span>
        );
      }
    },
    {
      title: 'Block/Sub-Area',
      key: 'block',
      width: 180,
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return '-';

        const proposed = getProposedActivity(record.id);
        const editable = isEditing(record);

        if (editable) {
          return (
            <Form.Item name="block_id" style={{ margin: 0 }}>
              <Select
                placeholder="Select block"
                allowClear
                options={blocks.map(b => ({ label: b.block_name || b.name, value: b.id }))}
                onChange={(blockId) => {
                  form.setFieldValue('sub_area_id', undefined);
                }}
              />
            </Form.Item>
          );
        }

        return (
          <Popover
            content={
              <BlockSubAreaSelector
                blocks={blocksWithSubAreas}
                selectedAllBlocks={proposed?.assign_to_all_blocks || !proposed?.spatial_assignments?.length}
                selectedBlocks={proposed?.spatial_assignments?.filter((a: any) => a.block_id && !a.sub_area_id).map((a: any) => a.block_id) || []}
                selectedSubAreas={proposed?.spatial_assignments?.filter((a: any) => a.sub_area_id).map((a: any) => a.sub_area_id) || []}
                onChange={() => {}}
              />
            }
            title="Current Assignment"
            trigger="hover"
          >
            <Button 
              type="link" 
              size="small"
              onClick={() => handleBlockSelectorOpen(record)}
              style={{ whiteSpace: 'pre-line', textAlign: 'left', height: 'auto', minHeight: '22px', padding: '2px 4px' }}
            >
              {proposed?.assign_to_all_blocks ? 'All blocks' : 
                proposed?.spatial_assignments?.length > 0 
                  ? proposed.spatial_assignments.map((a: any) => {
                      if (a.sub_area_name) {
                        return `${a.sub_area_name}\n(${a.block_name})`;
                      }
                      return a.block_name;
                    }).filter(Boolean).join('\n')
                  : 'Select blocks'
              }
            </Button>
          </Popover>
        );
      }
    },
    {
      title: 'Map',
      key: 'map',
      width: 60,
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return '-';
        
        const canMap = record.requires_map === true;
        const proposed = getProposedActivity(record.id);
        
        return canMap ? (
          <Button 
            type="link" 
            size="small" 
            title="Manage spatial features per year"
            onClick={() => {
              if (proposed) {
                setSelectedActivity(proposed);
                setYearDetailVisible(true);
              }
            }}
          >
            📍
          </Button>
        ) : (
          <span style={{ color: '#ccc' }}>📍</span>
        );
      }
    },
    {
      title: 'Action',
      key: 'action',
      width: 100,
      fixed: 'right',
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return null;

        const editable = isEditing(record);
        return editable ? (
          <Space>
            <Button
              type="link"
              icon={<SaveOutlined />}
              onClick={() => save(record)}
              size="small"
            >
              Save
            </Button>
            <Button type="link" onClick={cancel} size="small">
              Cancel
            </Button>
          </Space>
        ) : (
          <Space>
            <Button
              type="link"
              icon={<CalendarOutlined />}
              onClick={() => {
                const proposed = getProposedActivity(record.id);
                if (proposed) {
                  setSelectedActivity(proposed);
                  setYearDetailVisible(true);
                }
              }}
              size="small"
              title="Year Details"
            />
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => edit(record)}
              disabled={editingKey !== ''}
              size="small"
            >
              Edit
            </Button>
          </Space>
        );
      }
    }
  ];

  // Summary tab content
  const summaryContent = (
    <div style={{ padding: '16px' }}>
      {summary ? (
        <>
          <Row gutter={16} style={{ marginBottom: '24px' }}>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Total Activities"
                  value={summary.total_activities}
                  suffix="activities"
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Total Budget (10 Years)"
                  value={Number(summary.total_budget_10_years)}
                  prefix="NPR"
                  precision={0}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Average Yearly Budget"
                  value={Number(summary.total_budget_10_years) / 10}
                  prefix="NPR"
                  precision={0}
                />
              </Card>
            </Col>
          </Row>

          <Card title="Activities by Project" style={{ marginBottom: '16px' }}>
            {Object.entries(summary.by_project || {}).map(([project, count]) => (
              <div key={project} style={{ marginBottom: '8px' }}>
                <strong>{project}:</strong> {count as number} activities
              </div>
            ))}
          </Card>

          <Card title="Activities by Block">
            {Object.entries(summary.by_block || {}).map(([block, count]) => (
              <div key={block} style={{ marginBottom: '8px' }}>
                <strong>{block}:</strong> {count as number} activities
              </div>
            ))}
          </Card>
        </>
      ) : (
        <p>No activities selected yet. Go to Activity Selection tab to add activities.</p>
      )}
    </div>
  );

  const tabItems: TabsProps['items'] = [
    {
      key: '1',
      label: 'Activity Selection',
      children: (
        <Form form={form} component={false}>
          <Table
            columns={columns}
            dataSource={groupedActivities}
            rowKey="key"
            pagination={false}
            scroll={{ x: 900 }}
            size="small"
            loading={loading}
            expandable={{
              expandedRowRender: (record) => (
                <Table
                  columns={columns}
                  dataSource={record.children}
                  rowKey="key"
                  pagination={false}
                  size="small"
                  title={() => `${record.program} - ${record.count} activities`}
                />
              ),
              rowExpandable: (record) => record.count > 0
            }}
          />
        </Form>
      )
    },
    {
      key: '2',
      label: 'Map View',
      children: (
        <ActivityMapView calculationId={calculationId} />
      )
    },
    {
      key: '3',
      label: 'Summary',
      children: summaryContent
    }
  ];

  return (
    <Spin spinning={loading}>
      <div style={{ padding: '16px' }}>
        <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between' }}>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => setRefreshKey(prev => prev + 1)}>
              Refresh
            </Button>
          </Space>

          {summary && (
            <Space>
              <span><strong>Total Activities:</strong> {summary.total_activities}</span>
              <span><strong>Total Budget (10 years):</strong> NPR {Number(summary.total_budget_10_years).toLocaleString()}</span>
            </Space>
          )}
        </div>

        <Tabs items={tabItems} />

        <YearDetailEditor
          visible={yearDetailVisible}
          onClose={() => {
            setYearDetailVisible(false);
            setSelectedActivity(null);
          }}
          proposedActivity={selectedActivity}
          onSaved={() => setRefreshKey(prev => prev + 1)}
        />

        <Modal
          title="Select Block/Sub-Area"
          open={blockSelectorVisible}
          onOk={handleBlockSelectorSave}
          onCancel={() => setBlockSelectorVisible(false)}
          width={400}
          okText="Save"
        >
          <BlockSubAreaSelector
            blocks={blocksWithSubAreas}
            selectedAllBlocks={selectedAllBlocks}
            selectedBlocks={selectedBlocks}
            selectedSubAreas={selectedSubAreas}
            onChange={handleBlockSelectorChange}
          />
        </Modal>
      </div>
    </Spin>
  );
};

export default YearlyActivitiesTab;
