import React, { useState, useEffect } from 'react';
import { Tabs, Button, message, Space, Spin, Table, InputNumber, Select, Form, Card, Statistic, Row, Col } from 'antd';
import type { TabsProps, ColumnsType } from 'antd/es/table';
import { PlusOutlined, ReloadOutlined, CheckCircleOutlined, SaveOutlined, EditOutlined } from '@ant-design/icons';
import { yearlyActivitiesApi, forestApi } from '../services/api';
import ActivityMapView from './YearlyActivities/ActivityMapView';

interface YearlyActivitiesTabProps {
  calculationId: string;
}

const YearlyActivitiesTab: React.FC<YearlyActivitiesTabProps> = ({ calculationId }) => {
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [potentialActivities, setPotentialActivities] = useState<any[]>([]);
  const [proposedActivities, setProposedActivities] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [blocks, setBlocks] = useState<any[]>([]);
  const [subAreas, setSubAreas] = useState<any[]>([]);
  const [editingKey, setEditingKey] = useState<string>('');
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
      setProposedActivities(proposed);
      setSummary(summaryData);

      // Load blocks from result_data
      if (calc.result_data?.blocks) {
        setBlocks(calc.result_data.blocks);
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
        // Add activity - use parsed values or defaults (must be > 0 per schema)
        const quantity = parseFloat(potentialActivity.quantity) || 1;
        const budget = parseFloat(potentialActivity.yearly_budget) || 10000;

        await yearlyActivitiesApi.createProposedActivity(calculationId, {
          potential_activity_id: potentialActivity.id,
          default_quantity: quantity,
          default_yearly_budget: budget
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
        default_yearly_budget: proposed.default_yearly_budget,
        block_id: proposed.block_id,
        sub_area_id: proposed.sub_area_id
      });
      setEditingKey(record.id);
    }
  };

  const cancel = () => {
    setEditingKey('');
  };

  const save = async (record: any) => {
    try {
      const row = await form.validateFields();
      const proposed = getProposedActivity(record.id);

      if (proposed) {
        await yearlyActivitiesApi.updateProposedActivity(proposed.id, {
          default_quantity: row.default_quantity,
          default_yearly_budget: row.default_yearly_budget,
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
      title: 'Project',
      dataIndex: 'project_name',
      key: 'project_name',
      width: 150,
    },
    {
      title: 'Program',
      dataIndex: 'program',
      key: 'program',
      width: 150,
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
      width: 150,
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
      title: 'Budget (per year)',
      key: 'budget',
      width: 150,
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return '-';

        const proposed = getProposedActivity(record.id);
        const editable = isEditing(record);

        return editable ? (
          <Form.Item
            name="default_yearly_budget"
            style={{ margin: 0 }}
            rules={[{ required: true, message: 'Required' }]}
          >
            <InputNumber
              min={0}
              formatter={value => `NPR ${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={(value: any) => value!.replace(/NPR\s?|(,*)/g, '')}
              style={{ width: '100%' }}
            />
          </Form.Item>
        ) : (
          <span>NPR {proposed ? Number(proposed.default_yearly_budget).toLocaleString() : '-'}</span>
        );
      }
    },
    {
      title: 'Block',
      key: 'block',
      width: 150,
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return '-';

        const proposed = getProposedActivity(record.id);
        const editable = isEditing(record);

        return editable ? (
          <Form.Item name="block_id" style={{ margin: 0 }}>
            <Select
              placeholder="Select block"
              allowClear
              options={blocks.map(b => ({ label: b.block_name || b.name, value: b.id }))}
              onChange={(blockId) => {
                // Reset sub-area when block changes
                form.setFieldValue('sub_area_id', undefined);
              }}
            />
          </Form.Item>
        ) : (
          <span>{proposed?.block_name || 'All blocks'}</span>
        );
      }
    },
    {
      title: 'Sub-Area',
      key: 'sub_area',
      width: 180,
      render: (_, record) => {
        if (!isActivitySelected(record.id)) return '-';

        const proposed = getProposedActivity(record.id);
        const editable = isEditing(record);
        const blockId = form.getFieldValue('block_id');

        return editable ? (
          <Form.Item
            name="sub_area_id"
            style={{ margin: 0 }}
            dependencies={['block_id']}
          >
            <Select
              placeholder={blockId ? "Select sub-area" : "Select block first"}
              allowClear
              disabled={!blockId}
              options={subAreas
                .filter(sa => sa.block_id === blockId)
                .map(sa => ({
                  label: `${sa.name} (${sa.category})`,
                  value: sa.id
                }))}
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
        ) : (
          <span>
            {proposed?.sub_area_name ? (
              <>
                {proposed.sub_area_name}
                {proposed.sub_area_category && (
                  <span style={{ marginLeft: 4, color: '#888', fontSize: '0.9em' }}>
                    ({proposed.sub_area_category})
                  </span>
                )}
              </>
            ) : (
              'All sub-areas'
            )}
          </span>
        );
      }
    },
    {
      title: 'Action',
      key: 'action',
      width: 120,
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
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => edit(record)}
            disabled={editingKey !== ''}
            size="small"
          >
            Edit
          </Button>
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
            dataSource={potentialActivities}
            rowKey="id"
            pagination={{ pageSize: 20 }}
            scroll={{ x: 1400 }}
            size="small"
            loading={loading}
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
      </div>
    </Spin>
  );
};

export default YearlyActivitiesTab;
