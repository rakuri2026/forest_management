# HTML Preview — Match DOCX Export

## Problem

The HTML preview and DOCX export are **completely separate rendering implementations** of the same document tree. They share the same data pipeline (variable resolution, table cache) but diverge in what each renders. The user sees one thing in preview, gets something different in DOCX.

## Root Cause

Two independent code paths evolved separately:

| | HTML Preview | DOCX Export |
|--|-------------|-------------|
| **Entry** | `_walk_tree_html()` at `op_docx_builder.py:3169` | `_walk_tree()` at `op_docx_builder.py:2708` |
| **Cover page** | CSS divs (approximate) | `_add_cover_page()` (proper Word layout) |
| **TOC** | Static link list | Word TOC field (auto-updates in Word) |
| **English subtitles** | Not rendered | Rendered under each heading |
| **Custom notes** | Not rendered | Added at end of document |
| **Fonts** | `Noto Sans` (CSS) | `Nirmala UI` (explicit Word font) |
| **Page layout** | CSS `max-width: 21cm` (browser-dependent) | A4 with 2.5cm margins (precise) |
| **Field inventory** | HTML table (ORM columns) | Two-column monospace section (raw SQL, 7pt Courier) |
| **Table captions** | Not rendered | Centered italic below table |
| **Charts (node-level)** | Extended set (15+ types) | Narrower set (10 types) |
| **Maps** | Fallback message for boundary | Full boundary map rendering |

## Proposed Approach: Single Source of Truth

**Make DOCX the authoritative renderer. Generate HTML from the same logic.**

Instead of maintaining two parallel tree-walkers, create a shared rendering layer that both HTML and DOCX consume.

### Architecture

```
Document Tree (JSONB)
        │
        ▼
  TreeWalker (shared)
   ├── resolve variables
   ├── build table cache
   └── for each node, call NodeRenderer
        │
        ├──→ DOCXNodeRenderer  → python-docx Document
        │
        └──→ HTMLNodeRenderer  → HTML string
```

**Key insight:** Both renderers receive the same resolved node data. They differ only in output format (Word XML vs HTML tags).

### Implementation Plan

#### Phase 1: Extract shared node resolution (no behavior change)

Create `backend/app/services/operational_plan/tree_renderer.py` with:

```python
class ResolvedNode:
    """A node with all variables resolved, ready for rendering."""
    id: str
    title_ne: str
    title_en: str
    number: str | None
    level: int
    node_type: str
    content_type: str
    resolved_content: str          # {{var}} replaced with values
    chart_data: dict | None        # resolved chart payload
    table_data: dict | None        # resolved table payload
    map_data: dict | None          # resolved map payload
    static_table_data: dict | None # resolved static table
    children: list['ResolvedNode']
    page_break_before: bool
    hidden_in_export: bool
    deleted: bool

def resolve_tree(tree, raw_data, table_cache, calculation_id, db) -> list[ResolvedNode]:
    """Walk tree once, resolve all variables, return flat list of ResolvedNodes."""
```

This extracts the resolution logic that currently exists in both `_walk_tree` and `_walk_tree_html` into one place.

#### Phase 2: Rewrite HTML renderer to use ResolvedNode

Replace `_walk_tree_html()` with a renderer that consumes `ResolvedNode`:

```python
def render_tree_as_html(resolved_nodes: list[ResolvedNode], ...) -> str:
    """Render resolved nodes to HTML. Same features as DOCX."""
    for node in resolved_nodes:
        # Heading with English subtitle (like DOCX)
        # Table captions (like DOCX)
        # All chart types (like HTML currently has)
        # Field inventory section (like DOCX two-column layout)
        # Custom notes (like DOCX)
```

#### Phase 3: Rewrite DOCX renderer to use ResolvedNode

Refactor `_walk_tree()` to consume `ResolvedNode` instead of raw `TreeNode` + inline resolution.

#### Phase 4: Unify chart type support

Both renderers support the same chart types. The extended types currently in HTML (`forest_health_pie`, `aspect_rose`, household charts, budget charts) are added to the DOCX path.

### What Changes for the User

| Before | After |
|--------|-------|
| HTML preview shows different formatting than DOCX | HTML preview matches DOCX layout (headings, subtitles, tables, charts) |
| English subtitles missing in preview | English subtitles shown in preview |
| Table captions missing in preview | Table captions shown in preview |
| Custom notes missing in preview | Custom notes shown in preview |
| Some charts missing in DOCX | All charts available in both |
| Field inventory looks different | Field inventory layout matches (simplified for HTML but same structure) |

### Files to Modify

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/services/operational_plan/tree_renderer.py` | **New** — shared `ResolvedNode` + `resolve_tree()` |
| 2 | `backend/app/services/operational_plan/op_docx_builder.py` | Refactor `_walk_tree_html()` to use `ResolvedNode`; refactor `_walk_tree()` to use `ResolvedNode` |
| 3 | `backend/app/api/operational_plans.py` | Update preview endpoints to use new renderer |

### Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking existing DOCX output | Keep `_walk_tree()` as the DOCX path; only change its input from raw tree to ResolvedNode |
| HTML regression | Test both preview and export for every section type |
| Performance | ResolvedNode resolution is the same work, just consolidated — no overhead |
| Large document slow preview | Same as current — tree walk is O(N) |

### Testing Checklist

- [ ] Cover page renders correctly in both HTML and DOCX
- [ ] TOC links work in HTML preview
- [ ] All heading levels render with English subtitles
- [ ] Rich text with variables resolves correctly in both
- [ ] All table types render with captions
- [ ] All chart types render in both HTML and DOCX
- [ ] Maps render in both
- [ ] Static tables with merges render correctly
- [ ] Field inventory section renders in both
- [ ] Custom notes appear in both
- [ ] Page breaks work in HTML (CSS) and DOCX (Word)
