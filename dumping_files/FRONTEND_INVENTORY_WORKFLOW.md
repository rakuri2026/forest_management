# Frontend Inventory Workflow - Updated

## Issue
After uploading and validating inventory, users couldn't see tree counts/volumes and export failed.

## Cause
The frontend was only calling the validation endpoint. It needed to call a second endpoint to actually process (calculate volumes and store trees).

## Solution - Two-Step Workflow

### Step 1: Upload & Validate

**Endpoint:** `POST /api/inventory/upload`

```javascript
const formData = new FormData();
formData.append('file', csvFile);
formData.append('calculation_id', calculationId); // optional
formData.append('grid_spacing_meters', 20.0);
formData.append('projection_epsg', 32645); // optional

const response = await fetch('/api/inventory/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

const result = await response.json();

if (result.summary.ready_for_processing) {
  const inventoryId = result.inventory_id;
  // Now proceed to Step 2
}
```

### Step 2: Process Inventory

**Endpoint:** `POST /api/inventory/{inventory_id}/process`

**IMPORTANT:** You must re-upload the same CSV file for processing.

```javascript
const formData = new FormData();
formData.append('file', csvFile); // Same file from Step 1

const response = await fetch(`/api/inventory/${inventoryId}/process`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
});

const result = await response.json();

if (result.status === 'completed') {
  // Processing complete!
  // Can now view summary and export
}
```

### Step 3: View Summary

**Endpoint:** `GET /api/inventory/{inventory_id}/summary`

```javascript
const response = await fetch(`/api/inventory/${inventoryId}/summary`, {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

const summary = await response.json();

console.log(`Total trees: ${summary.total_trees}`);
console.log(`Total volume: ${summary.total_volume_m3} m³`);
console.log(`Seedlings: ${summary.seedling_count}`);
console.log(`Felling trees: ${summary.felling_trees_count}`);
```

### Step 4: Export

**Endpoint:** `GET /api/inventory/{inventory_id}/export?format=csv`

```javascript
const response = await fetch(
  `/api/inventory/${inventoryId}/export?format=csv`,
  {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  }
);

const blob = await response.blob();
const url = window.URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = `inventory_${inventoryId}.csv`;
a.click();
```

## Complete React Component Example

```typescript
import React, { useState } from 'react';

export const InventoryUpload = () => {
  const [file, setFile] = useState<File | null>(null);
  const [inventoryId, setInventoryId] = useState<string | null>(null);
  const [status, setStatus] = useState<string>('idle');
  const [summary, setSummary] = useState<any>(null);

  const handleUpload = async () => {
    if (!file) return;

    setStatus('validating');

    // Step 1: Upload & Validate
    const formData = new FormData();
    formData.append('file', file);
    formData.append('grid_spacing_meters', '20.0');

    const uploadResponse = await fetch('/api/inventory/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token')}`
      },
      body: formData
    });

    const uploadResult = await uploadResponse.json();

    if (uploadResult.summary.ready_for_processing) {
      const invId = uploadResult.inventory_id;
      setInventoryId(invId);

      // Step 2: Process Inventory
      setStatus('processing');

      const processFormData = new FormData();
      processFormData.append('file', file); // Re-upload same file

      const processResponse = await fetch(
        `/api/inventory/${invId}/process`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          },
          body: processFormData
        }
      );

      const processResult = await processResponse.json();

      if (processResult.status === 'completed') {
        setStatus('completed');

        // Step 3: Get Summary
        const summaryResponse = await fetch(
          `/api/inventory/${invId}/summary`,
          {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`
            }
          }
        );

        const summaryData = await summaryResponse.json();
        setSummary(summaryData);
      }
    }
  };

  const handleExport = async () => {
    if (!inventoryId) return;

    const response = await fetch(
      `/api/inventory/${inventoryId}/export?format=csv`,
      {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      }
    );

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `inventory_${inventoryId}.csv`;
    a.click();
  };

  return (
    <div>
      <h2>Upload Tree Inventory</h2>

      <input
        type="file"
        accept=".csv"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />

      <button
        onClick={handleUpload}
        disabled={!file || status !== 'idle'}
      >
        Upload & Process
      </button>

      {status === 'validating' && <p>Validating file...</p>}
      {status === 'processing' && <p>Processing inventory (calculating volumes)...</p>}

      {status === 'completed' && summary && (
        <div>
          <h3>Processing Complete!</h3>
          <p>Total Trees: {summary.total_trees}</p>
          <p>Total Volume: {summary.total_volume_m3} m³</p>
          <p>Net Volume: {summary.total_net_volume_m3} m³</p>
          <p>Net Volume: {summary.total_net_volume_cft} cft</p>
          <p>Seedlings: {summary.seedling_count}</p>
          <p>Felling Trees: {summary.felling_trees_count}</p>
          <p>Firewood: {summary.total_firewood_chatta} chatta</p>

          <button onClick={handleExport}>
            Export to CSV
          </button>
        </div>
      )}
    </div>
  );
};
```

## Key Points

1. **Two-step process is required:**
   - Step 1: Validate file structure and data
   - Step 2: Calculate volumes and store trees

2. **Must re-upload file for processing:**
   - The validated data is not stored
   - Processing needs the actual CSV data
   - Frontend should keep the File object in state

3. **Status tracking:**
   - `validated` - File passed validation
   - `processing` - Currently calculating volumes
   - `completed` - Processing done, can view/export
   - `failed` - Processing error occurred

4. **Export only works after processing:**
   - If status is `validated`, export will fail
   - Must be status `completed` to have trees in database

## Error Handling

```typescript
const handleUpload = async () => {
  try {
    // ... upload and validate ...

    if (!uploadResult.summary.ready_for_processing) {
      // Show validation errors
      const errors = uploadResult.summary.validation_errors;
      alert(`Validation failed:\n${errors.join('\n')}`);
      return;
    }

    // ... process inventory ...

    if (processResult.status === 'failed') {
      alert(`Processing failed: ${processResult.error_message}`);
      return;
    }

  } catch (error) {
    console.error('Upload failed:', error);
    alert(`Error: ${error.message}`);
  }
};
```

## Testing

To test if your changes work:

1. Upload a CSV file
2. Wait for validation
3. Wait for processing (may take a while for large files)
4. Check that tree count and volume are displayed
5. Try to export - should download CSV with all trees

## Troubleshooting

**Problem:** "Failed to export inventory"
- **Cause:** Inventory status is still `validated`, not `completed`
- **Solution:** Make sure you call the process endpoint

**Problem:** "No trees found for this inventory"
- **Cause:** Processing step was skipped
- **Solution:** Call `POST /api/inventory/{id}/process` with file

**Problem:** Processing takes too long
- **Cause:** Large CSV file (40,000+ trees)
- **Solution:** Show loading indicator, processing runs in background

---

**Status:** ✅ Backend fixed to support two-step workflow
**Frontend Task:** Update UI to call both upload and process endpoints
**Date:** February 2, 2026
