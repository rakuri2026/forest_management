import React, { useState } from 'react';
import { Drawer, Button, Spin, message } from 'antd';
import { EyeOutlined, CloseOutlined } from '@ant-design/icons';
import { operationalPlanApi } from '../../services/api';

interface PreviewDrawerProps {
  planId: string;
  forestName?: string;
}

const PreviewDrawer: React.FC<PreviewDrawerProps> = ({ planId, forestName }) => {
  const [open, setOpen] = useState(false);
  const [html, setHtml] = useState('');
  const [loading, setLoading] = useState(false);

  const handleOpen = async () => {
    setOpen(true);
    setLoading(true);
    try {
      const content = await operationalPlanApi.previewOperationalPlan(planId);
      setHtml(content);
    } catch {
      message.error('Failed to load preview');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Button icon={<EyeOutlined />} size="small" onClick={handleOpen}>
        Preview
      </Button>
      <Drawer
        title={`Preview — ${forestName || 'Operational Plan'}`}
        placement="right"
        size="large"
        onClose={() => setOpen(false)}
        open={open}
        extra={<Button icon={<CloseOutlined />} onClick={() => setOpen(false)} type="text" />}
      >
        {loading ? (
          <div style={{ textAlign: 'center', paddingTop: 80 }}>
            <Spin size="large" tip="Generating preview..." />
          </div>
        ) : (
          <iframe
            srcDoc={html}
            style={{ width: '100%', height: '100%', border: 'none' }}
            title="Operational Plan Preview"
          />
        )}
      </Drawer>
    </>
  );
};

export default PreviewDrawer;
