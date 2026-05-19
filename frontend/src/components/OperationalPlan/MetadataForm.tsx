import React, { useState, useEffect } from 'react';
import { Form, Input, InputNumber, Select, Button, message, Spin, Divider, DatePicker } from 'antd';
import { operationalPlanApi } from '../../services/api';

interface MetadataFormProps {
  planId: string;
  visible: boolean;
  onClose: () => void;
}

const MetadataForm: React.FC<MetadataFormProps> = ({ planId, visible, onClose }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (visible && planId) {
      loadFormData();
    }
  }, [visible, planId]);

  const loadFormData = async () => {
    setLoading(true);
    try {
      const data = await operationalPlanApi.getMetadataForm(planId);
      form.setFieldsValue({
        ...data.user_inputs,
        ...data.hybrid_overrides,
      });
    } catch {
      message.error('Failed to load metadata form');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const userInputKeys = [
        'plan_year_start', 'plan_year_end', 'plan_duration_years',
        'user_group_name', 'user_group_code', 'registration_date',
        'registration_office', 'cf_area_provided', 'cf_handover_date',
        'cf_total_households', 'cf_total_population', 'vdc_ward',
        'contact_person', 'contact_designation', 'contact_phone',
        'ranger_name', 'ranger_phone', 'prepared_by', 'reviewed_by',
        'approved_by', 'plan_language',
      ];
      const hybridKeys = [
        'altitude_min_m', 'altitude_max_m', 'altitude_mean_m',
        'dominant_slope', 'dominant_aspect', 'dominant_soil',
        'crown_density_pct', 'trees_per_hectare',
        'growing_stock_m3_per_ha', 'biomass_t_per_ha', 'carbon_stock_tc_per_ha',
      ];

      const userInputs: Record<string, any> = {};
      const hybridOverrides: Record<string, any> = {};

      for (const key of userInputKeys) {
        if (values[key] !== undefined && values[key] !== null) {
          userInputs[key] = values[key];
        }
      }
      for (const key of hybridKeys) {
        if (values[key] !== undefined && values[key] !== null) {
          hybridOverrides[key] = values[key];
        }
      }

      await operationalPlanApi.updateMetadataForm(planId, {
        user_inputs: userInputs,
        hybrid_overrides: hybridOverrides,
      });

      message.success('Metadata saved');
      onClose();
    } catch (err: any) {
      if (err.errorFields) return;
      message.error('Failed to save metadata');
    } finally {
      setSaving(false);
    }
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-start justify-center overflow-y-auto" style={{ paddingTop: '40px', paddingBottom: '40px' }}>
      <div style={{ background: '#fff', borderRadius: 8, width: 800, maxWidth: '95%', padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
            Operational Plan Metadata (योजना विवरण)
          </h2>
          <Button onClick={onClose} type="text">✕</Button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>
        ) : (
          <Form form={form} layout="vertical" onFinish={handleSave}>

            <Divider orientation="left" plain>Plan Period (योजना अवधि)</Divider>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <Form.Item label="Start Year (सुरु वर्ष)" name="plan_year_start" rules={[{ required: true }]}>
                <InputNumber style={{ width: '100%' }} min={2020} max={2100} />
              </Form.Item>
              <Form.Item label="End Year (अन्त वर्ष)" name="plan_year_end" rules={[{ required: true }]}>
                <InputNumber style={{ width: '100%' }} min={2020} max={2100} />
              </Form.Item>
              <Form.Item label="Duration (अवधि वर्ष)" name="plan_duration_years" rules={[{ required: true }]}>
                <InputNumber style={{ width: '100%' }} min={1} max={20} />
              </Form.Item>
            </div>

            <Divider orientation="left" plain>User Group (उपभोक्ता समूह)</Divider>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Form.Item label="Group Name (समूहको नाम)" name="user_group_name" rules={[{ required: true }]}>
                <Input />
              </Form.Item>
              <Form.Item label="Registration No (दर्ता नं.)" name="user_group_code">
                <Input />
              </Form.Item>
              <Form.Item label="Registration Date (दर्ता मिति)" name="registration_date">
                <Input placeholder="YYYY-MM-DD" />
              </Form.Item>
              <Form.Item label="Registration Office (दर्ता कार्यालय)" name="registration_office">
                <Input placeholder="जिल्ला वन कार्यालय" />
              </Form.Item>
            </div>

            <Divider orientation="left" plain>Community Forest (सामुदायिक वन)</Divider>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Form.Item label="Area Provided (प्रदान क्षेत्रफल हे.)" name="cf_area_provided">
                <InputNumber style={{ width: '100%' }} min={0} step={0.01} />
              </Form.Item>
              <Form.Item label="Handover Date (हस्तान्तरण मिति)" name="cf_handover_date">
                <Input placeholder="YYYY-MM-DD" />
              </Form.Item>
              <Form.Item label="Total Households (कुल घरधुरी)" name="cf_total_households">
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
              <Form.Item label="Total Population (कुल जनसंख्या)" name="cf_total_population">
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
              <Form.Item label="Ward No (वडा नं.)" name="vdc_ward">
                <Input />
              </Form.Item>
            </div>

            <Divider orientation="left" plain>Contacts (सम्पर्क)</Divider>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <Form.Item label="Contact Person (सम्पर्क व्यक्ति)" name="contact_person">
                <Input />
              </Form.Item>
              <Form.Item label="Designation (पद)" name="contact_designation">
                <Input placeholder="अध्यक्ष" />
              </Form.Item>
              <Form.Item label="Phone (फोन)" name="contact_phone">
                <Input />
              </Form.Item>
              <Form.Item label="Ranger Name (रेन्जरको नाम)" name="ranger_name">
                <Input />
              </Form.Item>
              <Form.Item label="Ranger Phone (रेन्जर फोन)" name="ranger_phone">
                <Input />
              </Form.Item>
            </div>

            <Divider orientation="left" plain>Document Signatories (हस्ताक्षरकर्ता)</Divider>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <Form.Item label="Prepared By (तयार गर्ने)" name="prepared_by">
                <Input />
              </Form.Item>
              <Form.Item label="Reviewed By (समीक्षा गर्ने)" name="reviewed_by">
                <Input />
              </Form.Item>
              <Form.Item label="Approved By (स्वीकृत गर्ने)" name="approved_by">
                <Input />
              </Form.Item>
            </div>

            <Divider orientation="left" plain>Hybrid Overrides (प्रणाली डाटा ओभरराइड)</Divider>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <Form.Item label="Min Altitude (m)" name="altitude_min_m"><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item label="Max Altitude (m)" name="altitude_max_m"><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item label="Mean Altitude (m)" name="altitude_mean_m"><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item label="Dominant Slope" name="dominant_slope"><Input /></Form.Item>
              <Form.Item label="Dominant Aspect" name="dominant_aspect"><Input /></Form.Item>
              <Form.Item label="Dominant Soil" name="dominant_soil"><Input /></Form.Item>
              <Form.Item label="Crown Density (%)" name="crown_density_pct"><InputNumber style={{ width: '100%' }} min={0} max={100} /></Form.Item>
              <Form.Item label="Trees / ha" name="trees_per_hectare"><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item label="Growing Stock (m³/ha)" name="growing_stock_m3_per_ha"><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item label="Biomass (t/ha)" name="biomass_t_per_ha"><InputNumber style={{ width: '100%' }} /></Form.Item>
              <Form.Item label="Carbon Stock (tC/ha)" name="carbon_stock_tc_per_ha"><InputNumber style={{ width: '100%' }} /></Form.Item>
            </div>

            <Divider orientation="left" plain>Settings</Divider>
            <Form.Item label="Language (भाषा)" name="plan_language">
              <Select>
                <Select.Option value="NP">Nepali (नेपाली)</Select.Option>
                <Select.Option value="EN">English</Select.Option>
              </Select>
            </Form.Item>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <Button onClick={onClose}>Cancel</Button>
              <Button type="primary" htmlType="submit" loading={saving}>Save Metadata</Button>
            </div>
          </Form>
        )}
      </div>
    </div>
  );
};

export default MetadataForm;
