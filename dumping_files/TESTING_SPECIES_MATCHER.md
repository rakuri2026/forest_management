# Testing Species Matcher - Quick Guide

## Option 1: Backend Python Test (Easiest)

### Run the test script:
```bash
cd D:\forest_management
venv\Scripts\python test_species_matcher.py
```

This will show you:
- ✅ All matching patterns working
- ✅ Confidence scores
- ✅ Match types (code, exact, abbreviated, fuzzy)
- ✅ Batch identification
- ✅ Autocomplete suggestions
- ✅ CSV column validation

**Expected output:**
```
Input: 'sho'
  => Matched: Shorea robusta (Sal)
  => Code: 18
  => Match Type: abbreviated
  => Confidence: 0.7
  => Field: abbrev_genus
```

---

## Option 2: Test via API (Browser/Postman)

### Step 1: Start Backend
```bash
cd D:\forest_management
start_backend.bat
```

Wait for:
```
Application startup complete.
Uvicorn running on http://0.0.0.0:8001
```

### Step 2: Open API Documentation
Open in browser:
```
http://localhost:8001/docs
```

### Step 3: Test Species Endpoints

#### A. Identify Single Species
**Endpoint:** `GET /api/species/identify`

**Try these in the browser:**

1. **Numeric code:**
   ```
   http://localhost:8001/api/species/identify?q=18
   ```

2. **Abbreviated code:**
   ```
   http://localhost:8001/api/species/identify?q=sho
   http://localhost:8001/api/species/identify?q=sho%20rob
   http://localhost:8001/api/species/identify?q=aln
   ```

3. **Scientific name:**
   ```
   http://localhost:8001/api/species/identify?q=Shorea%20robusta
   ```

4. **Nepali romanized:**
   ```
   http://localhost:8001/api/species/identify?q=Sal
   ```

**Expected Response:**
```json
{
  "success": true,
  "species": {
    "code": 18,
    "species": "Shorea robusta",
    "species_nepali_unicode": "साल",
    "name_nep": "Sal",
    "common_name": "Sal"
  },
  "match_type": "abbreviated",
  "confidence": 0.7,
  "matched_field": "abbrev_genus"
}
```

#### B. Get Suggestions (Autocomplete)
**Endpoint:** `GET /api/species/suggest`

```
http://localhost:8001/api/species/suggest?q=sho&limit=3
http://localhost:8001/api/species/suggest?q=pin&limit=5
http://localhost:8001/api/species/suggest?q=sal&limit=3
```

**Expected Response:**
```json
{
  "suggestions": [
    {
      "species": {
        "code": 18,
        "species": "Shorea robusta",
        "species_nepali_unicode": "साल",
        "name_nep": "Sal",
        "common_name": "Sal"
      },
      "confidence": 1.0,
      "matched_field": "nepali_romanized"
    }
  ],
  "count": 1
}
```

#### C. Batch Identification
**Endpoint:** `POST /api/species/identify-batch`

Use Swagger UI at http://localhost:8001/docs

**Request Body:**
```json
{
  "species_list": ["18", "sho", "aln nep", "साल", "Sal", "pin rox"]
}
```

**Expected Response:**
```json
{
  "results": [
    {
      "species": {...},
      "match_type": "code",
      "confidence": 1.0
    },
    {
      "species": {...},
      "match_type": "abbreviated",
      "confidence": 0.7
    },
    ...
  ],
  "total": 6,
  "matched": 6,
  "unmatched": 0
}
```

#### D. Get All Species
**Endpoint:** `GET /api/species/all`

```
http://localhost:8001/api/species/all
```

Returns all 23 species with full details.

#### E. Get Species by Code
**Endpoint:** `GET /api/species/{code}`

```
http://localhost:8001/api/species/18
http://localhost:8001/api/species/5
http://localhost:8001/api/species/9
```

---

## Option 3: Test with cURL (Command Line)

### 1. Identify Species
```bash
# By abbreviation
curl "http://localhost:8001/api/species/identify?q=sho"

# Two-part abbreviation
curl "http://localhost:8001/api/species/identify?q=sho%20rob"

# By code
curl "http://localhost:8001/api/species/identify?q=18"

# By Nepali name
curl "http://localhost:8001/api/species/identify?q=Sal"
```

### 2. Get Suggestions
```bash
curl "http://localhost:8001/api/species/suggest?q=pin&limit=3"
```

### 3. Batch Identify
```bash
curl -X POST "http://localhost:8001/api/species/identify-batch" \
  -H "Content-Type: application/json" \
  -d '{"species_list": ["sho", "aln", "18", "Sal"]}'
```

### 4. Validate Column (CSV scenario)
```bash
curl -X POST "http://localhost:8001/api/species/validate-column" \
  -H "Content-Type: application/json" \
  -d '{"species_list": ["1", "sho", "Uttis", "Shisham", "XYZ", "", "18", "Pine"]}'
```

---

## Option 4: Test in Frontend (If you have one)

### JavaScript/TypeScript Example

```typescript
// api.ts
export const identifySpecies = async (input: string) => {
  const response = await fetch(
    `http://localhost:8001/api/species/identify?q=${encodeURIComponent(input)}`
  );
  return response.json();
};

export const suggestSpecies = async (partial: string, limit: number = 5) => {
  const response = await fetch(
    `http://localhost:8001/api/species/suggest?q=${encodeURIComponent(partial)}&limit=${limit}`
  );
  return response.json();
};
```

### React Component Example

```tsx
import React, { useState } from 'react';

function SpeciesSearch() {
  const [input, setInput] = useState('');
  const [result, setResult] = useState(null);

  const handleSearch = async () => {
    const res = await fetch(
      `http://localhost:8001/api/species/identify?q=${encodeURIComponent(input)}`
    );
    const data = await res.json();
    setResult(data);
  };

  return (
    <div>
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Enter species code, name, or abbreviation"
      />
      <button onClick={handleSearch}>Search</button>

      {result && result.success && (
        <div>
          <h3>{result.species.species}</h3>
          <p>Code: {result.species.code}</p>
          <p>Nepali: {result.species.species_nepali_unicode} ({result.species.name_nep})</p>
          <p>Confidence: {result.confidence * 100}%</p>
          <p>Match Type: {result.match_type}</p>
        </div>
      )}
    </div>
  );
}
```

---

## What to Test

### ✅ Test Cases to Try:

#### Numeric Codes:
- `1`, `18`, `5`, `9`, `14`

#### Abbreviated Codes:
- `sho`, `rob`, `aln`, `dal`, `pin`, `que`, `sch`
- `sho rob`, `aln nep`, `dal sis`, `pin rox`
- `sho/rob`, `sho-rob`, `sho_rob`

#### Scientific Names:
- `Shorea robusta`
- `Alnus nepalensis`
- `Dalbergia sissoo`

#### Nepali Unicode:
- `साल`, `उत्तिस`, `खयर`

#### Nepali Romanized:
- `Sal`, `Uttis`, `Khayar`

#### Common Names:
- `Khair`, `Utis`, `Sisau`

#### Invalid Inputs:
- `XYZ`, `999`, `ab` (should return no match)

---

## Expected Results Summary

| Input | Species | Confidence | Match Type |
|-------|---------|------------|------------|
| `18` | Shorea robusta | 100% | code |
| `sho` | Shorea robusta | 70% | abbreviated |
| `sho rob` | Shorea robusta | 80% | abbreviated |
| `Shorea robusta` | Shorea robusta | 100% | exact |
| `साल` | Shorea robusta | 100% | exact |
| `Sal` | Shorea robusta | 100% | exact |
| `aln` | Alnus nepalensis | 70% | abbreviated |
| `aln nep` | Alnus nepalensis | 80% | abbreviated |

---

## Troubleshooting

### Backend Not Starting
```bash
# Check if port 8001 is free
netstat -aon | findstr ":8001"

# If occupied, stop it
stop_all.bat

# Then start again
start_backend.bat
```

### 404 Not Found
Make sure backend is fully started. Look for:
```
Application startup complete.
```

### Import Error
```bash
# Make sure species.txt exists
dir D:\forest_management\species.txt

# If missing, check the file location
```

### CORS Error (from frontend)
If testing from a different origin, CORS should already be configured, but check:
```python
# In backend/app/main.py
allow_origins=settings.CORS_ORIGINS
```

---

## Next Steps After Testing

Once you've verified it works:

1. ✅ **Integrate with inventory upload** - Use species matcher during CSV validation
2. ✅ **Add to frontend forms** - Autocomplete for species selection
3. ✅ **Data cleaning** - Normalize existing inventory data
4. ✅ **API documentation** - Already available at /docs

---

**Quick Start Commands:**

```bash
# Test backend directly
venv\Scripts\python test_species_matcher.py

# Or test via API
start_backend.bat
# Then open http://localhost:8001/docs
```
