import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Card,
  Row,
  Col,
  Button,
  Input,
  InputNumber,
  Select,
  Checkbox,
  Radio,
  Table,
  Modal,
  message,
  Space,
  Divider,
  Collapse,
  Dropdown,
  Typography,
  Tag,
  Statistic,
  Empty,
  Drawer
} from 'antd';
import {
  SaveOutlined,
  CloseOutlined,
  DeleteOutlined,
  DownOutlined,
  UpOutlined,
  ReloadOutlined,
  FileTextOutlined,
  BarChartOutlined
} from '@ant-design/icons';
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { yearlyActivitiesApi, forestApi } from '../../services/api';
import DrawingCanvas from './DrawingCanvas';
import './YearlyActivitiesPage.css';
import { downloadBlob } from '../../utils/download';
import CopyTag from '../DetailDescription/CopyTag';

const { Text, Title } = Typography;
const { Panel } = Collapse;

interface YearlyActivitiesPageProps {
  calculationId: string;
  forestName: string;
  area: number;
  onClose?: () => void;
}

interface ProposedActivity {
  id: string;
  potential_activity_id: string;
  potential_activity?: any;
  activity: string;
  program: string;
  unit: string;
  default_quantity: number;
  default_yearly_budget: number;
  assign_to_all_blocks: boolean;
  spatial_assignments: any[];
  drawn_features: any[];
  year_details: any[];
}

interface SpatialAssignment {
  id: string;
  block_id: string;
  block_name: string;
  sub_area_id: string;
  sub_area_name: string;
}

interface DrawnFeature {
  id: string;
  year_number: number;
  feature_type: string;
  geometry: any;
  properties: {
    name?: string;
    label?: string;
    year?: number;
    area_sqm?: number;
    length_m?: number;
    block_ids?: string[];
  };
}

interface Block {
  id: string;
  name: string;
  area_hectares: number;
  geometry?: any;
}

interface SubArea {
  id: string;
  name: string;
  block_id: string;
  block_name: string;
  area_hectares: number;
  category: string;
}

interface YearBudget {
  year: number;
  quantity: number;
  budget: number;
  year_detail_id: string | null;
  location: 'none' | 'all' | 'blocks' | 'sub_areas';
  selected_blocks: string[];
  selected_sub_areas: string[];
}

interface ActivityConfig {
  id: string;
  proposed_activity_id: string;
  activity: string;
  program: string;
  unit: string;
  default_quantity: number;
  default_budget: number;
  expanded: boolean;
  year_budgets: YearBudget[];
  spatial_assignments: SpatialAssignment[];
  drawn_features: DrawnFeature[];
}

interface MatrixRow {
  key: string;
  type: 'proposed' | 'available';
  activity: string;
  program: string;
  unit: string;
  sn: string;
  config?: ActivityConfig;
  potentialId?: string;
}

const YearlyActivitiesPage: React.FC<YearlyActivitiesPageProps> = ({
  calculationId,
  forestName,
  area,
  onClose
}) => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [potentialActivities, setPotentialActivities] = useState<any[]>([]);
  const [proposedActivities, setProposedActivities] = useState<ProposedActivity[]>([]);
  const [activityConfigs, setActivityConfigs] = useState<ActivityConfig[]>([]);
  const [yearDetailsMap, setYearDetailsMap] = useState<Record<string, any[]>>({});
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [subAreas, setSubAreas] = useState<SubArea[]>([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false);
  const [activeDetailConfigIdx, setActiveDetailConfigIdx] = useState<number | null>(null);

  // Load initial data
  useEffect(() => {
    loadData();
  }, [calculationId]);

  // Track unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Mark as unsaved when activity configs change
  const markUnsaved = () => setHasUnsavedChanges(true);
  const markSaved = () => setHasUnsavedChanges(false);

  const loadData = async () => {
    setLoading(true);
    try {
      // Load potential activities (master list)
      const potentialRes = await yearlyActivitiesApi.getPotentialActivities(calculationId);
      setPotentialActivities(potentialRes || []);

      // Load proposed activities
      const proposedRes = await yearlyActivitiesApi.getProposedActivities(calculationId);
      setProposedActivities(proposedRes || []);

      // Load blocks
      const blocksRes = await yearlyActivitiesApi.getBlocksWithSubareas(calculationId);
      const blockList: Block[] = [];
      const subAreaList: SubArea[] = [];
      
      blocksRes?.forEach((item: any) => {
        // Only include actual blocks, not boundary (boundary is shown as "All Blocks" option)
        if (item.type === 'block') {
          blockList.push({
            id: item.id,
            name: item.name,
            area_hectares: item.area_hectares || 0,
            geometry: item.geometry
          });
        }
        // Handle nested sub-areas (if backend returns them nested)
        if (item.sub_areas) {
          item.sub_areas.forEach((sa: any) => {
            subAreaList.push({
              id: sa.id,
              name: sa.name,
              block_id: sa.block_id || item.id,
              block_name: sa.block_name || item.name,
              area_hectares: sa.area_hectares || 0,
              category: sa.category || ''
            });
          });
        }
        // Handle flat sub-area items (backend returns sub-areas as separate items with type === 'sub_area')
        if (item.type === 'sub_area') {
          subAreaList.push({
            id: item.id,
            name: item.name,
            block_id: item.block_id || '',
            block_name: item.block_name || '',
            area_hectares: item.area_hectares || 0,
            category: item.category || ''
          });
        }
      });
      
      setBlocks(blockList);
      setSubAreas(subAreaList);

      // Load existing configs
      await loadActivityConfigs(proposedRes || []);
    } catch (error) {
      console.error('Failed to load data:', error);
      message.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadActivityConfigs = async (proposed: ProposedActivity[]) => {
    const configs: ActivityConfig[] = [];
    
    for (const pa of proposed) {
      // Use potential_activity from backend response if available, otherwise fallback to state lookup
      const potential = pa.potential_activity || potentialActivities.find(p => 
        String(p.id) === String(pa.potential_activity_id)
      );
      
      // Load spatial assignments
      const spatialRes = await yearlyActivitiesApi.getSpatialAssignments(pa.id);
      const existingBlockIds = (spatialRes || [])
        .filter((a: any) => a.block_id && a.assignment_type === 'block')
        .map((a: any) => a.block_id);
      const existingSubAreaIds = (spatialRes || [])
        .filter((a: any) => a.sub_area_id && a.assignment_type === 'sub_area')
        .map((a: any) => a.sub_area_id);
      
      // Load drawn features
      const featuresRes = await yearlyActivitiesApi.getDrawnFeatures(pa.id);
      
      // Load year details
      const yearDetailsRes = await yearlyActivitiesApi.getYearDetails(pa.id);
      yearDetailsMap[pa.id] = yearDetailsRes || [];
      
      // Parse budget values properly (handle string/number)
      const defaultQuantity = typeof pa.default_quantity === 'string' 
        ? parseFloat(pa.default_quantity) || 1 
        : Number(pa.default_quantity) || 1;
      const defaultBudget = typeof pa.default_yearly_budget === 'string'
        ? parseFloat(pa.default_yearly_budget) || 5000
        : Number(pa.default_yearly_budget) || 5000;
      
      configs.push({
        id: pa.id,
        proposed_activity_id: String(pa.potential_activity_id),
        activity: potential?.activity || potential?.activities || 'Unknown',
        program: potential?.program || potential?.progarms || '',
        unit: potential?.unit || 'units',
        default_quantity: defaultQuantity,
        default_budget: defaultBudget,
        expanded: false,
        year_budgets: (yearDetailsRes && yearDetailsRes.length > 0)
          ? yearDetailsRes.map((yd: any) => ({
            year: yd.year_number || 1,
            quantity: typeof yd.quantity === 'string' ? parseFloat(yd.quantity) || 1 : Number(yd.quantity) || 1,
            budget: typeof yd.yearly_budget === 'string' ? parseFloat(yd.yearly_budget) || defaultBudget : Number(yd.yearly_budget) || defaultBudget,
            year_detail_id: yd.id || null,
            location: existingBlockIds.length > 0 ? 'blocks' : existingSubAreaIds.length > 0 ? 'sub_areas' : 'none',
            selected_blocks: existingBlockIds,
            selected_sub_areas: existingSubAreaIds
          }))
          : generateDefaultYearBudgets(pa, defaultBudget),
        spatial_assignments: spatialRes || [],
        drawn_features: featuresRes || []
      });
    }
    
    setActivityConfigs(configs);
    setYearDetailsMap({...yearDetailsMap});
  };

  const generateDefaultYearBudgets = (pa: ProposedActivity, budget: number): YearBudget[] => {
    return Array.from({ length: 10 }, (_, i) => ({
      year: i + 1,
      quantity: pa.default_quantity || 1,
      budget: budget || 5000,
      year_detail_id: null,
      location: 'none' as const,
      selected_blocks: [],
      selected_sub_areas: []
    }));
  };

  // Remove activity
  const handleRemoveActivity = async (configId: string) => {
    try {
      await yearlyActivitiesApi.deleteProposedActivity(configId);
      setActivityConfigs(activityConfigs.filter(c => c.id !== configId));
      setProposedActivities(proposedActivities.filter(p => p.id !== configId));
      message.success('Activity removed');
    } catch (error) {
      console.error('Failed to remove activity:', error);
      message.error('Failed to remove activity');
    }
  };

  // Toggle activity expanded
  const handleToggleExpand = (configId: string) => {
    setActivityConfigs(activityConfigs.map(c =>
      c.id === configId ? { ...c, expanded: !c.expanded } : c
    ));
  };

  // Update quantity
  // Update quantity - also recalculate year budgets
  const handleQuantityChange = (configId: string, value: number) => {
    markUnsaved();
    setActivityConfigs(activityConfigs.map(c => {
      if (c.id !== configId) return c;
      // Recalculate year_budgets based on new quantity
      const newYearBudgets = c.year_budgets.map(yb => ({
        ...yb,
        quantity: value
      }));
      return { ...c, default_quantity: value, year_budgets: newYearBudgets };
    }));
  };

  // Update budget - also recalculate all year budgets
  const handleBudgetChange = (configId: string, value: number) => {
    markUnsaved();
    setActivityConfigs(activityConfigs.map(c => {
      if (c.id !== configId) return c;
      // Recalculate year_budgets based on new default_budget (value is in NPR)
      const newYearBudgets = c.year_budgets.map(yb => ({
        ...yb,
        budget: Math.round(value) // Keep value as NPR
      }));
      return { ...c, default_budget: value, year_budgets: newYearBudgets };
    }));
  };

  // Update specific year budget
  const handleYearBudgetChange = (configId: string, yearIndex: number, value: number) => {
    markUnsaved();
    setActivityConfigs(activityConfigs.map(c =>
      c.id === configId ? {
        ...c,
        year_budgets: c.year_budgets.map((yb, idx) =>
          idx === yearIndex ? { ...yb, budget: value } : yb
        )
      } : c
    ));
  };

  // Update specific year quantity
  const handleYearQuantityChange = (configId: string, yearIndex: number, value: number) => {
    markUnsaved();
    setActivityConfigs(activityConfigs.map(c =>
      c.id === configId ? {
        ...c,
        year_budgets: c.year_budgets.map((yb, idx) =>
          idx === yearIndex ? { ...yb, quantity: value } : yb
        )
      } : c
    ));
  };

  // Update location type
  const handleLocationTypeChange = (configId: string, type: 'none' | 'all' | 'blocks' | 'sub_areas') => {
    const config = activityConfigs.find(c => c.id === configId);
    const currentType = config?.year_budgets[0]?.location;
    const hasSelectedBlocks = (config?.year_budgets[0]?.selected_blocks?.length || 0) > 0;
    const hasSelectedSubAreas = (config?.year_budgets[0]?.selected_sub_areas?.length || 0) > 0;
    
    // Check if user is switching away from blocks/sub_areas with selections
    if ((currentType === 'blocks' && hasSelectedBlocks) || (currentType === 'sub_areas' && hasSelectedSubAreas)) {
      if (type === 'all' || type === 'none') {
        Modal.confirm({
          title: 'Clear Selections?',
          content: `You have ${hasSelectedBlocks ? 'blocks' : 'sub-areas'} selected. Switching to "${type === 'all' ? 'All Blocks' : 'No specific location'}" will clear these selections. Do you want to continue?`,
          okText: 'Clear & Switch',
          cancelText: 'Keep Selections',
          okButtonProps: { danger: true },
          onOk: () => {
            markUnsaved();
            setActivityConfigs(activityConfigs.map(c =>
              c.id === configId ? {
                ...c,
                year_budgets: c.year_budgets.map(yb => ({
                  ...yb,
                  location: type,
                  selected_blocks: [],
                  selected_sub_areas: []
                }))
              } : c
            ));
          }
        });
        return;
      }
    }
    
    markUnsaved();
    setActivityConfigs(activityConfigs.map(c =>
      c.id === configId ? {
        ...c,
        year_budgets: c.year_budgets.map(yb => ({
          ...yb,
          location: type,
          selected_blocks: type !== 'blocks' ? [] : yb.selected_blocks,
          selected_sub_areas: type !== 'sub_areas' ? [] : yb.selected_sub_areas
        }))
      } : c
    ));
  };

  // Toggle block selection
  const handleBlockToggle = (configId: string, blockId: string) => {
    // Skip if blockId is not a valid UUID format
    if (!blockId || blockId.length !== 36) {
      console.warn('Invalid block ID:', blockId);
      return;
    }
    
    markUnsaved();
    setActivityConfigs(activityConfigs.map(c => {
      if (c.id !== configId) return c;
      return {
        ...c,
        year_budgets: c.year_budgets.map(yb => {
          const hasBlock = yb.selected_blocks.includes(blockId);
          return {
            ...yb,
            selected_blocks: hasBlock
              ? yb.selected_blocks.filter(id => id !== blockId)
              : [...yb.selected_blocks, blockId]
          };
        })
      };
    }));
  };

  // Toggle sub-area selection - auto-select parent block
  const handleSubAreaToggle = (configId: string, subAreaId: string) => {
    // Skip if subAreaId is not a valid UUID format
    if (!subAreaId || subAreaId.length !== 36) {
      console.warn('Invalid sub-area ID:', subAreaId);
      return;
    }
    
    markUnsaved();
    const subArea = subAreas.find(sa => sa.id === subAreaId);
    const parentBlockId = subArea?.block_id;
    
    setActivityConfigs(activityConfigs.map(c => {
      if (c.id !== configId) return c;
      return {
        ...c,
        year_budgets: c.year_budgets.map(yb => {
          const hasSubArea = yb.selected_sub_areas.includes(subAreaId);
          let newSelectedBlocks = [...yb.selected_blocks];
          
          // Only add parent block if it's a valid UUID
          if (!hasSubArea && parentBlockId && parentBlockId.length === 36 && !newSelectedBlocks.includes(parentBlockId)) {
            newSelectedBlocks.push(parentBlockId);
          }
          
          return {
            ...yb,
            selected_blocks: newSelectedBlocks,
            selected_sub_areas: hasSubArea
              ? yb.selected_sub_areas.filter(id => id !== subAreaId)
              : [...yb.selected_sub_areas, subAreaId]
          };
        })
      };
    }));
  };

  // Update drawn features
  const handleFeaturesChange = async (configId: string) => {
    try {
      const features = await yearlyActivitiesApi.getDrawnFeatures(configId);
      setActivityConfigs(activityConfigs.map(c =>
        c.id === configId ? { ...c, drawn_features: features || [] } : c
      ));
    } catch (error) {
      console.error('Failed to load features:', error);
    }
  };

  // Copy feature to year
  const handleCopyFeature = async (configId: string, featureId: string, targetYear: number) => {
    try {
      await yearlyActivitiesApi.copyDrawnFeature(configId, featureId, targetYear);
      await handleFeaturesChange(configId);
      message.success(`Feature copied to Year ${targetYear}`);
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to copy feature');
    }
  };

  // Delete feature
  const handleDeleteFeature = async (configId: string, featureId: string) => {
    try {
      await yearlyActivitiesApi.deleteDrawnFeature(configId, featureId);
      await handleFeaturesChange(configId);
      message.success('Feature deleted');
    } catch (error) {
      console.error('Failed to delete feature:', error);
      message.error('Failed to delete feature');
    }
  };

  // Export to CSV
  const handleExportCSV = async () => {
    const headers = [
      'S.No',
      'Activity',
      'Program',
      'Unit',
      'Quantity (Year-Value)',
      'Budget (Year-Value)',
      'Total Budget (10 Yrs)',
      'Location Type',
      'Location Details',
      'Spatial Features'
    ];
    
    const rows = activityConfigs.map((config, idx) => {
      // Quantity: only years with value > 0
      const qtyValues = config.year_budgets
        .filter(yb => yb.quantity > 0)
        .map(yb => `Y${yb.year}:${Math.round(yb.quantity)}`)
        .join(', ');
      
      // Budget: only years with value > 0
      const budgetValues = config.year_budgets
        .filter(yb => yb.budget > 0)
        .map(yb => `Y${yb.year}:${yb.budget}`)
        .join(', ');
      
      // Total budget
      const totalBudget = config.year_budgets.reduce((sum, yb) => sum + yb.budget, 0);
      
      // Location details
      const locationType = config.year_budgets[0]?.location || 'all';
      let locationDetails = '';
      if (locationType === 'all') {
        locationDetails = 'All Blocks';
      } else if (locationType === 'blocks') {
        const selectedBlockNames = config.year_budgets[0]?.selected_blocks
          ?.map(id => blocks.find(b => b.id === id)?.name)
          .filter(Boolean)
          .join(', ');
        locationDetails = selectedBlockNames || '';
      } else if (locationType === 'sub_areas') {
        const selectedSubAreaNames = config.year_budgets[0]?.selected_sub_areas
          ?.map(id => subAreas.find(sa => sa.id === id)?.name)
          .filter(Boolean)
          .join(', ');
        locationDetails = selectedSubAreaNames || '';
      } else {
        locationDetails = 'No specific location';
      }
      
      // Spatial features
      const featureNames = config.drawn_features
        .map(f => f.properties?.name || f.properties?.label || 'Unnamed')
        .join(', ');
      
      return [
        idx + 1,
        config.activity,
        config.program,
        config.unit,
        qtyValues || 'None',
        budgetValues || 'None',
        totalBudget,
        locationType,
        locationDetails,
        featureNames || 'None'
      ];
    });
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');
    
    const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '');
    const name = forestName.replace(/\s+/g, '_');
    downloadBlob(new Blob([csvContent], { type: 'text/csv;charset=utf-8;' }), `${name}_YearlyActivity_Plan_${dateStr}.csv`);
    message.success('CSV exported successfully');
  };

  // Save all
  const handleSaveAll = async () => {
    setSaving(true);
    try {
      for (const config of activityConfigs) {
        // Update proposed activity
        await yearlyActivitiesApi.updateProposedActivity(config.id, {
          default_quantity: config.default_quantity,
          default_yearly_budget: config.default_budget
        });

        // Update year details
        for (const yb of config.year_budgets) {
          if (yb.year_detail_id) {
            await yearlyActivitiesApi.updateYearDetail(config.id, yb.year_detail_id, {
              quantity: yb.quantity,
              yearly_budget: yb.budget
            });
          } else {
            const newDetail = await yearlyActivitiesApi.createYearDetail(config.id, {
              year_number: yb.year,
              quantity: yb.quantity,
              yearly_budget: yb.budget
            });
            yb.year_detail_id = newDetail.id;
          }
        }

        // Sync spatial assignments (blocks/sub-areas)
        const locationType = config.year_budgets[0]?.location || 'all';
        const selectedBlocks = config.year_budgets[0]?.selected_blocks || [];
        const selectedSubAreas = config.year_budgets[0]?.selected_sub_areas || [];
        
        // Get current spatial assignments
        const currentAssignments = config.spatial_assignments || [];
        
        if (locationType === 'all' || locationType === 'none') {
          // Remove all specific assignments when "all" or "none" is selected
          for (const assignment of currentAssignments) {
            await yearlyActivitiesApi.deleteSpatialAssignment(config.id, assignment.id);
          }
        } else if (locationType === 'blocks') {
          // Sync block assignments
          const currentBlockIds = currentAssignments.filter(a => a.block_id).map(a => a.block_id);
          
          // Add new blocks (validate UUID format)
          for (const blockId of selectedBlocks) {
            if (!currentBlockIds.includes(blockId) && blockId && blockId.length === 36) {
              await yearlyActivitiesApi.createSpatialAssignment(config.id, {
                block_id: blockId,
                assignment_type: 'block'
              });
            }
          }
          
          // Remove deselected blocks
          for (const assignment of currentAssignments) {
            if (assignment.block_id && !selectedBlocks.includes(assignment.block_id)) {
              await yearlyActivitiesApi.deleteSpatialAssignment(config.id, assignment.id);
            }
          }
        } else if (locationType === 'sub_areas') {
          // Sync sub-area assignments
          const currentSubAreaIds = currentAssignments.filter(a => a.sub_area_id).map(a => a.sub_area_id);
          
          // Add new sub-areas (validate UUID format)
          for (const subAreaId of selectedSubAreas) {
            if (!currentSubAreaIds.includes(subAreaId) && subAreaId && subAreaId.length === 36) {
              const subArea = subAreas.find(sa => sa.id === subAreaId);
              await yearlyActivitiesApi.createSpatialAssignment(config.id, {
                block_id: subArea?.block_id && subArea.block_id.length === 36 ? subArea.block_id : null,
                sub_area_id: subAreaId,
                assignment_type: 'sub_area'
              });
            }
          }
          
          // Remove deselected sub-areas
          for (const assignment of currentAssignments) {
            if (assignment.sub_area_id && !selectedSubAreas.includes(assignment.sub_area_id)) {
              await yearlyActivitiesApi.deleteSpatialAssignment(config.id, assignment.id);
            }
          }
        }
      }
      message.success('All changes saved');
      markSaved();
      
      // Update local yearDetailsMap to reflect saved state
      const newYearDetailsMap = {...yearDetailsMap};
      for (const config of activityConfigs) {
        newYearDetailsMap[config.id] = config.year_budgets.map(yb => ({
          id: yb.year_detail_id,
          year_number: yb.year,
          quantity: yb.quantity,
          yearly_budget: yb.budget
        }));
      }
      setYearDetailsMap(newYearDetailsMap);
      
      // Also update activityConfigs to reflect saved year_detail_ids and spatial_assignments
      setActivityConfigs(prev => prev.map(config => {
        const updatedConfig = {
          ...config,
          year_budgets: config.year_budgets.map(yb => ({ ...yb }))
        };
        
        // Update spatial_assignments based on what we did in the save
        const locationType = config.year_budgets[0]?.location || 'all';
        const selectedBlocks = config.year_budgets[0]?.selected_blocks || [];
        const selectedSubAreas = config.year_budgets[0]?.selected_sub_areas || [];
        const originalAssignments = config.spatial_assignments || [];
        
        if (locationType === 'all' || locationType === 'none') {
          // All assignments should be deleted
          updatedConfig.spatial_assignments = [];
        } else if (locationType === 'blocks') {
          // Keep only selected block assignments
          updatedConfig.spatial_assignments = originalAssignments.filter(
            a => a.block_id && selectedBlocks.includes(a.block_id)
          );
        } else if (locationType === 'sub_areas') {
          // Keep only selected sub-area assignments
          updatedConfig.spatial_assignments = originalAssignments.filter(
            a => a.sub_area_id && selectedSubAreas.includes(a.sub_area_id)
          );
        }
        
        return updatedConfig;
      }));
    } catch (error: any) {
      console.error('Failed to save:', error);
      const rawDetail = error.response?.data?.detail;
      let errorDetail = 'Unknown error occurred';
      if (typeof rawDetail === 'string') {
        errorDetail = rawDetail;
      } else if (Array.isArray(rawDetail)) {
        errorDetail = rawDetail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join(', ');
      } else if (rawDetail && typeof rawDetail === 'object') {
        errorDetail = rawDetail.msg || rawDetail.message || JSON.stringify(rawDetail);
      } else if (error.message) {
        errorDetail = error.message;
      }
      message.error(`Failed to save: ${errorDetail}`);
    } finally {
      setSaving(false);
    }
  };

  // Calculate totals (display in thousands to match user input)
  const totals = useMemo(() => {
    let totalActivities = activityConfigs.length;
    let totalBudgetRaw = activityConfigs.reduce((sum, c) => 
      sum + c.year_budgets.reduce((ySum, yb) => ySum + (Number(yb.budget) || 0), 0), 0
    );
    let totalFeatures = activityConfigs.reduce((sum, c) => sum + (c.drawn_features?.length || 0), 0);
    return { 
      totalActivities, 
      totalBudgetRaw,  // Actual NPR value
      totalBudget: Math.round(totalBudgetRaw / 1000),  // Display in thousands
      totalFeatures 
    };
  }, [activityConfigs]);

  // OP document preview data — mirrors the backend _collect_yearly_activities_data()
  const opPreview = useMemo(() => {
    const planYears = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    // Year-wise budget summary
    const yearSummary = planYears.map(y => {
      let yearBudget = 0, yearQty = 0, yearCount = 0;
      activityConfigs.forEach(c => {
        const yb = c.year_budgets[y - 1];
        if (yb) {
          const b = Number(yb.budget) || 0;
          const q = Number(yb.quantity) || 0;
          yearBudget += b;
          yearQty += q;
          if (b > 0 || q > 0) yearCount++;
        }
      });
      return { year: y, activity_count: yearCount, total_quantity: yearQty, total_budget: yearBudget };
    });
    let cumulative = 0;
    const yearChartData = yearSummary.map(ys => {
      cumulative += ys.total_budget;
      return { year: `Y${ys.year}`, budget: ys.total_budget, cumulative, label: `Year ${ys.year}` };
    });
    const totalBudgetAll = cumulative;

    // Program-wise pie data
    const progMap: Record<string, number> = {};
    activityConfigs.forEach(c => {
      const prog = c.program || 'Uncategorized';
      const total = c.year_budgets.reduce((s, yb) => s + (Number(yb.budget) || 0), 0);
      progMap[prog] = (progMap[prog] || 0) + total;
    });
    const programPieData = Object.entries(progMap)
      .filter(([, v]) => v > 0)
      .sort(([, a], [, b]) => b - a)
      .map(([program, budget]) => ({ program, budget }));

    return { yearSummary, yearChartData, programPieData, totalBudgetAll };
  }, [activityConfigs]);

  // Build combined matrix rows (all potential activities + proposed activities)
  const matrixRows = useMemo<MatrixRow[]>(() => {
    const rows: MatrixRow[] = [];
    const proposedIds = new Set(activityConfigs.map(c => c.proposed_activity_id));
    let sn = 0;

    // Group potential activities by program, then sort
    const byProgram = new Map<string, any[]>();
    potentialActivities.forEach(pa => {
      const program = pa.program || pa.progarms || 'Uncategorized';
      if (!byProgram.has(program)) byProgram.set(program, []);
      byProgram.get(program)!.push(pa);
    });
    const sortedPrograms = Array.from(byProgram.keys()).sort();
    const sortedActivities: any[] = [];
    sortedPrograms.forEach(prog => {
      sortedActivities.push(...byProgram.get(prog)!);
    });

    // First pass: add proposed activities (preserving their order within each program)
    const addedKeys = new Set<string>();
    sortedActivities.forEach(pa => {
      const paId = String(pa.id);
      const matchingConfig = activityConfigs.find(c => c.proposed_activity_id === paId);
      if (matchingConfig) {
        sn++;
        rows.push({
          key: matchingConfig.id,
          type: 'proposed',
          activity: matchingConfig.activity,
          program: matchingConfig.program || 'Uncategorized',
          unit: matchingConfig.unit,
          sn: String(sn),
          config: matchingConfig,
        });
        addedKeys.add(paId);
      }
    });

    // Second pass: add available activities (not yet proposed)
    sortedActivities.forEach(pa => {
      const paId = String(pa.id);
      if (addedKeys.has(paId)) return;
      sn++;
      rows.push({
        key: `avail-${paId}`,
        type: 'available',
        activity: pa.activity || pa.activities || 'Unknown',
        program: pa.program || pa.progarms || 'Uncategorized',
        unit: pa.unit || 'units',
        sn: String(sn),
        potentialId: paId,
      });
    });

    return rows;
  }, [activityConfigs, potentialActivities]);

  // Group rows by program for rendering
  const groupedByProgram = useMemo(() => {
    const map = new Map<string, MatrixRow[]>();
    matrixRows.forEach(row => {
      const program = row.program || 'Uncategorized';
      if (!map.has(program)) map.set(program, []);
      map.get(program)!.push(row);
    });
    const groups: { program: string; rows: MatrixRow[]; count: number }[] = [];
    map.forEach((rows, program) => {
      const proposedCount = rows.filter(r => r.type === 'proposed').length;
      groups.push({ program, rows, count: proposedCount });
    });
    return groups;
  }, [matrixRows]);

  const closeDetailDrawer = () => setDetailDrawerVisible(false);

  const activeDetailConfig = useMemo(() => {
    if (activeDetailConfigIdx === null || activeDetailConfigIdx < 0 || activeDetailConfigIdx >= activityConfigs.length) return null;
    return activityConfigs[activeDetailConfigIdx];
  }, [activeDetailConfigIdx, activityConfigs]);

  const handleChooseActivity = async (potentialId: string) => {
    try {
      const newActivity = await yearlyActivitiesApi.createProposedActivity(calculationId, {
        potential_activity_id: Number(potentialId),
        default_quantity: 1,
        default_yearly_budget: 5000
      });
      const potential = potentialActivities.find(p => String(p.id) === potentialId);
      const newConfig: ActivityConfig = {
        id: newActivity.id,
        proposed_activity_id: potentialId,
        activity: potential?.activity || potential?.activities || 'Unknown',
        program: potential?.program || potential?.progarms || '',
        unit: potential?.unit || 'units',
        default_quantity: 1,
        default_budget: 5000,
        expanded: true,
        year_budgets: generateDefaultYearBudgets({ default_quantity: 1, default_yearly_budget: 5000 } as ProposedActivity, 5000),
        spatial_assignments: [],
        drawn_features: []
      };
      const newConfigs = [...activityConfigs, newConfig];
      const newIdx = newConfigs.length - 1;
      setActivityConfigs(newConfigs);
      setProposedActivities([...proposedActivities, newActivity]);
      setActiveDetailConfigIdx(newIdx);
      setDetailDrawerVisible(true);
      message.success('Activity added');
    } catch (error) {
      console.error('Failed to add activity:', error);
      message.error('Failed to add activity');
    }
  };

  // Get blocks for a specific config (based on location selection)
  const getBlocksForConfig = (config: ActivityConfig) => {
    if (config.year_budgets[0]?.location === 'sub_areas') {
      const selectedSubAreaIds = config.year_budgets[0]?.selected_sub_areas || [];
      const relevantBlocks = subAreas
        .filter(sa => selectedSubAreaIds.includes(sa.id))
        .map(sa => blocks.find(b => b.id === sa.block_id))
        .filter(Boolean);
      return relevantBlocks as Block[];
    }
    return blocks;
  };

  if (loading) {
    return (
      <div className="yearly-activities-loading">
        <Text>Loading...</Text>
      </div>
    );
  }

  return (
    <div className="yearly-activities-page">
      {/* Header */}
      <div className="page-header">
        <div className="header-info">
          <Title level={4}>
            Yearly Activities Planning
            <CopyTag label="{{ya_activity_plan_detail}}" value="{{ya_activity_plan_detail}}" variant="section" />
          </Title>
          <Text strong>Forest: {forestName}</Text>
          <Text type="secondary"> | Area: {Number(area || 0).toFixed(1)} ha</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={loadData}>
            Refresh
          </Button>
          <Button onClick={onClose} icon={<CloseOutlined />}>
            Close
          </Button>
        </Space>
      </div>

      {/* Summary Bar */}
      <div className="summary-bar">
        <Statistic title="Activities" value={totals.totalActivities} />
        <Statistic 
          title="Total Budget (10 years)" 
          value={totals.totalBudget} 
          suffix="ह (NPR 1,000s)"
          formatter={(val) => Math.round(Number(val)).toLocaleString()} 
        />
        <Statistic title="Spatial Features" value={totals.totalFeatures} />
      </div>

      {/* Activity Catalog Matrix */}
      <div className="activity-cards">
        <div className="activity-matrix">
          {groupedByProgram.map(group => (
            <div key={group.program} className="matrix-program-group">
              <div className="matrix-program-header">
                <Space>
                  <Text strong style={{ fontSize: 15 }}>{group.program}</Text>
                  <Tag color="blue">{group.count}/{group.rows.length} chosen</Tag>
                </Space>
              </div>
              <Table
                size="small"
                dataSource={group.rows}
                rowKey="key"
                pagination={false}
                showHeader={true}
                scroll={{ x: 'max-content' }}
                onRow={(record) => ({
                  onClick: () => {
                    if (record.type === 'proposed') {
                      const idx = activityConfigs.findIndex(c => c.id === record.key);
                      setActiveDetailConfigIdx(idx);
                      setDetailDrawerVisible(true);
                    }
                  },
                  style: { cursor: record.type === 'proposed' ? 'pointer' : 'default' },
                  className: record.type === 'proposed' ? 'matrix-row-chosen' : ''
                })}
                columns={[
                  {
                    title: '#',
                    dataIndex: 'sn',
                    width: 40,
                    align: 'center' as const,
                  },
                  {
                    title: 'Activity',
                    dataIndex: 'activity',
                    width: 280,
                    render: (text: string, record: MatrixRow) => (
                      <Space>
                        <Text style={record.type === 'available' ? { color: '#999' } : undefined}>{text}</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>({record.unit})</Text>
                        {record.type === 'proposed' && <Tag color="green" style={{ fontSize: 10, lineHeight: '16px' }}>Chosen</Tag>}
                      </Space>
                    )
                  },
                  {
                    title: '',
                    width: 100,
                    align: 'center' as const,
                    render: (_: any, record: MatrixRow) => {
                      if (record.type === 'available') {
                        return (
                          <Button
                            type="primary"
                            size="small"
                            style={{ fontSize: 12, height: 26 }}
                            onClick={(e) => {
                              e.stopPropagation();
                              handleChooseActivity(record.potentialId!);
                            }}
                          >
                            Choose
                          </Button>
                        );
                      }
                      return (
                        <Button
                          size="small"
                          type="link"
                          style={{ fontSize: 12, height: 22 }}
                          onClick={(e) => {
                            e.stopPropagation();
                            const idx = activityConfigs.findIndex(c => c.id === record.key);
                            setActiveDetailConfigIdx(idx);
                            setDetailDrawerVisible(true);
                          }}
                        >
                          Edit
                        </Button>
                      );
                    }
                  },
                  ...Array.from({ length: 10 }, (_, i) => ({
                    title: `Y${i + 1}`,
                    width: 90,
                    align: 'center' as const,
                    render: (_: any, record: MatrixRow) => (
                      <EditableYearCell
                        record={record}
                        yearIndex={i}
                        onYearBudgetChange={handleYearBudgetChange}
                        onYearQuantityChange={handleYearQuantityChange}
                      />
                    ),
                  })),
                  {
                    title: 'Total',
                    width: 90,
                    align: 'center' as const,
                    render: (_: any, record: MatrixRow) => {
                      if (record.type === 'available') return null;
                      const total = record.config!.year_budgets.reduce((s, yb) => s + (Number(yb.budget) || 0), 0);
                      return <Text strong style={{ fontSize: 13 }}>{Math.round(total / 1000).toLocaleString()}ह</Text>;
                    }
                  },
                ]}
              />
            </div>
          ))}
        </div>
      </div>

      {/* OP Document Preview Section */}
      {activityConfigs.length > 0 && (
        <Card
          className="op-preview-card"
          size="small"
          title={
            <Space>
              <BarChartOutlined />
              <span>OP Document Preview — 10-Year Plan Summary</span>
            </Space>
          }
        >
          <Row gutter={[16, 16]}>
            {/* Year-wise Budget Bar Chart */}
            <Col xs={24} lg={14}>
              <div className="op-preview-chart">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Text strong style={{ fontSize: 13 }}>Year-wise Budget (NPR)</Text>
                  <CopyTag label="{{chart:ya_budget_year_bar}}" value="{{chart:ya_budget_year_bar}}" variant="variable" />
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={opPreview.yearChartData} margin={{ top: 8, right: 16, left: 16, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="year" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${Math.round(v / 1000)}K`} />
                    <RechartsTooltip formatter={(value: number) => `NPR ${value.toLocaleString()}`} />
                    <Bar dataKey="budget" radius={[4, 4, 0, 0]}>
                      {opPreview.yearChartData.map((entry, i) => (
                        <Cell key={i} fill={['#2ecc71','#27ae60','#1abc9c','#16a085','#3498db','#2980b9','#9b59b6','#8e44ad','#e67e22','#d35400'][i]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Col>

            {/* Program-wise Budget Pie Chart */}
            <Col xs={24} lg={10}>
              <div className="op-preview-chart">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Text strong style={{ fontSize: 13 }}>Program Budget Share</Text>
                  <CopyTag label="{{chart:ya_program_pie}}" value="{{chart:ya_program_pie}}" variant="variable" />
                </div>
                {opPreview.programPieData.length > 0 && (
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie
                        data={opPreview.programPieData}
                        dataKey="budget"
                        nameKey="program"
                        cx="50%"
                        cy="50%"
                        outerRadius={70}
                        innerRadius={30}
                        label={(entry: any) => `${entry.program} (${Math.round(entry.budget / opPreview.totalBudgetAll * 100)}%)`}
                        labelLine={false}
                      >
                        {opPreview.programPieData.map((_, i) => (
                          <Cell key={i} fill={['#27ae60','#2980b9','#e67e22','#e74c3c','#9b59b6','#f1c40f','#1abc9c','#2c3e50','#d35400','#8e44ad'][i % 10]} />
                        ))}
                      </Pie>
                      <RechartsTooltip formatter={(value: number) => `NPR ${value.toLocaleString()}`} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </Col>
          </Row>

          {/* Year Summary Table — matches {{ya_year_summary}} */}
          <Divider style={{ margin: '12px 0' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Text strong style={{ fontSize: 13 }}>Year-wise Summary</Text>
            <CopyTag label="{{ya_year_summary}}" value="{{ya_year_summary}}" variant="variable" />
          </div>
          <Table
            size="small"
            dataSource={opPreview.yearSummary}
            rowKey="year"
            pagination={false}
            bordered
            columns={[
              { title: 'Year', dataIndex: 'year', width: 60, align: 'center' },
              { title: 'Activities', dataIndex: 'activity_count', width: 80, align: 'center' },
              { title: 'Total Qty', dataIndex: 'total_quantity', width: 100, align: 'right', render: (v: number) => v.toFixed(2) },
              { title: 'Budget (NPR)', dataIndex: 'total_budget', align: 'right', render: (v: number) => v.toLocaleString() },
            ]}
          />
        </Card>
      )}

      {/* Activity Detail Full-Screen Drawer */}
      <Drawer
        title={activeDetailConfig ? `${(activeDetailConfigIdx ?? 0) + 1}. ${activeDetailConfig.activity}` : 'Activity Details'}
        open={detailDrawerVisible}
        onClose={closeDetailDrawer}
        width="100%"
        extra={
          <Space>
            <Button onClick={closeDetailDrawer}>Close</Button>
            <Button
              danger
              onClick={() => {
                if (activeDetailConfig) {
                  handleRemoveActivity(activeDetailConfig.id);
                  closeDetailDrawer();
                }
              }}
            >
              Remove
            </Button>
            <Button
              type="primary"
              onClick={async () => {
                await handleSaveAll();
                closeDetailDrawer();
              }}
            >
              OK
            </Button>
          </Space>
        }
      >
        {activeDetailConfig && activeDetailConfigIdx !== null && activeDetailConfigIdx >= 0 && activeDetailConfigIdx < activityConfigs.length && (
          <ActivityCard
            config={activeDetailConfig}
            index={(activeDetailConfigIdx ?? 0) + 1}
            blocks={blocks}
            subAreas={subAreas}
            embedded
            showRemove={false}
            onToggleExpand={() => {}}
            onRemove={() => {
              handleRemoveActivity(activeDetailConfig.id);
              closeDetailDrawer();
            }}
            onQuantityChange={(val) => handleQuantityChange(activeDetailConfig.id, val)}
            onBudgetChange={(val) => handleBudgetChange(activeDetailConfig.id, val)}
            onYearBudgetChange={(configId, yearIndex, value) => handleYearBudgetChange(configId, yearIndex, value)}
            onYearQuantityChange={(configId, yearIndex, value) => handleYearQuantityChange(configId, yearIndex, value)}
            onLocationTypeChange={(type) => handleLocationTypeChange(activeDetailConfig.id, type)}
            onBlockToggle={(blockId) => handleBlockToggle(activeDetailConfig.id, blockId)}
            onSubAreaToggle={(subAreaId) => handleSubAreaToggle(activeDetailConfig.id, subAreaId)}
            onFeaturesChange={() => handleFeaturesChange(activeDetailConfig.id)}
            onCopyFeature={(featureId, year) => handleCopyFeature(activeDetailConfig.id, featureId, year)}
            onDeleteFeature={(featureId) => handleDeleteFeature(activeDetailConfig.id, featureId)}
          />
        )}
      </Drawer>

      {/* Footer */}
      <div className="page-footer">
        <Space>
          <Button 
            onClick={() => {
              if (hasUnsavedChanges) {
                Modal.confirm({
                  title: 'Unsaved Changes',
                  content: 'You have unsaved changes. Are you sure you want to leave? Your changes will be lost.',
                  okText: 'Leave Without Saving',
                  cancelText: 'Cancel',
                  okButtonProps: { danger: true },
                  onOk: () => {
                    markSaved();
                    onClose();
                  }
                });
              } else {
                onClose();
              }
            }}
          >
            Cancel
          </Button>
          <Button 
            icon={<FileTextOutlined />} 
            onClick={handleExportCSV}
            disabled={activityConfigs.length === 0}
          >
            Export CSV
          </Button>
          <Button 
            type="primary" 
            icon={<SaveOutlined />} 
            loading={saving}
            onClick={handleSaveAll}
            disabled={activityConfigs.length === 0}
          >
            Save All Changes
          </Button>
        </Space>
      </div>

    </div>
  );
};

// Activity Card Component
interface ActivityCardProps {
  config: ActivityConfig;
  index: number;
  blocks: Block[];
  subAreas: SubArea[];
  onToggleExpand: () => void;
  onRemove: () => void;
  onQuantityChange: (value: number) => void;
  onBudgetChange: (value: number) => void;
  onYearBudgetChange: (configId: string, yearIndex: number, value: number) => void;
  onYearQuantityChange: (configId: string, yearIndex: number, value: number) => void;
  onLocationTypeChange: (type: 'none' | 'all' | 'blocks' | 'sub_areas') => void;
  onBlockToggle: (blockId: string) => void;
  onSubAreaToggle: (subAreaId: string) => void;
  onFeaturesChange: () => void;
  onCopyFeature: (featureId: string, year: number) => void;
  onDeleteFeature: (featureId: string) => void;
  embedded?: boolean;
  showRemove?: boolean;
}

const ActivityCard: React.FC<ActivityCardProps> = ({
  config,
  index,
  blocks,
  subAreas,
  onToggleExpand,
  onRemove,
  onQuantityChange,
  onBudgetChange,
  onYearBudgetChange,
  onYearQuantityChange,
  onLocationTypeChange,
  onBlockToggle,
  onSubAreaToggle,
  onFeaturesChange,
  onCopyFeature,
  onDeleteFeature,
  embedded = false,
  showRemove = true
}) => {
  const [editingQuantity, setEditingQuantity] = useState(false);
  const [editingBudget, setEditingBudget] = useState(false);
  const [tempQuantity, setTempQuantity] = useState(config.default_quantity);
  const [tempBudget, setTempBudget] = useState(config.default_budget);
  const [showAddFeature, setShowAddFeature] = useState(false);
  const [copyYearModal, setCopyYearModal] = useState<string | null>(null);
  const [editingQtyIndex, setEditingQtyIndex] = useState<number | null>(null);
  const [tempQty, setTempQty] = useState(0);
  const [editingYearIndex, setEditingYearIndex] = useState<number | null>(null);
  const [tempYearBudget, setTempYearBudget] = useState(0);

  const locationType = config.year_budgets[0]?.location || 'all';
  const selectedBlocks = config.year_budgets[0]?.selected_blocks || [];
  const selectedSubAreas = config.year_budgets[0]?.selected_sub_areas || [];

  const totalBudget = config.year_budgets.reduce((sum, yb) => sum + yb.budget, 0);

  // Get filtered blocks based on sub-area selection
  const filteredBlocks = locationType === 'sub_areas' && selectedSubAreas.length > 0
    ? blocks.filter(b => subAreas.some(sa => selectedSubAreas.includes(sa.id) && sa.block_id === b.id))
    : blocks;

  const expandedContent = (
    <div className="card-content">
      {/* Quantity and Budget */}
      <div className="content-section">
        <Row gutter={24}>
          <Col span={12}>
            <label>Quantity (per year):</label>
            <InputNumber
              min={1}
              value={config.default_quantity}
              onChange={(val) => onQuantityChange(val || 1)}
              style={{ width: '100%' }}
              addonAfter={config.unit}
            />
          </Col>
          <Col span={12}>
            <label>Budget (per year):</label>
            <InputNumber
              min={0}
              value={config.default_budget / 1000}
              onChange={(val) => onBudgetChange((val || 0) * 1000)}
              style={{ width: '100%' }}
              addonAfter="ह (NPR)"
              formatter={(value) => `${value || 0}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              = NPR {config.default_budget.toLocaleString()}
            </Text>
          </Col>
        </Row>
      </div>

      <Divider />

      {/* Location Selection */}
      <div className="content-section">
        <label>📍 Location:</label>
        <Radio.Group
          value={locationType}
          onChange={(e) => onLocationTypeChange(e.target.value)}
          style={{ display: 'block', marginTop: 8 }}
        >
          <Space direction="vertical" style={{ width: '100%' }}>
            <Radio value="none">
              <Space>
                <span>No specific location</span>
                <Tag color="default">General activity</Tag>
              </Space>
            </Radio>

            <Radio value="all">
              <Space>
                <span>All Blocks (Forest-wide)</span>
                <Tag color="green">{blocks.length} blocks</Tag>
              </Space>
            </Radio>

            <Radio value="blocks" disabled={blocks.length === 0 || locationType === 'all' || locationType === 'sub_areas'}>
              <Space>
                <span>Specific Blocks</span>
                {locationType === 'blocks' && (
                  <Tag color="blue">{selectedBlocks.length} selected</Tag>
                )}
              </Space>
            </Radio>
            
            {locationType === 'blocks' && (
              <div className="checkbox-list">
                {blocks.map(block => (
                  <Checkbox
                    key={block.id}
                    checked={selectedBlocks.includes(block.id)}
                    onChange={() => onBlockToggle(block.id)}
                    style={{ marginLeft: 24 }}
                  >
                    <Space>
                      <span>{block.name}</span>
                      <Tag>{block.area_hectares.toFixed(0)} ha</Tag>
                    </Space>
                  </Checkbox>
                ))}
              </div>
            )}

            <Radio value="sub_areas" disabled={subAreas.length === 0 || locationType === 'all' || locationType === 'blocks'}>
              <Space>
                <span>Specific Sub-Areas</span>
                {locationType === 'sub_areas' && (
                  <Tag color="green">{selectedSubAreas.length} selected</Tag>
                )}
              </Space>
            </Radio>

                {locationType === 'sub_areas' && (
                  <div className="checkbox-list">
                    {subAreas.map(sa => (
                      <Checkbox
                        key={sa.id}
                        checked={selectedSubAreas.includes(sa.id)}
                        onChange={() => onSubAreaToggle(sa.id)}
                        style={{ marginLeft: 24 }}
                      >
                        <Space>
                          <span>{sa.name}</span>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            ({sa.block_name})
                          </Text>
                          <Tag>{sa.area_hectares.toFixed(0)} ha</Tag>
                        </Space>
                      </Checkbox>
                    ))}
                  </div>
                )}
              </Space>
            </Radio.Group>
          </div>

          <Divider />

          {/* Spatial Features */}
          <div className="content-section">
            <div className="section-header">
              <label>🗺️ Spatial Features:</label>
              <Space>
                <Button 
                  size="small" 
                  onClick={() => setShowAddFeature(!showAddFeature)}
                  disabled={locationType === 'none'}
                >
                  {showAddFeature ? 'Hide Map' : 'Draw Feature'}
                </Button>
                <Text type="secondary">
                  {config.drawn_features.length} feature(s)
                </Text>
              </Space>
            </div>

            {/* Drawing Canvas */}
            {showAddFeature && (
              <div className="drawing-panel">
                <DrawingCanvas
                  calculationId=""
                  activityId={config.id}
                  featureType="polygon"
                  onFeatureTypeChange={() => {}}
                  drawnFeatures={config.drawn_features}
                  onFeaturesChange={onFeaturesChange}
                  blocksWithSubAreas={blocks.map(b => ({
                    id: b.id,
                    name: b.name,
                    type: 'block' as const,
                    geometry: b.geometry
                  }))}
                  availableYears={config.year_budgets.map(yb => ({ year: yb.year }))}
                />
              </div>
            )}

            {/* Feature List */}
            {config.drawn_features.length > 0 && (
              <div className="feature-list">
                <Table
                  size="small"
                  dataSource={config.drawn_features}
                  rowKey="id"
                  pagination={false}
                  columns={[
                    {
                      title: 'Year',
                      dataIndex: ['properties', 'year'],
                      width: 60,
                      render: (year) => <Tag color="blue">Y{year}</Tag>
                    },
                    {
                      title: 'Name',
                      dataIndex: ['properties', 'name'],
                      ellipsis: true
                    },
                    {
                      title: 'Type',
                      dataIndex: 'feature_type',
                      width: 80
                    },
                    {
                      title: 'Size',
                      width: 100,
                      render: (_, record) => {
                        if (record.feature_type === 'polygon') {
                          return `${(record.properties?.area_sqm || 0).toLocaleString()} m²`;
                        }
                        return `${(record.properties?.length_m || 0).toLocaleString()} m`;
                      }
                    },
                    {
                      title: 'Action',
                      width: 150,
                      render: (_, record) => (
                        <Space size="small">
                          <Button
                            type="link"
                            size="small"
                            onClick={() => setCopyYearModal(record.id)}
                          >
                            Copy
                          </Button>
                          <Button
                            type="link"
                            danger
                            size="small"
                            onClick={() => onDeleteFeature(record.id)}
                          >
                            Delete
                          </Button>
                        </Space>
                      )
                    }
                  ]}
                />
              </div>
            )}

            {/* Copy Year Modal */}
            <Modal
              title="Copy to Year"
              open={!!copyYearModal}
              onCancel={() => setCopyYearModal(null)}
              footer={null}
              width={300}
            >
              <div style={{ padding: '16px 0' }}>
                <Text>Select years to copy the feature:</Text>
                <div style={{ marginTop: 16 }}>
                  {config.year_budgets.map(yb => {
                    const existingYear = config.drawn_features.some(
                      f => f.properties?.year === yb.year && f.id === copyYearModal
                    );
                    const alreadyCopied = config.drawn_features.some(
                      f => f.properties?.year === yb.year && f.id !== copyYearModal
                    );
                    
                    return (
                      <Checkbox
                        key={yb.year}
                        disabled={alreadyCopied}
                        style={{ display: 'block', marginBottom: 8 }}
                      >
                        Year {yb.year} {alreadyCopied ? '(Already exists)' : ''}
                      </Checkbox>
                    );
                  })}
                </div>
              </div>
            </Modal>
          </div>

          <Divider />

          {/* Year-wise Quantity & Budget Table */}
          <div className="content-section">
            <label>📊 Year-wise Plan:</label>
            <Table
              size="small"
              dataSource={config.year_budgets}
              rowKey="year"
              pagination={false}
              showHeader={true}
              columns={[
                {
                  title: 'Year',
                  dataIndex: 'year',
                  width: 60,
                  render: (year: number) => <Text strong>Y{year}</Text>
                },
                {
                  title: `Quantity (${config.unit})`,
                  width: 140,
                  render: (_: any, _record: any, idx: number) => (
                    editingQtyIndex === idx ? (
                      <Input
                        size="small"
                        style={{ width: 90 }}
                        value={tempQty}
                        onChange={(e) => setTempQty(Number(e.target.value) || 0)}
                        onBlur={() => {
                          onYearQuantityChange(config.id, idx, tempQty);
                          setEditingQtyIndex(null);
                        }}
                        onPressEnter={() => {
                          onYearQuantityChange(config.id, idx, tempQty);
                          setEditingQtyIndex(null);
                        }}
                        autoFocus
                      />
                    ) : (
                      <span
                        style={{ cursor: 'pointer' }}
                        onClick={() => {
                          setTempQty(_record.quantity);
                          setEditingQtyIndex(idx);
                        }}
                        title="Click to edit"
                      >
                        {Math.round(_record.quantity)}
                      </span>
                    )
                  )
                },
                {
                  title: 'Budget (NPR)',
                  width: 180,
                  render: (_: any, _record: any, idx: number) => (
                    editingYearIndex === idx ? (
                      <Input
                        size="small"
                        style={{ width: 140 }}
                        value={tempYearBudget}
                        onChange={(e) => setTempYearBudget(Number(e.target.value) || 0)}
                        onBlur={() => {
                          onYearBudgetChange(config.id, idx, tempYearBudget);
                          setEditingYearIndex(null);
                        }}
                        onPressEnter={() => {
                          onYearBudgetChange(config.id, idx, tempYearBudget);
                          setEditingYearIndex(null);
                        }}
                        autoFocus
                      />
                    ) : (
                      <span
                        style={{ cursor: 'pointer' }}
                        onClick={() => {
                          setTempYearBudget(_record.budget);
                          setEditingYearIndex(idx);
                        }}
                        title="Click to edit"
                      >
                        NPR {_record.budget.toLocaleString()}
                      </span>
                    )
                  )
                }
              ]}
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0}>
                    <Text strong>Total</Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={1}>
                    <Text strong>{Math.round(config.year_budgets.reduce((s, yb) => s + (Number(yb.quantity) || 0), 0))}</Text>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={2}>
                    <Space>
                      <Text strong>NPR {totalBudget.toLocaleString()}</Text>
                      <Text type="secondary">| Avg: {(totalBudget / 10).toLocaleString()}/yr</Text>
                    </Space>
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              )}
            />
          </div>
        </div>
      );

  const footerContent = (
    <div className="card-footer">
      <Button 
        type="text" 
        danger 
        size="small" 
        icon={<DeleteOutlined />}
        onClick={onRemove}
      >
        Remove
      </Button>
    </div>
  );

  if (embedded) {
    return (
      <div className="activity-card-embedded">
        {expandedContent}
        {showRemove && footerContent}
      </div>
    );
  }

  const showExpanded = config.expanded;

  return (
    <Card className={`activity-card ${config.expanded ? 'expanded' : ''}`}>
      {/* Card Header */}
      <div className="card-header" onClick={onToggleExpand}>
        <div className="card-title">
          <Text strong style={{ fontSize: 16 }}>
            {index}. {config.activity}
          </Text>
          <Tag color="blue">{config.program}</Tag>
        </div>
        <div className="card-actions">
          {!config.expanded && (
            <Space size="small">
              <Text type="secondary">
                Qty: {Math.round(config.default_quantity)} | Budget: {Math.round((config.default_budget || 0) / 1000)}ह/year
              </Text>
              <Text type="secondary">|</Text>
              <Text type="secondary">
                📍 {locationType === 'all' ? 'All Blocks' : 
                    locationType === 'blocks' ? `${selectedBlocks.length} blocks` : 
                    `${selectedSubAreas.length} sub-areas`}
              </Text>
              <Text type="secondary">|</Text>
              <Text type="secondary">🗺️ {config.drawn_features?.length || 0} features</Text>
            </Space>
          )}
          <Button
            type="text"
            size="small"
            icon={config.expanded ? <UpOutlined /> : <DownOutlined />}
          />
        </div>
      </div>

      {showExpanded && expandedContent}

      {footerContent}
    </Card>
  );
};

// Editable year cell for the matrix table
interface EditableYearCellProps {
  record: MatrixRow;
  yearIndex: number;
  onYearBudgetChange: (configId: string, yearIndex: number, value: number) => void;
  onYearQuantityChange: (configId: string, yearIndex: number, value: number) => void;
}

const EditableYearCell: React.FC<EditableYearCellProps> = ({
  record, yearIndex, onYearBudgetChange, onYearQuantityChange
}) => {
  const [editing, setEditing] = useState(false);
  const [editQty, setEditQty] = useState(0);
  const [editBudget, setEditBudget] = useState(0);

  if (record.type === 'available') {
    return <Text type="secondary" style={{ fontSize: 12 }}>-</Text>;
  }

  const yb = record.config!.year_budgets[yearIndex];
  if (!yb) return <Text type="secondary" style={{ fontSize: 12 }}>-</Text>;

  const saveEdit = () => {
    onYearQuantityChange(record.key, yearIndex, editQty);
    onYearBudgetChange(record.key, yearIndex, editBudget);
    setEditing(false);
  };

  if (editing) {
    return (
      <div onClick={e => e.stopPropagation()} style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'center' }}>
        <InputNumber
          size="small"
          value={editQty}
          onChange={val => setEditQty(val || 0)}
          onBlur={saveEdit}
          onPressEnter={saveEdit}
          style={{ width: 72, height: 24, fontSize: 11 }}
          min={0}
          placeholder="Qty"
          autoFocus
        />
        <InputNumber
          size="small"
          value={editBudget / 1000}
          onChange={val => setEditBudget((val || 0) * 1000)}
          onBlur={saveEdit}
          onPressEnter={saveEdit}
          style={{ width: 72, height: 24, fontSize: 11 }}
          min={0}
          step={0.5}
          placeholder="Budget"
        />
      </div>
    );
  }

  return (
    <div
      style={{ cursor: 'pointer', lineHeight: 1.4 }}
      onClick={(e) => {
        e.stopPropagation();
        setEditQty(yb.quantity);
        setEditBudget(yb.budget);
        setEditing(true);
      }}
      title="Click to edit"
    >
      <div style={{ fontSize: 10, color: '#888' }}>Q:{Math.round(yb.quantity)}</div>
      <div style={{ fontSize: 11, fontWeight: 500 }}>{(Number(yb.budget) / 1000).toFixed(1)}ह</div>
    </div>
  );
};

export default YearlyActivitiesPage;
