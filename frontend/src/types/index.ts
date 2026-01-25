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
  result_data?: any;
}
