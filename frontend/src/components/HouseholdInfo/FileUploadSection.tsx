/**
 * File Upload Section
 * Handles Excel (.xlsx, .xls) and CSV file upload with validation preview
 */
import React, { useState } from 'react';
import { Upload, Button, Card, Alert, Table, Tag, Space, message, Modal, Form, Input, InputNumber, Select } from 'antd';
import { UploadOutlined, CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, PlusOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import * as api from '../../services/api';
import type { HouseholdUploadResponse, HouseholdUploadValidation } from '../../types/household';

interface FileUploadSectionProps {
  calculationId: string;
  hasExistingData: boolean;
  onUploadSuccess: () => void;
}

const FileUploadSection: React.FC<FileUploadSectionProps> = ({
  calculationId,
  hasExistingData,
  onUploadSuccess,
}) => {
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<HouseholdUploadResponse | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [addForm] = Form.useForm();
  const [adding, setAdding] = useState(false);

  const handleUpload = async () => {
    if (!selectedFile) {
      message.warning('Please select a file first');
      return;
    }

    setUploading(true);
    try {
      const result = await api.userGroupApi.uploadHouseholdData(calculationId, selectedFile);
      setUploadResult(result);

      if (result.success && (result.records_imported > 0 || result.records_updated > 0)) {
        const updatedMsg = result.records_updated > 0
          ? `, updated ${result.records_updated} existing record${result.records_updated > 1 ? 's' : ''}`
          : '';
        const importedMsg = result.records_imported > 0
          ? `Successfully imported ${result.records_imported} new record${result.records_imported > 1 ? 's' : ''}`
          : '';

        const finalMsg = importedMsg && updatedMsg
          ? `${importedMsg}${updatedMsg}.`
          : importedMsg
          ? `${importedMsg}.`
          : `Successfully updated ${result.records_updated} existing record${result.records_updated > 1 ? 's' : ''}.`;

        Modal.success({
          title: 'Upload Successful!',
          content: finalMsg,
          onOk: () => {
            onUploadSuccess();
          },
        });
      } else if (result.invalid_rows > 0) {
        Modal.warning({
          title: 'Upload Completed with Errors',
          content: `${result.valid_rows} valid records, ${result.invalid_rows} invalid records. Review the validation results below.`,
        });
      }
    } catch (error: any) {
      console.error('Error uploading file:', error);
      message.error(error.response?.data?.detail || 'Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const uploadProps: UploadProps = {
    accept: '.xlsx,.xls,.csv',
    multiple: false,
    maxCount: 1,
    beforeUpload: (file) => {
      setSelectedFile(file);
      setUploadResult(null);
      return false; // Prevent auto upload
    },
    onRemove: () => {
      setSelectedFile(null);
      setUploadResult(null);
    },
  };

  const validationColumns = [
    {
      title: 'Row',
      dataIndex: 'row_number',
      key: 'row_number',
      width: 80,
    },
    {
      title: 'Status',
      key: 'status',
      width: 100,
      render: (_: any, record: HouseholdUploadValidation) => (
        record.is_valid ? (
          <Tag icon={<CheckCircleOutlined />} color="success">Valid</Tag>
        ) : (
          <Tag icon={<CloseCircleOutlined />} color="error">Invalid</Tag>
        )
      ),
    },
    {
      title: 'House No',
      key: 'house_no',
      width: 100,
      render: (_: any, record: HouseholdUploadValidation) => record.data?.house_no || '-',
    },
    {
      title: 'Surname',
      key: 'surname',
      width: 120,
      render: (_: any, record: HouseholdUploadValidation) => record.data?.surname || '-',
    },
    {
      title: 'Errors',
      dataIndex: 'errors',
      key: 'errors',
      render: (errors: string[]) => (
        errors.length > 0 ? (
          <Space direction="vertical" size={0}>
            {errors.map((error, idx) => (
              <Tag key={idx} color="red" icon={<CloseCircleOutlined />}>
                {error}
              </Tag>
            ))}
          </Space>
        ) : (
          <Tag color="success">No errors</Tag>
        )
      ),
    },
    {
      title: 'Warnings',
      dataIndex: 'warnings',
      key: 'warnings',
      render: (warnings: string[]) => (
        warnings.length > 0 ? (
          <Space direction="vertical" size={0}>
            {warnings.map((warning, idx) => (
              <Tag key={idx} color="orange" icon={<WarningOutlined />}>
                {warning}
              </Tag>
            ))}
          </Space>
        ) : null
      ),
    },
  ];

  const handleAddHousehold = async (values: any) => {
    setAdding(true);
    try {
      await api.userGroupApi.createHousehold(calculationId, values);
      message.success('Household added successfully');
      setAddModalVisible(false);
      addForm.resetFields();
      onUploadSuccess();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to add household');
    } finally {
      setAdding(false);
    }
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setAddModalVisible(true)}
        >
          Add Household Manually
        </Button>
        <span style={{ marginLeft: 12, color: '#666' }}>
          Or upload a file below
        </span>
      </div>

      {hasExistingData && (
        <Alert
          message="Append Mode Enabled"
          description="You have existing household data. New uploads will be ADDED to your existing data (not replaced). Make sure house numbers don't conflict with existing records."
          type="info"
          showIcon
          style={{ marginBottom: 20 }}
        />
      )}

      <Card title="Upload Household Data">
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <Alert
            message="Before Uploading"
            description={
              <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                <li>Make sure you have downloaded and filled the Excel template or prepared a CSV file</li>
                <li>All required fields must be filled (House No, Surname, Population counts)</li>
                <li>Supported formats: .xlsx, .xls, or .csv files</li>
                {hasExistingData && (
                  <li><strong>⚠️ New records will be ADDED to existing data (not replaced)</strong></li>
                )}
                <li>Ensure house numbers are unique to avoid duplicate entries</li>
              </ul>
            }
            type="info"
            showIcon
          />

          <Upload.Dragger {...uploadProps} disabled={uploading}>
            <p className="ant-upload-drag-icon">
              <UploadOutlined style={{ fontSize: 48, color: uploading ? '#ccc' : '#1890ff' }} />
            </p>
            <p className="ant-upload-text">
              Click or drag file to this area to upload
            </p>
            <p className="ant-upload-hint">
              Support for .xlsx, .xls, and .csv files. {hasExistingData ? 'New records will be appended to existing data.' : 'The file will be validated before import.'}
            </p>
          </Upload.Dragger>

          {selectedFile && !uploadResult && (
            <Button
              type="primary"
              size="large"
              icon={<UploadOutlined />}
              onClick={handleUpload}
              loading={uploading}
              block
            >
              {hasExistingData ? 'Upload and Append Data' : 'Upload and Import Data'}
            </Button>
          )}

          {uploadResult && (
            <>
              <Alert
                message="Upload Results"
                description={
                  <div>
                    <p><strong>Total Rows:</strong> {uploadResult.total_rows}</p>
                    <p><strong>Valid Rows:</strong> {uploadResult.valid_rows}</p>
                    <p><strong>Invalid Rows:</strong> {uploadResult.invalid_rows}</p>
                    <p><strong>Records Imported (New):</strong> {uploadResult.records_imported}</p>
                    <p><strong>Records Updated (Existing):</strong> {uploadResult.records_updated}</p>
                  </div>
                }
                type={uploadResult.success ? 'success' : 'warning'}
                showIcon
              />

              <Card title="Validation Details" size="small">
                <Table
                  dataSource={uploadResult.validations}
                  columns={validationColumns}
                  rowKey="row_number"
                  size="small"
                  pagination={{ pageSize: 10 }}
                  scroll={{ x: 1000 }}
                />
              </Card>

              {uploadResult.success && (uploadResult.records_imported > 0 || uploadResult.records_updated > 0) && (
                <Button
                  type="primary"
                  size="large"
                  onClick={() => {
                    setUploadResult(null);
                    setSelectedFile(null);
                    onUploadSuccess();
                  }}
                  block
                >
                  Continue to View Data
                </Button>
              )}
            </>
          )}
        </Space>
      </Card>

      <Modal
        title="Add New Household"
        open={addModalVisible}
        onCancel={() => { setAddModalVisible(false); addForm.resetFields(); }}
        footer={null}
        width={600}
        destroyOnClose
      >
        <Form
          form={addForm}
          layout="vertical"
          onFinish={handleAddHousehold}
        >
          <Form.Item
            name="house_no"
            label="House No"
            rules={[{ required: true, message: 'Please enter house number' }]}
          >
            <Input placeholder="e.g., H-001" />
          </Form.Item>

          <Form.Item
            name="surname"
            label="Surname / Family Name"
            rules={[{ required: true, message: 'Please enter surname' }]}
          >
            <Input placeholder="e.g., Sharma" />
          </Form.Item>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            <Form.Item
              name="male_population"
              label="Male Population"
            >
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              name="female_population"
              label="Female Population"
            >
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              name="total_population"
              label="Total Population"
            >
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item
              name="forest_dependent"
              label="Forest Dependent"
            >
              <Select placeholder="Select">
                <Select.Option value="Yes">Yes</Select.Option>
                <Select.Option value="No">No</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item
              name="caste"
              label="Caste/Ethnicity"
            >
              <Input placeholder="e.g., Brahmin" />
            </Form.Item>
          </div>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={adding}>
                Add Household
              </Button>
              <Button onClick={() => { setAddModalVisible(false); addForm.resetFields(); }}>
                Cancel
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default FileUploadSection;
