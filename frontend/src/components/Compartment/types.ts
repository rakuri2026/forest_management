export interface AvailableBlock {
  id: string;
  name: string;
  area_sqm: number;
  area_hectares: number;
  geometry: GeoJSON.Polygon;
  has_compartments: boolean;
  tree_count: number;
  total_trees_in_calculation?: number;
  compartment_count: number;
}

export interface CompartmentPreview {
  index: number;
  name: string;
  geometry: GeoJSON.Polygon;
  area_sqm: number;
  area_hectares: number;
  area_deviation_percent: number;
  tree_count: number;
  perimeter_m?: number;
}

export interface SplitValidation {
  is_valid: boolean;
  warnings: string[];
  errors: string[];
  total_area_match: boolean;
}

export interface SplitPreviewResponse {
  compartments: CompartmentPreview[];
  validation: SplitValidation;
  total_area_sqm: number;
  parent_block_name: string;
}

export interface ExecuteSplitResponse {
  split_history_id: string;
  compartments_created: string[];
  trees_reassigned: number;
  success: boolean;
  message: string;
}

export interface SplitDirection {
  name: string;
  angle: number | null;
  description?: string;
}

export interface TreeReassignmentPreview {
  tree_id: string;
  species: string;
  location: { lat: number; lon: number };
  suggested_compartment_id: string | null;
  suggested_compartment_name: string | null;
}

export interface TreesNeedingAssignmentResponse {
  block_name: string;
  compartments: Array<{
    id: string;
    name: string;
    geometry: GeoJSON.Polygon;
  }>;
  trees: TreeReassignmentPreview[];
  total_trees: number;
}

export interface TreeReassignmentResponse {
  success: boolean;
  trees_assigned: number;
  trees_unassigned: number;
  assignments_by_compartment: Record<string, { name: string; count: number }>;
}

export interface SplitConfig {
  method: 'parallel' | 'grid' | 'custom';
  parameters: {
    direction_angle?: number;
    num_compartments?: number;
    rows?: number;
    columns?: number;
    min_area_sqm?: number;
    max_deviation_percent?: number;
  };
  naming_pattern?: string;
  reassign_trees?: boolean;
  notes?: string;
}
