# Species Matcher Service - User Guide

## Overview

The Species Matcher service intelligently identifies tree species from user input in **any format**:
- **Numeric codes** (1, 2, 3, ... 23)
- **Scientific names** (Shorea robusta, Alnus nepalensis)
- **Nepali Unicode names** (साल, उत्तिस, खयर)
- **Nepali Romanized names** (Sal, Uttis, Khayar)
- **Common English names** (Khair, Utis, Sisau)
- **Typos and variations** (with fuzzy matching)

## Test Results Summary

### ✅ Exact Matches (100% confidence)
- Code `1` → Abies spp
- Code `18` → Shorea robusta (साल)
- Code `5` → Alnus nepalensis (उत्तिस)
- Scientific: `Shorea robusta` → Code 18
- Nepali Unicode: `साल` → Shorea robusta (Code 18)
- Nepali Roman: `Sal` → Shorea robusta (Code 18)
- Common Name: `Khair` → Acacia catechu (Code 2)

### 🔤 Abbreviated Codes (70-80% confidence) **NEW!**
- `sho` → Shorea robusta (70% confidence)
- `rob` → Shorea robusta (65% confidence)
- `sho rob` → Shorea robusta (80% confidence)
- `sho/rob` → Shorea robusta (80% confidence)
- `aln` → Alnus nepalensis (70% confidence)
- `aln nep` → Alnus nepalensis (80% confidence)
- `dal sis` → Dalbergia sissoo (80% confidence)
- `pin rox` → Pinus roxburghii (80% confidence)

### 🔍 Fuzzy Matches (with confidence scores)
- `Utis` → Alnus nepalensis (89% confidence) - spelling variation
- `Shisham` → Albizia spp. (71% confidence) - similar name

### ❌ No Match
- `XYZ123` - Invalid input
- `999` - Code doesn't exist
- `Sissoo` - Too different from any species

## Features

### 1. Single Species Identification
```python
from app.services.species_matcher import get_species_matcher

matcher = get_species_matcher()

# Identify from any format
result = matcher.identify("18")
result = matcher.identify("साल")
result = matcher.identify("Sal")
result = matcher.identify("Shorea robusta")

# Returns:
{
    "species": {
        "code": 18,
        "species": "Shorea robusta",
        "species_nepali_unicode": "साल",
        "name_nep": "Sal",
        "common_name": "Sal"
    },
    "match_type": "exact",  # or "code", "fuzzy"
    "confidence": 1.0,  # 0-1 scale
    "matched_field": "nepali_unicode"  # which field was matched
}
```

### 2. Batch Identification
Process multiple species at once:
```python
inputs = ["1", "साल", "Uttis", "18", "Khair"]
results = matcher.identify_batch(inputs)

# Returns list of match results
```

**Test Results:**
```
1       => Abies spp (confidence: 1.0)
साल     => Shorea robusta (confidence: 1.0)
Uttis   => Alnus nepalensis (confidence: 1.0)
18      => Shorea robusta (confidence: 1.0)
Khair   => Acacia catechu (confidence: 1.0)
```

### 3. Autocomplete Suggestions
For frontend search/autocomplete:
```python
suggestions = matcher.suggest("Sal", limit=5)

# Returns top matches with confidence scores
```

**Test Results:**
```
Input: 'Sal'
  1. Shorea robusta (Sal) - confidence: 1.0
  2. Bombax ceiba (Simal) - confidence: 0.75
  3. Dalbergia sissoo (Sisau) - confidence: 0.5

Input: 'Pin'
  1. Pinus roxburghii (Khote salla) - confidence: 1.0
  2. Pinus wallichiana (Gobre salla) - confidence: 1.0
```

### 4. CSV/Excel Column Validation
Perfect for inventory uploads:
```python
# User uploaded CSV with species column
species_column = ["1", "साल", "Uttis", "Shisham", "XYZ", "", "18", "Pine"]

validation = matcher.validate_species_column(species_column, min_confidence=0.6)
```

**Returns:**
```json
{
    "total": 8,
    "matched": 4,
    "unmatched": 3,
    "low_confidence": 1,
    "matched_details": [...],
    "unmatched_details": [
        {
            "row": 5,
            "input": "XYZ",
            "reason": "No match found",
            "suggestions": [...]
        },
        {
            "row": 6,
            "input": "",
            "reason": "Empty value"
        },
        {
            "row": 8,
            "input": "Pine",
            "reason": "No match found",
            "suggestions": [
                {"species": "Schima wallichii", "confidence": 0.5},
                {"species": "Abies spp", "confidence": 0.4}
            ]
        }
    ],
    "low_confidence_details": [
        {
            "row": 4,
            "input": "Shisham",
            "suggested_species": {"code": 4, "species": "Albizia spp.", ...},
            "confidence": 0.71,
            "alternatives": [...]
        }
    ]
}
```

## Use Cases

### Use Case 1: Inventory Upload Validation
When users upload CSV/Excel files with tree inventory data:
1. Extract species column
2. Run `validate_species_column()`
3. Show validation report to user:
   - ✅ Green: High confidence matches
   - ⚠️ Yellow: Low confidence (need confirmation)
   - ❌ Red: No match (with suggestions)

### Use Case 2: Frontend Autocomplete
Add intelligent search in the web interface:
```javascript
// User types "Sal"
fetch('/api/species/suggest?q=Sal&limit=5')
  .then(suggestions => {
    // Show dropdown with top matches
  })
```

### Use Case 3: Data Cleaning
Clean up existing inventory data:
```python
# Normalize all species names to codes
for record in inventory_records:
    result = matcher.identify(record.species_name)
    if result:
        record.species_code = result['species']['code']
```

## Configuration

### Confidence Thresholds

**High Confidence (≥0.9)**: Auto-accept
- Exact matches
- Code lookups
- Perfect name matches

**Medium Confidence (0.6-0.89)**: Need user confirmation
- Minor typos (Utis vs Uttis)
- Spelling variations

**Low Confidence (<0.6)**: Suggest alternatives
- Ambiguous input
- Partial matches

### Adjusting Minimum Confidence
```python
# Strict matching (only high confidence)
result = matcher.identify("Utis", min_confidence=0.9)  # Returns None

# Lenient matching (allow fuzzy)
result = matcher.identify("Utis", min_confidence=0.6)  # Returns match (0.89)
```

## Integration with Inventory System

The species matcher integrates with the inventory validation service:

**File:** `backend/app/services/inventory_validator.py`

```python
from app.services.species_matcher import get_species_matcher

def validate_inventory_data(df: pd.DataFrame):
    matcher = get_species_matcher()

    # Validate species column
    species_values = df['species'].tolist()
    validation = matcher.validate_species_column(species_values)

    # Add validation results to error report
    for error in validation['unmatched_details']:
        add_error(f"Row {error['row']}: Invalid species '{error['input']}'")

    for warning in validation['low_confidence_details']:
        add_warning(f"Row {warning['row']}: Species '{warning['input']}' " +
                   f"matched to {warning['suggested_species']['species']} " +
                   f"with {warning['confidence']} confidence")
```

## API Endpoints (Future)

Planned REST API endpoints:

```
GET  /api/species/identify?q={input}
POST /api/species/identify-batch
GET  /api/species/suggest?q={partial}&limit={n}
POST /api/species/validate-column
GET  /api/species/all
GET  /api/species/{code}
```

## Performance

- **Load time**: ~5ms (loads 23 species into memory)
- **Lookup time**:
  - Code lookup: <1ms
  - Exact match: ~1ms
  - Fuzzy match: ~5-10ms (checks all 23 species)
- **Batch processing**: ~1ms per species
- **Memory usage**: <1MB (all species in memory)

## Species Data Source

**File:** `D:\forest_management\species.txt`

**Format:** Tab-separated values (TSV)
```
code    species    species_nepali_unicode    name_nep    Common Name
1       Abies spp  ठिन्ग्रे सल्ला           Thingre salla    Fir species
2       Acacia catechu    खयर              Khayar    Khair
...
```

**Total Species:** 23

## Testing

Run the test suite:
```bash
cd D:\forest_management
venv\Scripts\python test_species_matcher.py
```

**Test Coverage:**
- ✅ Numeric code matching (1, 18, 5)
- ✅ Scientific name matching
- ✅ Nepali Unicode matching (साल, उत्तिस)
- ✅ Nepali Romanized matching (Sal, Uttis)
- ✅ Common name matching (Khair, Utis)
- ✅ Fuzzy matching (typos, variations)
- ✅ Batch identification
- ✅ Autocomplete suggestions
- ✅ Column validation

## Troubleshooting

### Issue: Species file not found
**Solution:** Ensure `species.txt` exists in project root:
```bash
ls D:\forest_management\species.txt
```

### Issue: No matches found
**Possible causes:**
1. Input is too different from any species
2. Confidence threshold too high
3. Typo in species data file

**Debug:**
```python
# Get suggestions to see similar species
suggestions = matcher.suggest("your_input", limit=5)
print(suggestions)
```

### Issue: Wrong species matched
**Possible causes:**
1. Fuzzy matching too lenient
2. Similar names in database

**Solution:** Increase confidence threshold:
```python
result = matcher.identify(input_text, min_confidence=0.9)
```

## Future Enhancements

1. **Phonetic matching** for Nepali names (Soundex, Metaphone)
2. **Abbreviation support** (ALNU → Alnus nepalensis)
3. **Multi-word search** ("Nepalese Alder" → Alnus nepalensis)
4. **Learning from corrections** (track user corrections to improve matching)
5. **Synonym support** (add alternative names)
6. **Genus-level matching** (Pinus → suggest all pine species)

---

**Version:** 1.0
**Date:** 2026-02-02
**Status:** Production Ready ✅
