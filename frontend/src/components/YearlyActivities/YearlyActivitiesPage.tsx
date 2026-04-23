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
  Tooltip,
  Dropdown,
  Typography,
  Tag,
  Statistic,
  Empty
} from 'antd';
import {
  PlusOutlined,
  SaveOutlined,
  CloseOutlined,
  EditOutlined,
  DeleteOutlined,
  DownOutlined,
  UpOutlined,
  ExportOutlined,
  ReloadOutlined,
  CheckCircleFilled,
  EnvironmentOutlined,
  MapOutlined,
  CopyOutlined,
  ClearOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import { yearlyActivitiesApi, forestApi } from '../../services/api';
import DrawingCanvas from './DrawingCanvas';
import './YearlyActivitiesPage.css';

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
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [selectedPotentialId, setSelectedPotentialId] = useState<string | null>(null);
  const [selectedProgram, setSelectedProgram] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

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
        year_budgets: yearDetailsRes?.map((yd: any) => ({
          year: yd.year_number || 1,
          quantity: typeof yd.quantity === 'string' ? parseFloat(yd.quantity) || 1 : Number(yd.quantity) || 1,
          budget: typeof yd.yearly_budget === 'string' ? parseFloat(yd.yearly_budget) || defaultBudget : Number(yd.yearly_budget) || defaultBudget,
          year_detail_id: yd.id || null,
          location: existingBlockIds.length > 0 ? 'blocks' : existingSubAreaIds.length > 0 ? 'sub_areas' : 'none',
          selected_blocks: existingBlockIds,
          selected_sub_areas: existingSubAreaIds
        })) || generateDefaultYearBudgets(pa, defaultBudget),
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

  // Add new activity
  const handleAddActivity = async () => {
    if (!selectedPotentialId) {
      message.warning('Please select an activity');
      return;
    }

    try {
      const newActivity = await yearlyActivitiesApi.createProposedActivity(calculationId, {
        potential_activity_id: selectedPotentialId,
        default_quantity: 1,
        default_yearly_budget: 5000
      });

      const potential = potentialActivities.find(p => p.id === selectedPotentialId);
      
      const newConfig: ActivityConfig = {
        id: newActivity.id,
        proposed_activity_id: selectedPotentialId,
        activity: potential?.activity || 'Unknown',
        program: potential?.program || '',
        unit: potential?.unit || 'units',
        default_quantity: 1,
        default_budget: 5000,
        expanded: true,
        year_budgets: generateDefaultYearBudgets({ default_quantity: 1, default_yearly_budget: 5000 } as ProposedActivity, 5000),
        spatial_assignments: [],
        drawn_features: []
      };

      setActivityConfigs([...activityConfigs, newConfig]);
      setProposedActivities([...proposedActivities, newActivity]);
      setAddModalVisible(false);
      setSelectedPotentialId(null);
      message.success('Activity added');
    } catch (error) {
      console.error('Failed to add activity:', error);
      message.error('Failed to add activity');
    }
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
  const handleExportCSV = () => {
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
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${forestName}_yearly_activities_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
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

  // Available activities for add modal
  const availableActivities = potentialActivities.filter(
    pa => !proposedActivities.some(pr => pr.potential_activity_id === pa.id)
  );

  // Unique programs from available activities
  const uniquePrograms = useMemo(() => {
    const programs = new Set(availableActivities.map(pa => pa.program).filter(Boolean));
    return Array.from(programs).sort();
  }, [availableActivities]);

  // Filtered activities based on selected program
  const filteredActivities = useMemo(() => {
    if (!selectedProgram) return availableActivities;
    return availableActivities.filter(pa => pa.program === selectedProgram);
  }, [availableActivities, selectedProgram]);

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
          <Title level={4}>Yearly Activities Planning</Title>
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

      {/* Add Activity Button */}
      <div className="add-activity-bar">
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          onClick={() => setAddModalVisible(true)}
          disabled={availableActivities.length === 0}
        >
          Add Activity
        </Button>
        {availableActivities.length === 0 && (
          <Text type="secondary" style={{ marginLeft: 16 }}>
            All activities have been added
          </Text>
        )}
      </div>

      {/* Activity Cards */}
      <div className="activity-cards">
        {activityConfigs.length === 0 ? (
          <Empty 
            description="No activities added yet. Click 'Add Activity' to get started."
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        ) : (
          activityConfigs.map((config, index) => (
            <ActivityCard
              key={config.id}
              config={config}
              index={index + 1}
              blocks={blocks}
              subAreas={subAreas}
              onToggleExpand={() => handleToggleExpand(config.id)}
              onRemove={() => handleRemoveActivity(config.id)}
              onQuantityChange={(val) => handleQuantityChange(config.id, val)}
              onBudgetChange={(val) => handleBudgetChange(config.id, val)}
              onYearBudgetChange={(configId, yearIndex, value) => handleYearBudgetChange(configId, yearIndex, value)}
              onYearQuantityChange={(configId, yearIndex, value) => handleYearQuantityChange(configId, yearIndex, value)}
              onLocationTypeChange={(type) => handleLocationTypeChange(config.id, type)}
              onBlockToggle={(blockId) => handleBlockToggle(config.id, blockId)}
              onSubAreaToggle={(subAreaId) => handleSubAreaToggle(config.id, subAreaId)}
              onFeaturesChange={() => handleFeaturesChange(config.id)}
              onCopyFeature={(featureId, year) => handleCopyFeature(config.id, featureId, year)}
              onDeleteFeature={(featureId) => handleDeleteFeature(config.id, featureId)}
            />
          ))
        )}
      </div>

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

      {/* Add Activity Modal */}
      <Modal
        title="Add Activity"
        open={addModalVisible}
        onCancel={() => {
          setAddModalVisible(false);
          setSelectedPotentialId(null);
          setSelectedProgram(null);
        }}
        onOk={handleAddActivity}
        okText="Add"
        okButtonProps={{ disabled: !selectedPotentialId }}
        width={500}
      >
        <div style={{ marginBottom: 16 }}>
          <Text strong>Select Program:</Text>
        </div>
        <Select
          style={{ width: '100%', marginBottom: 16 }}
          placeholder="Select a program..."
          value={selectedProgram}
          onChange={(value) => {
            setSelectedProgram(value);
            setSelectedPotentialId(null);
          }}
          allowClear
        >
          {uniquePrograms.map(program => (
            <Select.Option key={program} value={program}>
              {program}
            </Select.Option>
          ))}
        </Select>
        
        <div style={{ marginBottom: 16 }}>
          <Text strong>Select Activity:</Text>
        </div>
        <Select
          style={{ width: '100%' }}
          placeholder={selectedProgram ? "Select an activity..." : "First select a program"}
          showSearch
          optionFilterProp="children"
          value={selectedPotentialId}
          onChange={setSelectedPotentialId}
          disabled={!selectedProgram}
        >
          {filteredActivities.map(pa => (
            <Select.Option key={pa.id} value={pa.id}>
              <div>
                <Text strong>{pa.activity}</Text>
                <br />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Unit: {pa.unit} | Budget: NPR {(pa.yearly_budget || 5000).toLocaleString()}/year
                </Text>
              </div>
            </Select.Option>
          ))}
        </Select>
        
        {selectedPotentialId && (
          <div style={{ marginTop: 16, padding: 16, background: '#f0f7ff', borderRadius: 4, border: '1px solid #91caff' }}>
            {(() => {
              const selected = availableActivities.find(a => a.id === selectedPotentialId);
              return selected ? (
                <>
                  <Text strong style={{ fontSize: 14 }}>{selected.activity}</Text>
                  <br />
                  <Text type="secondary">Program: {selected.program}</Text>
                  <br />
                  <Text type="secondary">Default Quantity: {selected.quantity || 1} {selected.unit}</Text>
                  <br />
                  <Text type="secondary">Default Budget: NPR {(selected.yearly_budget || 5000).toLocaleString()}/year</Text>
                </>
              ) : null;
            })()}
          </div>
        )}
      </Modal>
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
  onDeleteFeature
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

      {/* Expanded Content */}
      {config.expanded && (
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

          {/* Quantity by Year */}
          <div className="content-section">
            <label>📊 Quantity by Year ({config.unit}):</label>
            <div className="year-budget-grid">
              {config.year_budgets.map((yb, idx) => (
                <div key={`qty-${yb.year}`} className="year-budget-item">
                  {editingQtyIndex === idx ? (
                    <Input
                      size="small"
                      style={{ width: 60 }}
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
                        setTempQty(yb.quantity);
                        setEditingQtyIndex(idx);
                      }}
                      title="Click to edit"
                    >
                      <Text strong>Y{yb.year}:</Text>
                      <Text> {Math.round(yb.quantity)}</Text>
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>

          <Divider />

          {/* Budget by Year */}
          <div className="content-section">
            <label>💰 Budget by Year:</label>
            <div className="year-budget-grid">
              {config.year_budgets.map((yb, idx) => (
                <div key={`budget-${yb.year}`} className="year-budget-item">
                  {editingYearIndex === idx ? (
                    <Input
                      size="small"
                      style={{ width: 70 }}
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
                        setTempYearBudget(yb.budget);
                        setEditingYearIndex(idx);
                      }}
                      title="Click to edit"
                    >
                      <Text strong>Y{yb.year}:</Text>
                      <Text> NPR {yb.budget.toLocaleString()}</Text>
                    </span>
                  )}
                </div>
              ))}
            </div>
            <div className="budget-total">
              <Text strong>Total (10 years): NPR {totalBudget.toLocaleString()}</Text>
              <Text type="secondary"> | Avg: NPR {(totalBudget / 10).toLocaleString()}/year</Text>
            </div>
          </div>
        </div>
      )}

      {/* Card Footer */}
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
    </Card>
  );
};

export default YearlyActivitiesPage;
