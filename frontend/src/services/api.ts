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
import { downloadFromApi } from '../utils/download';
import { downloadFromApi } from '../utils/download';

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

  // Block area detail (Table 5) - get per-block forest area description
  getBlockAreaDetail: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/forests/calculations/${calculationId}/block-area-detail`
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
      block_breakdown?: Array<{ blockId: string; blockName: string; area: number; percentage: number }>;
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
      geometry?: any;
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
   * Update block geometries (from block editor)
   * Handles vertex editing with automatic sub-area clipping
   */
  updateBlocksGeometry: async (
    calculationId: string,
    data: {
      blocks: Array<{
        block_id: string;
        block_name: string;
        geometry: any;
        area_hectares: number;
        index: number;
      }>;
      update_boundary: boolean;
    }
  ): Promise<any> => {
    const response = await api.patch(
      `/api/forests/calculations/${calculationId}/update-blocks`,
      data
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

  /**
   * Update forest boundary geometry
   */
  updateBoundaryGeometry: async (calculationId: string, data: {
    geometry: any;
    area_hectares: number;
  }): Promise<any> => {
    const response = await api.put(
      `/api/forests/calculations/${calculationId}/boundary`,
      data
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

export const allTreeExportApi = {
  generate: async (calculationId: string, config?: {
    min_dbh_cm?: number;
    max_dbh_cm?: number;
    min_height_m?: number;
    max_trees_per_ha?: number;
    algorithm_version?: string;
    species_role_target_ratio?: Record<string, number> | null;
  }) => {
    const response = await api.post(`/api/calculations/${calculationId}/generate-all-trees`, {
      config: config || null
    });
    return response.data;
  },

  getExport: async (exportId: string) => {
    const response = await api.get(`/api/all-tree-exports/${exportId}`);
    return response.data;
  },

  listExports: async (calculationId: string) => {
    const response = await api.get(`/api/calculations/${calculationId}/all-tree-exports`);
    return response.data;
  },

  downloadGpkg: async (exportId: string) => {
    const response = await api.get(`/api/all-tree-exports/${exportId}/download`, {
      responseType: 'blob'
    });
    return response.data;
  },

  downloadExcel: async (exportId: string) => {
    const response = await api.get(`/api/all-tree-exports/${exportId}/download-excel`, {
      responseType: 'blob'
    });
    return response.data;
  },

  downloadCsv: async (exportId: string) => {
    const response = await api.get(`/api/all-tree-exports/${exportId}/download-csv`, {
      responseType: 'blob'
    });
    return response.data;
  },

  delete: async (exportId: string) => {
    const response = await api.delete(`/api/all-tree-exports/${exportId}`);
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

  // Preview column mapping for uploaded CSV
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

  // Confirm column mapping and save preferences
  confirmColumnMapping: async (
    file: File,
    mapping: Record<string, string>,
    savePreference: boolean,
    gridSpacing: number,
    calculationId?: string,
    projectionEpsg?: number
  ): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("mapping", JSON.stringify(mapping));
    formData.append("save_preference", savePreference.toString());
    formData.append("grid_spacing_meters", gridSpacing.toString());
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

  // Get tree mapping data for a calculation
  getTreeMappingByCalculation: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/inventory/tree-mapping/${calculationId}`);
    return response.data;
  },

  // Check if ANY tree mapping exists (regardless of owner)
  checkTreeMappingExists: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/inventory/by-calculation/${calculationId}/check`);
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

exportInventory: async (id: string, format: "csv" | "geojson" | "excel"): Promise<{blob: Blob, filename: string}> => {
    const response = await api.get(`/api/inventory/${id}/export`, {
      params: { format },
      responseType: "blob",
    });
    return {
      blob: response.data,
      filename: `inventory_${id}.${format}`
    };
  },

  deleteInventory: async (id: string): Promise<void> => {
    await api.delete(`/api/inventory/${id}`);
  },

  // Force delete tree mapping by calculation (ignores user ownership)
  forceDeleteByCalculation: async (calculationId: string): Promise<any> => {
    const response = await api.delete(`/api/inventory/by-calculation/${calculationId}/force`);
    return response.data;
  },

  // Get correction preview for boundary correction
  getCorrectionPreview: async (inventoryId: string): Promise<any> => {
    const response = await api.get(`/api/inventory/${inventoryId}/correction-preview`);
    return response.data;
  },

  // Accept boundary corrections
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

  // Update block/sub-area via spatial intersection
  updateTreeBlockSubarea: async (inventoryId: string): Promise<any> => {
    const response = await api.post(`/api/inventory/${inventoryId}/update-block-subarea`);
    return response.data;
  },

  // Get grid cells for a specific inventory calculation
  getGridCells: async (inventoryId: string): Promise<any> => {
    const response = await api.get(`/api/inventory/${inventoryId}/grid-cells`);
    return response.data;
  },

  // Export grid cells as GeoJSON or KML
  exportGrid: async (inventoryId: string, format: 'geojson' | 'kml'): Promise<Blob> => {
    const response = await api.get(`/api/inventory/${inventoryId}/export-grid`, {
      params: { format },
      responseType: 'blob',
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

  exportExcel: async (
    fieldInventoryId: string,
    aahGood: number = 75,
    aahModerate: number = 60,
    aahWeak: number = 40,
    customMultipliers?: Record<string, number>
  ): Promise<Blob> => {
    const params: any = {
      aah_good: aahGood,
      aah_moderate: aahModerate,
      aah_weak: aahWeak
    };

    if (customMultipliers && Object.keys(customMultipliers).length > 0) {
      params.custom_multipliers = JSON.stringify(customMultipliers);
    }

    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/export-excel`, {
      params,
      responseType: 'blob'
    });
    return response.data;
  },

  exportDfoSummary: async (
    fieldInventoryId: string,
    calculationId: string,
    aahGood: number = 75,
    aahModerate: number = 60,
    aahWeak: number = 40,
  ): Promise<Blob> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/export-dfo-summary`, {
      params: {
        calculation_id: calculationId,
        aah_good: aahGood,
        aah_moderate: aahModerate,
        aah_weak: aahWeak,
      },
      responseType: 'blob'
    });
    return response.data;
  },

  getManagementPlanData: async (
    fieldInventoryId: string,
    calculationId: string,
    aahGood?: number,
    aahModerate?: number,
    aahWeak?: number,
  ): Promise<any> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/management-plan-data`, {
      params: {
        calculation_id: calculationId,
        aah_good: aahGood,
        aah_moderate: aahModerate,
        aah_weak: aahWeak,
      },
    });
    return response.data;
  },

  exportManagementPlanDocx: async (
    fieldInventoryId: string,
    calculationId: string,
    aahGood?: number,
    aahModerate?: number,
    aahWeak?: number,
  ): Promise<Blob> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/export-management-plan-docx`, {
      params: {
        calculation_id: calculationId,
        aah_good: aahGood,
        aah_moderate: aahModerate,
        aah_weak: aahWeak,
      },
      responseType: 'blob'
    });
    return response.data;
  },

  export10yrPlanDocx: async (
    fieldInventoryId: string,
    calculationId: string,
    aahGood?: number,
    aahModerate?: number,
    aahWeak?: number,
    includeMaps?: boolean,
    includeCharts?: boolean,
  ): Promise<Blob> => {
    const response = await api.get(`/api/field-inventory/${fieldInventoryId}/export-10yr-plan-docx`, {
      params: {
        calculation_id: calculationId,
        aah_good: aahGood,
        aah_moderate: aahModerate,
        aah_weak: aahWeak,
        include_maps: includeMaps,
        include_charts: includeCharts,
      },
      responseType: 'blob'
    });
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

  list: async (calculationId: string, includeTopographic: boolean = false): Promise<any> => {
    const response = await api.get(`/api/calculations/${calculationId}/fieldbook`, {
      params: { include_topographic: includeTopographic }
    });
    return response.data;
  },

  // Explicitly request with topographic features
  listWithTopographic: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/calculations/${calculationId}/fieldbook`, {
      params: { include_topographic: true }
    });
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
      // Method selection (NEW - Phase 3: Guideline-2061)
      sampling_method?: "guideline_2061" | "manual"; // Default: guideline_2061

      // Guideline-2061 specific parameters
      productive_intensity?: "0.5" | "1.0"; // For productive blocks (default: 0.5)
      sample_protected_zone?: boolean; // Include protected zone at 0.1% (default: false)
      plot_size_sqm?: number; // 100-500 for production, 25-100 for protected (default: 500)

      // Manual method parameters
      sampling_type?: "systematic" | "random" | "stratified";
      sampling_intensity_percent?: number; // Percentage of block area (0.1-10%, default 0.5%)
      min_samples_per_block?: number; // Minimum samples for blocks >= 1ha (2-10, default 5)
      min_samples_small_blocks?: number; // Minimum samples for blocks < 1ha (1-5, default 2)
      intensity_per_hectare?: number; // DEPRECATED: Use sampling_intensity_percent instead
      grid_spacing_meters?: number; // DEPRECATED: Calculated automatically
      min_distance_meters?: number;

      // Common parameters
      plot_shape?: "circular" | "square" | "rectangular";
      plot_radius_meters?: number; // For manual method
      plot_length_meters?: number; // For manual method
      plot_width_meters?: number; // For manual method
      notes?: string;

      // Accessible forest filtering (common to both methods)
      filter_tree_cover?: boolean; // Filter to tree cover only (default: true)
      filter_slope?: boolean; // Filter by slope (default: false)
      max_slope_degrees?: number; // Max slope threshold (default: 45.0)
      boundary_buffer_meters?: number; // Minimum distance from boundary (default: 50)
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/calculations/${calculationId}/sampling/create`,
      params
    );
    return response.data;
  },

  getProtectedZones: async (calculationId: string): Promise<{
    has_protected: boolean;
    protected_area_hectares: number;
    protected_zone_names: string[];
    protected_zone_count: number;
    productive_area_hectares: number;
    total_area_hectares: number;
  }> => {
    const response = await api.get(
      `/api/calculations/${calculationId}/protected-zones`
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

/**
 * Yearly Activities API - Manage yearly program activities with spatial integration
 */
export const yearlyActivitiesApi = {
  /**
   * List all potential activities from master list
   */
  listPotentialActivities: async (filters?: {
    project_name?: string;
    program?: string;
    is_default?: string;
    is_active?: boolean;
  }): Promise<any[]> => {
    const params = { is_active: true, ...filters };
    const response = await api.get('/api/yearly-activities/potential-activities', { params });
    return response.data;
  },

  /**
   * List proposed activities for a calculation with spatial filtering
   */
  listProposedActivities: async (
    calculationId: string,
    filters?: {
      block_id?: string;
      sub_area_id?: string;
      sub_area_category?: string;
      status?: string;
    }
  ): Promise<any[]> => {
    const params = filters || {};
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/proposed-activities`,
      { params }
    );
    return response.data;
  },

  /**
   * Create a new proposed activity
   */
  createProposedActivity: async (
    calculationId: string,
    data: {
      potential_activity_id: number;
      block_id?: string;
      sub_area_id?: string;
      default_quantity: number;
      default_yearly_budget: number;
      notes?: string;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/yearly-activities/calculations/${calculationId}/proposed-activities`,
      data
    );
    return response.data;
  },

  /**
   * Update a proposed activity (including spatial assignment)
   */
  updateProposedActivity: async (
    proposedActivityId: string,
    data: {
      block_id?: string;
      sub_area_id?: string;
      default_quantity?: number;
      default_yearly_budget?: number;
      notes?: string;
      status?: string;
    }
  ): Promise<any> => {
    const response = await api.patch(
      `/api/yearly-activities/proposed-activities/${proposedActivityId}`,
      data
    );
    return response.data;
  },

  /**
   * Delete a proposed activity
   */
  deleteProposedActivity: async (proposedActivityId: string): Promise<void> => {
    await api.delete(`/api/yearly-activities/proposed-activities/${proposedActivityId}`);
  },

  /**
   * Get activities with geometry for map visualization
   */
  getActivitiesWithGeometry: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/proposed-activities/spatial`
    );
    return response.data;
  },

  /**
   * Get location summary (activities by block/sub-area)
   */
  getLocationSummary: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/location-summary`
    );
    return response.data;
  },

  /**
   * Get activity summary statistics
   */
  getSummary: async (calculationId: string): Promise<any> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/summary`
    );
    return response.data;
  },

  // ===== NEW: SPATIAL ASSIGNMENT APIs =====

  /**
   * Get spatial assignments for a proposed activity
   */
  getSpatialAssignments: async (activityId: string): Promise<any[]> => {
    const response = await api.get(
      `/api/yearly-activities/proposed-activities/${activityId}/spatial`
    );
    return response.data;
  },

  /**
   * Create spatial assignment
   */
  createSpatialAssignment: async (
    activityId: string,
    data: {
      block_id?: string;
      sub_area_id?: string;
      assignment_type: string;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/yearly-activities/proposed-activities/${activityId}/spatial`,
      data
    );
    return response.data;
  },

  /**
   * Delete spatial assignment
   */
  deleteSpatialAssignment: async (
    activityId: string,
    assignmentId: string
  ): Promise<void> => {
    await api.delete(
      `/api/yearly-activities/proposed-activities/${activityId}/spatial/${assignmentId}`
    );
  },

  // ===== NEW: DRAWN FEATURES APIs =====

  /**
   * Get drawn features for a proposed activity
   */
  getDrawnFeatures: async (activityId: string): Promise<any[]> => {
    const response = await api.get(
      `/api/yearly-activities/proposed-activities/${activityId}/drawn-features`
    );
    return response.data;
  },

  /**
   * Create drawn feature
   */
  createDrawnFeature: async (
    activityId: string,
    data: {
      feature_type: string;
      geometry: string;
      properties: object;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/yearly-activities/proposed-activities/${activityId}/drawn-features`,
      data
    );
    return response.data;
  },

  /**
   * Update drawn feature
   */
  updateDrawnFeature: async (
    activityId: string,
    featureId: string,
    data: {
      feature_type?: string;
      geometry?: string;
      properties?: object;
    }
  ): Promise<any> => {
    const response = await api.patch(
      `/api/yearly-activities/proposed-activities/${activityId}/drawn-features/${featureId}`,
      data
    );
    return response.data;
  },

  /**
   * Delete drawn feature
   */
  deleteDrawnFeature: async (
    activityId: string,
    featureId: string
  ): Promise<void> => {
    await api.delete(
      `/api/yearly-activities/proposed-activities/${activityId}/drawn-features/${featureId}`
    );
  },

  // ===== YEAR DETAILS APIs =====

  /**
   * Get year details for a proposed activity
   */
  getYearDetails: async (activityId: string): Promise<any[]> => {
    const response = await api.get(
      `/api/yearly-activities/proposed-activities/${activityId}/year-details`
    );
    return response.data;
  },

  /**
   * Create year detail
   */
  createYearDetail: async (
    activityId: string,
    data: {
      year_number: number;
      quantity?: number;
      yearly_budget?: number;
      notes?: string;
    }
  ): Promise<any> => {
    const response = await api.post(
      `/api/yearly-activities/proposed-activities/${activityId}/year-details`,
      data
    );
    return response.data;
  },

  /**
   * Update year detail
   */
  updateYearDetail: async (
    activityId: string,
    detailId: string,
    data: {
      quantity?: number;
      yearly_budget?: number;
      notes?: string;
    }
  ): Promise<any> => {
    const response = await api.patch(
      `/api/yearly-activities/proposed-activities/${activityId}/year-details/${detailId}`,
      data
    );
    return response.data;
  },

  /**
   * Delete year detail
   */
  deleteYearDetail: async (
    activityId: string,
    detailId: string
  ): Promise<void> => {
    await api.delete(
      `/api/yearly-activities/proposed-activities/${activityId}/year-details/${detailId}`
    );
  },

  // ===== EXPORT SPATIAL FEATURES =====

  /**
   * Export spatial features to KML format
   */
  exportSpatialFeaturesKml: async (activityId: string): Promise<void> => {
    try {
      await downloadFromApi(
        `/api/yearly-activities/proposed-activities/${activityId}/export/kml`,
        'spatial.kml'
      );
    } catch (error: any) {
      console.error('KML export error:', error);
      const errorMsg = error.response?.data?.detail || 'Failed to export KML';
      throw new Error(errorMsg);
    }
  },

  /**
   * Export spatial features to GPKG format
   */
  exportSpatialFeaturesGpkg: async (activityId: string): Promise<void> => {
    try {
      await downloadFromApi(
        `/api/yearly-activities/proposed-activities/${activityId}/export/gpkg`,
        'spatial.gpkg'
      );
    } catch (error: any) {
      console.error('GPKG export error:', error);
      const errorMsg = error.response?.data?.detail || 'Failed to export GPKG';
      throw new Error(errorMsg);
    }
  },

  // ===== NEW PAGE API METHODS =====

  /**
   * Get potential activities (master list) for a calculation
   */
  getPotentialActivities: async (calculationId: string): Promise<any[]> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/potential-activities`
    );
    return response.data;
  },

  /**
   * Get proposed activities for a calculation
   */
  getProposedActivities: async (calculationId: string): Promise<any[]> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/proposed-activities`
    );
    return response.data;
  },

  /**
   * Get all year details for a proposed activity
   */
  getAllYearDetails: async (activityId: string): Promise<any[]> => {
    const response = await api.get(
      `/api/yearly-activities/proposed-activities/${activityId}/year-details`
    );
    return response.data;
  },

  /**
   * Copy drawn feature to another year
   */
  copyDrawnFeature: async (
    activityId: string,
    featureId: string,
    targetYear: number
  ): Promise<any> => {
    const response = await api.post(
      `/api/yearly-activities/proposed-activities/${activityId}/drawn-features/${featureId}/copy`,
      { target_year: targetYear }
    );
    return response.data;
  },

  /**
   * Get blocks with sub-areas for a calculation
   */
  getBlocksWithSubareas: async (calculationId: string): Promise<any[]> => {
    const response = await api.get(
      `/api/yearly-activities/calculations/${calculationId}/blocks-with-subareas`
    );
    return response.data;
  },

  /**
   * Update spatial assignment
   */
  updateSpatialAssignment: async (
    activityId: string,
    assignmentId: string,
    data: {
      block_id?: string;
      sub_area_id?: string;
    }
  ): Promise<any> => {
    const response = await api.patch(
      `/api/yearly-activities/proposed-activities/${activityId}/spatial/${assignmentId}`,
      data
    );
    return response.data;
  },
};


// ============================================================================
// Compartment Management API
// ============================================================================

export const compartmentApi = {
  getAvailableBlocks: async (calculationId: string): Promise<any[]> => {
    const response = await api.get(`/api/compartments/available-blocks/${calculationId}`);
    return response.data;
  },

  getAllBlocks: async (calculationId: string): Promise<any[]> => {
    const response = await api.get(`/api/compartments/calculation/${calculationId}/all-blocks`);
    return response.data;
  },

  previewSplit: async (request: {
    block_id: string;
    method: 'parallel' | 'grid' | 'custom';
    parameters: Record<string, any>;
  }): Promise<any> => {
    const response = await api.post('/api/compartments/preview-split', request);
    return response.data;
  },

  executeSplit: async (request: {
    block_id: string;
    method: 'parallel' | 'grid' | 'custom';
    parameters: Record<string, any>;
    naming_pattern?: string;
    reassign_trees?: boolean;
    notes?: string;
  }): Promise<any> => {
    const response = await api.post('/api/compartments/execute-split', request);
    return response.data;
  },

  getSplitDirections: async (): Promise<any[]> => {
    const response = await api.get('/api/compartments/split-directions');
    return response.data;
  },

  undoSplit: async (splitHistoryId: string): Promise<any> => {
    const response = await api.delete(`/api/compartments/split/${splitHistoryId}`);
    return response.data;
  },

  deleteCompartments: async (blockId: string): Promise<any> => {
    const response = await api.delete(`/api/compartments/block/${blockId}/compartments`);
    return response.data;
  },

  deleteCompartment: async (compartmentId: string): Promise<any> => {
    const response = await api.delete(`/api/compartments/${compartmentId}`);
    return response.data;
  },

  /**
   * Update compartment name
   */
  updateCompartmentName: async (compartmentId: string, name: string): Promise<any> => {
    const response = await api.patch(`/api/compartments/${compartmentId}/name`, { name });
    return response.data;
  },

  getTreesNeedingAssignment: async (blockId: string): Promise<any> => {
    const response = await api.get(`/api/compartments/trees-needing-assignment/${blockId}`);
    return response.data;
  },

  reassignTrees: async (request: {
    block_id: string;
    auto_assign?: boolean;
    manual_assignments?: Record<string, string>;
  }): Promise<any> => {
    const response = await api.post('/api/compartments/reassign-trees', request);
    return response.data;
  },

  getTreesForMap: async (calculationId: string): Promise<{ count: number; trees: any[] }> => {
    const response = await api.get(`/api/compartments/calculation/${calculationId}/trees`);
    return response.data;
  },

  exportGpkg: async (calculationId: string): Promise<void> => {
    await downloadFromApi(
      `/api/compartments/calculation/${calculationId}/export-gpkg`,
      'compartments.gpkg'
    );
  },

  exportKml: async (calculationId: string): Promise<void> => {
    await downloadFromApi(
      `/api/compartments/calculation/${calculationId}/export-kml`,
      'compartments.kml'
    );
  },

  /**
   * Toggle lock status for a block/compartment
   */
  toggleLockBlock: async (blockId: string): Promise<any> => {
    const response = await api.patch(`/api/compartments/blocks/${blockId}/toggle-lock`);
    return response.data;
  },

  /**
   * Get hierarchical compartment tree for a calculation
   */
  getCompartmentTree: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/compartments/calculations/${calculationId}/compartment-tree`);
    return response.data;
  },

  /**
   * Sub-divide a compartment into sub-compartments
   */
  subdivideBlock: async (
    blockId: string,
    config: {
      method: 'parallel' | 'grid' | 'custom';
      parameters: Record<string, any>;
      naming_pattern?: string;
      reassign_trees?: boolean;
      notes?: string;
    }
  ): Promise<any> => {
    const response = await api.post(`/api/compartments/blocks/${blockId}/sub-divide`, config);
    return response.data;
  },
};

export const operationalPlanApi = {
  create: async (calculationId: string, forestName?: string, templateId?: string): Promise<any> => {
    const params = templateId ? `?template_id=${templateId}` : '';
    const response = await api.post(`/api/operational-plans${params}`, { calculation_id: calculationId, forest_name: forestName });
    return response.data;
  },

  getByCalculation: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/operational-plans/calculation/${calculationId}`);
    return response.data;
  },

  update: async (planId: string, data: any): Promise<any> => {
    const response = await api.put(`/api/operational-plans/${planId}`, data);
    return response.data;
  },

  autoPopulate: async (planId: string): Promise<any> => {
    const response = await api.post(`/api/operational-plans/${planId}/auto-populate`);
    return response.data;
  },

  getTree: async (planId: string): Promise<any> => {
    const response = await api.get(`/api/operational-plans/${planId}/tree`);
    return response.data;
  },

  addNode: async (planId: string, data: any): Promise<any> => {
    const response = await api.post(`/api/operational-plans/${planId}/tree/nodes`, data);
    return response.data;
  },

  updateNode: async (planId: string, nodeId: string, data: any): Promise<any> => {
    const response = await api.put(`/api/operational-plans/${planId}/tree/nodes/${nodeId}`, data);
    return response.data;
  },

  deleteNode: async (planId: string, nodeId: string): Promise<any> => {
    const response = await api.delete(`/api/operational-plans/${planId}/tree/nodes/${nodeId}`);
    return response.data;
  },

  reorderTree: async (planId: string, data: any): Promise<any> => {
    const response = await api.put(`/api/operational-plans/${planId}/tree/reorder`, data);
    return response.data;
  },

  getMetadataForm: async (planId: string): Promise<any> => {
    const response = await api.get(`/api/operational-plans/${planId}/metadata-form`);
    return response.data;
  },

  updateMetadataForm: async (planId: string, data: any): Promise<any> => {
    const response = await api.put(`/api/operational-plans/${planId}/metadata-form`, data);
    return response.data;
  },

  // ── Cascading Location Data (from admin.admin_nepal) ──
  getProvinces: async (): Promise<string[]> => {
    const response = await api.get('/api/operational-plans/locations/provinces');
    return response.data;
  },

  getDivisions: async (province?: string): Promise<string[]> => {
    const params = province ? { province } : {};
    const response = await api.get('/api/operational-plans/locations/divisions', { params });
    return response.data;
  },

  getSubDivisions: async (province?: string, division?: string): Promise<string[]> => {
    const params: Record<string, string> = {};
    if (province) params.province = province;
    if (division) params.division = division;
    const response = await api.get('/api/operational-plans/locations/sub-divisions', { params });
    return response.data;
  },

  getMunicipalities: async (province?: string, division?: string, subDivision?: string): Promise<{ name: string; type: string }[]> => {
    const params: Record<string, string> = {};
    if (province) params.province = province;
    if (division) params.division = division;
    if (subDivision) params.sub_division = subDivision;
    const response = await api.get('/api/operational-plans/locations/municipalities', { params });
    return response.data;
  },

  getWards: async (province?: string, division?: string, subDivision?: string, municipality?: string): Promise<string[]> => {
    const params: Record<string, string> = {};
    if (province) params.province = province;
    if (division) params.division = division;
    if (subDivision) params.sub_division = subDivision;
    if (municipality) params.municipality = municipality;
    const response = await api.get('/api/operational-plans/locations/wards', { params });
    return response.data;
  },

  getPhysiographyJurisdiction: async (province?: string, division?: string, subDivision?: string, municipality?: string): Promise<{ physiography_zone: string; protected_area_status: string }> => {
    const params: Record<string, string> = {};
    if (province) params.province = province;
    if (division) params.division = division;
    if (subDivision) params.sub_division = subDivision;
    if (municipality) params.municipality = municipality;
    const response = await api.get('/api/operational-plans/locations/physiography-jurisdiction', { params });
    return response.data;
  },

  // ── District-based Cascade (new civil admin hierarchy) ──
  getDistricts: async (province?: string): Promise<string[]> => {
    const params = province ? { province } : {};
    const response = await api.get('/api/operational-plans/locations/districts', { params });
    return response.data;
  },

  getMunicipalitiesByDistrict: async (province: string, district: string): Promise<{ name: string; type: string }[]> => {
    const response = await api.get('/api/operational-plans/locations/municipalities-by-district', { params: { province, district } });
    return response.data;
  },

  getWardsByDistrict: async (province: string, district: string, municipality: string): Promise<string[]> => {
    const response = await api.get('/api/operational-plans/locations/wards-by-district', { params: { province, district, municipality } });
    return response.data;
  },

  getPhysiographyByDistrict: async (province: string, district: string, municipality: string): Promise<{ physiography_zone: string; protected_area_status: string }> => {
    const response = await api.get('/api/operational-plans/locations/physiography-by-district', { params: { province, district, municipality } });
    return response.data;
  },

  listVariables: async (params?: { category?: string; search?: string }): Promise<any> => {
    const response = await api.get('/api/operational-plans/variables', { params });
    return response.data;
  },

  getVariable: async (key: string): Promise<any> => {
    const response = await api.get(`/api/operational-plans/variables/${key}`);
    return response.data;
  },

  getVariableCatalog: async (calculationId: string, params?: { category?: string; search?: string }): Promise<any> => {
    const response = await api.get(`/api/operational-plans/${calculationId}/variable-catalog`, { params });
    return response.data;
  },

  listTables: async (): Promise<any> => {
    const response = await api.get('/api/op-tables');
    return response.data;
  },

  getTableData: async (tableId: string, calculationId: string): Promise<any> => {
    const response = await api.get(`/api/op-tables/${tableId}/data`, { params: { calculation_id: calculationId } });
    return response.data;
  },

  updateTableData: async (tableId: string, calculationId: string, data: any): Promise<any> => {
    const response = await api.put(`/api/op-tables/${tableId}/data?calculation_id=${calculationId}`, data);
    return response.data;
  },

  autoPopulateTable: async (tableId: string, calculationId: string): Promise<any> => {
    const response = await api.post(`/api/op-tables/${tableId}/auto-populate?calculation_id=${calculationId}`);
    return response.data;
  },

  exportDocx: async (planId: string, forestName: string): Promise<void> => {
    await downloadFromApi(
      `/api/operational-plans/${planId}/export`,
      `${forestName}_OP_DOCX.docx`
    );
  },

  previewOperationalPlan: async (planId: string): Promise<string> => {
    const response = await api.get(`/api/operational-plans/${planId}/preview`, {
      responseType: 'text',
    });
    return response.data;
  },

  getChartData: async (planId: string, chartType: string): Promise<any> => {
    const response = await api.get(`/api/operational-plans/${planId}/chart-data/${chartType}`);
    return response.data;
  },

  getMapGeojson: async (planId: string): Promise<any> => {
    const response = await api.get(`/api/operational-plans/${planId}/map-geojson`);
    return response.data;
  },

  clearMapCache: async (planId: string, layer?: string): Promise<any> => {
    const params = layer ? `?layer=${encodeURIComponent(layer)}` : '';
    const response = await api.post(`/api/operational-plans/${planId}/clear-map-cache${params}`);
    return response.data;
  },

  resetTree: async (planId: string): Promise<any> => {
    const response = await api.post(`/api/operational-plans/${planId}/reset-tree`);
    return response.data;
  },

  // ── Template Management ──

  listTemplates: async (scope: string = 'mine', tag?: string): Promise<any> => {
    let url = `/api/operational-plans/templates?scope=${scope}`;
    if (tag) url += `&tag=${encodeURIComponent(tag)}`;
    const response = await api.get(url);
    return response.data;
  },

  listPublicTemplates: async (tag?: string, search?: string): Promise<any> => {
    let url = '/api/operational-plans/templates/public';
    const params: any = {};
    if (tag) params.tag = tag;
    if (search) params.search = search;
    const response = await api.get(url, { params });
    return response.data;
  },

  listPendingTemplates: async (): Promise<any> => {
    const response = await api.get('/api/operational-plans/templates/pending-approval');
    return response.data;
  },

  getTemplate: async (templateId: string): Promise<any> => {
    const response = await api.get(`/api/operational-plans/templates/${templateId}`);
    return response.data;
  },

  createTemplate: async (data: { name: string; description?: string; tree: any[]; is_default?: boolean; visibility?: string; tags?: string[] }): Promise<any> => {
    const response = await api.post('/api/operational-plans/templates', data);
    return response.data;
  },

  updateTemplate: async (templateId: string, data: any): Promise<any> => {
    const response = await api.put(`/api/operational-plans/templates/${templateId}`, data);
    return response.data;
  },

  deleteTemplate: async (templateId: string): Promise<any> => {
    const response = await api.delete(`/api/operational-plans/templates/${templateId}`);
    return response.data;
  },

  submitTemplateForApproval: async (templateId: string): Promise<any> => {
    const response = await api.post(`/api/operational-plans/templates/${templateId}/submit`);
    return response.data;
  },

  reviewTemplate: async (templateId: string, action: 'approve' | 'reject', note?: string): Promise<any> => {
    const response = await api.post(`/api/operational-plans/templates/${templateId}/review`, { action, note: note || '' });
    return response.data;
  },

  savePlanAsTemplate: async (planId: string, data: { name: string; description?: string; tree?: any[]; is_default?: boolean; visibility?: string; tags?: string[] }): Promise<any> => {
    const response = await api.post(`/api/operational-plans/${planId}/save-as-template`, data);
    return response.data;
  },
};

export const biodiversityApi = {
  getCalculationSpecies: async (calculationId: string): Promise<any> => {
    const response = await api.get(`/api/biodiversity/calculations/${calculationId}/species`);
    return response.data;
  },
};
