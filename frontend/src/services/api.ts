import axios from 'axios';
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
  CommunityForest,
  MyForestsResponse,
  Calculation,
} from '../types';

export const API_BASE_URL = 'http://localhost:8001';

const api = axios.create({
  // In dev mode, use relative URLs so Vite proxy handles them
  // In production, use absolute URL
  baseURL: import.meta.env.DEV ? undefined : API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
  },
});

// Debug interceptor to log full URL
api.interceptors.request.use(
  (config) => {
    const fullUrl = config.baseURL ? `${config.baseURL}${config.url}` : config.url;
    console.log('Axios request URL:', fullUrl);
    return config;
  },
  (error) => Promise.reject(error)
);

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    // If sending FormData, remove Content-Type header so browser sets it with boundary
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type'];
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth endpoints
export const authApi = {
  login: async (credentials: LoginRequest): Promise<TokenResponse> => {
    const response = await api.post<TokenResponse>('/api/auth/login', credentials);
    return response.data;
  },

  register: async (userData: RegisterRequest): Promise<User> => {
    const response = await api.post<User>('/api/auth/register', userData);
    return response.data;
  },

  me: async (): Promise<User> => {
    const response = await api.get<User>('/api/auth/me');
    return response.data;
  },
};

// Forest endpoints
export const forestApi = {
  listCommunityForests: async (params?: {
    search?: string;
    regime?: string;
    limit?: number;
    offset?: number;
  }): Promise<CommunityForest[]> => {
    const response = await api.get<CommunityForest[]>('/api/forests/community-forests', {
      params,
    });
    return response.data;
  },

  getCommunityForest: async (id: number): Promise<CommunityForest> => {
    const response = await api.get<CommunityForest>(`/api/forests/community-forests/${id}`);
    return response.data;
  },

  getMyForests: async (): Promise<MyForestsResponse> => {
    const response = await api.get<MyForestsResponse>('/api/forests/my-forests');
    return response.data;
  },

  uploadBoundary: async (
    file: File,
    forestName?: string,
    analysisOptions?: Record<string, boolean>,
    mapOptions?: Record<string, boolean>
  ): Promise<Calculation> => {
    const formData = new FormData();
    formData.append('file', file);
    if (forestName) formData.append('forest_name', forestName);

    // Append analysis options as form fields
    if (analysisOptions) {
      Object.entries(analysisOptions).forEach(([key, value]) => {
        formData.append(key, String(value));
      });
    }

    // Append map options as form fields
    if (mapOptions) {
      Object.entries(mapOptions).forEach(([key, value]) => {
        formData.append(key, String(value));
      });
    }

    const response = await api.post<Calculation>('/api/forests/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  createFromMap: async (data: {
    forest_name: string;
    outer_boundary: any;
    gps_points?: any[];
    blocks: any[];
    sub_areas?: any[];
    analysis_options?: Record<string, boolean>;
    map_options?: Record<string, boolean>;
    run_analysis?: boolean;
  }): Promise<Calculation> => {
    const response = await api.post<Calculation>('/api/forests/create-from-map', data);
    return response.data;
  },

  listCalculations: async (): Promise<Calculation[]> => {
    const response = await api.get<Calculation[]>('/api/forests/calculations');
    return response.data;
  },

  getCalculation: async (id: string): Promise<Calculation> => {
    const response = await api.get<Calculation>(`/api/forests/calculations/${id}`);
    return response.data;
  },

  updateResultData: async (id: string, data: Record<string, any>): Promise<void> => {
    await api.patch(`/api/forests/calculations/${id}/result-data`, data);
  },

  deleteCalculation: async (id: string): Promise<void> => {
    await api.delete(`/api/forests/calculations/${id}`);
  },

  reanalyze: async (
    id: string,
    analysisOptions: Partial<Record<string, boolean>>
  ): Promise<Calculation> => {
    const response = await api.post<Calculation>(
      `/api/forests/calculations/${id}/reanalyze`,
      analysisOptions
    );
    return response.data;
  },

  generateMaps: async (
    id: string,
    mapOptions: Record<string, boolean>
  ): Promise<{
    calculation_id: string;
    status: string;
    generated_maps: Array<{
      map_type: string;
      status: string;
      download_url: string;
    }>;
    failed_maps: Array<{
      map_type: string;
      status: string;
      error: string;
    }>;
    not_implemented: string[];
    message: string;
  }> => {
    const response = await api.post(
      `/api/forests/calculations/${id}/generate-maps`,
      mapOptions
    );
    return response.data;
  },

  // Species confirmation endpoints
  toggleSpeciesConfirmation: async (
    calculationId: string,
    scientificName: string,
    confirmed: boolean,
    blockName?: string  // NEW: Optional block identifier
  ): Promise<Calculation> => {
    const response = await api.patch<Calculation>(
      `/api/forests/calculations/${calculationId}/species/${encodeURIComponent(scientificName)}/confirm`,
      {
        confirmed,
        block_name: blockName  // NEW: Pass block_name if provided
      }
    );
    return response.data;
  },

  confirmAllSpecies: async (
    calculationId: string,
    confirmed: boolean
  ): Promise<Calculation> => {
    const response = await api.post<Calculation>(
      `/api/forests/calculations/${calculationId}/species/confirm-all`,
      { confirmed }
    );
    return response.data;
  },

  getSpeciesSummary: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/forests/calculations/${calculationId}/species-summary`);
    return response.data;
  },

  // Accessible forest area endpoint (Phase 2)
  getAccessibleForestArea: async (
    calculationId: string,
    params?: {
      filter_slope?: boolean;
      max_slope_degrees?: number;
    }
  ): Promise<any> => {
    const response = await api.get(
      `/api/forests/calculations/${calculationId}/accessible-area`,
      { params }
    );
    return response.data;
  },

  // Tree cover areas endpoint - calculate effective forest areas for all blocks
  calculateTreeCoverAreas: async (calculationId: string): Promise<any> => {
    const response = await api.post(
      `/api/forests/calculations/${calculationId}/tree-cover-areas`
    );
    return response.data;
  },

  // Geometry editing endpoints
  updateGeometry: async (
    calculationId: string,
    geometry: any,
    reanalyze: boolean = false
  ): Promise<any> => {
    const response = await api.patch(
      `/api/forests/calculations/${calculationId}/geometry`,
      { geometry, reanalyze }
    );
    return response.data;
  },

  // Sub-area management endpoints
  addSubArea: async (
    calculationId: string,
    data: {
      name: string;
      category: string;
      geometry: any;
      block_id?: string;
      block_name?: string;
      is_excluded?: boolean;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/forests/calculations/${calculationId}/sub-areas`,
      data
    );
    return response.data;
  },

  listSubAreas: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/forests/calculations/${calculationId}/sub-areas`
    );
    return response.data;
  },

  updateSubArea: async (
    calculationId: string,
    subAreaId: string,
    data: {
      name?: string;
      category?: string;
      block_id?: string;
      block_name?: string;
      is_excluded?: boolean;
    }
  ): Promise<any> => {
    const response = await api.patch(
      `/api/forests/calculations/${calculationId}/sub-areas/${subAreaId}`,
      data
    );
    return response.data;
  },

  deleteSubArea: async (
    calculationId: string,
    subAreaId: string
  ): Promise<any> => {
    const response = await api.delete(
      `/api/forests/calculations/${calculationId}/sub-areas/${subAreaId}`
    );
    return response.data;
  },

  // Interactive boundary editing
  editBoundary: async (
    calculationId: string,
    data: {
      operation: string;
      features?: any[];
      target_index?: number;
      reanalyze?: boolean;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/forests/calculations/${calculationId}/edit-boundary`,
      data
    );
    return response.data;
  },

  // Block naming endpoints
  getPolygons: async (calculationId: string): Promise<{
    polygons: Array<{
      index: number;
      geometry: any;
      area_hectares: number;
      current_name: string;
    }>;
    total_count: number;
  }> => {
    const response = await api.get(
      `/api/forests/calculations/${calculationId}/polygons`
    );
    return response.data;
  },

  /**
   * Create a single default block from calculation's boundary
   * Used when user chooses "Single Block" option
   */
  createSingleBlock: async (
    calculationId: string,
    blockName?: string
  ): Promise<any> => {
    const response = await api.post(
      `/api/forests/calculations/${calculationId}/create-single-block`,
      null,
      { params: { block_name: blockName } }
    );
    return response.data;
  },

  /**
   * Save work-in-progress polygon creation as draft
   */
  saveDraft: async (draftData: {
    forest_name: string;
    islands: Array<{
      id: string;
      geometry: any;
      area: number;
    }>;
    mode: 'auto' | 'manual';
    draft_id?: string;
  }): Promise<any> => {
    const response = await api.post('/api/forests/save-draft', draftData);
    return response.data;
  },

  /**
   * List all drafts for current user
   */
  listDrafts: async (): Promise<any[]> => {
    const response = await api.get('/api/forests/drafts');
    return response.data;
  },

  /**
   * Get full draft data including all islands
   */
  getDraft: async (draftId: string): Promise<any> => {
    const response = await api.get(`/api/forests/drafts/${draftId}`);
    return response.data;
  },

  /**
   * Delete a draft
   */
  deleteDraft: async (draftId: string): Promise<void> => {
    await api.delete(`/api/forests/drafts/${draftId}`);
  },

  /**
   * Create multiple blocks from polygon mapping
   * Note: run_analysis parameter removed - analysis triggered separately from Analysis page
   */
  createBlocks: async (calculationId: string, blocks: Array<{
    polygon_index: number;
    name: string;
  }>): Promise<any> => {
    const response = await api.post(
      `/api/forests/calculations/${calculationId}/blocks`,
      { blocks }
    );
    return response.data;
  },

  getBlocks: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/forests/calculations/${calculationId}/blocks`
    );
    return response.data;
  },

  updateBlock: async (
    calculationId: string,
    blockId: string,
    name: string
  ): Promise<any> => {
    const response = await api.patch(
      `/api/forests/calculations/${calculationId}/blocks/${blockId}`,
      null,
      { params: { name } }
    );
    return response.data;
  },

  deleteBlock: async (
    calculationId: string,
    blockId: string
  ): Promise<void> => {
    await api.delete(
      `/api/forests/calculations/${calculationId}/blocks/${blockId}`
    );
  },
};

// Tree Model endpoints
export const treeModelApi = {
  generate: async (calculationId: string, config?: {
    min_dbh_cm?: number;
    min_height_m?: number;
    max_trees_per_ha?: number;
    spatial_distribution?: string;
    plot_buffer_meters?: number;
    algorithm_version?: string;
  }) => {
    const response = await api.post(`/api/calculations/${calculationId}/generate-tree-model`, {
      config: config || null
    });
    return response.data;
  },

  getModel: async (modelId: string) => {
    const response = await api.get(`/api/tree-models/${modelId}`);
    return response.data;
  },

  listModels: async (calculationId: string) => {
    const response = await api.get(`/api/calculations/${calculationId}/tree-models`);
    return response.data;
  },

  download: async (modelId: string) => {
    const response = await api.get(`/api/tree-models/${modelId}/download`, {
      responseType: 'blob'
    });
    return response.data;
  },

  delete: async (modelId: string) => {
    const response = await api.delete(`/api/tree-models/${modelId}`);
    return response.data;
  },
};

export default api;


// Inventory endpoints
export const inventoryApi = {
  listSpecies: async (): Promise<any[]> => {
    const response = await api.get("/api/inventory/species");
    return response.data;
  },

  downloadTemplate: async (): Promise<Blob> => {
    const response = await api.get("/api/inventory/template", {
      responseType: "blob",
    });
    return response.data;
  },

  uploadInventory: async (
    file: File,
    gridSpacing: number = 20.0,
    projectionEpsg?: number,
    calculationId?: string
  ): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("grid_spacing_meters", gridSpacing.toString());
    if (projectionEpsg) {
      formData.append("projection_epsg", projectionEpsg.toString());
    }
    if (calculationId) {
      formData.append("calculation_id", calculationId);
    }

    const response = await api.post("/api/inventory/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  processInventory: async (id: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post(`/api/inventory/${id}/process`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  listMyInventories: async (): Promise<any> => {
    const response = await api.get("/api/inventory/my-inventories");
    return response.data;
  },

  getInventoryStatus: async (id: string): Promise<any> => {
    const response = await api.get(`/api/inventory/${id}/status`);
    return response.data;
  },

  getInventorySummary: async (id: string): Promise<any> => {
    const response = await api.get(`/api/inventory/${id}/summary`);
    return response.data;
  },

  listInventoryTrees: async (
    id: string,
    params?: {
      page?: number;
      page_size?: number;
      remark?: string;
    }
  ): Promise<any> => {
    const response = await api.get(`/api/inventory/${id}/trees`, { params });
    return response.data;
  },

  exportInventory: async (id: string, format: "csv" | "geojson"): Promise<Blob> => {
    const response = await api.get(`/api/inventory/${id}/export`, {
      params: { format },
      responseType: "blob",
    });
    return response.data;
  },

  deleteInventory: async (id: string): Promise<void> => {
    await api.delete(`/api/inventory/${id}`);
  },

  getTreeMappingByCalculation: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/inventory/by-calculation/${calculationId}`);
    return response.data;
  },

  getCorrectionPreview: async (inventoryId: string): Promise<any> => {
    const response = await api.get(`/api/inventory/${inventoryId}/correction-preview`);
    return response.data;
  },

  acceptCorrections: async (inventoryId: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post(`/api/inventory/${inventoryId}/accept-corrections`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  // Column Mapping endpoints
  previewColumnMapping: async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post("/api/inventory/preview-mapping", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  confirmColumnMapping: async (
    file: File,
    mapping: Record<string, string>,
    savePreference: boolean = false,
    gridSpacing: number = 20.0,
    calculationId?: string,
    projectionEpsg?: number,
    correctionStrategy: string = "nearest_tree"
  ): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mapping", JSON.stringify(mapping));
    formData.append("save_preference", savePreference.toString());
    formData.append("grid_spacing_meters", gridSpacing.toString());
    formData.append("correction_strategy", correctionStrategy);

    if (calculationId) {
      formData.append("calculation_id", calculationId);
    }
    if (projectionEpsg) {
      formData.append("projection_epsg", projectionEpsg.toString());
    }

    const response = await api.post("/api/inventory/confirm-mapping", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },
};

// Field Inventory endpoints
export const fieldInventoryApi = {
  previewMapping: async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post("/api/field-inventory/preview-mapping", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  upload: async (
    file: File,
    calculationId: string,
    mapping: Record<string, string>,
    sampleSizes: {
      regeneration_area_sqm: number;
      sapling_area_sqm: number;
      pole_area_sqm: number;
      tree_area_sqm: number;
    }
  ): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("calculation_id", calculationId);
    formData.append("mapping", JSON.stringify(mapping));
    formData.append("regeneration_area_sqm", sampleSizes.regeneration_area_sqm.toString());
    formData.append("sapling_area_sqm", sampleSizes.sapling_area_sqm.toString());
    formData.append("pole_area_sqm", sampleSizes.pole_area_sqm.toString());
    formData.append("tree_area_sqm", sampleSizes.tree_area_sqm.toString());

    const response = await api.post("/api/field-inventory/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  process: async (fieldInventoryId: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post(`/api/field-inventory/${fieldInventoryId}/process`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  },

  getStatus: async (fieldInventoryId: string): Promise<any> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/status`);
    return response.data;
  },

  getSummary: async (fieldInventoryId: string): Promise<any> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/summary`);
    return response.data;
  },

  listBlocks: async (fieldInventoryId: string): Promise<any> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/blocks`);
    return response.data;
  },

  getSpeciesBreakdown: async (fieldInventoryId: string): Promise<any> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/species-breakdown`);
    return response.data;
  },

  getMaiAah: async (
    fieldInventoryId: string,
    aahGood: number = 75,
    aahModerate: number = 60,
    aahWeak: number = 40,
    customMultipliers?: Record<string, number>
  ): Promise<any> => {
    const params: any = {
      aah_good: aahGood,
      aah_moderate: aahModerate,
      aah_weak: aahWeak
    };

    if (customMultipliers && Object.keys(customMultipliers).length > 0) {
      params.custom_multipliers = JSON.stringify(customMultipliers);
    }

    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/mai-aah`, { params });
    return response.data;
  },

  getByCalculation: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/field-inventory/by-calculation/${calculationId}`);
    return response.data;
  },

  delete: async (fieldInventoryId: string): Promise<void> => {
    await api.delete(`/api/field-inventory/${fieldInventoryId}`);
  },

  getTotalInventory: async (
    fieldInventoryId: string,
    blockAreas: Record<string, number>,
    customMultipliers?: Record<string, number>,
    aahGood: number = 75,
    aahModerate: number = 60,
    aahWeak: number = 40
  ): Promise<any> => {
    const params: any = {
      block_areas: JSON.stringify(blockAreas),
      aah_good: aahGood,
      aah_moderate: aahModerate,
      aah_weak: aahWeak
    };

    if (customMultipliers && Object.keys(customMultipliers).length > 0) {
      params.custom_multipliers = JSON.stringify(customMultipliers);
    }

    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/total-inventory`, { params });
    return response.data;
  },
};

// Fieldbook endpoints
export const fieldbookApi = {
  generate: async (
    calculationId: string,
    params: {
      interpolation_distance_meters: number;
      extract_elevation: boolean;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/calculations/${calculationId}/fieldbook/generate`,
      params
    );
    return response.data;
  },

  list: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/calculations/${calculationId}/fieldbook`);
    return response.data;
  },

  delete: async (calculationId: string): Promise<void> => {
    await api.delete(`/api/calculations/${calculationId}/fieldbook`);
  },

  export: async (
    calculationId: string,
    format: "csv" | "excel" | "gpx" | "geojson"
  ): Promise<Blob> => {
    const response = await api.get(
      `/api/calculations/${calculationId}/fieldbook`,
      {
        params: { format },
        responseType: "blob",
      }
    );
    return response.data;
  },
};

// Sampling endpoints
export const samplingApi = {
  create: async (
    calculationId: string,
    params: {
      sampling_type: "systematic" | "random" | "stratified";
      sampling_intensity_percent?: number; // NEW: Percentage of block area (0.1-10%, default 0.5%)
      min_samples_per_block?: number; // NEW: Minimum samples for blocks >= 1ha (2-10, default 5)
      min_samples_small_blocks?: number; // NEW: Minimum samples for blocks < 1ha (1-5, default 2)
      intensity_per_hectare?: number; // DEPRECATED: Use sampling_intensity_percent instead
      grid_spacing_meters?: number; // DEPRECATED: Calculated automatically
      min_distance_meters?: number;
      plot_shape?: "circular" | "square" | "rectangular";
      plot_radius_meters?: number;
      plot_length_meters?: number;
      plot_width_meters?: number;
      notes?: string;
      // Accessible forest filtering (Phase 2)
      filter_tree_cover?: boolean; // Filter to tree cover only (default: true)
      filter_slope?: boolean; // Filter by slope (default: false)
      max_slope_degrees?: number; // Max slope threshold (default: 45.0)
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/calculations/${calculationId}/sampling/create`,
      params
    );
    return response.data;
  },

  list: async (calculationId: string): Promise<any[]> => {
    const response = await api.get(`/api/calculations/${calculationId}/sampling`);
    return response.data;
  },

  getDesign: async (designId: string): Promise<any> => {
    const response = await api.get(`/api/sampling/${designId}`);
    return response.data;
  },

  getPoints: async (
    designId: string,
    options?: {
      format?: "json" | "geojson";
      include_elevation?: boolean;
      include_topographic_features?: boolean;
    }
  ): Promise<any> => {
    const params: any = {};
    if (options?.format) params.format = options.format;
    if (options?.include_elevation !== undefined) params.include_elevation = options.include_elevation;
    if (options?.include_topographic_features !== undefined) params.include_topographic_features = options.include_topographic_features;

    const response = await api.get(`/api/sampling/${designId}/points`, {
      params: Object.keys(params).length > 0 ? params : undefined,
    });
    return response.data;
  },

  delete: async (designId: string): Promise<void> => {
    await api.delete(`/api/sampling/${designId}`);
  },

  export: async (
    designId: string,
    format: "csv" | "gpx" | "geojson" | "kml"
  ): Promise<Blob> => {
    const response = await api.get(`/api/sampling/${designId}/points`, {
      params: { format },
      responseType: "blob",
    });
    return response.data;
  },

  getMapLayers: async (designId: string): Promise<any> => {
    const response = await api.get(`/api/sampling/${designId}/map-layers`);
    return response.data;
  },

  previewAccessibleForest: async (
    calculationId: string,
    options: {
      filter_tree_cover?: boolean;
      filter_slope?: boolean;
      max_slope_degrees?: number;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/calculations/${calculationId}/preview-accessible-forest`,
      null,
      {
        params: {
          filter_tree_cover: options.filter_tree_cover ?? true,
          filter_slope: options.filter_slope ?? false,
          max_slope_degrees: options.max_slope_degrees ?? 45.0,
        },
      }
    );
    return response.data;
  },
};

// ============================================================================
// User Group Map API
// ============================================================================

export const userGroupApi = {
  /**
   * Upload user group extent boundary file
   */
  uploadExtent: async (
    calculationId: string,
    file: File
  ): Promise<{ extent_id: number; message: string }> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(
      `/api/calculations/${calculationId}/user-group/upload`,
      formData
    );
    return response.data;
  },

  /**
   * Create manual extent from digitized polygon
   */
  createManualExtent: async (
    calculationId: string,
    geometry: any
  ): Promise<{ extent_id: number; message: string }> => {
    const response = await api.post(
      `/api/calculations/${calculationId}/user-group/manual`,
      { geometry }
    );
    return response.data;
  },

  /**
   * Create auto-buffer extent
   */
  createAutoBuffer: async (
    calculationId: string,
    bufferDistance: number = 1000
  ): Promise<{ extent_id: number; message: string }> => {
    const response = await api.post(
      `/api/calculations/${calculationId}/user-group/auto-buffer`,
      null,
      { params: { buffer_distance: bufferDistance } }
    );
    return response.data;
  },

  /**
   * Run building and settlement analysis
   */
  analyzeUserGroup: async (
    calculationId: string,
    extentId: number
  ): Promise<{ message: string; settlements_analyzed: number; total_buildings: number }> => {
    const response = await api.post(
      `/api/calculations/${calculationId}/user-group/analyze`,
      null,
      { params: { extent_id: extentId } }
    );
    return response.data;
  },

  /**
   * Get analysis results for visualization
   */
  getResults: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/calculations/${calculationId}/user-group/results`
    );
    return response.data;
  },

  /**
   * Get POI layers (points of interest, education, health, rivers)
   */
  getPOILayers: async (
    calculationId: string,
    layerType: 'all' | 'poi' | 'education' | 'health' | 'rivers' = 'all'
  ): Promise<any> => {
    const response = await api.get(
      `/api/calculations/${calculationId}/user-group/poi`,
      { params: { layer_type: layerType } }
    );
    return response.data;
  },

  /**
   * Delete user group extent and all related data
   */
  deleteExtent: async (calculationId: string): Promise<void> => {
    await api.delete(`/api/calculations/${calculationId}/user-group`);
  },

  /**
   * Export user group map (PDF, GPKG, GeoJSON, CSV)
   */
  exportMap: async (
    extentId: number,
    format: 'pdf' | 'gpkg' | 'geojson' | 'csv'
  ): Promise<Blob> => {
    const response = await api.get(`/api/user-group/${extentId}/export`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  },

  /**
   * Query land cover and biomass at a specific point
   */
  queryPoint: async (
    calculationId: string,
    lat: number,
    lon: number
  ): Promise<{
    location: { lat: number; lon: number };
    land_cover: { class_code: number; class_name: string } | null;
    biomass: { value_mg_ha: number; volume_m3_ha: number } | null;
  }> => {
    const response = await api.get(
      `/api/calculations/${calculationId}/user-group/query`,
      {
        params: { lat, lon },
      }
    );
    return response.data;
  },

  /**
   * Analyze land cover and biomass for user group extent
   *
   * Performs comprehensive spatial analysis including:
   * - Land use classification (ESA World Cover)
   * - Biomass estimation (AGB 2022 Nepal)
   * - Community forest overlap exclusion
   * - Timber volume calculation
   *
   * Prerequisites:
   * 1. Community forest boundary must be uploaded (Analysis tab)
   * 2. User group extent must be created (Forest User Map tab)
   */
  analyzeLandCover: async (calculationId: string, forceRefresh: boolean = false): Promise<{
    user_group_area_ha: number;
    forest_overlap_area_ha: number;
    net_analysis_area_ha: number;
    land_cover_classes: Array<{
      class_code: number;
      class_name: string;
      area_ha: number;
      percentage: number;
      avg_biomass_mg_per_ha: number;
      min_biomass_mg_per_ha: number;
      max_biomass_mg_per_ha: number;
      total_biomass_mg: number;
      avg_volume_m3_per_ha: number;
      total_volume_m3: number;
      pixel_count: number;
    }>;
    total_biomass_mg: number;
    total_volume_m3: number;
    avg_biomass_mg_per_ha: number;
    avg_volume_m3_per_ha: number;
    analysis_date: string;
    has_forest_overlap: boolean;
    from_cache?: boolean;
  }> => {
    const response = await api.get(
      `/api/calculations/${calculationId}/user-group/land-cover`,
      {
        params: { force_refresh: forceRefresh }
      }
    );
    return response.data;
  },

  // ============================================================================
  // Household Information API
  // ============================================================================

  /**
   * Download Excel template for household information entry
   */
  downloadHouseholdTemplate: async (
    calculationId: string,
    options: { land_unit: 'ropani' | 'kaththa'; include_coordinates: boolean }
  ): Promise<Blob> => {
    const response = await api.post(
      `/api/household/calculations/${calculationId}/template`,
      options,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },

  /**
   * Upload filled Excel file with household data
   */
  uploadHouseholdData: async (
    calculationId: string,
    file: File
  ): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post(
      `/api/household/calculations/${calculationId}/upload`,
      formData
    );
    return response.data;
  },

  /**
   * Get all household records for a calculation
   */
  getHouseholds: async (
    calculationId: string,
    skip = 0,
    limit = 100
  ): Promise<any[]> => {
    const response = await api.get(
      `/api/household/calculations/${calculationId}/households`,
      {
        params: { skip, limit },
      }
    );
    return response.data;
  },

  /**
   * Get a single household by ID
   */
  getHousehold: async (householdId: string): Promise<any> => {
    const response = await api.get(`/api/household/households/${householdId}`);
    return response.data;
  },

  /**
   * Create a new household record
   */
  createHousehold: async (calculationId: string, data: any): Promise<any> => {
    const response = await api.post(
      `/api/household/calculations/${calculationId}/households`,
      data
    );
    return response.data;
  },

  /**
   * Update a household record
   */
  updateHousehold: async (householdId: string, data: any): Promise<any> => {
    console.log('API: updateHousehold called', householdId, data);
    const response = await api.put(
      `/api/household/households/${householdId}`,
      data
    );
    console.log('API: updateHousehold response', response.data);
    return response.data;
  },

  /**
   * Delete a household record
   */
  deleteHousehold: async (householdId: string): Promise<void> => {
    await api.delete(`/api/household/households/${householdId}`);
  },

  /**
   * Delete all household records for a calculation
   */
  deleteAllHouseholds: async (calculationId: string): Promise<any> => {
    const response = await api.delete(
      `/api/household/calculations/${calculationId}/households`
    );
    return response.data;
  },

  /**
   * Get summary statistics for household data
   */
  getHouseholdSummary: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/household/calculations/${calculationId}/summary`
    );
    return response.data;
  },

  /**
   * Export household analysis to Excel
   */
  exportHouseholdAnalysis: async (calculationId: string): Promise<Blob> => {
    const response = await api.get(
      `/api/household/calculations/${calculationId}/export`,
      {
        responseType: 'blob',
      }
    );
    return response.data;
  },

  /**
   * Get surname suggestions for autocomplete
   */
  getSurnameSuggestions: async (
    query: string,
    limit = 10
  ): Promise<any[]> => {
    const response = await api.get(`/api/household/surnames`, {
      params: { q: query, limit },
    });
    return response.data;
  },

  /**
   * Lookup caste classification by surname
   */
  lookupCasteBySurname: async (surname: string): Promise<any[]> => {
    const response = await api.get(`/api/household/caste-lookup/${surname}`);
    return response.data;
  },

  // ============================================================================
  // Forest Committee API
  // ============================================================================

  /**
   * Get all committee data for a user group
   */
  getAllCommittees: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/forest-committee/user-groups/${calculationId}`);
    return response.data;
  },

  /**
   * Create/replace all committees in bulk
   */
  createCommitteesBulk: async (calculationId: string, data: any): Promise<any> => {
    const response = await api.post(`/api/forest-committee/user-groups/${calculationId}/bulk`, data);
    return response.data;
  },

  /**
   * Create a main committee member
   */
  createMainCommitteeMember: async (calculationId: string, member: any): Promise<any> => {
    const response = await api.post(`/api/forest-committee/user-groups/${calculationId}/main`, member);
    return response.data;
  },

  /**
   * Update a main committee member
   */
  updateMainCommitteeMember: async (memberId: string, updates: any): Promise<any> => {
    const response = await api.put(`/api/forest-committee/main/${memberId}`, updates);
    return response.data;
  },

  /**
   * Delete a main committee member
   */
  deleteMainCommitteeMember: async (memberId: string): Promise<void> => {
    await api.delete(`/api/forest-committee/main/${memberId}`);
  },

  /**
   * Create an advisory committee member
   */
  createAdvisoryMember: async (calculationId: string, member: any): Promise<any> => {
    const response = await api.post(`/api/forest-committee/user-groups/${calculationId}/advisory`, member);
    return response.data;
  },

  /**
   * Update an advisory committee member
   */
  updateAdvisoryMember: async (memberId: string, updates: any): Promise<any> => {
    const response = await api.put(`/api/forest-committee/advisory/${memberId}`, updates);
    return response.data;
  },

  /**
   * Delete an advisory committee member
   */
  deleteAdvisoryMember: async (memberId: string): Promise<void> => {
    await api.delete(`/api/forest-committee/advisory/${memberId}`);
  },

  /**
   * Create a financial committee member
   */
  createFinancialMember: async (calculationId: string, member: any): Promise<any> => {
    const response = await api.post(`/api/forest-committee/user-groups/${calculationId}/financial`, member);
    return response.data;
  },

  /**
   * Update a financial committee member
   */
  updateFinancialMember: async (memberId: string, updates: any): Promise<any> => {
    const response = await api.put(`/api/forest-committee/financial/${memberId}`, updates);
    return response.data;
  },

  /**
   * Delete a financial committee member
   */
  deleteFinancialMember: async (memberId: string): Promise<void> => {
    await api.delete(`/api/forest-committee/financial/${memberId}`);
  },

  /**
   * Delete all committee data for a user group
   */
  deleteAllCommittees: async (calculationId: string): Promise<any> => {
    const response = await api.delete(`/api/forest-committee/user-groups/${calculationId}`);
    return response.data;
  },
};
