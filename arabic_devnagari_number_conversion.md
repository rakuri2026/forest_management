# Arabic ↔ Devanagari Number Conversion + Configurable Precision

## Goal

1. **Input**: User-uploaded Devanagari digits (`१२३`) are silently normalized to Arabic (`123`) in the database.
2. **Output**: Numbers in DOCX/HTML reports render as Devanagari digits (`१२५.३४`) with per-variable configurable decimal precision.
3. **Scope**: Report generation only (DOCX + HTML preview). No frontend UI changes.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Conversion layer | Output-only for render, input-only for normalize | DB stays Arabic — math, sorting, aggregation work natively |
| Precision control | Per-variable in registry | `carbon: 0.0032` vs `area: 125.34` need different decimals |
| Trailing zero strip | Always strip | `125.00` → `१२५` (clean for village users) |
| Language-aware | Only convert when language=NP | English docs keep Arabic numerals |
| Mixed input handling | Auto-normalize silently | No friction for users |
| Non-numeric passthrough | Return as-is on error | IDs, codes, names unaffected |

---

## Phase 1: Input Normalization + Formatting Utility

**File:** `backend/app/utils/number_format.py` (new)

```python
DEV_TO_ARABIC = str.maketrans("०१२३४५६७८९", "0123456789")
ARABIC_TO_DEV = str.maketrans("0123456789", "०१२३४५६७८९")

def normalize_nepali_digits(value) -> str
    """Convert Devanagari digits → Arabic. Used during upload/import."""
    # "१२३.४५" → "123.45"

def format_devanagari(value, precision=2) -> str
    """Round to precision → strip trailing zeros → Devanagari digits."""
    # 125.00 → "१२५"
    # 0.0032 → "०.००३२"
    # None → "-"
```

---

## Phase 2: Variable Registry — Add `precision` Field

**File:** `backend/app/services/operational_plan/variable_registry.py`

### Add to `VariableDef`
```python
precision: int = 2
```

### Update `_reg()` signature
```python
def _reg(..., precision=2):
```

### Update every `_reg()` call for number variables

| Category | Examples | Precision |
|----------|----------|-----------|
| Areas | `total_area_hectares`, `effective_area_hectares` | 2 |
| Volumes | `inventory_volume_m3`, `fi_growing_stock_m3_per_ha` | 2 |
| Counts | `total_blocks`, `hh_total_households`, `fi_total_plots` | 0 |
| Percentages | `forest_pct`, `fi_mai_percent` | 1 |
| Carbon | `fi_carbon_stock_tc_per_ha`, `total_carbon_stock_tc` | 3 |
| Wood density | `fi_weighted_wood_density` | 4 |
| Budget | `activities_total_budget` | 0 |
| Elevation | `elevation_mean_m`, `altitude_min_m` | 0 |
| Temperature | `temperature_mean_c` | 1 |
| Precipitation | `precipitation_mean_mm` | 1 |
| Rates per ha | `fi_regeneration_per_ha`, `fi_tree_per_ha` | 2 |
| Dimensions | `sampling_plot_radius_m` | 2 |
| Years | `op_preparation_year`, `plan_year_start` | 0 |
| Totals | `total_plan_area_ha`, `annual_increment_m3` | 2 |
| Carbon total | `total_co2_tco2` | 2 |
| Units | `inventory_net_volume_cft`, `hh_firewood_demand_bhari` | 0 |

---

## Phase 3: OP DOCX Builder — Apply Formatting

**File:** `backend/app/services/operational_plan/op_docx_builder.py`

### Add helper
```python
def _fmt_value(value, var_name, raw_data):
    """Look up precision from registry, convert to Devanagari."""
    var_def = get_variable(var_name)
    precision = var_def.precision if var_def else 2
    return format_devanagari(value, precision)
```

### Apply at 4 points:

| Location | Line | What changes |
|----------|------|--------------|
| `_add_text_content()` | ~329 | `run.text = _fmt_value(var_val, var_name, raw_data)` |
| `_add_list_table()` | ~292 | Cell values: `_fmt_value(row.get(h, ""), ...)` |
| `_add_table_inline()` | ~357 | Cell values: `str(r.get(h, ""))` → `format_devanagari(val, 2)` |
| `_render_list_value_as_text()` | ~255 | Dict/string values containing numbers |

### How to detect numeric cells vs text headers
- Check if the **header name** contains "number", "count", "ha", "m3", "pct", "%", "rs", "cft", "bhari", "tC", "tCO2" — or simply try `float()` conversion and format only numeric values.
- Headers stay as-is (no digit conversion).

---

## Phase 4: OP HTML Preview — Apply Formatting

**File:** `backend/app/services/operational_plan/op_docx_builder.py`

### Apply at 2 points:

| Location | Line | What changes |
|----------|--------------|--------------|
| `_render_html_list_vars()` | ~882-888 | Cell values in auto-generated HTML tables |
| `_add_table_html()` | ~859 | `<td>` cell values |

Same `_fmt_value()` helper, same numeric detection approach.

---

## Phase 5: AI Report Path — Apply Formatting

**File:** `backend/app/services/report/document_builder.py`

### Apply at 2 points:

| Location | What changes |
|----------|--------------|
| `add_text_content()` | Convert numbers in paragraph text |
| `add_table_from_dict()` | Convert numeric cells |

No variable registry available in this path, so use a single `language` parameter (default precision=2) — or pass a `var_precisions` dict from the caller.

---

## Phase 6: Chart Labels

**File:** `backend/app/services/report/chart_generator.py`

Convert matplotlib numeric labels (tick labels, pie percentages, bar values) using `format_devanagari()` when document language is Nepali.

---

## Phase 7: Upload Pipeline — Silent Normalization

Call `normalize_nepali_digits()` in upload/data-entry paths:

| Endpoint / File | Description |
|-----------------|-------------|
| Field inventory upload | `api/field_inventory/...` |
| Species bulk import | `api/species/...` |
| Household data import | `api/household/...` |
| User group data import | `api/user_group/...` |
| Activities import | `api/activities/...` |
| Any CSV/Excel upload endpoint | Generic catch-all |

Apply at the **parser/validator layer**, not the DB layer, so all downstream code sees clean Arabic digits.

---

## Files Changed Summary

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/utils/number_format.py` | **New** — core utility |
| 2 | `backend/app/services/operational_plan/variable_registry.py` | Add `precision` field + update all `_reg()` calls (~80 number vars) |
| 3 | `backend/app/services/operational_plan/op_docx_builder.py` | Apply `_fmt_value` in 4 DOCX + 2 HTML locations |
| 4 | `backend/app/services/report/document_builder.py` | Apply formatting in AI report path |
| 5 | `backend/app/services/report/chart_generator.py` | Convert chart labels |
| 6 | Upload/import endpoints (6+ files) | Add `normalize_nepali_digits()` call |

---

## Edge Cases & Risks

| Case | Handling |
|------|----------|
| Mixed input `१2३` | Auto-normalized to `123` — no error |
| Non-numeric value in number field | `format_devanagari` catches `TypeError`, returns as-is |
| Table cell with text + number mixed | Only convert if entire cell passes `float()` test |
| Chart labels: `0.5` → `०.५` | Allowed — village users understand decimals |
| Empty/null values | Return `"-"` (dash) — matches existing convention |
| Very large numbers (e.g., 1000000) | Convert all digits: `१००००००` — comma grouping TBD separately |
