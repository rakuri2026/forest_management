/**
 * Template Download Section
 * Allows users to configure and download Excel template
 */
import React, { useState } from 'react';
import { Button, Card, Radio, Checkbox, Alert, Space, message } from 'antd';
import { DownloadOutlined, FileExcelOutlined } from '@ant-design/icons';
import * as api from '../../services/api';

interface TemplateDownloadSectionProps {
  calculationId: string;
  hasExistingData: boolean;
}

const TemplateDownloadSection: React.FC<TemplateDownloadSectionProps> = ({
  calculationId,
  hasExistingData,
}) => {
  const [landUnit, setLandUnit] = useState<'ropani' | 'kaththa'>('ropani');
  const [includeCoordinates, setIncludeCoordinates] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await api.userGroupApi.downloadHouseholdTemplate(calculationId, {
        land_unit: landUnit,
        include_coordinates: includeCoordinates,
      });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `household_template_${landUnit}_${new Date().toISOString().split('T')[0]}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      message.success('Template downloaded successfully');
    } catch (error) {
      console.error('Error downloading template:', error);
      message.error('Failed to download template');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div>
      {hasExistingData && (
        <Alert
          message="Data Already Exists"
          description="You already have household data uploaded. To re-upload, delete the existing data first using the 'Delete All Data' button."
          type="warning"
          showIcon
          style={{ marginBottom: 20 }}
        />
      )}

      <Card title="Download Excel Template" style={{ maxWidth: 800 }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <h4>Land Unit</h4>
            <p style={{ color: '#666', marginBottom: 10 }}>
              Choose the land measurement unit for your data entry
            </p>
            <Radio.Group
              value={landUnit}
              onChange={(e) => setLandUnit(e.target.value)}
              size="large"
            >
              <Radio.Button value="ropani">
                <strong>Ropani</strong> (रोपनी)
              </Radio.Button>
              <Radio.Button value="kaththa">
                <strong>Kaththa</strong> (कठ्ठा)
              </Radio.Button>
            </Radio.Group>
            <p style={{ color: '#999', marginTop: 10, fontSize: 12 }}>
              Note: 1 Ropani = 16 Kaththa
            </p>
          </div>

          <div>
            <h4>Optional Fields</h4>
            <Checkbox
              checked={includeCoordinates}
              onChange={(e) => setIncludeCoordinates(e.target.checked)}
            >
              <strong>Include coordinate fields</strong> (Latitude/Longitude)
            </Checkbox>
            <p style={{ color: '#999', marginTop: 5, fontSize: 12 }}>
              Enable this if you want to record GPS coordinates for each household
            </p>
          </div>

          <Alert
            message="Template Features"
            description={
              <ul style={{ marginBottom: 0, paddingLeft: 20 }}>
                <li>
                  <strong>Built-in formulas</strong> for automatic calculation of
                  firewood, grass, and bedding demands
                </li>
                <li>
                  <strong>Data validation</strong> dropdowns for Yes/No fields and
                  prosperity levels
                </li>
                <li>
                  <strong>Instructions sheet</strong> with detailed guidance in both
                  Nepali and English
                </li>
                <li>
                  <strong>Pre-configured defaults</strong>: Timber (5 cft), Poles (5),
                  Prosperity (मध्यम)
                </li>
              </ul>
            }
            type="info"
            showIcon
          />

          <div>
            <h4>Next Steps</h4>
            <ol style={{ color: '#666', paddingLeft: 20 }}>
              <li>Download the template below</li>
              <li>Open the file in Microsoft Excel or LibreOffice Calc</li>
              <li>Fill in household data starting from Row 3</li>
              <li>
                Formulas will calculate demands automatically (or you can override)
              </li>
              <li>Save the file and return to upload it</li>
            </ol>
          </div>

          <Button
            type="primary"
            size="large"
            icon={<DownloadOutlined />}
            onClick={handleDownload}
            loading={downloading}
            block
          >
            <FileExcelOutlined /> Download Excel Template
          </Button>
        </Space>
      </Card>
    </div>
  );
};

export default TemplateDownloadSection;
