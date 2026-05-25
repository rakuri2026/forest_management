import React, { useState, useEffect, useCallback } from 'react';
import { Form, Input, InputNumber, Select, Button, message, Spin, Collapse } from 'antd';
import { operationalPlanApi } from '../../services/api';
import { useAdminLocation } from './hooks/useAdminLocation';
import { NepaliDatePicker } from './NepaliDatePicker';

interface MetadataFormProps {
  planId: string;
  visible: boolean;
  onClose: () => void;
}

const MetadataForm: React.FC<MetadataFormProps> = ({ planId, visible, onClose }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const forestLoc = useAdminLocation();
  const ugLoc = useAdminLocation();

  const [ugPrepopulated, setUgPrepopulated] = useState(false);

  useEffect(() => {
    if (visible && planId) {
      loadFormData();
    }
  }, [visible, planId]);

  const copyForestToUg = useCallback(() => {
    const fv = form.getFieldsValue();
    const ugFields: Record<string, any> = {};
    if (fv.province) ugFields.ug_province = fv.province;
    if (fv.division) ugFields.ug_division = fv.division;
    if (fv.sub_division) ugFields.ug_sub_division = fv.sub_division;
    if (fv.forest_municipality) ugFields.ug_municipality = fv.forest_municipality;
    if (fv.forest_ward) ugFields.ug_ward = fv.forest_ward;
    form.setFieldsValue(ugFields);
    setUgPrepopulated(true);
  }, [form]);

  const loadFormData = async () => {
    setLoading(true);
    try {
      const data = await operationalPlanApi.getMetadataForm(planId);
      form.setFieldsValue({
        ...data.user_inputs,
        ...data.system_defaults,
        ...data.hybrid_overrides,
      });

      if (data.admin_locations?.provinces) {
        forestLoc.setOptions(prev => ({ ...prev, provinces: data.admin_locations.provinces }));
      }

      const ui = data.user_inputs || {};
      const DATE_FIELDS = ['registration_date', 'constitution_approved_year', 'cf_handover_date', 'op_general_assembly_date'];
      for (const f of DATE_FIELDS) {
        if (ui[f]) form.setFieldValue(f, ui[f].replace(/-/g, '/'));
      }
      if (ui.province) {
        forestLoc.setOptions(prev => ({ ...prev, province: ui.province }));
        const divisions = await operationalPlanApi.getDivisions(ui.province);
        forestLoc.setOptions(prev => ({ ...prev, divisions }));
      }
      if (ui.province && ui.division) {
        const subDivs = await operationalPlanApi.getSubDivisions(ui.province, ui.division);
        forestLoc.setOptions(prev => ({ ...prev, subDivisions: subDivs }));
      }
      if (ui.province && ui.division && ui.sub_division) {
        const muns = await operationalPlanApi.getMunicipalities(ui.province, ui.division, ui.sub_division);
        forestLoc.setOptions(prev => ({ ...prev, municipalities: muns }));
      }
      if (ui.province && ui.division && ui.sub_division && ui.forest_municipality) {
        const wards = await operationalPlanApi.getWards(ui.province, ui.division, ui.sub_division, ui.forest_municipality);
        forestLoc.setOptions(prev => ({ ...prev, wards }));
      }

      if (!ui.ug_prepopulated && ui.province) {
        copyForestToUg();
      }

      if (ui.ug_province) {
        ugLoc.setOptions(prev => ({ ...prev, province: ui.ug_province }));
        const ugDivs = await operationalPlanApi.getDivisions(ui.ug_province);
        ugLoc.setOptions(prev => ({ ...prev, divisions: ugDivs }));
      }
      if (ui.ug_province && ui.ug_division) {
        const ugSubDivs = await operationalPlanApi.getSubDivisions(ui.ug_province, ui.ug_division);
        ugLoc.setOptions(prev => ({ ...prev, subDivisions: ugSubDivs }));
      }
      if (ui.ug_province && ui.ug_division && ui.ug_sub_division) {
        const ugMuns = await operationalPlanApi.getMunicipalities(ui.ug_province, ui.ug_division, ui.ug_sub_division);
        ugLoc.setOptions(prev => ({ ...prev, municipalities: ugMuns }));
      }
      if (ui.ug_province && ui.ug_division && ui.ug_sub_division && ui.ug_municipality) {
        const ugWards = await operationalPlanApi.getWards(ui.ug_province, ui.ug_division, ui.ug_sub_division, ui.ug_municipality);
        ugLoc.setOptions(prev => ({ ...prev, wards: ugWards }));
      }

      const alreadyPrepopulated = !!ui.ug_prepopulated;
      setUgPrepopulated(alreadyPrepopulated);
    } catch {
      message.error('मेटाडाटा लोड गर्न असफल');
    } finally {
      setLoading(false);
    }
  };

  const handleProvinceChange = async (value: string | undefined) => {
    form.setFieldsValue({ division: undefined, sub_division: undefined, forest_municipality: undefined, forest_ward: undefined });
    await forestLoc.cascadeOnProvinceChange(value);
    await forestLoc.cascadeOnDivisionChange(value, undefined);
  };

  const handleDivisionChange = async (value: string | undefined) => {
    const province = form.getFieldValue('province');
    form.setFieldsValue({ sub_division: undefined, forest_municipality: undefined, forest_ward: undefined });
    await forestLoc.cascadeOnDivisionChange(province, value);
    await forestLoc.cascadeOnSubDivisionChange(province, value, undefined);
  };

  const handleSubDivisionChange = async (value: string | undefined) => {
    const province = form.getFieldValue('province');
    const division = form.getFieldValue('division');
    form.setFieldsValue({ forest_municipality: undefined, forest_ward: undefined });
    await forestLoc.cascadeOnSubDivisionChange(province, division, value);
    await forestLoc.cascadeOnMunicipalityChange(province, division, value, undefined, false);
  };

  const handleMunicipalityChange = async (value: string | undefined) => {
    const province = form.getFieldValue('province');
    const division = form.getFieldValue('division');
    const subDivision = form.getFieldValue('sub_division');
    form.setFieldsValue({ forest_ward: undefined });
    await forestLoc.cascadeOnMunicipalityChange(province, division, subDivision, value, true);

    if (value) {
      const munData = forestLoc.options.municipalities.find(m => m.name === value);
      if (munData) {
        form.setFieldValue('municipality_type', munData.type);
      }
      if (!ugPrepopulated) {
        const result = await operationalPlanApi.getPhysiographyJurisdiction(province, division, subDivision, value);
        form.setFieldsValue({
          physiography_zone: result.physiography_zone,
          protected_area_status: result.protected_area_status,
        });
        forestLoc.setOptions(prev => ({ ...prev, physiographyZone: result.physiography_zone, protectedAreaStatus: result.protected_area_status }));
      }
    }
  };

  const handleUgProvinceChange = async (value: string | undefined) => {
    form.setFieldsValue({ ug_division: undefined, ug_sub_division: undefined, ug_municipality: undefined, ug_ward: undefined });
    await ugLoc.cascadeOnProvinceChange(value);
  };

  const handleUgDivisionChange = async (value: string | undefined) => {
    const province = form.getFieldValue('ug_province');
    form.setFieldsValue({ ug_sub_division: undefined, ug_municipality: undefined, ug_ward: undefined });
    await ugLoc.cascadeOnDivisionChange(province, value);
  };

  const handleUgSubDivisionChange = async (value: string | undefined) => {
    const province = form.getFieldValue('ug_province');
    const division = form.getFieldValue('ug_division');
    form.setFieldsValue({ ug_municipality: undefined, ug_ward: undefined });
    await ugLoc.cascadeOnSubDivisionChange(province, division, value);
  };

  const handleUgMunicipalityChange = async (value: string | undefined) => {
    const province = form.getFieldValue('ug_province');
    const division = form.getFieldValue('ug_division');
    const subDivision = form.getFieldValue('ug_sub_division');
    form.setFieldsValue({ ug_ward: undefined });
    await ugLoc.cascadeOnMunicipalityChange(province, division, subDivision, value, false);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const userInputKeys = [
        'cf_registration_number', 'op_preparation_year', 'sn_number', 'province_guideline_year',
        'province', 'division', 'sub_division', 'sub_division_chief',
        'forest_management_section_chief', 'division_forest_officer',
        'forest_municipality', 'municipality_type', 'forest_ward',
        'cf_sn_number', 'constitution_approved_year', 'user_group_reg_no',
        'op_start_fy', 'op_end_fy', 'cf_code', 'cf_name',
        'cf_boundary_east', 'cf_boundary_south', 'cf_boundary_west', 'cf_boundary_north',
        'physiography_zone', 'protected_area_status', 'cf_handover_date',
        'ug_prepopulated', 'ug_province', 'ug_division', 'ug_sub_division',
        'ug_municipality', 'ug_ward', 'ug_settlement',
        'ug_boundary_east', 'ug_boundary_south', 'ug_boundary_west', 'ug_boundary_north',
        'technical_assistance_org', 'op_general_assembly_date',
        'forest_type', 'forest_abundance', 'forest_avg_age', 'main_non_timber_fp',
        'avg_crown_density_pct',
        'plan_language',
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
        if (values[key] !== undefined && values[key] !== null && values[key] !== '') {
          let val = values[key];
          if (['constitution_approved_year', 'cf_handover_date', 'op_general_assembly_date'].includes(key) && typeof val === 'string') {
            val = val.replace(/-/g, '/');
          }
          userInputs[key] = val;
        }
      }
      for (const key of hybridKeys) {
        if (values[key] !== undefined && values[key] !== null && values[key] !== '') {
          hybridOverrides[key] = values[key];
        }
      }

      userInputs.ug_prepopulated = true;

      await operationalPlanApi.updateMetadataForm(planId, {
        user_inputs: userInputs,
        hybrid_overrides: hybridOverrides,
      });

      message.success('मेटाडाटा सुरक्षित गरियो');
      onClose();
    } catch (err: any) {
      if (err.errorFields) return;
      if (err.response?.data?.detail) {
        message.error(Array.isArray(err.response.data.detail) ? err.response.data.detail.join(', ') : err.response.data.detail);
      } else {
        message.error('मेटाडाटा सुरक्षित गर्न असफल');
      }
    } finally {
      setSaving(false);
    }
  };

  if (!visible) return null;

  const selectStyle = { width: '100%' };

  const locationSelects = (prefix: string, loc: typeof forestLoc, onProvinceChange: any, onDivisionChange: any, onSubDivisionChange: any, onMunicipalityChange: any) => (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <Form.Item label="प्रदेश" name={`${prefix}province`}>
        <Select showSearch allowClear placeholder="प्रदेश चुन्नुहोस्" style={selectStyle} options={loc.options.provinces.map(p => ({ value: p, label: p }))} onChange={onProvinceChange} />
      </Form.Item>
      <Form.Item label="डिभिजन" name={`${prefix}division`}>
        <Select showSearch allowClear placeholder="डिभिजन चुन्नुहोस्" style={selectStyle} options={loc.options.divisions.map(d => ({ value: d, label: d }))} onChange={onDivisionChange} />
      </Form.Item>
      <Form.Item label="सव डिभिजन" name={`${prefix}sub_division`}>
        <Select showSearch allowClear placeholder="सव डिभिजन चुन्नुहोस्" style={selectStyle} options={loc.options.subDivisions.map(s => ({ value: s, label: s }))} onChange={onSubDivisionChange} />
      </Form.Item>
      <Form.Item label="स्थानिय तह" name={`${prefix}municipality`}>
        <Select showSearch allowClear placeholder="स्थानिय तह चुन्नुहोस्" style={selectStyle} options={loc.options.municipalities.map(m => ({ value: m.name, label: `${m.name} (${m.type})` }))} onChange={onMunicipalityChange} />
      </Form.Item>
      <Form.Item label="वार्ड नं." name={`${prefix}ward`}>
        <Select showSearch allowClear placeholder="वार्ड चुन्नुहोस्" style={selectStyle} options={loc.options.wards.map(w => ({ value: w, label: w }))} />
      </Form.Item>
    </div>
  );

  const collapsibleSections = [
    {
      key: 'A',
      label: 'वन दर्ता तथा परिचय',
      children: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Form.Item label="सामुदायिक वन द.नं." name="cf_registration_number">
            <Input placeholder="जस्तै: ३२८/२०६६/०२/२०" />
          </Form.Item>
          <Form.Item label="कार्ययोजना तयारी वर्ष" name="op_preparation_year">
            <InputNumber style={selectStyle} min={2050} max={2099} placeholder="जस्तै: २०८१" />
          </Form.Item>
          <Form.Item label="क्रम संख्या" name="sn_number">
            <Input placeholder="जस्तै: MAK/PH/42/33" />
          </Form.Item>
          <Form.Item label="प्रदेशको कार्यविधि स्विकृत वर्ष" name="province_guideline_year" initialValue={2079}>
            <InputNumber style={selectStyle} min={2050} max={2099} />
          </Form.Item>
        </div>
      ),
    },
    {
      key: 'B',
      label: 'प्रशासनिक स्थान (सामुदायिक वन)',
      children: (
        <>
          {locationSelects('', forestLoc, handleProvinceChange, handleDivisionChange, handleSubDivisionChange, handleMunicipalityChange)}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginTop: 16 }}>
            <Form.Item label="सव डिभिजन प्रमुखको नाम" name="sub_division_chief">
              <Input placeholder="रामचन्द्र श्रेष्ठ" />
            </Form.Item>
            <Form.Item label="वन ब्यवस्थापन शाखा प्रमुखको नाम" name="forest_management_section_chief">
              <Input placeholder="दिपक अधिकारी" />
            </Form.Item>
            <Form.Item label="डिभिजन प्रमुखको नाम" name="division_forest_officer">
              <Input placeholder="राकेश प्रसाद चन्द्रवंशी" />
            </Form.Item>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item label="स्थानिय तहको प्रकार" name="municipality_type">
              <Input disabled />
            </Form.Item>
          </div>
        </>
      ),
    },
    {
      key: 'C',
      label: 'सामुदायिक वन विवरण',
      children: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Form.Item label="संख्या" name="cf_sn_number">
            <InputNumber style={selectStyle} min={0} />
          </Form.Item>
          <Form.Item label="विधान स्वीकृति वर्ष" name="constitution_approved_year">
            <NepaliDatePicker placeholder="२०८१/०१/१५" />
          </Form.Item>
          <Form.Item label="समूह दर्ता नं." name="user_group_reg_no">
            <InputNumber style={selectStyle} min={0} />
          </Form.Item>
          <Form.Item label="कार्ययोजना लागुहुने सुरू आर्थिक वर्ष" name="op_start_fy">
            <Input placeholder="जस्तै: २०८१/२०८२" />
          </Form.Item>
          <Form.Item label="कार्ययोजना समाप्त हुने अन्तिम वर्ष" name="op_end_fy">
            <Input placeholder="जस्तै: २०९०/२०९१" />
          </Form.Item>
          <Form.Item label="सामुदायिक वनको कोड" name="cf_code">
            <Input placeholder="जस्तै: MAK/PH/42/33" />
          </Form.Item>
          <Form.Item label="सामुदायिक वनको नाम" name="cf_name" style={{ gridColumn: 'span 2' }}>
            <Input placeholder="जस्तै: अमृता" />
          </Form.Item>
        </div>
      ),
    },
    {
      key: 'D',
      label: 'सामुदायिक वनको चारकिल्ला',
      children: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 16 }}>
          <Form.Item label="पूर्व" name="cf_boundary_east">
            <Input placeholder="पटपटे खहरे" />
          </Form.Item>
          <Form.Item label="दक्षिण" name="cf_boundary_south">
            <Input placeholder="दार्खाडाडा" />
          </Form.Item>
          <Form.Item label="पश्चिम" name="cf_boundary_west">
            <Input placeholder="खोले गाँउ" />
          </Form.Item>
          <Form.Item label="उत्तर" name="cf_boundary_north">
            <Input placeholder="जिम्वाल बारी" />
          </Form.Item>
        </div>
      ),
    },
    {
      key: 'E',
      label: 'भू-आकृति तथा संरक्षण',
      children: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
          <Form.Item label="भू-आकृति क्षेत्र" name="physiography_zone">
            <Input placeholder="प्रणालीबाट स्वतः भरिने" />
          </Form.Item>
          <Form.Item label="संरक्षित क्षेत्र भित्र वा बाहीर" name="protected_area_status">
            <Input placeholder="प्रणालीबाट स्वतः भरिने" />
          </Form.Item>
          <Form.Item label="वन हस्तान्तरण मिति" name="cf_handover_date">
            <NepaliDatePicker />
          </Form.Item>
        </div>
      ),
    },
    {
      key: 'F',
      label: 'उपभोक्ता समूहको स्थान',
      extra: ugPrepopulated ? null : <Button size="small" type="link" onClick={copyForestToUg}>वन स्थानबाट प्रतिलिपि गर्नुहोस्</Button>,
      children: (
        <>
          <div style={{ marginBottom: 8, color: '#888', fontSize: 12 }}>
            {ugPrepopulated ? 'पहिलो पटक वन स्थानबाट स्वतः भरिएको। तपाईं परिवर्तन गर्न सक्नुहुन्छ।' : 'वन स्थान चयन गरेपछि यहाँ स्वतः भरिनेछ।'}
          </div>
          {locationSelects('ug_', ugLoc, handleUgProvinceChange, handleUgDivisionChange, handleUgSubDivisionChange, handleUgMunicipalityChange)}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <Form.Item label="उपभोक्ता समूह रहेको मुख्य टोल" name="ug_settlement">
              <Input placeholder="टोलको नाम" />
            </Form.Item>
          </div>
        </>
      ),
    },
    {
      key: 'G',
      label: 'उपभोक्ता समूहको चारकिल्ला',
      children: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 16 }}>
          <Form.Item label="पूर्व" name="ug_boundary_east"><Input placeholder="रातमाटे डाडा" /></Form.Item>
          <Form.Item label="दक्षिण" name="ug_boundary_south"><Input placeholder="डाँडा गाँउको आवादी" /></Form.Item>
          <Form.Item label="पश्चिम" name="ug_boundary_west"><Input placeholder="प्याउली खोला" /></Form.Item>
          <Form.Item label="उत्तर" name="ug_boundary_north"><Input placeholder="जरूङ्गेको बन" /></Form.Item>
        </div>
      ),
    },
    {
      key: 'H',
      label: 'प्राविधिक तथा वन विशेषता',
      children: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <Form.Item label="प्राविधिक सहयोग गर्ने संस्थाको नाम ठेगाना" name="technical_assistance_org" style={{ gridColumn: 'span 2' }}>
            <Input placeholder="रिसोर्स एन्ड रिसर्च सर्भिस सेन्टर प्रा.लि., बानेश्वर, काठमाडौ" />
          </Form.Item>
          <Form.Item label="कार्ययोजना पास गरेको साधरण सभा बसेको मिति" name="op_general_assembly_date">
            <NepaliDatePicker />
          </Form.Item>
          <Form.Item label="वनको किसिम" name="forest_type" initialValue="प्राकृतिक">
            <Select style={selectStyle}>
              <Select.Option value="प्राकृतिक">प्राकृतिक</Select.Option>
              <Select.Option value="वृक्षारोपण">वृक्षारोपण</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="वनको बाहुल्यता अवस्था" name="forest_abundance" initialValue="रुख">
            <Select style={selectStyle}>
              <Select.Option value="रुख">रुख</Select.Option>
              <Select.Option value="खाँवा">खाँवा</Select.Option>
              <Select.Option value="पुनरोत्पादन">पुनरोत्पादन</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="वनको औषत उमेर वर्ष" name="forest_avg_age" initialValue={80}>
            <InputNumber style={selectStyle} min={0} />
          </Form.Item>
          <Form.Item label="मुख्य गै.का.व.पै." name="main_non_timber_fp">
            <Input placeholder="हर्रो, वर्रो, अमला आदी" />
          </Form.Item>
          <Form.Item label="औषत छत्र घनत्व प्रतिशत" name="avg_crown_density_pct">
            <InputNumber style={selectStyle} min={0} max={100} />
          </Form.Item>
        </div>
      ),
    },
    {
      key: 'K',
      label: 'प्रणाली डाटा ओभरराइड',
      children: (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
          <Form.Item label="न्यूनतम उचाइ (m)" name="altitude_min_m"><InputNumber style={selectStyle} /></Form.Item>
          <Form.Item label="अधिकतम उचाइ (m)" name="altitude_max_m"><InputNumber style={selectStyle} /></Form.Item>
          <Form.Item label="औषत उचाइ (m)" name="altitude_mean_m"><InputNumber style={selectStyle} /></Form.Item>
          <Form.Item label="मुख्य ढलान" name="dominant_slope"><Input /></Form.Item>
          <Form.Item label="मुख्य दिशा" name="dominant_aspect"><Input /></Form.Item>
          <Form.Item label="मुख्य माटो" name="dominant_soil"><Input /></Form.Item>
          <Form.Item label="छत्र घनत्व (%)" name="crown_density_pct"><InputNumber style={selectStyle} min={0} max={100} /></Form.Item>
          <Form.Item label="रूख / हे." name="trees_per_hectare"><InputNumber style={selectStyle} /></Form.Item>
          <Form.Item label="मौज्दात (m³/ha)" name="growing_stock_m3_per_ha"><InputNumber style={selectStyle} /></Form.Item>
          <Form.Item label="बायोमास (t/ha)" name="biomass_t_per_ha"><InputNumber style={selectStyle} /></Form.Item>
          <Form.Item label="कार्बन (tC/ha)" name="carbon_stock_tc_per_ha"><InputNumber style={selectStyle} /></Form.Item>
        </div>
      ),
    },
    {
      key: 'L',
      label: 'भाषा सेटिङ',
      children: (
        <Form.Item label="भाषा" name="plan_language" initialValue="NP">
          <Select style={selectStyle}>
            <Select.Option value="NP">नेपाली</Select.Option>
            <Select.Option value="EN">English</Select.Option>
          </Select>
        </Form.Item>
      ),
    },
  ];

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-start justify-center overflow-y-auto" style={{ paddingTop: '20px', paddingBottom: '20px' }}>
      <div style={{ background: '#fff', borderRadius: 8, width: 900, maxWidth: '96%', padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
            कार्ययोजना मेटाडाटा
          </h2>
          <Button onClick={onClose} type="text">✕</Button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}><Spin size="large" /></div>
        ) : (
          <Form form={form} layout="vertical" onFinish={handleSave} noValidate>
            <Collapse
              defaultActiveKey={['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']}
              items={collapsibleSections}
              style={{ marginBottom: 16 }}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
              <Button onClick={onClose}>रद्द गर्नुहोस्</Button>
              <Button type="primary" htmlType="submit" loading={saving}>सुरक्षित गर्नुहोस्</Button>
            </div>
          </Form>
        )}
      </div>
    </div>
  );
};

export default MetadataForm;
