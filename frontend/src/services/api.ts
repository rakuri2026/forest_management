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
};

export default api;
