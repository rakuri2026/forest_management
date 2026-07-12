# Operational Plan — Global Template System

## Problem Statement

Currently, the super admin can edit the operational plan document (add text, variables, tables), but those edits are saved **per-calculation**. When a new user signs up and uploads their forest, they get the original hardcoded seed template — not the super admin's enriched version.

**Goal:** Super admin edits the document template once → all new users automatically get that latest version.

---

## Current Architecture

### What Already Works

| Component | Status | Location |
|-----------|--------|----------|
| `op_templates` table | ✅ Exists | `backend/app/models/op_template.py` |
| `is_system` + `is_default` flags | ✅ Exist | `op_templates` columns |
| Plan creation picks default template | ✅ Works | `operational_plans.py:166-172` |
| Fallback to seed data | ✅ Works | `operational_plans.py:172` |
| Template Manager modal | ✅ Exists | `TemplateManager.tsx` |
| Save as template | ✅ Works | `POST /{plan_id}/save-as-template` |
| Template versioning | ✅ Exists | `OPTemplateVersion` model |
| Template designer page | ✅ Exists | `TemplateDesignerPage.tsx` |

### What Blocks the Workflow

| # | Blocker | File:Line | Impact |
|---|---------|-----------|--------|
| 1 | System templates cannot be edited | `operational_plans.py:1762-1763` | Super admin must create a NEW template each time instead of updating the existing one |
| 2 | No one-click "save as global default" | — | Super admin must open Template Manager modal, fill form, check "System" + "Default" boxes |
| 3 | Old system templates accumulate | `save-as-template` always creates new row | Query `is_default=True AND is_system=True` may hit stale rows |
| 4 | No version history UI for system templates | `TemplateManager.tsx` | Can't see/rollback previous versions |

---

## Proposed Changes

### Change 1: Allow Super Admin to Edit System Templates

**File:** `backend/app/api/operational_plans.py` (line ~1762)

**Current code:**
```python
if tmpl.is_system:
    raise HTTPException(status_code=400, detail="Cannot edit system templates")
```

**New code:**
```python
if tmpl.is_system and current_user.role != UserRole.SUPER_ADMIN:
    raise HTTPException(status_code=403, detail="Only super admins can edit system templates")
```

**Behavior:**
- Super admin → can edit system templates
- Regular user → blocked with 403

**Version snapshot:** Before overwriting a system template's tree, auto-save the old version to `op_templates`:
```python
if tmpl.is_system and tmpl.tree and tmpl_data.tree is not None:
    old_version = tmpl.version or 1
    snapshot = OPTemplateVersion(
        template_id=tmpl.id,
        version=old_version,
        tree=tmpl.tree,
        name=tmpl.name,
        description=tmpl.description or "",
        changelog=tmpl_data.changelog or f"Auto-saved before update v{old_version}",
    )
    db.add(snapshot)
    tmpl.version = old_version + 1
```

---

### Change 2: Add "Update Global Template" Endpoint

**File:** `backend/app/api/operational_plans.py`

**New endpoint:**
```
PUT /api/operational-plans/{plan_id}/update-default-template
```

**Request body (optional):**
```json
{
  "changelog": "Added biodiversity section with variables"
}
```

**Logic:**
1. Fetch the plan's current `sections["tree"]`
2. Find existing `is_system=True AND is_default=True` template
3. If exists → snapshot old version, update tree + metadata, bump version
4. If not exists → create new template row with `is_system=True, is_default=True`
5. Deactivate any other `is_default=True` system templates (safety cleanup)
6. Return the updated template record

**Response:**
```json
{
  "id": "uuid",
  "name": "System Default Template",
  "version": 3,
  "is_system": true,
  "is_default": true,
  "updated_at": "2026-07-12T..."
}
```

**Access control:** `super_admin` only.

---

### Change 3: Quick-Save Button in Editor Toolbar

**File:** `frontend/src/pages/OperationalPlanPage.tsx`

**Add to toolbar** (next to existing "Templates" button, super admin only):
```tsx
{isSuperAdmin && (
  <Popconfirm
    title="Update the global template?"
    description="All new users will see this version when they create their operational plan."
    onConfirm={handleUpdateDefaultTemplate}
    okText="Update"
    cancelText="Cancel"
  >
    <Button icon={<GlobalOutlined />} size="small" type="default">
      Update Global Template
    </Button>
  </Popconfirm>
)}
```

**Handler:**
```typescript
const handleUpdateDefaultTemplate = async () => {
  try {
    await operationalPlanApi.updateDefaultTemplate(planId!, { changelog: '' });
    message.success('Global template updated. New users will see this version.');
  } catch (err: any) {
    message.error(err?.response?.data?.detail || 'Failed to update global template');
  }
};
```

---

### Change 4: Improve Template Manager for System Templates

**File:** `frontend/src/components/OperationalPlan/TemplateManager.tsx`

**Changes:**
1. On the system default template row, add "Update from Current Plan" button
2. Show version history panel (collapsible) with rollback buttons
3. Show "last updated" timestamp prominently

**New UI elements:**
```
┌─────────────────────────────────────────────────────┐
│ ⭐ System Default Template  v3  [Published]          │
│ Official template for all new users                  │
│ Updated: 2026-07-12                                   │
│                                                       │
│ [Update from Current Plan] [View History] [Preview]  │
│                                                       │
│ ▸ Version History                                    │
│   v3 — 2026-07-12 — "Added biodiversity section"   │
│   v2 — 2026-07-10 — "Updated species variables"    │
│   v1 — 2026-07-01 — Initial system template         │
└─────────────────────────────────────────────────────┘
```

**"Update from Current Plan" handler:**
- Calls `PUT /api/operational-plans/{plan_id}/update-default-template`
- Refreshes the template list
- Shows success toast

**"View History" panel:**
- Fetches versions from `GET /api/operational-plans/templates/{template_id}/versions`
- Each version shows: version number, date, changelog
- "Rollback" button on each version (except current) → calls `POST /api/operational-plans/templates/{template_id}/rollback` with target version

---

### Change 5: Add Version History & Rollback Endpoints

**File:** `backend/app/api/operational_plans.py`

**New endpoints** (under existing `/api/operational-plans/templates/` prefix):

```
GET /api/operational-plans/templates/{template_id}/versions
```
Returns all `OPTemplateVersion` records for the template, ordered by version DESC.

```
POST /api/operational-plans/templates/{template_id}/rollback
Body: { "version": 2 }
```
Copies the specified version's tree back into the main `OPTemplate.tree`, creates a new version snapshot of the current state, bumps version.

---

### Change 6: Fix Standalone Template Creation for System Templates

**File:** `backend/app/api/operational_plans.py` (line ~1723)

The standalone `POST /templates` endpoint (used by TemplateDesignerPage) currently hardcodes `is_system=False`:

```python
tmpl = OPTemplate(
    ...
    is_system=False,  # ← always forced False
    ...
)
```

**Fix:** Respect the `is_system` flag from the request, with super admin check:

```python
is_system = tmpl_data.is_system and current_user.role == UserRole.SUPER_ADMIN

tmpl = OPTemplate(
    ...
    is_system=is_system,
    ...
)
```

This ensures super admins have a consistent path to create system templates from both endpoints.

---

### Impact on User Templates (No Change)

**User templates are completely unaffected** by these changes. The system maintains two separate template namespaces:

| Namespace | `is_system` | Who creates | `is_default` scope | Used for new plans? |
|-----------|-------------|-------------|---------------------|---------------------|
| **System** | `True` | Super admin only | Global (one across all users) | ✅ Yes |
| **User** | `False` | Any user | Per-user (each user has own default) | ❌ No |

**User template flows preserved:**
- `POST /templates` → creates user template (`is_system=False`)
- `POST /{plan_id}/save-as-template` with `is_system=False` → creates user template
- User marks template as `is_default=True` → clears only that user's previous default (line 2073-2074)
- User templates listed in Template Manager → still visible, still clonable/editable

**The `is_default` flag works differently per namespace:**
- User template `is_default=True` → `UPDATE op_templates SET is_default=False WHERE created_by = {user_id}`
- System template `is_default=True` → `UPDATE op_templates SET is_default=False` (global cleanup)

These two scopes never interfere with each other.

---

### Change 7: API Client Method

**File:** `frontend/src/services/api.ts`

Add method:
```typescript
updateDefaultTemplate: async (planId: string, data: { changelog?: string }) => {
  const response = await api.put(`/operational-plans/${planId}/update-default-template`, data);
  return response.data;
},
```

---

## Flow Diagrams

### Super Admin Flow

```
1. Super admin opens operational plan editor
2. Edits text, inserts variables, adds sections
3. Clicks "Save All" (saves to per-calculation plan)
4. Clicks "Update Global Template" button
5. Confirmation popover: "All new users will see this version"
6. Clicks "Update"
7. Backend: snapshots old template, updates tree, bumps version
8. Toast: "Global template updated"
```

### New User Flow

```
1. New user signs up, uploads forest boundary
2. Creates a calculation (raster analysis, etc.)
3. Goes to operational plan page
4. System: POST /api/operational-plans { calculation_id }
5. Backend: queries is_default=True AND is_system=True template
6. Found → copies template tree to new plan
7. Backend: auto-populates variables with user's forest data
8. User sees fully resolved document with their data
```

### Fallback Chain

```
1. Check op_templates for is_default=True AND is_system=True
   → Found? Use it
   → Not found? Fall through

2. Check seed_data.py (hardcoded Python tree)
   → Always available as ultimate fallback
```

---

## Files to Modify

| # | File | Change Type | Description |
|---|------|-------------|-------------|
| 1 | `backend/app/api/operational_plans.py` | Edit | Allow super admin to edit system templates, add version snapshot |
| 2 | `backend/app/api/operational_plans.py` | Edit | Add `PUT /{plan_id}/update-default-template` endpoint |
| 3 | `backend/app/api/operational_plans.py` | Edit | Add `GET /templates/{id}/versions` and `POST /templates/{id}/rollback` endpoints |
| 4 | `backend/app/api/operational_plans.py` | Edit | Fix `POST /templates` to allow super admin to create system templates |
| 5 | `backend/app/api/operational_plans.py` | Edit | Fix `save-as-template` to clean up old defaults properly |
| 6 | `frontend/src/pages/OperationalPlanPage.tsx` | Edit | Add "Update Global Template" button + handler |
| 7 | `frontend/src/components/OperationalPlan/TemplateManager.tsx` | Edit | Add update button on system template, version history panel |
| 8 | `frontend/src/services/api.ts` | Edit | Add `updateDefaultTemplate`, `getTemplateVersions`, `rollbackTemplate` methods |

---

## Testing Checklist

**System template changes:**
- [ ] Super admin can edit system template via `PUT /templates/{id}`
- [ ] Super admin can create system template via `POST /templates` with `is_system=True`
- [ ] Regular user gets 403 when trying to edit system template
- [ ] Regular user cannot create system template (forced `is_system=False`)
- [ ] "Update Global Template" button appears only for super admin
- [ ] Clicking button creates/updates system default template
- [ ] Old system template version is snapshotted before overwrite
- [ ] Previous system default is deactivated when new one is set

**New user flow:**
- [ ] New user's plan creation uses the latest system default template
- [ ] Fallback to seed data still works when no system template exists
- [ ] Auto-populate resolves variables correctly in new plan

**Version history:**
- [ ] Template Manager shows version history for system template
- [ ] Rollback to previous version works
- [ ] Version number increments correctly on each update

**User templates (unchanged):**
- [ ] Regular user can still create private/shared templates
- [ ] User `is_default` only clears their own previous default
- [ ] User templates not affected by system template updates
- [ ] Template Manager still lists all templates correctly
