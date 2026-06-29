# Template Management — Implementation Plan

## 1. Vision

**Super Admin** designs and manages OP templates using the full document tree editor.
**General User** browses available templates, selects one, fills metadata, and downloads the DOCX — no tree editing, no variable insertion, no content editing.

---

## 2. Current State Assessment

| Capability | Who Has Access | Notes |
|---|---|---|
| Document tree editing (add/delete/reorder sections) | All authenticated users | TreeSidebar + ContentPane |
| Variable insertion into content | All authenticated users | VariablePicker |
| Rich text content editing | All authenticated users | ContentPane textarea |
| Template creation (save plan as template) | All authenticated users | TemplateManager → `savePlanAsTemplate` |
| Template approval/review | SUPER_ADMIN only | ✅ Already gated |
| Template CRUD | Creator or SUPER_ADMIN | ✅ Already gated |
| System template management | SUPER_ADMIN only (via is_system flag) | Implicit — no dedicated UI |
| DOCX download | All authenticated users | ✅ Already works |
| Metadata form | All authenticated users | ✅ Already works |
| Preview | All authenticated users | ✅ PreviewDrawer exists |

**Key finding:** The approval pipeline already exists (private → submit → pending → review → approved/global) with SUPER_ADMIN gate. What's missing is:
- A dedicated super admin template designer UI (decoupled from plan editing)
- A simplified consumer interface for general users
- Template versioning
- Distinction between "editor workspace" and "template designer workspace"

---

## 3. Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Operational Plan Module                   │
├──────────────────────────┬──────────────────────────────────┤
│   SUPER_ADMIN View       │   General User View               │
│                          │                                   │
│  ┌──────────────────┐   │  ┌──────────────────────┐        │
│  │ Template Designer │   │  │ Template Browser      │        │
│  │  · TreeSidebar    │   │  │  · Card grid           │        │
│  │  · ContentPane    │   │  │  · Filter by tags      │        │
│  │  · VariablePicker │   │  │  · Preview thumbnail   │        │
│  │  · Version mgmt   │   │  │  · Select & confirm    │        │
│  │  · Publish/retire │   │  └──────────┬──────────────┘        │
│  └────────┬──────────┘   │             │                       │
│           │              │             ▼                       │
│           ▼              │  ┌──────────────────────┐        │
│  ┌──────────────────┐   │  │ Metadata Form (only)  │        │
│  │ Preview + Export │   │  │ → Download DOCX       │        │
│  └──────────────────┘   │  └──────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Database Changes

### 4.1 `op_templates` — Add Versioning Columns

| Column | Type | Purpose |
|--------|------|---------|
| `version` | INTEGER, default=1 | Monotonically increasing per template |
| `is_active` | BOOLEAN, default=true | If false, hidden from general users |
| `template_category` | VARCHAR(50), nullable | e.g. "normal_forest", "leasehold", "religious_forest" |
| `preview_image_url` | TEXT, nullable | Screenshot/thumbnail of generated DOCX for gallery |
| `changelog` | TEXT, nullable | Summary of what changed in this version |
| `source_template_id` | UUID FK→op_templates, nullable | When cloned, references original template |

### 4.2 `op_template_versions` — Optional Full Version History (Future)

```sql
CREATE TABLE public.op_template_versions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID REFERENCES public.op_templates(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    tree        JSONB NOT NULL,
    changelog   TEXT,
    created_by  UUID REFERENCES public.users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

This is optional for v1 — version metadata columns on the main table suffice initially. The full history table can be added later when rollback is needed.

---

## 5. API Changes

### 5.1 New Endpoints

| Method | Endpoint | Purpose | Auth |
|--------|----------|---------|------|
| GET | `/api/operational-plans/templates/public-browser` | List active/good templates for general user gallery | Any |
| GET | `/api/operational-plans/templates/{id}/preview-html` | Return resolved HTML preview (variables filled with sample data) | Any |
| POST | `/api/operational-plans/templates/{id}/clone` | Clone a template (for super admin to base new design on existing). Sets `source_template_id`, nulls `source_calculation_id`, version=1 | SUPER_ADMIN |
| POST | `/api/operational-plans/template-categories` | Create a new template category label | SUPER_ADMIN |
| GET | `/api/operational-plans/template-categories` | List all template categories | Any |
| DELETE | `/api/operational-plans/template-categories/{id}` | Delete a template category | SUPER_ADMIN |
| PUT | `/api/operational-plans/templates/{id}/publish` | Toggle `is_active`, set `version` | SUPER_ADMIN |
| GET | `/api/operational-plans/templates/designer` | List templates with full tree for super admin designer | SUPER_ADMIN |

### 5.2 Modified Endpoints

| Endpoint | Change |
|----------|--------|
| `POST /api/operational-plans` | Add `bypass_template_prompt` flag — if true and user is not SUPER_ADMIN, auto-select system default without showing template picker. Or better: **remove `template_id` from consumer flow entirely** — general users pick from browser, which then calls create with template_id. |
| `GET /api/operational-plans/templates` | Add `is_active` filtering for consumer-facing list |
| `POST /api/operational-plans/{plan_id}/save-as-template` | Bump `version` on existing template if name matches, or create new |

### 5.3 Removed Endpoints

| Endpoint | Reason |
|----------|--------|
| ~~`POST /{plan_id}/reset-tree`~~ | Already removed |

---

## 6. Frontend Changes

### 6.1 New Page: `TemplateGalleryPage.tsx`

A standalone page (route: `/ops/templates`) for general users.

**Layout:**
- Header: "Choose a Template for Your Operational Plan"
- Search/filter bar: by name, category tag, forest type
- Card grid showing available templates:
  - Template name, description, category badge
  - Thumbnail/preview image (generated server-side as PNG/JPEG)
  - Tags: forest type, region suitability
  - "Use This Template" button
- Clicking "Use This Template":
  - Creates a new plan from that template
  - Redirects to a simplified page: metadata only → export

**Data source:** `GET /api/operational-plans/templates/public-browser` (returns only `is_active=true, visibility=global, approval_status=approved`)

**States:**
- Loading: skeleton cards
- Empty: "No templates available yet. Contact your system administrator."
- Error: retry button + message

### 6.2 New Page: `TemplateConsumerPage.tsx`

A simplified page (route: `/ops/plan/:calculationId`) for general users after they select a template.

**Layout:**
- Top bar: forest name, status tag, template name
- No TreeSidebar (no document structure editing)
- No ContentPane (no content editing)
- No VariablePicker (no variable insertion)
- Left sidebar: read-only document outline (collapsible, non-editable)
- Main area: read-only content preview (rendered HTML with resolved variables)
- Action buttons: **Metadata** (fill forest name, location, dates), **Preview** (full document), **Download DOCX**
- No Save button needed (variables auto-resolve on export)

**Tab behavior:**
- **Document Editor** — the read-only preview of the document tree with resolved variables. This is the main view.
- **Tables 1-32** — fully editable. These are data-entry forms (not template editing). General users still need to enter forest inventory data.
- **Charts** — view-only. Chart data comes from the calculation; charts are rendered for preview. No chart configuration editing.
- **Maps** — view-only. Same as charts — maps display from calculation data.

**DocumentOutline data source:** The tree comes from the plan object loaded in state (same as `GET /{plan_id}` response). No separate fetch needed.

### 6.3 New Page: `TemplateDesignerPage.tsx`

A dedicated page (route: `/ops/templates/designer/:templateId`) for SUPER_ADMIN only.

**Route:** `/ops/templates/designer/:templateId` — if `templateId` is `new`, first `POST /api/operational-plans/templates` to create an empty template, then redirect to the designer with the new ID.

**Layout:** Reuses the current `OperationalPlanPage` layout but:
- Title: "Template Designer" instead of "Operational Plan Editor"
- TreeSidebar: full editing (add/delete/reorder sections). No chart/map node add buttons (charts and maps need live calculation data — not available in template designer). Admin can only add richtext and static_table node types.
- ContentPane: full richtext editing with VariablePicker. Chart/Map content types are not available.
- Additional toolbar buttons:
  - **Save Version** — saves tree with version bump + changelog prompt
  - **Publish / Unpublish** — toggle `is_active`
  - **Preview as Consumer** — opens the consumer view with a real calculation (admin picks one) to verify template renders correctly
  - **Set as System Default** — toggle `is_default`
- No "Export DOCX" (templates are structure, not data-filled documents)
- No "Auto-Populate" (no calculation context in template designer)

### 6.4 Modified: `OperationalPlanPage.tsx`

- Gate the full editor behind `currentUser.role === SUPER_ADMIN` (or equivalent check from token)
- **Grace period for existing in-progress plans:** Before redirecting non-admin users, check if the plan has existing tree content with user-authored changes (non-empty content beyond template defaults). If yes, allow **one final edit session** with a banner: *"This is your last chance to edit. After saving, the editor will be locked."* On next load, redirect to consumer view.
- For non-super-admin users without existing content: redirect to `TemplateConsumerPage.tsx`
- Remove the `Templates` button from the toolbar (replaced by consumer browser page)
- Remove `handleLoadTemplate` (templates are selected before plan creation, not during editing)

### 6.5 Modified: `TemplateManager.tsx`

- Keep as super admin tool only
- Remove "Use Template" action (super admins use TemplateDesignerPage)
- Add "Edit in Designer" action → navigates to TemplateDesignerPage
- Add "Publish/Unpublish" action
- Add "Clone" action

### 6.6 Removed Components (from consumer view)

| Component | Removed? | Notes |
|-----------|----------|-------|
| TreeSidebar | Read-only outline in consumer view | Editing removed |
| ContentPane | Yes (consumer) | Read-only preview instead |
| VariablePicker | Yes (consumer) | Not needed |
| TemplateManager | Yes (consumer) | Templates chosen before plan creation |

---

## 7. User Flows

### 7.1 Super Admin — Create/Edit Template

```
1. Navigate to /ops/templates/designer (or /ops/templates/manager)
2. Click "New Template" or "Edit" on existing
3. Build document tree using TreeSidebar (add sections, subsections, charts, maps, tables)
4. Edit content with {{variable}} placeholders via VariablePicker
5. Click "Save Version" → prompt for changelog → version auto-increments
6. Click "Publish" → template becomes available to general users
7. Click "Set as Default" → this template auto-selected for new plans
```

### 7.2 General User — Download OP

```
1. Navigate to /ops (or click "OP Report" in main nav)
2. See Template Gallery with cards/tiles
3. Filter by forest type or search by name
4. Click "Use This Template" on desired one
5. System creates a new plan from that template, redirect to consumer page
6. Fill Metadata (forest name, district, dates, etc.)
7. Click "Preview" to see the full rendered document
8. Click "Download DOCX" → document exports with resolved variables
```

### 7.3 General User — Plan Already Exists (Edge Case)

```
1. User returns to an existing plan (/ops/plan/:calcId)
2. System checks: does this user have a draft plan for this calculation?
3. If yes → show consumer page with that plan's tree (read-only)
4. User can re-fill metadata and re-download
5. If the plan's template was updated by admin → show badge: "New template version available"
   → "Upgrade to Latest Template" button (creates fresh plan from latest template)
```

---

## 8. Template Versioning Strategy

### Version Bump Rules

| Scenario | Action |
|----------|--------|
| Super admin edits tree of published template | Prompt for changelog → bump `version` |
| Super admin edits tree of unpublished/draft template | No version bump (still in design phase) |
| Super admin clicks "Publish" | If version already exists, bump; else set version=1 |
| General user saves current plan as template | Creates new `OPTemplate` row (not a version of existing) |
| Super admin clones template | New row, version=1, `source_template_id` references original |

### Consumer-Facing Display

- Show template version in the gallery card: "v2.1"
- Show "Updated: June 2026" date
- If user had a plan from v1 and v2 is now published → badge: "Updated version available"

---

## 9. Implementation Phases

### Phase 1: Role Gating + Cleanup (2-3 days)

- Gate `OperationalPlanPage` behind role check — non-admin users get redirected to a simplified view
- Implement grace period: existing plans with user-authored content get one final edit session
- Remove "Reset to Default" ✅ already done
- Remove `Templates` button from consumer toolbar
- Remove `TreeSidebar`, `ContentPane`, `VariablePicker` from consumer view
- Add read-only document outline for consumers (`DocumentOutline.tsx`)
- Backend: add `has_custom_content` check helper

### Phase 2: Template Gallery (2-3 days)

- Build `TemplateGalleryPage.tsx` with card grid
- Backend: `GET /templates/public-browser` endpoint
- Frontend: Client-side preview capture using html2canvas on template skeleton (approximate — not exact DOCX fidelity). Add note to UI: *"Preview is approximate."*
- Frontend: search/filter by name, tags, and controlled category
- Frontend: "Use This Template" → create plan → redirect to consumer page

### Phase 3: Template Designer (3-4 days)

- Build `TemplateDesignerPage.tsx` reusing TreeSidebar + ContentPane + VariablePicker
- Chart/map node types excluded from designer (no calculation context)
- Add version management UI (save version, changelog prompt)
- Add publish/unpublish toggle
- Add "Set as System Default" toggle
- Add "Preview as Consumer" button (admin picks a calculation ID to test with)
- Handle `:templateId` = `new` → create empty template then redirect
- Backend: `PUT /templates/{id}/publish` endpoint
- Backend: version auto-increment logic
- Backend: template clone endpoint (nulls `source_calculation_id`, sets `source_template_id`, version=1)

### Phase 4: Template Versioning (2-3 days)

- Alembic migration: add version columns to `op_templates`
- Build `op_template_versions` table (optional for v1 — can defer)
- Backend: version bump on save (only if template is published)
- Frontend: display version badge in gallery and consumer page
- "New version available" badge with upgrade flow (metadata carry-over on upgrade)

### Phase 5: Template Categories (1 day)

- Add `template_categories` table: `id, name (VARCHAR 100), created_at`
- Backend CRUD: `POST/GET/DELETE /api/operational-plans/template-categories`
- Frontend: category management UI in Template Designer (simple add/remove list)
- Frontend: category filter dropdown in Template Gallery

### Phase 6: Polish & Verification (2-3 days)

- Loading/empty/error states for all new pages
- Permission error handling (non-admin accessing designer page)
- Audit logging: use existing `plan_metadata.updated_at` patterns + add `version` + `changelog` to template history. No separate audit table needed for v1.
- Verification checklist (see section 14)
- Test with real data (Babarmahal CF, etc.)

---

## 10. Migration Strategy

### Data Migration

1. Existing system default template (`is_system=True, is_default=True`) remains as-is
2. Existing user-created templates with `approval_status=approved` and `visibility=global` get `is_active=True`
3. All other user-created templates get `is_active=False` (not shown in consumer gallery)
4. All templates get `version=1` initially

### User Transition

1. Existing plans remain editable by their owners in the current way until Phase 1 is deployed
2. After Phase 1: existing plan owners see the read-only consumer view for existing plans
3. Users with in-progress plans can still download (export uses their saved tree)
4. New plans must use the Template Gallery flow

---

## 11. Edge Cases

### 11.1 What if a general user needs to customize the document?

- **Answer:** They can't. The whole point is separation of concerns. If they need customization, they request it from super admin, who updates the template.
- **Alternatively (future):** Allow "custom notes" field at metadata level — a single rich text field appended to the document for site-specific remarks.

### 11.2 What if a template is updated while a user has an in-progress plan?

- The user's plan retains the tree from the template version it was created with
- Badge: "New template version available (v2). Click to upgrade."
- Upgrade = create a new plan from latest template (old plan remains as draft)
- No auto-migration — the user explicitly chooses to upgrade

### 11.3 What about Table 1-32 data entry?

- Tables 1-32 are data entry, not template editing. Both roles need access.
- Keep `activeTab` with Tables/Charts/Maps for all users.

### 11.4 Can a super admin preview the DOCX from the template designer?

- Template designer has no calculation context, so no live data. Add **"Preview as Consumer"** button that opens a picker to select a real calculation, then opens the consumer page with the template applied to that calculation's data. This allows the admin to verify charts, maps, and variable resolution before publishing.
- Long-term: add a "Test with sample data" mode that uses mock data for layout verification.

### 11.5 What about the approval workflow (user submits template for approval)?

- Preserve it. A user can still design a template (using the current plan → save-as-template flow) and submit for super admin approval. Once approved, super admin can then publish it.
- This is the **bottom-up template suggestion** pathway.

---

## 12. File Change Summary

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/pages/TemplateGalleryPage.tsx` | General user template browser |
| `frontend/src/pages/TemplateConsumerPage.tsx` | Simplified read-only plan view |
| `frontend/src/pages/TemplateDesignerPage.tsx` | Super admin template editor |
| `frontend/src/components/OperationalPlan/TemplateCard.tsx` | Reusable card for gallery |
| `frontend/src/components/OperationalPlan/DocumentOutline.tsx` | Read-only tree outline |
| `frontend/src/components/OperationalPlan/DocumentPreview.tsx` | Full-page document preview |

### New Files

| File | Purpose |
|------|---------|
| `backend/app/models/template_category.py` | TemplateCategory model |
| `backend/app/api/template_categories.py` | Category CRUD endpoints |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src/pages/OperationalPlanPage.tsx` | Role gate + grace period, remove template editing for non-admin |
| `frontend/src/components/OperationalPlan/TemplateManager.tsx` | Add designer link, publish, clone actions |
| `backend/app/models/op_template.py` | Add version, is_active, category, preview_image, changelog, source_template_id columns |
| `backend/app/models/__init__.py` | Register TemplateCategory |
| `backend/app/api/operational_plans.py` | New endpoints + modified existing |
| `backend/app/schemas/operational_plan.py` | New schemas for versioning, publish, clone |
| `frontend/src/services/api.ts` | New API methods |
| `frontend/src/App.tsx` (or router) | New routes |

### Deleted/Archived (from consumer view)

| Item | Replacement |
|------|-------------|
| TreeSidebar editing | DocumentOutline (read-only) |
| ContentPane + VariablePicker | DocumentPreview (read-only) |
| Reset to Default button | Already removed |

---

## 13. Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Template preview images — server or client? | **Client-side** (html2canvas). Simpler, no infra, good enough. **Note:** preview is approximate — client-side DOM capture won't reflect DOCX page breaks, headers/footers, or pagination. Communicated to users via label: *"Preview is approximate."* |
| 2 | Allow "custom notes" for general users? | **Yes** — a single rich-text field appended at end of document, for site-specific remarks. |
| 3 | Template categories — controlled vocabulary or freeform? | **Both** — existing freeform tags remain for searching. Add a controlled `template_category` managed via DB table with CRUD API (super admin can add/remove values). |
| 4 | Mobile responsiveness needed? | **No.** Desktop only. Field staff do not use tablets. |

---

## 14. Verification Checklist

Run through this checklist after each phase before marking it complete.

### Phase 1 — Role Gating
- [ ] Non-admin user accessing `/ops/plan/:calcId` sees consumer view (no TreeSidebar, no ContentPane, no VariablePicker)
- [ ] Non-admin user with existing plan content sees grace period banner and can edit one last time
- [ ] After grace period save, on next load user sees consumer view
- [ ] SUPER_ADMIN accessing same URL sees full editor with all toolbar buttons
- [ ] "Reset to Default" button does not appear for any role

### Phase 2 — Template Gallery
- [ ] Template gallery loads with card grid showing only `is_active=True, visibility=global, approval_status=approved` templates
- [ ] Empty state displays when no templates available
- [ ] Error state shows retry button on network failure
- [ ] Search/filter by name works
- [ ] Filter by controlled category works
- [ ] "Use This Template" creates a new plan and redirects to consumer page
- [ ] Preview thumbnail renders using html2canvas (approximate)

### Phase 3 — Template Designer
- [ ] SUPER_ADMIN can access `/ops/templates/designer/:id` 
- [ ] Non-admin gets 403 or redirect
- [ ] TreeSidebar shows only richtext and static_table node types (no chart/map add buttons)
- [ ] ContentPane works with VariablePicker for richtext nodes
- [ ] "Save Version" prompts for changelog and bumps version
- [ ] "Publish/Unpublish" toggles `is_active`
- [ ] "Set as System Default" toggles `is_default`
- [ ] "Preview as Consumer" lets admin pick a calculation and see consumer view
- [ ] Creating a new template (`:templateId = new`) creates empty template and redirects
- [ ] Clone endpoint creates a copy with `source_template_id` set, `source_calculation_id` null

### Phase 4 — Template Versioning
- [ ] Version badge displayed in gallery cards
- [ ] Version badge displayed on consumer page header
- [ ] When template is updated, existing plan shows "New version available" badge
- [ ] Clicking upgrade creates new plan with metadata carried over (forest_name, location, dates)
- [ ] Table 1-32 data preserved per-calculation after upgrade

### Phase 5 — Template Categories
- [ ] SUPER_ADMIN can add/remove categories via API
- [ ] Category filter dropdown appears in Template Gallery
- [ ] Category filter correctly scopes results

### Phase 6 — Full Integration
- [ ] Complete end-to-end flow: super admin creates template → publishes → general user sees in gallery → picks it → fills metadata → downloads DOCX
- [ ] Bottom-up flow: user saves plan as template → submits for approval → super admin approves → publishes → appears in gallery
- [ ] All loading/empty/error states render correctly
- [ ] Permission errors show meaningful messages (not raw 403 pages)
- [ ] Real-data test with Babarmahal CF produces correct DOCX
