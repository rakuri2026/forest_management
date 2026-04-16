import React, { useState, useEffect, useMemo } from 'react';
import { Modal, Table, InputNumber, Card, Row, Col, message, Button, Space, Select, Tabs } from 'antd';
import { EditOutlined, SaveOutlined, EnvironmentOutlined, HighlightOutlined, DownloadOutlined } from '@ant-design/icons';
import { yearlyActivitiesApi, forestApi } from '../../services/api';
import BlockSubAreaSelector from './BlockSubAreaSelector';
import DrawingCanvas from './DrawingCanvas';

interface YearDetailEditorProps {
  visible: boolean;
  onClose: () => void;
  proposedActivity: any;
  onSaved: () => void;
}

interface YearDetailWithSpatial extends any {
  year: number;
  quantity: number;
  yearly_budget: number;
  hasOverride: boolean;
  id: string | null;
  block_id?: string;
  sub_area_id?: string;
}

type FeatureType = 'point' | 'line' | 'polygon';

const YearDetailEditor: React.FC<YearDetailEditorProps> = ({
  visible,
  onClose,
  proposedActivity,
  onSaved,
}) => {
  const [loading, setLoading] = useState(false);
  const [yearDetails, setYearDetails] = useState<YearDetailWithSpatial[]>([]);
  const [editingYear, setEditingYear] = useState<number | null>(null);
  const [blocksWithSubAreas, setBlocksWithSubAreas] = useState<any[]>([]);
  const [formValues, setFormValues] = useState<{ quantity: number; budget: number }>({
    quantity: 0,
    budget: 0,
  });
  const [activeTab, setActiveTab] = useState<string>('years');
  const [featureType, setFeatureType] = useState<FeatureType>('polygon');
  const [drawnFeatures, setDrawnFeatures] = useState<any[]>([]);
  const [exporting, setExporting] = useState(false);

  const defaultQuantity = proposedActivity?.default_quantity || 0;
  const defaultBudget = Math.round((proposedActivity?.default_yearly_budget || 5000) / 1000);
  
  // Memoize availableYears to prevent unnecessary re-renders
  const availableYears = useMemo(() => 
    yearDetails.map(y => ({ year: y.year })),
    [yearDetails]
  );

  useEffect(() => {
    if (visible && proposedActivity) {
      loadYearDetails();
      loadBlocksWithSubAreas();
      loadDrawnFeatures();
    }
  }, [visible, proposedActivity]);

  const loadDrawnFeatures = async () => {
    if (!proposedActivity?.id) return;
    try {
      const features = await yearlyActivitiesApi.getDrawnFeatures(proposedActivity.id);
      setDrawnFeatures(features || []);
    } catch (err) {
      console.error('Failed to load drawn features', err);
      setDrawnFeatures([]);
    }
  };

  const handleExportKml = async () => {
    if (!proposedActivity?.id) return;
    if (drawnFeatures.length === 0) {
      message.warning('No spatial features to export');
      return;
    }
    setExporting(true);
    try {
      await yearlyActivitiesApi.exportSpatialFeaturesKml(proposedActivity.id);
      message.success('KML exported successfully');
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to export KML');
    } finally {
      setExporting(false);
    }
  };

  const handleExportGpkg = async () => {
    if (!proposedActivity?.id) return;
    if (drawnFeatures.length === 0) {
      message.warning('No spatial features to export');
      return;
    }
    setExporting(true);
    try {
      await yearlyActivitiesApi.exportSpatialFeaturesGpkg(proposedActivity.id);
      message.success('GPKG exported successfully');
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to export GPKG');
    } finally {
      setExporting(false);
    }
  };

  const loadBlocksWithSubAreas = async () => {
    if (!proposedActivity?.calculation_id) return;
    try {
      const blocks = await yearlyActivitiesApi.getBlocksWithSubareas(proposedActivity.calculation_id);
      setBlocksWithSubAreas(blocks);
    } catch (err) {
      console.error('Failed to load blocks', err);
    }
  };

  const loadYearDetails = async () => {
    if (!proposedActivity?.id) return;
    setLoading(true);
    try {
      const yearlyDetails = await yearlyActivitiesApi.getYearDetails(proposedActivity.id);
      const spatialAssignments = await yearlyActivitiesApi.getSpatialAssignments(proposedActivity.id);
      
      const details: YearDetailWithSpatial[] = [];
      for (let year = 1; year <= 10; year++) {
        const existing = yearlyDetails.find((yd: any) => yd.year_number === year);
        details.push({
          year,
          quantity: existing?.quantity ?? defaultQuantity,
          yearly_budget: existing?.yearly_budget ?? defaultBudget * 1000,
          hasOverride: !!existing,
          id: existing?.id,
          block_id: existing?.block_id,
          sub_area_id: existing?.sub_area_id,
        });
      }
      setYearDetails(details);
    } catch (error: any) {
      const details: YearDetailWithSpatial[] = [];
      for (let year = 1; year <= 10; year++) {
        details.push({
          year,
          quantity: defaultQuantity,
          yearly_budget: defaultBudget * 1000,
          hasOverride: false,
          id: null,
        });
      }
      setYearDetails(details);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveYear = async (year: number) => {
    if (!proposedActivity?.id) return;
    try {
      const data = yearDetails.find(y => y.year === year);
      if (data?.hasOverride && data?.id) {
        await yearlyActivitiesApi.updateYearDetail(proposedActivity.id, data.id, {
          quantity: data.quantity,
          yearly_budget: data.yearly_budget,
        });
      } else {
        await yearlyActivitiesApi.createYearDetail(proposedActivity.id, {
          year_number: year,
          quantity: data.quantity,
          yearly_budget: data.yearly_budget,
        });
      }
      
      // Save spatial assignment for this year
      const existingSpatial = await yearlyActivitiesApi.getSpatialAssignments(proposedActivity.id);
      for (const sa of existingSpatial) {
        await yearlyActivitiesApi.deleteSpatialAssignment(proposedActivity.id, sa.id);
      }
      
      if (data.sub_area_id) {
        await yearlyActivitiesApi.createSpatialAssignment(proposedActivity.id, {
          block_id: data.block_id,
          sub_area_id: data.sub_area_id,
          assignment_type: 'sub_area'
        });
      } else if (data.block_id) {
        await yearlyActivitiesApi.createSpatialAssignment(proposedActivity.id, {
          block_id: data.block_id,
          assignment_type: 'block'
        });
      } else {
        await yearlyActivitiesApi.createSpatialAssignment(proposedActivity.id, {
          assignment_type: 'all_blocks'
        });
      }
      
      message.success(`Year ${year} saved`);
      setEditingYear(null);
      onSaved();
    } catch (error: any) {
      message.error('Failed to save year');
    }
  };

  const handleSpatialChange = (year: number, type: 'all' | 'block' | 'sub_area', id?: string, checked?: boolean) => {
    setYearDetails(prev => prev.map(y => {
      if (y.year !== year) return y;
      
      if (type === 'all') {
        return { ...y, block_id: undefined, sub_area_id: undefined };
      } else if (type === 'block' && id) {
        return { ...y, block_id: id, sub_area_id: undefined };
      } else if (type === 'sub_area' && id) {
        const subArea = blocksWithSubAreas
          .flatMap(b => b.sub_areas?.map((sa: any) => ({ ...sa, block_id: b.block_id })) || [])
          .find((sa: any) => sa.id === id);
        return { ...y, block_id: subArea?.block_id, sub_area_id: id };
      }
      return y;
    }));
  };

  const getYearSpatialInfo = (year: number) => {
    const yearData = yearDetails.find(y => y.year === year);
    if (!yearData?.block_id) return 'All blocks';
    
    const block = blocksWithSubAreas.find(b => b.block_id === yearData.block_id);
    if (yearData.sub_area_id) {
      const subArea = block?.sub_areas?.find((sa: any) => sa.id === yearData.sub_area_id);
      return subArea ? `${subArea.name} (${block.block_name})` : block?.block_name || 'Custom';
    }
    return block?.block_name || 'Custom';
  };

  const columns = [
    {
      title: 'Year',
      dataIndex: 'year',
      key: 'year',
      width: 70,
      render: (year: number) => <strong>Year {year}</strong>,
    },
    {
      title: 'Quantity',
      dataIndex: 'quantity',
      key: 'quantity',
      width: 120,
      render: (_: any, record: any) =>
        editingYear === record.year ? (
          <InputNumber
            min={0}
            value={record.quantity}
            onChange={(val) => {
              const updated = yearDetails.map(y =>
                y.year === record.year ? { ...y, quantity: val || 0, hasOverride: true } : y
              );
              setYearDetails(updated);
            }}
            style={{ width: '100%' }}
          />
        ) : (
          record.quantity?.toLocaleString() || '-'
        ),
    },
    {
      title: 'Budget',
      dataIndex: 'yearly_budget',
      key: 'yearly_budget',
      width: 120,
      render: (_: any, record: any) =>
        editingYear === record.year ? (
          <InputNumber
            min={0}
            value={record.yearly_budget / 1000}
            placeholder="Enter in thousands"
            formatter={(value) => `${value || 0}ह`}
            parser={(value: any) => {
              const parsed = parseFloat(value?.replace(/हs?/g, '')) || 0;
              return parsed * 1000;
            }}
            onChange={(val) => {
              const updated = yearDetails.map(y =>
                y.year === record.year ? { ...y, yearly_budget: (val || 0) * 1000, hasOverride: true } : y
              );
              setYearDetails(updated);
            }}
            style={{ width: '100%' }}
          />
        ) : (
          record.yearly_budget > 0 ? `${Math.round(record.yearly_budget / 1000)}ह` : '-'
        ),
    },
    {
      title: 'Location',
      dataIndex: 'block_id',
      key: 'location',
      width: 180,
      render: (_: any, record: any) => {
        if (editingYear === record.year) {
          return (
            <Select
              style={{ width: '100%' }}
              placeholder="Select location"
              value={record.sub_area_id || record.block_id || 'all'}
              onChange={(val) => {
                if (val === 'all') {
                  handleSpatialChange(record.year, 'all', undefined, true);
                } else {
                  const isSubArea = blocksWithSubAreas
                    .flatMap(b => b.sub_areas || [])
                    .some((sa: any) => sa.id === val);
                  
                  if (isSubArea) {
                    handleSpatialChange(record.year, 'sub_area', val, true);
                  } else {
                    handleSpatialChange(record.year, 'block', val, true);
                  }
                }
              }}
              options={[
                { label: 'All blocks', value: 'all' },
                ...blocksWithSubAreas.flatMap(b => [
                  { label: b.block_name, value: b.block_id },
                  ...(b.sub_areas || []).map((sa: any) => ({
                    label: `  ↳ ${sa.name}`,
                    value: sa.id
                  }))
                ])
              ]}
            />
          );
        }
        return <span style={{ fontSize: '12px' }}>{getYearSpatialInfo(record.year)}</span>;
      }
    },
    {
      title: 'Spatial',
      dataIndex: 'has_spatial',
      key: 'has_spatial',
      width: 100,
      render: (_: any, record: any) => {
        const hasLocation = record.block_id || record.sub_area_id;
        const hasDrawnFeature = drawnFeatures.some((f: any) => f.properties?.year === record.year);
        const featureCount = drawnFeatures.filter((f: any) => f.properties?.year === record.year).length;
        
        if (hasDrawnFeature) {
          return (
            <span style={{ color: '#52c41a' }} title={`${featureCount} feature(s) drawn`}>
              ✓ {featureCount}
            </span>
          );
        }
        return hasLocation ? (
          <span style={{ color: '#1890ff' }} title="Block/Sub-area assigned">📍</span>
        ) : (
          <span style={{ color: '#ccc' }}>-</span>
        );
      }
    },
    {
      title: 'Status',
      dataIndex: 'hasOverride',
      key: 'status',
      width: 80,
      render: (hasOverride: boolean, record: any) => {
        const hasDrawnFeature = drawnFeatures.some((f: any) => f.properties?.year === record.year);
        
        if (hasDrawnFeature || hasOverride) {
          return <span style={{ color: '#52c41a' }}>Custom</span>;
        }
        return <span style={{ color: '#999' }}>Default</span>;
      },
    },
    {
      title: 'Action',
      key: 'action',
      width: 100,
      render: (_: any, record: any) =>
        editingYear === record.year ? (
          <Space>
            <Button
              type="link"
              icon={<SaveOutlined />}
              onClick={() => handleSaveYear(record.year)}
              size="small"
            >
              Save
            </Button>
            <Button type="link" onClick={() => setEditingYear(null)} size="small">
              Cancel
            </Button>
          </Space>
        ) : (
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => {
              setEditingYear(record.year);
              setFormValues({
                quantity: record.quantity,
                budget: record.yearly_budget,
              });
            }}
            size="small"
          >
            Edit
          </Button>
        ),
    },
  ];

  // Calculate totals
  const totalQuantity = yearDetails.reduce((sum, y) => sum + (Number(y.quantity) || 0), 0);
  const totalBudget = yearDetails.reduce((sum, y) => sum + (Number(y.yearly_budget) || 0), 0);

  const tabItems = [
    {
      key: 'years',
      label: 'Yearly Details',
      children: (
        <>
          <Row gutter={16} style={{ marginBottom: '16px' }}>
            <Col span={8}>
              <Card size="small">
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#999' }}>Total Quantity (10 years)</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                    {totalQuantity.toLocaleString()}
                  </div>
                </div>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small">
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#999' }}>Total Budget (10 years)</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                    NPR {totalBudget.toLocaleString()}
                  </div>
                </div>
              </Card>
            </Col>
            <Col span={8}>
              <Card size="small">
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#999' }}>Average / Year</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold' }}>
                    NPR {Math.round(totalBudget / 10).toLocaleString()}
                  </div>
                </div>
              </Card>
            </Col>
          </Row>
          <Table
            columns={columns}
            dataSource={yearDetails}
            rowKey="year"
            pagination={false}
            loading={loading}
            size="small"
          />
        </>
      ),
    },
    {
      key: 'spatial',
      label: `Spatial Features (${drawnFeatures.length})`,
      children: (
        <>
          <div style={{ marginBottom: '16px', padding: '12px', background: '#f5f5f5', borderRadius: '4px' }}>
            <Space style={{ marginBottom: '8px' }}>
              <span><strong>Draw:</strong></span>
              <Select
                value={featureType}
                onChange={setFeatureType}
                style={{ width: 120 }}
                options={[
                  { label: '📍 Point', value: 'point' },
                  { label: '〰️ Line', value: 'line' },
                  { label: '⬛ Polygon', value: 'polygon' },
                ]}
              />
            </Space>
            <div style={{ marginTop: '4px', fontSize: '12px', color: '#666' }}>
              Click on the map to draw • Double-click to finish line/polygon
            </div>
            <div style={{ marginTop: '12px', borderTop: '1px solid #ddd', paddingTop: '12px' }}>
              <Space>
                <span><strong>Download:</strong></span>
                <Button
                  icon={<DownloadOutlined />}
                  onClick={handleExportKml}
                  loading={exporting}
                  disabled={drawnFeatures.length === 0}
                  size="small"
                >
                  KML
                </Button>
                <Button
                  icon={<DownloadOutlined />}
                  onClick={handleExportGpkg}
                  loading={exporting}
                  disabled={drawnFeatures.length === 0}
                  size="small"
                >
                  GPKG
                </Button>
                <span style={{ fontSize: '11px', color: '#999' }}>
                  {drawnFeatures.length > 0 ? `${drawnFeatures.length} features` : 'No features'}
                </span>
              </Space>
            </div>
          </div>
          <DrawingCanvas
            calculationId={proposedActivity?.calculation_id || ''}
            activityId={proposedActivity?.id || ''}
            featureType={featureType}
            onFeatureTypeChange={setFeatureType}
            drawnFeatures={drawnFeatures}
            onFeaturesChange={loadDrawnFeatures}
            blocksWithSubAreas={blocksWithSubAreas}
            availableYears={availableYears}
          />
        </>
      ),
    },
  ];

  return (
    <Modal
      title={`Yearly Details - ${proposedActivity?.potential_activity?.activity || 'Activity'}`}
      open={visible}
      onCancel={onClose}
      width={900}
      footer={[
        <Button key="close" onClick={onClose}>
          Close
        </Button>,
      ]}
    >
      <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
    </Modal>
  );
};

export default YearDetailEditor;