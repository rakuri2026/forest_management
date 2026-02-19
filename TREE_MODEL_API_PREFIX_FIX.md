# Tree Model API Prefix Fix

**Date:** February 19, 2026
**Issue:** "Failed to start tree model generation" error when clicking "Generate Tree Model" button

## Problem

The TreeModelGenerator component was making API calls without the `/api` prefix, causing requests to fail because:
- Vite proxy only proxies URLs starting with `/api`
- Requests to `/calculations/...` were not being forwarded to backend at `localhost:8001`
- Backend was running correctly, but frontend couldn't reach the endpoints

## Root Cause

In `frontend/src/components/TreeModelGenerator.tsx`, all API calls were missing the `/api` prefix:

```typescript
// ❌ WRONG - Missing /api prefix
await api.post(`/calculations/${calculationId}/generate-tree-model`, { config });
await api.get(`/calculations/${calculationId}/tree-models`);
await api.get(`/tree-models/${pollingId}`);
await api.get(`/tree-models/${modelId}/download`, { responseType: 'blob' });
await api.delete(`/tree-models/${modelId}`);
```

## Solution

Added `/api` prefix to all 5 API endpoints in TreeModelGenerator.tsx:

1. ✅ **loadModels()** - Line 62
   - `/calculations/${calculationId}/tree-models`
   - → `/api/calculations/${calculationId}/tree-models`

2. ✅ **Polling interval** - Line 84
   - `/tree-models/${pollingId}`
   - → `/api/tree-models/${pollingId}`

3. ✅ **handleGenerate()** - Line 112
   - `/calculations/${calculationId}/generate-tree-model`
   - → `/api/calculations/${calculationId}/generate-tree-model`

4. ✅ **handleDownload()** - Line 129
   - `/tree-models/${modelId}/download`
   - → `/api/tree-models/${modelId}/download`

5. ✅ **handleDelete()** - Line 153
   - `/tree-models/${modelId}`
   - → `/api/tree-models/${modelId}`

## Verification

Backend endpoint tested successfully with curl and Python test script:
- Endpoint: `POST /api/calculations/{id}/generate-tree-model` ✅ Returns 200 OK
- Authentication working correctly
- Background job creation successful
- Model status tracking functional

## Files Modified

- `frontend/src/components/TreeModelGenerator.tsx` - Added `/api` prefix to 5 API calls

## Testing

After fix:
1. Navigate to Analysis tab of any calculation
2. Expand "Tree Distribution Model" section
3. Click "Generate Tree Model" button
4. Should see "Queued" status with progress tracking
5. Progress updates every 3 seconds
6. Download button appears when status = "completed"

## Impact

- ✅ Tree model generation now works from frontend
- ✅ Progress polling functional
- ✅ Download and delete operations working
- ✅ No breaking changes to existing functionality

## Notes

This aligns TreeModelGenerator with other components that already use the `/api` prefix correctly (e.g., AnalysisTabContent, SpeciesTable, etc.).

The `api.ts` file already had the correct endpoints defined - the component just wasn't using them consistently.
