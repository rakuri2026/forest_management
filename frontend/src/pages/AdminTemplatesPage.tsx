import React, { useState, useEffect } from 'react';
import { List, Tag, Typography, Spin, Empty, Button, message, Modal, Input, Space, Alert, Descriptions, Tooltip } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, EyeOutlined, SendOutlined } from '@ant-design/icons';
import { operationalPlanApi } from '../services/api';

const { Text, Title } = Typography;
const { TextArea } = Input;

interface PendingTemplate {
  id: string;
  name: string;
  description: string;
  tags: string[];
  created_by?: string | null;
  updated_at: string;
}

const AdminTemplatesPage: React.FC = () => {
  const [templates, setTemplates] = useState<PendingTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionModal, setActionModal] = useState<{ open: boolean; template: PendingTemplate | null; action: 'approve' | 'reject' }>({ open: false, template: null, action: 'approve' });
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchPending();
  }, []);

  const fetchPending = async () => {
    setLoading(true);
    try {
      const res = await operationalPlanApi.listPendingTemplates();
      setTemplates(res.templates || []);
    } catch {
      message.error('Failed to load pending templates');
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async () => {
    if (!actionModal.template) return;
    setSubmitting(true);
    try {
      await operationalPlanApi.reviewTemplate(actionModal.template.id, actionModal.action, note);
      message.success(`Template ${actionModal.action === 'approve' ? 'approved' : 'rejected'} successfully`);
      setActionModal({ open: false, template: null, action: 'approve' });
      setNote('');
      fetchPending();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || `Failed to ${actionModal.action} template`);
    } finally {
      setSubmitting(false);
    }
  };

  const openAction = (tmpl: PendingTemplate, action: 'approve' | 'reject') => {
    setActionModal({ open: true, template: tmpl, action });
    setNote('');
  };

  return (
    <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
      <Title level={3}><ClockCircleOutlined /> Pending Template Approvals</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
        Review templates submitted by users for global approval. Approved templates become available to all users.
      </Text>

      <Alert
        message="Super Admin Only"
        description="Only users with super_admin role can approve or reject templates."
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
      ) : templates.length === 0 ? (
        <Empty description="No pending approvals. All templates have been reviewed." />
      ) : (
        <List
          dataSource={templates}
          renderItem={(tmpl) => (
            <List.Item
              actions={[
                <Tooltip key="approve" title="Approve as global template">
                  <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    onClick={() => openAction(tmpl, 'approve')}
                  >
                    Approve
                  </Button>
                </Tooltip>,
                <Tooltip key="reject" title="Reject with note">
                  <Button
                    danger
                    icon={<CloseCircleOutlined />}
                    onClick={() => openAction(tmpl, 'reject')}
                  >
                    Reject
                  </Button>
                </Tooltip>,
              ]}
            >
              <List.Item.Meta
                title={<Text strong>{tmpl.name}</Text>}
                description={
                  <div>
                    <Text type="secondary">{tmpl.description || 'No description'}</Text>
                    <div style={{ marginTop: 4 }}>
                      {tmpl.tags?.map(t => <Tag key={t} style={{ fontSize: 11 }}>{t}</Tag>)}
                    </div>
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      Submitted by: {tmpl.created_by || 'Unknown'} &middot; {new Date(tmpl.updated_at).toLocaleDateString()}
                    </Text>
                  </div>
                }
              />
            </List.Item>
          )}
        />
      )}

      <Modal
        title={actionModal.action === 'approve' ? 'Approve Template' : 'Reject Template'}
        open={actionModal.open}
        onCancel={() => setActionModal({ ...actionModal, open: false })}
        onOk={handleReview}
        confirmLoading={submitting}
        okText={actionModal.action === 'approve' ? 'Approve' : 'Reject'}
        okButtonProps={{ danger: actionModal.action === 'reject' }}
      >
        <div style={{ marginBottom: 12 }}>
          <Text strong>{actionModal.template?.name}</Text>
        </div>
        {actionModal.action === 'reject' && (
          <div style={{ marginBottom: 8 }}>
            <Text type="danger">Provide a reason for rejection (required):</Text>
          </div>
        )}
        <TextArea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder={actionModal.action === 'approve' ? 'Optional approval note' : 'Reason for rejection...'}
        />
      </Modal>
    </div>
  );
};

export default AdminTemplatesPage;
