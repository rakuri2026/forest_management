/**
 * Household Information Tab
 * Main container for household survey data management
 */
import React, { useState, useEffect } from 'react';
import { Alert, Tabs, Spin, Button, Modal, message } from 'antd';
import {
  FileTextOutlined,
  UploadOutlined,
  TableOutlined,
  BarChartOutlined,
  DeleteOutlined,
  ReloadOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import * as api from '../../services/api';
import type { HouseholdInfo, HouseholdSummary } from '../../types/household';
import TemplateDownloadSection from './TemplateDownloadSection';
import FileUploadSection from './FileUploadSection';
import HouseholdDataTable from './HouseholdDataTable';
import HouseholdSummaryDashboard from './HouseholdSummary';
import CommitteeManagement from './CommitteeManagement';

interface HouseholdInfoTabProps {
  calculationId: string;
}

const HouseholdInfoTab: React.FC<HouseholdInfoTabProps> = ({
  calculationId,
}) => {
  const [households, setHouseholds] = useState<HouseholdInfo[]>([]);
  const [summary, setSummary] = useState<HouseholdSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [activeTab, setActiveTab] = useState('1');

  // Load household data
  const loadHouseholds = async () => {
    setLoading(true);
    try {
      const data = await api.userGroupApi.getHouseholds(calculationId);
      setHouseholds(data);

      // If we have data, also load summary
      if (data.length > 0) {
        const summaryData = await api.userGroupApi.getHouseholdSummary(calculationId);
        setSummary(summaryData);
      } else {
        setSummary(null);
      }
    } catch (error: any) {
      // If 404, no data exists yet - this is OK
      if (error.response?.status === 404) {
        setHouseholds([]);
        setSummary(null);
      } else {
        console.error('Error loading households:', error);
        message.error('Failed to load household data');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHouseholds();
  }, [calculationId, refreshKey]);

  // Handle successful upload
  const handleUploadSuccess = () => {
    message.success('Household data imported successfully!');
    setRefreshKey((prev) => prev + 1);
    setActiveTab('3'); // Switch to data table tab
  };

  // Handle delete all
  const handleDeleteAll = () => {
    Modal.confirm({
      title: 'Delete All Household Data?',
      content: `This will permanently delete all ${households.length} household records. This action cannot be undone.`,
      okText: 'Yes, Delete All',
      okType: 'danger',
      cancelText: 'Cancel',
      onOk: async () => {
        try {
          await api.userGroupApi.deleteAllHouseholds(calculationId);
          message.success('All household data deleted');
          setRefreshKey((prev) => prev + 1);
          setActiveTab('1');
        } catch (error) {
          console.error('Error deleting households:', error);
          message.error('Failed to delete household data');
        }
      },
    });
  };

  // Handle export
  const handleExport = async () => {
    try {
      const blob = await api.userGroupApi.exportHouseholdAnalysis(calculationId);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `household_analysis_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      message.success('Analysis exported successfully');
    } catch (error) {
      console.error('Error exporting analysis:', error);
      message.error('Failed to export analysis');
    }
  };

  const hasData = households.length > 0;

  const items = [
    {
      key: '1',
      label: (
        <span>
          <FileTextOutlined /> Download Template
        </span>
      ),
      children: (
        <TemplateDownloadSection
          calculationId={calculationId}
          hasExistingData={hasData}
        />
      ),
    },
    {
      key: '2',
      label: (
        <span>
          <UploadOutlined /> Upload Data
        </span>
      ),
      children: (
        <FileUploadSection
          calculationId={calculationId}
          hasExistingData={hasData}
          onUploadSuccess={handleUploadSuccess}
        />
      ),
      disabled: !hasData && false, // Always allow upload
    },
    {
      key: '3',
      label: (
        <span>
          <TableOutlined /> Household Data {hasData && `(${households.length})`}
        </span>
      ),
      children: hasData ? (
        <HouseholdDataTable
          households={households}
          onRefresh={() => setRefreshKey((prev) => prev + 1)}
          calculationId={calculationId}
        />
      ) : (
        <Alert
          message="No Data Available"
          description="Upload household data using the template to view the table here."
          type="info"
          showIcon
        />
      ),
    },
    {
      key: '4',
      label: (
        <span>
          <BarChartOutlined /> Summary & Analysis
        </span>
      ),
      children: hasData && summary ? (
        <HouseholdSummaryDashboard summary={summary} />
      ) : (
        <Alert
          message="No Data to Analyze"
          description="Upload household data to view summary statistics and charts."
          type="info"
          showIcon
        />
      ),
    },
    {
      key: '5',
      label: (
        <span>
          <TeamOutlined /> Forest User Committee
        </span>
      ),
      children: (
        <CommitteeManagement calculationId={calculationId} />
      ),
    },
  ];

  return (
    <div style={{ padding: '20px' }}>
      <div
        style={{
          marginBottom: 20,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <h2 style={{ margin: 0 }}>Household Information</h2>
          <p style={{ margin: '5px 0 0 0', color: '#666' }}>
            Manage household survey data for forest user groups
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {hasData && (
            <>
              <Button icon={<ReloadOutlined />} onClick={() => setRefreshKey((prev) => prev + 1)}>
                Refresh
              </Button>
              <Button icon={<UploadOutlined />} onClick={handleExport}>
                Export Analysis
              </Button>
              <Button
                icon={<DeleteOutlined />}
                danger
                onClick={handleDeleteAll}
              >
                Delete All Data
              </Button>
            </>
          )}
        </div>
      </div>

      {hasData && (
        <Alert
          message={`${households.length} Household Records`}
          description={`Total Population: ${summary?.total_population || 0} | Forest Dependent: ${summary?.forest_dependent_households || 0}`}
          type="success"
          showIcon
          style={{ marginBottom: 20 }}
        />
      )}

      <Spin spinning={loading}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={items}
          type="card"
        />
      </Spin>
    </div>
  );
};

export default HouseholdInfoTab;
