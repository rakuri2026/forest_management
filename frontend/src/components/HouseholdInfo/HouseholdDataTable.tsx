/**
 * Household Data Table
 * Displays household records with inline editing
 */
import React, { useState } from 'react';
import { Table, Button, Tag, Popconfirm, message, Space, Tooltip, Form, InputNumber, Input, Select, Modal } from 'antd';
import { DeleteOutlined, EditOutlined, ReloadOutlined, SaveOutlined, CloseOutlined, PlusOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import * as api from '../../services/api';
import type { HouseholdInfo } from '../../types/household';
import HouseholdVariablePanel from './HouseholdVariablePanel';

interface HouseholdDataTableProps {
  households: HouseholdInfo[];
  onRefresh: () => void;
  calculationId: string;
}

interface EditableCellProps {
  editing: boolean;
  dataIndex: string;
  title: string;
  inputType: 'number' | 'text' | 'select';
  record: HouseholdInfo;
  index: number;
  children: React.ReactNode;
  selectOptions?: { label: string; value: any }[];
}

const EditableCell: React.FC<EditableCellProps> = ({
  editing,
  dataIndex,
  title,
  inputType,
  record,
  index,
  children,
  selectOptions,
  ...restProps
}) => {
  let inputNode: React.ReactNode;

  if (inputType === 'number') {
    inputNode = <InputNumber style={{ width: '100%' }} min={0} />;
  } else if (inputType === 'select' && selectOptions) {
    inputNode = <Select options={selectOptions} style={{ width: '100%' }} />;
  } else {
    inputNode = <Input />;
  }

  return (
    <td {...restProps}>
      {editing ? (
        <Form.Item
          name={dataIndex}
          style={{ margin: 0 }}
          rules={[
            {
              required: ['surname', 'female_count', 'male_count'].includes(dataIndex),
              message: `Please input ${title}!`,
            },
          ]}
        >
          {inputNode}
        </Form.Item>
      ) : (
        children
      )}
    </td>
  );
};

const HouseholdDataTable: React.FC<HouseholdDataTableProps> = ({
  households,
  onRefresh,
  calculationId,
}) => {
  const [form] = Form.useForm();
  const [addForm] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const [autoSaving, setAutoSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [originalData, setOriginalData] = useState<Record<string, HouseholdInfo>>({});
  const autoSaveTimerRef = React.useRef<NodeJS.Timeout | null>(null);

  // Add household modal state
  const [isAddModalVisible, setIsAddModalVisible] = useState(false);
  const [isAdding, setIsAdding] = useState(false);

  const isEditing = (record: HouseholdInfo) => record.id === editingKey;

  // Auto-save effect
  React.useEffect(() => {
    if (editingKey) {
      // Clear existing timer
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }

      // Set new timer for 2 minutes (120000ms)
      autoSaveTimerRef.current = setTimeout(() => {
        handleAutoSave();
      }, 120000); // 2 minutes

      return () => {
        if (autoSaveTimerRef.current) {
          clearTimeout(autoSaveTimerRef.current);
        }
      };
    }
  }, [editingKey, form]);

  const handleAutoSave = async () => {
    if (!editingKey) return;

    try {
      const row = await form.validateFields();
      setAutoSaving(true);

      // Perform save
      const updateData = { ...row };
      const originalRecord = households.find(h => h.id === editingKey);

      if (originalRecord) {
        if (row.firewood_demand_bhari !== undefined &&
            Number(row.firewood_demand_bhari) !== Number(originalRecord.firewood_demand_bhari)) {
          updateData.firewood_auto_calculated = false;
        }
        if (row.grass_demand_bhari !== undefined &&
            Number(row.grass_demand_bhari) !== Number(originalRecord.grass_demand_bhari)) {
          updateData.grass_auto_calculated = false;
        }
        if (row.bedding_demand_bhari !== undefined &&
            Number(row.bedding_demand_bhari) !== Number(originalRecord.bedding_demand_bhari)) {
          updateData.bedding_auto_calculated = false;
        }
      }

      await api.userGroupApi.updateHousehold(editingKey, updateData);

      setLastSaved(new Date());
      message.success('Auto-saved successfully', 2);
      setOriginalData(prev => {
        const newData = { ...prev };
        delete newData[editingKey];
        return newData;
      });
      onRefresh();
    } catch (error: any) {
      console.error('Auto-save error:', error);
      message.warning('Auto-save failed. Please save manually.', 3);
    } finally {
      setAutoSaving(false);
    }
  };

  const edit = (record: HouseholdInfo) => {
    form.setFieldsValue({
      house_no: record.house_no,
      surname: record.surname,
      household_head_male: record.household_head_male,
      household_head_female: record.household_head_female,
      address_tole: record.address_tole,
      female_count: record.female_count,
      male_count: record.male_count,
      land_area: record.land_area ? Number(record.land_area) : undefined,
      land_unit: record.land_unit,
      cow_ox_count: record.cow_ox_count,
      buffalo_count: record.buffalo_count,
      goat_sheep_count: record.goat_sheep_count,
      timber_demand_cft: Number(record.timber_demand_cft),
      pole_demand: record.pole_demand,
      firewood_demand_bhari: record.firewood_demand_bhari ? Number(record.firewood_demand_bhari) : undefined,
      grass_demand_bhari: record.grass_demand_bhari ? Number(record.grass_demand_bhari) : undefined,
      bedding_demand_bhari: record.bedding_demand_bhari ? Number(record.bedding_demand_bhari) : undefined,
      caste_classification_ne: record.caste_classification_ne,
      prosperity_level: record.prosperity_level,
      forest_based_occupation: record.forest_based_occupation,
      remarks: record.remarks,
    });
    setOriginalData(prev => ({ ...prev, [record.id]: record }));
    setEditingKey(record.id);
  };

  const revertChanges = (record: HouseholdInfo) => {
    const original = originalData[record.id];
    if (original) {
      form.setFieldsValue({
        house_no: original.house_no,
        surname: original.surname,
        household_head_male: original.household_head_male,
        household_head_female: original.household_head_female,
        address_tole: original.address_tole,
        female_count: original.female_count,
        male_count: original.male_count,
        land_area: original.land_area ? Number(original.land_area) : undefined,
        land_unit: original.land_unit,
        cow_ox_count: original.cow_ox_count,
        buffalo_count: original.buffalo_count,
        goat_sheep_count: original.goat_sheep_count,
        timber_demand_cft: Number(original.timber_demand_cft),
        pole_demand: original.pole_demand,
        firewood_demand_bhari: original.firewood_demand_bhari ? Number(original.firewood_demand_bhari) : undefined,
        grass_demand_bhari: original.grass_demand_bhari ? Number(original.grass_demand_bhari) : undefined,
        bedding_demand_bhari: original.bedding_demand_bhari ? Number(original.bedding_demand_bhari) : undefined,
        caste_classification_ne: original.caste_classification_ne,
        prosperity_level: original.prosperity_level,
        forest_based_occupation: original.forest_based_occupation,
        remarks: original.remarks,
      });
      message.info('Reverted to original values');
    }
  };

  const cancel = () => {
    setEditingKey('');
    setLastSaved(null);
    setOriginalData(prev => {
      const newData = { ...prev };
      delete newData[editingKey];
      return newData;
    });
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
  };

  const save = async (id: string) => {
    try {
      const row = await form.validateFields();
      setSavingIds((prev) => new Set(prev).add(id));

      const updateData: any = { ...row };

      // Handle auto-calculated field flags
      const originalRecord = households.find(h => h.id === id);
      if (originalRecord) {
        if (row.firewood_demand_bhari !== undefined &&
            Number(row.firewood_demand_bhari) !== Number(originalRecord.firewood_demand_bhari)) {
          updateData.firewood_auto_calculated = false;
        }
        if (row.grass_demand_bhari !== undefined &&
            Number(row.grass_demand_bhari) !== Number(originalRecord.grass_demand_bhari)) {
          updateData.grass_auto_calculated = false;
        }
        if (row.bedding_demand_bhari !== undefined &&
            Number(row.bedding_demand_bhari) !== Number(originalRecord.bedding_demand_bhari)) {
          updateData.bedding_auto_calculated = false;
        }
        if (row.prosperity_level !== undefined &&
            row.prosperity_level !== originalRecord.prosperity_level) {
          updateData.prosperity_auto_suggested = false;
        }
        if (row.caste_classification_ne !== undefined &&
            row.caste_classification_ne !== originalRecord.caste_classification_ne) {
          updateData.caste_classification_manual = true;
        }
        if (row.forest_based_occupation !== undefined &&
            row.forest_based_occupation !== originalRecord.forest_based_occupation) {
          // No flag needed, just save the value
        }
      }

      console.log('Saving household:', id, updateData);
      try {
        const response = await api.userGroupApi.updateHousehold(id, updateData);
        console.log('Save response:', response);
      } catch (saveError: any) {
        console.error('Save error details:', saveError);
        throw saveError;
      }

      message.success('Household updated successfully');
      setEditingKey('');
      setLastSaved(null);
      setOriginalData(prev => {
        const newData = { ...prev };
        delete newData[id];
        return newData;
      });
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
      onRefresh();
    } catch (error: any) {
      if (error?.errorFields) {
        message.error('Please fill in all required fields');
      } else {
        console.error('Error updating household:', error);
        message.error(error.response?.data?.detail || 'Failed to update household');
      }
    } finally {
      setSavingIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingIds((prev) => new Set(prev).add(id));
    try {
      await api.userGroupApi.deleteHousehold(id);
      message.success('Household deleted successfully');
      onRefresh();
    } catch (error) {
      console.error('Error deleting household:', error);
      message.error('Failed to delete household');
    } finally {
      setDeletingIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };

  const handleShowAddModal = () => {
    addForm.resetFields();
    // Set default values
    addForm.setFieldsValue({
      land_unit: 'ropani',
      cow_ox_count: 0,
      buffalo_count: 0,
      goat_sheep_count: 0,
      timber_demand_cft: 0,
      pole_demand: 0,
      forest_based_occupation: false,
    });
    setIsAddModalVisible(true);
  };

  const handleAddCancel = () => {
    setIsAddModalVisible(false);
    addForm.resetFields();
  };

  const handleAdd = async (values: any) => {
    setIsAdding(true);
    try {
      // Prepare the data
      const addData = {
        ...values,
        // Convert numeric values
        house_no: Number(values.house_no),
        female_count: Number(values.female_count),
        male_count: Number(values.male_count),
        land_area: values.land_area ? Number(values.land_area) : 0,
        cow_ox_count: values.cow_ox_count || 0,
        buffalo_count: values.buffalo_count || 0,
        goat_sheep_count: values.goat_sheep_count || 0,
        timber_demand_cft: values.timber_demand_cft || 0,
        pole_demand: values.pole_demand || 0,
        firewood_demand_bhari: values.firewood_demand_bhari || undefined,
        grass_demand_bhari: values.grass_demand_bhari || undefined,
        bedding_demand_bhari: values.bedding_demand_bhari || undefined,
      };

      await api.userGroupApi.createHousehold(calculationId, addData);
      message.success('Household added successfully');
      setIsAddModalVisible(false);
      addForm.resetFields();
      onRefresh();
    } catch (error: any) {
      console.error('Error adding household:', error);
      message.error(error.response?.data?.detail || 'Failed to add household');
    } finally {
      setIsAdding(false);
    }
  };

  const columns: ColumnsType<HouseholdInfo> = [
    {
      title: 'House No',
      dataIndex: 'house_no',
      key: 'house_no',
      width: 90,
      fixed: 'left',
      sorter: (a, b) => a.house_no - b.house_no,
      editable: true,
      render: (value: number, record: HouseholdInfo) => (
        <Tag color="blue">{value}</Tag>
      ),
    },
    {
      title: 'Surname (थर)',
      dataIndex: 'surname',
      key: 'surname',
      width: 150,
      fixed: 'left',
      editable: true,
    },
    {
      title: 'Male Head',
      dataIndex: 'household_head_male',
      key: 'household_head_male',
      width: 150,
      ellipsis: true,
      editable: true,
    },
    {
      title: 'Female Head',
      dataIndex: 'household_head_female',
      key: 'household_head_female',
      width: 150,
      ellipsis: true,
      editable: true,
    },
    {
      title: 'Address',
      dataIndex: 'address_tole',
      key: 'address_tole',
      width: 150,
      ellipsis: true,
      editable: true,
    },
    {
      title: 'Female',
      dataIndex: 'female_count',
      key: 'female_count',
      width: 90,
      editable: true,
    },
    {
      title: 'Male',
      dataIndex: 'male_count',
      key: 'male_count',
      width: 90,
      editable: true,
    },
    {
      title: 'Land Area',
      dataIndex: 'land_area',
      key: 'land_area',
      width: 120,
      editable: true,
      render: (value: any, record: HouseholdInfo) =>
        value ? `${Number(value).toFixed(2)} ${record.land_unit || ''}` : '-',
    },
    {
      title: 'Land Unit',
      dataIndex: 'land_unit',
      key: 'land_unit',
      width: 110,
      editable: true,
      selectOptions: [
        { label: 'Ropani', value: 'ropani' },
        { label: 'Kaththa', value: 'kaththa' },
      ],
    },
    {
      title: 'Cow/Ox',
      dataIndex: 'cow_ox_count',
      key: 'cow_ox_count',
      width: 90,
      editable: true,
    },
    {
      title: 'Buffalo',
      dataIndex: 'buffalo_count',
      key: 'buffalo_count',
      width: 90,
      editable: true,
    },
    {
      title: 'Goat/Sheep',
      dataIndex: 'goat_sheep_count',
      key: 'goat_sheep_count',
      width: 110,
      editable: true,
    },
    {
      title: 'Firewood (भारी)',
      dataIndex: 'firewood_demand_bhari',
      key: 'firewood_demand_bhari',
      width: 140,
      editable: true,
      render: (value: any, record: HouseholdInfo) => (
        <Space>
          <span>{value ? Number(value).toFixed(1) : '0.0'}</span>
          {record.firewood_auto_calculated !== false ? (
            <Tag icon={<ReloadOutlined />} color="green" size="small">Auto</Tag>
          ) : (
            <Tag icon={<EditOutlined />} color="orange" size="small">Manual</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Grass (भारी)',
      dataIndex: 'grass_demand_bhari',
      key: 'grass_demand_bhari',
      width: 140,
      editable: true,
      render: (value: any, record: HouseholdInfo) => (
        <Space>
          <span>{value ? Number(value).toFixed(1) : '0.0'}</span>
          {record.grass_auto_calculated !== false ? (
            <Tag icon={<ReloadOutlined />} color="green" size="small">Auto</Tag>
          ) : (
            <Tag icon={<EditOutlined />} color="orange" size="small">Manual</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Bedding (भारी)',
      dataIndex: 'bedding_demand_bhari',
      key: 'bedding_demand_bhari',
      width: 140,
      editable: true,
      render: (value: any, record: HouseholdInfo) => (
        <Space>
          <span>{value ? Number(value).toFixed(1) : '0.0'}</span>
          {record.bedding_auto_calculated !== false ? (
            <Tag icon={<ReloadOutlined />} color="green" size="small">Auto</Tag>
          ) : (
            <Tag icon={<EditOutlined />} color="orange" size="small">Manual</Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Timber (cft)',
      dataIndex: 'timber_demand_cft',
      key: 'timber_demand_cft',
      width: 110,
      editable: true,
      render: (value: any) => Number(value).toFixed(1),
    },
    {
      title: 'Poles',
      dataIndex: 'pole_demand',
      key: 'pole_demand',
      width: 90,
      editable: true,
    },
    {
      title: 'Caste Classification',
      dataIndex: 'caste_classification_ne',
      key: 'caste_classification_ne',
      width: 180,
      editable: true,
      selectOptions: [
        { label: 'जनजाती', value: 'जनजाती' },
        { label: 'दलित', value: 'दलित' },
        { label: 'सीमान्तकृत', value: 'सीमान्तकृत' },
        { label: 'अति सीमान्तकृत', value: 'अति सीमान्तकृत' },
        { label: 'लोपोन्मुख र सीमान्तकृत', value: 'लोपोन्मुख र सीमान्तकृत' },
        { label: 'अन्य', value: 'अन्य' },
      ],
      render: (value: string, record: HouseholdInfo) => (
        <Space direction="vertical" size={0}>
          <Tag color={record.caste_classification_manual === true ? 'orange' : 'green'}>
            {value || 'N/A'}
          </Tag>
          {record.caste_classification_manual === true && (
            <Tag icon={<EditOutlined />} color="orange" style={{ fontSize: 10 }}>
              Manual
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Prosperity Level',
      dataIndex: 'prosperity_level',
      key: 'prosperity_level',
      width: 130,
      editable: true,
      selectOptions: [
        { label: 'अति विपन्न', value: 'अति विपन्न' },
        { label: 'विपन्न', value: 'विपन्न' },
        { label: 'मध्यम', value: 'मध्यम' },
        { label: 'सम्पन्न', value: 'सम्पन्न' },
      ],
      render: (value: string, record: HouseholdInfo) => {
        const colorMap: Record<string, string> = {
          'सम्पन्न': 'green',
          'मध्यम': 'blue',
          'विपन्न': 'orange',
          'अति विपन्न': 'red',
        };
        return (
          <Space direction="vertical" size={0}>
            <Tag color={colorMap[value] || 'default'}>{value}</Tag>
            {record.prosperity_auto_suggested !== false && (
              <Tag color="green" style={{ fontSize: 10 }}>Auto</Tag>
            )}
          </Space>
        );
      },
    },
    {
      title: 'Forest Occupation',
      dataIndex: 'forest_based_occupation',
      key: 'forest_occupation',
      width: 120,
      editable: true,
      selectOptions: [
        { label: 'Yes', value: true },
        { label: 'No', value: false },
      ],
      render: (value: boolean, record: HouseholdInfo) =>
        record.forest_based_occupation ? (
          <Tag color="green">Yes</Tag>
        ) : (
          <Tag>No</Tag>
        ),
    },
    {
      title: 'Remarks',
      dataIndex: 'remarks',
      key: 'remarks',
      width: 150,
      ellipsis: true,
      editable: true,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 280,
      fixed: 'right',
      render: (_: any, record: HouseholdInfo) => {
        const editable = isEditing(record);
        return editable ? (
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space>
              <Button
                type="primary"
                size="small"
                icon={<SaveOutlined />}
                onClick={() => save(record.id)}
                loading={savingIds.has(record.id)}
              >
                Save
              </Button>
              <Tooltip title="Revert to original values">
                <Button 
                  size="small" 
                  icon={<ReloadOutlined />} 
                  onClick={() => revertChanges(record)}
                  disabled={!originalData[record.id]}
                >
                  Revert
                </Button>
              </Tooltip>
              <Button size="small" icon={<CloseOutlined />} onClick={cancel}>
                Cancel
              </Button>
            </Space>
            {autoSaving && (
              <Tag color="processing" icon={<ReloadOutlined spin />} style={{ margin: 0 }}>
                Auto-saving...
              </Tag>
            )}
          </Space>
        ) : (
          <Space>
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => edit(record)}
              disabled={editingKey !== ''}
            >
              Edit
            </Button>
            <Popconfirm
              title="Delete this household?"
              description="This action cannot be undone."
              onConfirm={() => handleDelete(record.id)}
              okText="Yes"
              cancelText="No"
            >
              <Button
                danger
                size="small"
                icon={<DeleteOutlined />}
                loading={deletingIds.has(record.id)}
                disabled={editingKey !== ''}
              >
                Delete
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  const mergedColumns = columns.map((col: any) => {
    if (!col.editable) {
      return col;
    }
    const selectFields = ['land_unit', 'prosperity_level', 'caste_classification_ne', 'forest_occupation'];
    const numberFields = ['female_count', 'male_count', 'cow_ox_count', 'buffalo_count', 'goat_sheep_count',
                    'timber_demand_cft', 'pole_demand', 'land_area', 'firewood_demand_bhari',
                    'grass_demand_bhari', 'bedding_demand_bhari', 'house_no'];
    return {
      ...col,
      onCell: (record: HouseholdInfo) => ({
        record,
        inputType: selectFields.includes(col.dataIndex) ? 'select' :
                   numberFields.includes(col.dataIndex) ? 'number' : 'text',
        dataIndex: col.dataIndex,
        title: col.title,
        editing: isEditing(record),
        selectOptions: col.selectOptions,
      }),
    };
  });

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <Space wrap>
          <Tag color="blue">💡 Click "Edit" to modify any row (Excel-like editing)</Tag>
          <Tag color="green" icon={<ReloadOutlined />}>Auto-calculated</Tag>
          <Tag color="orange" icon={<EditOutlined />}>Manually entered</Tag>
        </Space>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleShowAddModal}
            disabled={editingKey !== ''}
          >
            Add Household
          </Button>
          {editingKey && (
            <Tag color="purple" icon={autoSaving ? <ReloadOutlined spin /> : <ReloadOutlined />}>
              {autoSaving ? 'Auto-saving...' : 'Auto-save: Every 2 min'}
            </Tag>
          )}
          {lastSaved && (
            <Tag color="green">
              Last saved: {lastSaved.toLocaleTimeString()}
            </Tag>
          )}
        </Space>
      </div>

      <Form form={form} component={false}>
        <Table
          components={{
            body: {
              cell: EditableCell,
            },
          }}
          dataSource={households}
          columns={mergedColumns}
          rowKey="id"
          scroll={{ x: 2800, y: 600 }}
          pagination={{
            pageSize: 20,
            showSizeChanger: true,
            showTotal: (total) => `Total ${total} households`,
            onChange: cancel,
          }}
          size="small"
          bordered
        />
      </Form>

      {/* Variable Panel + Notes Section */}
      <div style={{ marginTop: 24, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 60%', minWidth: 300 }}>
          <div style={{
            border: '1px solid #d9d9d9',
            borderRadius: 6,
            padding: 12,
            background: '#fafafa',
          }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: 13 }}>
              अतिरिक्त विवरण / नोट (Additional Notes)
            </h4>
            <textarea
              id="household-notes"
              rows={4}
              style={{
                width: '100%',
                border: '1px solid #d9d9d9',
                borderRadius: 4,
                padding: '8px 12px',
                fontSize: 13,
                lineHeight: 1.6,
                fontFamily: 'inherit',
                resize: 'vertical',
              }}
              placeholder="चर सम्मिलित गर्न दायाँ प्यानलको 'सम्मिलित' बटन प्रयोग गर्नुहोस्।"
            />
          </div>
        </div>
        <div style={{ flex: '0 0 340px' }}>
          <HouseholdVariablePanel
            calculationId={calculationId}
            tabKey="households"
            onInsert={(varStr) => {
              const ta = document.getElementById('household-notes') as HTMLTextAreaElement;
              if (ta) {
                const start = ta.selectionStart;
                const end = ta.selectionEnd;
                ta.value = ta.value.substring(0, start) + varStr + ta.value.substring(end);
                ta.focus();
                ta.selectionStart = ta.selectionEnd = start + varStr.length;
              }
            }}
          />
        </div>
      </div>

      {/* Add Household Modal */}
      <Modal
        title="Add New Household"
        open={isAddModalVisible}
        onCancel={handleAddCancel}
        footer={null}
        width={800}
        destroyOnClose
      >
        <Form
          form={addForm}
          layout="vertical"
          onFinish={handleAdd}
        >
          <div style={{ maxHeight: '60vh', overflowY: 'auto', padding: '0 8px' }}>
            {/* Basic Information */}
            <h3 style={{ borderBottom: '1px solid #d9d9d9', paddingBottom: 8 }}>Basic Information</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Form.Item
                label="House No (घर नं.)"
                name="house_no"
                rules={[{ required: true, message: 'House number is required' }]}
              >
                <InputNumber style={{ width: '100%' }} min={1} />
              </Form.Item>

              <Form.Item
                label="Surname (थर)"
                name="surname"
                rules={[{ required: true, message: 'Surname is required' }]}
              >
                <Input />
              </Form.Item>

              <Form.Item
                label="Male Head (घरमुली पुरुष)"
                name="household_head_male"
              >
                <Input />
              </Form.Item>

              <Form.Item
                label="Female Head (घरमुली महिला)"
                name="household_head_female"
              >
                <Input />
              </Form.Item>

              <Form.Item
                label="Address (ठेगाना)"
                name="address_tole"
              >
                <Input />
              </Form.Item>
            </div>

            {/* Family Members */}
            <h3 style={{ borderBottom: '1px solid #d9d9d9', paddingBottom: 8, marginTop: 16 }}>Family Members</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Form.Item
                label="Female Count (महिला संख्या)"
                name="female_count"
                rules={[{ required: true, message: 'Female count is required' }]}
              >
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>

              <Form.Item
                label="Male Count (पुरुष संख्या)"
                name="male_count"
                rules={[{ required: true, message: 'Male count is required' }]}
              >
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
            </div>

            {/* Land & Livestock */}
            <h3 style={{ borderBottom: '1px solid #d9d9d9', paddingBottom: 8, marginTop: 16 }}>Land & Livestock</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Form.Item
                label="Land Area (जग्गा क्षेत्रफल)"
                name="land_area"
              >
                <InputNumber style={{ width: '100%' }} min={0} step={0.01} />
              </Form.Item>

              <Form.Item
                label="Land Unit (एकाई)"
                name="land_unit"
              >
                <Select>
                  <Select.Option value="ropani">Ropani</Select.Option>
                  <Select.Option value="kaththa">Kaththa</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="Cow/Ox (गाई/गोरु)"
                name="cow_ox_count"
              >
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>

              <Form.Item
                label="Buffalo (भैंसी)"
                name="buffalo_count"
              >
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>

              <Form.Item
                label="Goat/Sheep (बाख्रा/भेडा)"
                name="goat_sheep_count"
              >
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
            </div>

            {/* Forest Product Demand */}
            <h3 style={{ borderBottom: '1px solid #d9d9d9', paddingBottom: 8, marginTop: 16 }}>Forest Product Demand</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Form.Item
                label="Timber Demand (काठ माग cft)"
                name="timber_demand_cft"
              >
                <InputNumber style={{ width: '100%' }} min={0} step={0.1} />
              </Form.Item>

              <Form.Item
                label="Pole Demand (डल्लो माग)"
                name="pole_demand"
              >
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>

              <Form.Item
                label="Firewood Demand (दाउरा भारी)"
                name="firewood_demand_bhari"
                extra="Leave blank for auto-calculation"
              >
                <InputNumber style={{ width: '100%' }} min={0} step={0.1} />
              </Form.Item>

              <Form.Item
                label="Grass Demand (घाँस भारी)"
                name="grass_demand_bhari"
                extra="Leave blank for auto-calculation"
              >
                <InputNumber style={{ width: '100%' }} min={0} step={0.1} />
              </Form.Item>

              <Form.Item
                label="Bedding Demand (ओछ्यान भारी)"
                name="bedding_demand_bhari"
                extra="Leave blank for auto-calculation"
              >
                <InputNumber style={{ width: '100%' }} min={0} step={0.1} />
              </Form.Item>
            </div>

            {/* Classification */}
            <h3 style={{ borderBottom: '1px solid #d9d9d9', paddingBottom: 8, marginTop: 16 }}>Classification</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <Form.Item
                label="Caste Classification (जातीय वर्गीकरण)"
                name="caste_classification_ne"
              >
                <Select>
                  <Select.Option value="जनजाती">जनजाती</Select.Option>
                  <Select.Option value="दलित">दलित</Select.Option>
                  <Select.Option value="सीमान्तकृत">सीमान्तकृत</Select.Option>
                  <Select.Option value="अति सीमान्तकृत">अति सीमान्तकृत</Select.Option>
                  <Select.Option value="लोपोन्मुख र सीमान्तकृत">लोपोन्मुख र सीमान्तकृत</Select.Option>
                  <Select.Option value="अन्य">अन्य</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="Prosperity Level (समृद्धि स्तर)"
                name="prosperity_level"
              >
                <Select>
                  <Select.Option value="अति विपन्न">अति विपन्न</Select.Option>
                  <Select.Option value="विपन्न">विपन्न</Select.Option>
                  <Select.Option value="मध्यम">मध्यम</Select.Option>
                  <Select.Option value="सम्पन्न">सम्पन्न</Select.Option>
                </Select>
              </Form.Item>

              <Form.Item
                label="Forest Based Occupation (वन आधारित पेशा)"
                name="forest_based_occupation"
              >
                <Select>
                  <Select.Option value={true}>Yes</Select.Option>
                  <Select.Option value={false}>No</Select.Option>
                </Select>
              </Form.Item>
            </div>

            {/* Remarks */}
            <h3 style={{ borderBottom: '1px solid #d9d9d9', paddingBottom: 8, marginTop: 16 }}>Additional Information</h3>
            <Form.Item
              label="Remarks (कैफियत)"
              name="remarks"
            >
              <Input.TextArea rows={3} />
            </Form.Item>
          </div>

          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: '8px', borderTop: '1px solid #d9d9d9', paddingTop: 16 }}>
            <Button onClick={handleAddCancel}>
              Cancel
            </Button>
            <Button type="primary" htmlType="submit" loading={isAdding}>
              Add Household
            </Button>
          </div>
        </Form>
      </Modal>
    </div>
  );
};

export default HouseholdDataTable;
