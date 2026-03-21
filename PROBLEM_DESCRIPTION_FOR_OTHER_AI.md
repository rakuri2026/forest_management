# Frontend API Endpoint Missing `/api` Prefix - Need Help

## Problem Summary

I have a React + TypeScript frontend (Vite) calling a FastAPI backend. The API calls are returning 404 errors because they're missing the `/api` prefix in the URL path.

## Current Behavior (Wrong)

**Backend logs show:**
```
POST /calculations/5375a8a7-1b73-4a2d-8502-d5b427543d9d/generate-tree-model HTTP/1.1" 404 Not Found
GET /calculations/5375a8a7-1b73-4a2d-8502-d5b427543d9d/tree-models HTTP/1.1" 404 Not Found
```

**Browser console shows:**
```
POST http://localhost:8001/calculations/5375a8a7-1b73-4a2d-8502-d5b427543d9d/generate-tree-model 404 (Not Found)
Response: {"detail":"Not Found"}
```

## Expected Behavior (Correct)

The URLs should include `/api` prefix:
```
POST /api/calculations/5375a8a7-1b73-4a2d-8502-d5b427543d9d/generate-tree-model
GET /api/calculations/5375a8a7-1b73-4a2d-8502-d5b427543d9d/tree-models
```

## Source Code (Appears Correct)

**File: `frontend/src/services/api.ts` (lines 214-249)**
```typescript
export const treeModelApi = {
  generate: async (calculationId: string, config?: {
    min_dbh_cm?: number;
    min_height_m?: number;
    max_trees_per_ha?: number;
    spatial_distribution?: string;
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
```

**The source code clearly has `/api` prefix in all endpoints** (lines 222, 229, 234, 239, 246), but the actual HTTP requests don't include it.

## Configuration Files

**File: `frontend/src/services/api.ts` (lines 1-22)**
```typescript
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
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
  },
});
```

**File: `frontend/vite.config.ts`**
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      }
    }
  }
})
```

## Backend Routes (Working for Other Endpoints)

**File: `backend/app/main.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import auth_router, forests_router, inventory_router, species_router, tree_models_router

app = FastAPI(title="Community Forest Management System", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with /api prefix
app.include_router(auth_router, prefix="/api", tags=["Authentication"])
app.include_router(forests_router, prefix="/api", tags=["Forests"])
app.include_router(inventory_router, prefix="/api", tags=["Inventory"])
app.include_router(species_router, prefix="/api", tags=["Species"])
app.include_router(tree_models_router, prefix="/api", tags=["Tree Distribution Models"])
```

**Note:** Other API endpoints work fine:
- ✅ `GET /api/forests/calculations/{id}/species-summary` - Returns 200 OK
- ✅ `PATCH /api/forests/calculations/{id}/species/{name}/confirm` - Works (or 404 for other reasons)
- ❌ `POST /calculations/{id}/generate-tree-model` - Missing `/api` prefix, returns 404
- ❌ `GET /calculations/{id}/tree-models` - Missing `/api` prefix, returns 404

## Component Using the API

**File: `frontend/src/components/TreeModelGenerator.tsx` (line 111)**
```typescript
const handleGenerate = async () => {
  if (generating) return;

  setGenerating(true);
  setError(null);

  try {
    console.log('Generating tree model with config:', config);
    const result = await treeModelApi.generate(calculationId, config);
    console.log('Generation started:', result);

    setModels(prev => [...prev, result]);
    setPollingId(result.id);
  } catch (err: any) {
    console.error('Error generating tree model:', err);
    setError(err.response?.data?.detail || err.message || 'Failed to generate tree model');
    setGenerating(false);
  }
};
```

## What I've Tried

1. ✅ Verified source code has `/api` prefix in all treeModelApi functions
2. ✅ Confirmed other API calls (forestApi, inventoryApi) work correctly with `/api` prefix
3. ✅ Checked Vite proxy configuration - looks correct
4. ✅ Confirmed backend routes are registered with `/api` prefix
5. ✅ Attempted to clear Vite cache by deleting `node_modules/.vite`, `.vite`, `dist` folders
6. ❌ Still getting 404 with missing `/api` prefix in actual HTTP requests

## Environment

- **Frontend:** React 18 + TypeScript + Vite 5.4.21
- **Backend:** FastAPI + Python 3.14
- **Axios Version:** Latest
- **OS:** Windows
- **Servers:**
  - Backend: http://localhost:8001 (running correctly)
  - Frontend: http://localhost:3001 (running, but making wrong API calls)

## Questions

1. Why would the source code show `/api` prefix but actual HTTP requests not include it?
2. Could there be a build cache issue that deleting Vite cache folders didn't fix?
3. Could the Vite proxy configuration be stripping the `/api` prefix somehow?
4. Is there a way to debug exactly what URL axios is sending before it leaves the browser?
5. Could there be multiple versions of `api.ts` being loaded?

## Additional Context

- This is a new feature (Tree Model Generator) added today
- Other existing features in the same codebase work correctly with `/api` prefix
- The treeModelApi code was added to the same `api.ts` file where other working APIs exist
- The axios instance is shared between all APIs (forestApi, inventoryApi, treeModelApi, etc.)

---

**Please help identify why the `/api` prefix is disappearing from the actual HTTP requests despite being in the source code.**
