# HTML Preview ↔ DOCX Export — Alignment Plan

## Problem

HTML preview and DOCX export are **two independent rendering implementations** of the same document tree. The user sees one thing in preview, gets something different in DOCX. They should match.

## Root Cause Analysis

Both renderers share the same data pipeline (variable resolution, table cache) but diverge at the rendering layer:

| Feature | DOCX (`_walk_tree`) | HTML (`_walk_tree_html`) | Gap |
|---------|---------------------|--------------------------|-----|
| **English subtitles** | Rendered under each heading | Not rendered | HTML missing |
| **Table captions** | Centered italic below table | Not rendered | HTML missing |
| **Custom notes** | Added at end of document | Not rendered | HTML missing |
| **Cover page** | `_add_cover_page()` — proper layout | Inline CSS divs in endpoint | Approximate |
| **TOC** | Word TOC field | `_build_toc_html()` — link list | Different format (expected) |
| **Fonts** | `Nirmala UI` explicit | `Noto Sans` CSS | Different (acceptable for web) |
| **Field inventory** | Two-column monospace Courier 7pt | HTML `<table>` with ORM data | Structurally different |
| **Charts (node-level)** | `_add_chart()` — 10 types | `_render_chart_html()` — 15+ types | HTML has more |
| **Maps** | `_add_map()` — boundary fallback | `_render_map_html()` — no boundary fallback | DOCX more robust |
| **Variable resolution** | `_fix()` first, then split/resolve | `_html_escape()` first, then regex | Different approach |
| **Line splitting** | Splits on `\n`, one paragraph per line | Single HTML blob | Different |
| **Page breaks** | `doc.add_page_break()` | CSS `page-break-before: always` | Different (expected) |

## Strategy: Enhance HTML to Match DOCX

Rather than rewriting both renderers from scratch (high risk), enhance the existing HTML renderer to include the features DOCX has that HTML lacks. This is the safest approach — DOCX is the authoritative output, HTML becomes a faithful preview.

### What to Add to HTML (from DOCX)

| # | Feature | DOCX source | HTML target | Effort |
|---|---------|-------------|-------------|--------|
| 1 | English subtitles under headings | `_add_heading()` line ~1580 | `_walk_tree_html()` heading section | Small |
| 2 | Table captions (centered italic) | `_add_table()` line ~2395 | `_add_table_html()` | Small |
| 3 | Custom notes at end | `build_op_document()` line ~3855 | `_walk_tree_html()` or endpoint | Small |
| 4 | Node-level chart type parity | `_add_chart()` line ~2239 | `_render_chart_html()` line ~2906 | Medium |
| 5 | Field inventory structural match | `_add_field_inventory_tables()` | `_render_fieldinventory_html()` | Medium |
| 6 | Variable resolution order | `_fix()` before resolve | Currently `_html_escape()` before resolve | Small |

### What to Keep As-Is (Different by Design)

| Feature | Reason |
|---------|--------|
| Cover page CSS | HTML cover is inherently different from Word — CSS approximation is fine |
| TOC format | HTML links vs Word field — different by nature |
| Font family | Web fonts vs Word fonts — acceptable difference |
| Page break mechanism | CSS vs Word API — different by nature |
| Map rendering | Both call same `generate_standard_map()` — output format differs |

---

## Detailed Changes

### Change 1: Add English Subtitles to HTML Headings

**File:** `op_docx_builder.py` — `_walk_tree_html()` (line ~3195)

**Current code:**
```python
parts.append(f'<{tag}>{num}{node.title_ne}</{tag}>')
```

**New code:**
```python
parts.append(f'<{tag}>{num}{node.title_ne}</{tag}>')
if node.title_en and node.title_en != node.title_ne:
    parts.append(f'<p style="color:#666;font-style:italic;font-size:0.85em;margin:0 0 8px;">{num}{_html_escape(node.title_en)}</p>')
```

**DOCX reference:** `_add_heading()` at line ~1580 renders English subtitle as gray italic paragraph when `title_en != title_ne`.

---

### Change 2: Add Table Captions to HTML Tables

**File:** `op_docx_builder.py` — `_add_table_html()` (line ~3271)

**Current code:** No caption after table.

**New code:** Add after `</table></div>`:
```python
if node and node.title_ne:
    parts.append(f'<p style="text-align:center;font-style:italic;font-size:9pt;color:#666;margin:4px 0 12px;">{_html_escape(node.title_ne)}</p>')
```

**Note:** `_add_table_html` currently doesn't receive `node`. Need to pass it or extract `title_ne` from the caller.

**DOCX reference:** `_add_table()` at line ~2395 adds centered italic caption paragraph.

---

### Change 3: Add Custom Notes to HTML Preview

**File:** `operational_plans.py` — `preview_operational_plan()` (line ~979)

**Current code:**
```python
{body_html}
</body></html>
```

**New code:**
```python
{body_html}
{_render_custom_notes_html(metadata)}
</body></html>
```

**New helper function:**
```python
def _render_custom_notes_html(metadata: dict) -> str:
    custom_notes = metadata.get("custom_notes")
    if not custom_notes:
        return ""
    parts = ['<div style="page-break-before:always;margin-top:24px;">']
    parts.append('<h1>Custom Notes</h1>')
    for line in custom_notes.strip().split("\n"):
        parts.append(f'<p>{_html_escape(line.strip())}</p>')
    parts.append('</div>')
    return "\n".join(parts)
```

**DOCX reference:** `build_op_document()` at line ~3855 adds page break + heading + paragraphs.

---

### Change 4: Align Node-Level Chart Types

**File:** `op_docx_builder.py` — `_add_chart()` (line ~2239)

The DOCX `_add_chart()` handles fewer chart types than HTML `_render_chart_html()`. Add the missing types to DOCX:

| Missing in DOCX `_add_chart()` | Present in HTML `_render_chart_html()` |
|--------------------------------|----------------------------------------|
| `forest_health_pie` | ✅ |
| `aspect_rose` | ✅ |
| `nasa_forest_2020_pie` | ✅ |
| `soil_bar` | ✅ |
| `hh_prosperity_pie` | ✅ |
| `hh_caste_bar` / `hh_caste_pie` | ✅ |
| `hh_prosperity_bar` | ✅ |
| `hh_demand_supply_bar` | ✅ |
| `demand_supply_bar` | ✅ |
| `demand_supply_deficit_bar` | ✅ |
| `budget_bar` | ✅ |
| `ya_budget_year_bar` | ✅ |
| `ya_program_pie` | ✅ |
| `dbh_class_bar` / `dbh_class_count_bar` | ✅ |

**Approach:** Refactor `_add_chart()` to call the same chart generation functions that `_render_chart_html()` uses, then insert the result as an image. This eliminates the duplication.

**New `_add_chart()` structure:**
```python
def _add_chart(doc, node, raw_data, calculation_id=None):
    # 1. Check cache → if hit, insert image + caption + return
    # 2. Generate chart using shared dispatch (same as _render_chart_html)
    #    → call a shared _generate_chart(chart_type, raw_data, calculation_id, forest_name)
    # 3. Insert as image with caption
    # 4. Fallback: red italic error text
```

**Shared chart generation function:**
```python
def _generate_chart(chart_type, raw_data, calculation_id=None, forest_name=""):
    """Generate chart and return (img_data, chart_type) or (None, None).
    Shared by both DOCX and HTML renderers."""
    # Check cache
    if calculation_id:
        cached = _chart_cache_get(calculation_id, chart_type)
        if cached:
            return cached, chart_type
    # Dispatch to chart_generator functions
    # ... (same logic as current _render_chart_html lines 2924-3128)
    # Return img_data (data: URI or file path) or (None, None)
```

Then both `_add_chart()` (DOCX) and `_render_chart_html()` (HTML) call `_generate_chart()` and format the output differently.

---

### Change 5: Align Field Inventory Rendering

**File:** `op_docx_builder.py` — `_render_fieldinventory_html()` (line ~2805)

The HTML version uses ORM queries with proper column names. The DOCX version uses raw SQL with dash-separated monospace format. For preview purposes, the HTML table format is actually better (more readable). Keep the HTML format but ensure it shows the same data columns.

**Current DOCX columns:** `ब्लक | प्लट | प्रकार | वैज्ञानिक नाम | DBH | उचाइ | वर्ग | गणना`
**Current HTML columns:** `ब्लक | प्लट नं. | प्रकार | प्रजाति | DBH (से.मि.) | उचाइ (मि.) | वर्ग | गणना`

These are equivalent — just slightly different header labels. **No change needed** for the preview to be useful. The HTML format is more readable for web preview.

---

### Change 6: Fix Variable Resolution Order

**File:** `op_docx_builder.py` — `_walk_tree_html()` (line ~3207)

**Current problem:** HTML escapes content first (`_html_escape`), then does regex replacement. This means `{{variable}}` patterns are NOT escaped (they pass through `_html_escape` unchanged because they don't contain `<`, `>`, `&`, `"`). So this is actually fine — the regex works on both escaped and unescaped text.

**However**, the DOCX path calls `_fix()` (NFC normalize + Devanagari fixes + Arabic digit conversion) on the raw text first. The HTML path does NOT call `_fix()` on the content before processing.

**Fix:** Add `_fix()` call before HTML processing:
```python
if has_content:
    content = _fix(node.content)  # ← Add this
    escaped = _html_escape(content)
    # ... rest of regex processing
```

---

## Files to Modify

| # | File | Lines | Change |
|---|------|-------|--------|
| 1 | `op_docx_builder.py` | `_walk_tree_html()` ~3195 | Add English subtitle + `_fix()` call |
| 2 | `op_docx_builder.py` | `_add_table_html()` ~3243 | Add table caption (need `node` param) |
| 3 | `op_docx_builder.py` | `_add_table_html()` caller in `_walk_tree_html` | Pass `node` to `_add_table_html` |
| 4 | `op_docx_builder.py` | `_add_chart()` ~2239 | Refactor to use shared `_generate_chart()` |
| 5 | `op_docx_builder.py` | New function | Add `_generate_chart()` shared chart dispatcher |
| 6 | `op_docx_builder.py` | `_render_chart_html()` ~2906 | Refactor to use shared `_generate_chart()` |
| 7 | `operational_plans.py` | `preview_operational_plan()` ~979 | Add custom notes HTML section |
| 8 | `operational_plans.py` | New helper | Add `_render_custom_notes_html()` |

## What NOT to Change

| Item | Reason |
|------|--------|
| Cover page CSS | HTML cover is inherently different from Word layout — CSS approximation works |
| TOC format | HTML links vs Word field — different by nature |
| Font family | Web fonts vs Word fonts — acceptable |
| Page break mechanism | CSS vs Word API — different by nature |
| Field inventory format | HTML table is more readable for web preview |
| `_walk_tree()` (DOCX) | Keep as-is — only add shared chart generation |
| Map rendering | Both call same `generate_standard_map()` — output format differs by nature |

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking DOCX output | Only adding a shared helper function; DOCX path unchanged except calling it |
| Breaking HTML preview | Adding features incrementally; each is independently testable |
| Performance | `_generate_chart()` uses same cache — no overhead |
| Regression in existing features | Test both preview and export for every section type |

## Testing Checklist

- [ ] English subtitles appear under headings in HTML preview
- [ ] Table captions appear below tables in HTML preview
- [ ] Custom notes appear at end of HTML preview
- [ ] All chart types render in both HTML and DOCX
- [ ] Variable resolution produces same output in both
- [ ] DOCX export unchanged (regression test)
- [ ] HTML preview matches DOCX layout for each section type
