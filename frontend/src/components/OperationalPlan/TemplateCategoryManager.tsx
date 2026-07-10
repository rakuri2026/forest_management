import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Input, Form, message, Space, Tag, Popconfirm, Tooltip, ColorPicker } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SortAscendingOutlined } from '@ant-design/icons';
import { operationalPlanApi } from '../../services/api';

const { TextArea } = Input;

interface Category {
  id: string;
  key: string;
  label_ne: string;
  label_en: string;
  description: string;
  color: string;
  sort_order: number;
}

const TemplateCategoryManager: React.FC = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    setLoading(true);
    try {
      const data = await operationalPlanApi.listTemplateCategories();
      setCategories(data || []);
    } catch {
      message.error('Failed to load categories');
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = (cat: Category) => {
    setEditing(cat);
    form.setFieldsValue(cat);
    setModalOpen(true);
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      if (editing) {
        await operationalPlanApi.updateTemplateCategory(editing.id, values);
        message.success('Category updated');
      } else {
        await operationalPlanApi.createTemplateCategory(values);
        message.success('Category created');
      }
      setModalOpen(false);
      fetchCategories();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to save category');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await operationalPlanApi.deleteTemplateCategory(id);
      message.success('Category deleted');
      fetchCategories();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to delete category');
    }
  };

  const columns = [
    {
      title: 'Sort',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 60,
    },
    {
      title: 'Key',
      dataIndex: 'key',
      key: 'key',
      width: 120,
    },
    {
      title: 'Label (EN)',
      dataIndex: 'label_en',
      key: 'label_en',
    },
    {
      title: 'Label (NE)',
      dataIndex: 'label_ne',
      key: 'label_ne',
    },
    {
      title: 'Color',
      dataIndex: 'color',
      key: 'color',
      width: 100,
      render: (color: string) => <Tag color={color || 'default'}>{color || 'default'}</Tag>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_: any, record: Category) => (
        <Space>
          <Tooltip title="Edit">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          </Tooltip>
          <Popconfirm title="Delete this category?" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="Delete">
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          <SortAscendingOutlined style={{ marginRight: 8 }} />
          <strong>{categories.length}</strong> categories defined
        </span>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          Add Category
        </Button>
      </div>

      <Table
        dataSource={categories}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
      />

      <Modal
        title={editing ? 'Edit Category' : 'Create Category'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        okText={editing ? 'Update' : 'Create'}
        width={520}
      >
        <Form form={form} layout="vertical">
          {!editing && (
            <Form.Item name="key" label="Key" rules={[{ required: true, message: 'Enter a unique key (e.g. community_forest)' }]}>
              <Input placeholder="community_forest" />
            </Form.Item>
          )}
          <Form.Item name="label_en" label="Label (English)" rules={[{ required: true }]}>
            <Input placeholder="Community Forest" />
          </Form.Item>
          <Form.Item name="label_ne" label="Label (Nepali)" rules={[{ required: true }]}>
            <Input placeholder="सामुदायिक वन" />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <TextArea rows={2} placeholder="Brief description of this category" />
          </Form.Item>
          <Space>
            <Form.Item name="color" label="Tag Color">
              <Input placeholder="green, blue, purple, orange, red" />
            </Form.Item>
            <Form.Item name="sort_order" label="Sort Order">
              <Input type="number" style={{ width: 80 }} placeholder="0" />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
};

export default TemplateCategoryManager;
