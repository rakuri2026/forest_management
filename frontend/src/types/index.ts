export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  role: 'guest' | 'user' | 'org_admin' | 'super_admin';
  status: 'pending' | 'active' | 'suspended';
  organization_id?: string;
  created_at: string;
  last_login?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  phone?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface CommunityForest {
  id: number;
  name: string;
  code: string;
  regime: string;
  area_hectares: number;
  geometry?: any;
  role?: string;
}

export interface MyForest extends CommunityForest {
  role: string;
}

export interface MyForestsResponse {
  forests: MyForest[];
  total_count: number;
  total_area_hectares: number;
}

export interface ApiError {
  detail: string;
}

export interface ForestBlock {
  block_index: number;
  block_name: string;
  area_sqm: number;
  area_hectares: number;
  geometry: any;
  centroid: {
    lon: number;
    lat: number;
  };

  // Extent (bounding box)
  extent?: {
    N: number;
    S: number;
    E: number;
    W: number;
  };

  // Analysis fields for each block
  elevation_min_m?: number;
  elevation_max_m?: number;
  elevation_mean_m?: number;
  slope_dominant_class?: string;
  slope_percentages?: Record<string, number>;
  aspect_dominant?: string;
  aspect_percentages?: Record<string, number>;
  canopy_dominant_class?: string;
  canopy_percentages?: Record<string, number>;
  canopy_mean_m?: number;
  agb_mean_mg_ha?: number;
  agb_total_mg?: number;
  carbon_stock_mg?: number;
  forest_health_dominant?: string;
  forest_health_percentages?: Record<string, number>;
  forest_type_dominant?: string;
  forest_type_percentages?: Record<string, number>;
  landcover_dominant?: string;
  landcover_percentages?: Record<string, number>;
  forest_loss_hectares?: number;
  forest_loss_by_year?: Record<string, number>;
  forest_gain_hectares?: number;
  fire_loss_hectares?: number;
  fire_loss_by_year?: Record<string, number>;
  temperature_mean_c?: number;
  temperature_min_c?: number;
  precipitation_mean_mm?: number;
  soil_texture?: string;
  soil_properties?: Record<string, any>;

  // Administrative Location
  province?: string;
  district?: string;
  municipality?: string;
  ward?: string;
  watershed?: string;
  major_river_basin?: string;

  // Geology
  geology_percentages?: Record<string, number>;

  // Access
  access_info?: string;

  // Nearby Features (within 100m)
  features_north?: string;
  features_east?: string;
  features_south?: string;
  features_west?: string;
}

export interface AnalysisResultData {
  area_sqm?: number;
  area_hectares?: number;
  utm_zone?: number;
  total_blocks?: number;
  blocks?: ForestBlock[];

  // Elevation
  elevation_min_m?: number;
  elevation_max_m?: number;
  elevation_mean_m?: number;

  // Slope
  slope_dominant_class?: string;
  slope_percentages?: Record<string, number>;

  // Aspect
  aspect_dominant?: string;
  aspect_percentages?: Record<string, number>;

  // Canopy
  canopy_dominant_class?: string;
  canopy_percentages?: Record<string, number>;
  canopy_mean_m?: number;

  // Biomass
  agb_mean_mg_ha?: number;
  agb_total_mg?: number;
  carbon_stock_mg?: number;

  // Forest Health
  forest_health_dominant?: string;
  forest_health_percentages?: Record<string, number>;

  // Forest Type
  forest_type_dominant?: string;
  forest_type_percentages?: Record<string, number>;

  // Land Cover
  landcover_dominant?: string;
  landcover_percentages?: Record<string, number>;

  // Climate
  temperature_mean_c?: number;
  temperature_min_c?: number;
  precipitation_mean_mm?: number;

  // Extent (bounding box)
  whole_forest_extent?: {
    N: number;
    S: number;
    E: number;
    W: number;
  };

  // Forest Change
  forest_loss_hectares?: number;
  forest_gain_hectares?: number;
  forest_loss_by_year?: Record<string, number>;
  fire_loss_hectares?: number;
  fire_loss_by_year?: Record<string, number>;

  // Soil
  soil_texture?: string;
  soil_properties?: Record<string, any>;
  soil_ph_dominant?: string;

  // Proximity
  buildings_within_1km?: number;
  nearest_settlement?: string;
  nearest_road?: string;

  // Administrative (old fields - kept for backward compatibility)
  province?: string;
  municipality?: string;
  ward?: string;

  // Administrative Location (whole forest)
  whole_province?: string;
  whole_district?: string;
  whole_municipality?: string;
  whole_ward?: string;
  whole_watershed?: string;
  whole_major_river_basin?: string;

  // Geology (whole forest)
  whole_geology_percentages?: Record<string, number>;

  // Access (whole forest)
  whole_access_info?: string;

  // Nearby Features (whole forest, within 100m)
  whole_features_north?: string;
  whole_features_east?: string;
  whole_features_south?: string;
  whole_features_west?: string;

  // Processing
  processing_info?: {
    partitioned: boolean;
    partition_info: Record<string, any>;
  };
}

export interface Calculation {
  id: string;
  user_id: string;
  uploaded_filename: string;
  forest_name?: string;
  block_name?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  processing_time_seconds?: number;
  error_message?: string;
  created_at: string;
  completed_at?: string;
  geometry?: any;
  result_data?: AnalysisResultData;
}
