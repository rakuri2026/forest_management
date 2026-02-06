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

const API_BASE_URL = 'http://localhost:8001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
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
    blockName?: string
  ): Promise<Calculation> => {
    const formData = new FormData();
    formData.append('file', file);
    if (forestName) formData.append('forest_name', forestName);
    if (blockName) formData.append('block_name', blockName);

    const response = await api.post<Calculation>('/api/forests/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
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

  getPoints: async (designId: string, format?: "json" | "geojson"): Promise<any> => {
    const response = await api.get(`/api/sampling/${designId}/points`, {
      params: format ? { format } : undefined,
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
};
