# Operational Plan Metadata Form — Implementation Plan

## 1. Current State

The existing metadata form (`frontend/src/components/OperationalPlan/MetadataForm.tsx`) is a **modal overlay** with ~32 fields across 7 sections (Plan Period, User Group, Community Forest, Contacts, Signatories, Hybrid Overrides, Settings). It stores data as `user_inputs` and `hybrid_overrides` dicts inside the `plan_metadata` JSONB column of the `operational_plans` table.

### Pain Points

- Missing ~30+ fields listed in the requirement (location hierarchy, dates, forest characteristics, etc.)
- No cascading dropdowns for province → division → subdivision → municipality → ward
- No Nepali date (BS) support — only English AD `YYYY-MM-DD` text inputs
- No admin_nepal table integration for auto-population
- Backend validation is minimal (3 regex checks only)
- No Pydantic schema for the form payload

---

## 2. Admin Database (`admin.admin_nepal`)

The table `admin.admin_nepal` has 23 columns with Nepali and English names:

| Column                           | Type     | Nepali Meaning                 |
| -------------------------------- | -------- | ------------------------------ |
| `province_ne`                    | VARCHAR  | प्रदेश (Nepali name)           |
| `division_n` / `division`        | VARCHAR  | डिभिजन (Nepali/English)        |
| `subdivis_n` / `subdivisio`      | VARCHAR  | सव डिभिजन (Nepali/English)     |
| `palika_n` / `palika`            | VARCHAR  | पालिका (Nepali/English)        |
| `type_nep` / `palikatype`        | VARCHAR  | पालिका प्रकार (Nepali/English) |
| `district_n` / `district`        | VARCHAR  | जिल्ला (Nepali/English)        |
| `ward_ne` / `ward`               | VARCHAR  | वडा (Nepali/English)           |
| `physiography_ne` / `physiograp` | VARCHAR  | भू-आकृति क्षेत्र               |
| `juridiction_ne` / `juridiction` | VARCHAR  | संरक्षित क्षेत्र               |
| `ddgnww`                         | VARCHAR  | DDG code (province-level)      |
| `state_code`                     | INTEGER  | State code                     |
| `mainid`                         | INTEGER  | Parent ID for hierarchy        |
| `geom`                           | GEOMETRY | Spatial boundary               |

**Hierarchy:** `province_ne` → `division_n` → `subdivis_n` → `palika_n` → `ward_ne` (all Nepali names). The `district_n` column sits between `province_ne` and `palika_n` (filters by district within province).

---

## 3. Required Fields — Complete Mapping

Below is the **full mapping** from user requirements to implementation. Each field specifies:

- **Key:** Backend storage key in `plan_metadata.user_inputs`
- **NP Label:** Nepali label only (no English)
- **Type:** Input type for the form
- **Source:** `user_input` (manual), `cascade` (from admin_nepal), `auto` (computed)
- **Validation:** Rules to enforce
- **DB Column:** Where auto-population reads from `admin.admin_nepal`

### Section A: वन दर्ता तथा परिचय

| # | Key | NP Label | Type | Source | Validation | DB Column |
|---|-----|----------|------|--------|------------|-----------|
| 1 | `cf_registration_number` | सामुदायिक वन द.नं. | Text | user_input | Regex: `^\d{3}/\d{4}/\d{2}/\d{2}$` | — |
| 2 | `op_preparation_year` | कार्ययोजना तयारी वर्ष | InputNumber | user_input | Year (2070-2090), required | — |
| 3 | `sn_number` | क्रम संख्या | Text | user_input | Regex: `^[\w/]+$` | — |
| 4 | `province_guideline_year` | प्रदेशको कार्यविधि स्विकृत वर्ष | InputNumber | user_input | Year, default=2079 | — |

### Section B: प्रशासनिक स्थान (Cascading)

| # | Key | NP Label | Type | Source | Validation | DB Column |
|---|-----|----------|------|--------|------------|-----------|
| 5 | `province` | प्रदेश | Select | cascade→auto | From calc, editable | `province_ne` |
| 6 | `division` | डिभिजन | Select | cascade | Filters by province | `division_n` |
| 7 | `sub_division` | सव डिभिजन | Select | cascade | Filters by division | `subdivis_n` |
| 8 | `sub_division_chief` | सव डिभिजन प्रमुखको नाम | Text | user_input | Free text | — |
| 9 | `forest_management_section_chief` | वन ब्यवस्थापन शाखा प्रमुखको नाम | Text | user_input | Free text | — |
| 10 | `division_forest_officer` | डिभिजन प्रमुखको नाम | Text | user_input | Free text | — |
| 11 | `forest_municipality` | सामुदायिक वन रहेको स्थानिय तह | Select | cascade | Filters by sub_division | `palika_n` |
| 12 | `municipality_type` | स्थानिय तहको प्रकार | Text (readonly) | auto | From cascade | `type_nep` |
| 13 | `forest_ward` | सामुदायिक वन रहेको वार्ड नं. | Select | cascade | Filters by municipality | `ward_ne` |

### Section C: सामुदायिक वन विवरण

| # | Key | NP Label | Type | Source | Validation | DB Column |
|---|-----|----------|------|--------|------------|-----------|
| 14 | `cf_sn_number` | संख्या | InputNumber | user_input | Number | — |
| 15 | `constitution_approved_year` | विधान स्वीकृति वर्ष | Date (Nepali) | user_input | Nepali date | — |
| 16 | `user_group_reg_no` | समूह दर्ता नं. | InputNumber | user_input | Number | — |
| 17 | `op_start_fy` | कार्ययोजना लागुहुने सुरू आर्थिक वर्ष | Text | user_input | Regex: `^\d{4}/\d{4}$` | — |
| 18 | `op_end_fy` | कार्ययोजना समाप्त हुने अन्तिम वर्ष | Text | user_input | Regex: `^\d{4}/\d{4}$` | — |
| 19 | `cf_code` | सामुदायिक वनको कोड | Text | user_input | Regex: `^[\w/]+$` | — |
| 20 | `cf_name` | सामुदायिक वनको नाम | Text | user_input | Free text | — |

### Section D: सामुदायिक वनको चारकिल्ला

| # | Key | NP Label | Type | Source | Validation | DB Column |
|---|-----|----------|------|--------|------------|-----------|
| 21 | `cf_boundary_east` | पूर्व | Text | user_input | Free text | — |
| 22 | `cf_boundary_south` | दक्षिण | Text | user_input | Free text | — |
| 23 | `cf_boundary_west` | पश्चिम | Text | user_input | Free text | — |
| 24 | `cf_boundary_north` | उत्तर | Text | user_input | Free text | — |

### Section E: भू-आकृति तथा संरक्षण

| # | Key | NP Label | Type | Source | Validation | DB Column |
|---|-----|----------|------|--------|------------|-----------|
| 25 | `physiography_zone` | भू-आकृति क्षेत्र | Select | auto+edit | From admin_nepal | `physiography_ne` |
| 26 | `protected_area_status` | संरक्षित क्षेत्र भित्र वा बाहीर | Select | auto+edit | From admin_nepal | `juridiction_ne` |
| 27 | `cf_handover_date` | वन हस्तान्तरण मिति | Date (Nepali) | user_input | Nepali date | — |

### Section F: उपभोक्ता समूहको स्थान

Pre-populated from Section B cascading data on first load (same province/division/sub_division/municipality/ward). User can override any field independently — changes in Section B do NOT auto-update Section F once user has modified Section F.

| # | Key | NP Label | Type | Source | Validation |
|---|-----|----------|------|--------|------------|
| 28 | `ug_province` | प्रदेश | Select | pre-filled from Section B | Editable independently |
| 29 | `ug_division` | डिभिजन | Select | cascade | Filters by ug_province |
| 30 | `ug_sub_division` | सव डिभिजन | Select | cascade | Filters by ug_division |
| 31 | `ug_municipality` | उपभोक्ता समूह रहेको पालिका | Select | cascade (pre-filled from Section B) | Same cascade as Section B |
| 32 | `ug_ward` | उपभोक्ता समूह रहेको वार्ड नं. | Select | cascade (pre-filled from Section B) | Filters by municipality |
| 33 | `ug_settlement` | उपभोक्ता समूह रहेको मुख्य टोल | Text | user_input | Free text |

### Section G: उपभोक्ता समूहको चारकिल्ला

| # | Key | NP Label | Type | Source | Validation |
|---|-----|----------|------|--------|------------|
| 34 | `ug_boundary_east` | पूर्व | Text | user_input | Free text |
| 35 | `ug_boundary_south` | दक्षिण | Text | user_input | Free text |
| 36 | `ug_boundary_west` | पश्चिम | Text | user_input | Free text |
| 37 | `ug_boundary_north` | उत्तर | Text | user_input | Free text |

### Section H: प्राविधिक तथा वन विशेषता

| # | Key | NP Label | Type | Source | Validation |
|---|-----|----------|------|--------|------------|
| 38 | `technical_assistance_org` | प्राविधिक सहयोग गर्ने संस्थाको नाम ठेगाना | Text | user_input | Free text |
| 39 | `op_general_assembly_date` | कार्ययोजना पास गरेको साधरण सभा बसेको मिति | Date (Nepali) | user_input | Nepali date |
| 40 | `forest_type` | वनको किसिम | Select | user_input | प्राकृतिक / वृक्षारोपण (default: प्राकृतिक) |
| 41 | `forest_abundance` | वनको बाहुल्यता अवस्था | Select | user_input | रुख / खाँवा / पुनरोत्पादन (default: रुख) |
| 42 | `forest_avg_age` | वनको औषत उमेर वर्ष | InputNumber | user_input | Number, default=80 |
| 43 | `main_non_timber_fp` | मुख्य गै.का.व.पै. | Text | user_input | Free text (e.g. हर्रो, वर्रो, अमला) |
| 44 | `avg_crown_density_pct` | औषत छत्र घनत्व प्रतिशत | InputNumber | user_input | 0-100 |

---

## 4. Architecture Changes

### 4.1 Backend: New Files & Modifications

#### New: `backend/app/schemas/metadata_form.py`

```python
# Pydantic schemas for the entire metadata form
class MetadataFormUserInputs(BaseModel):
    # Section A
    cf_registration_number: Optional[str] = None       # regex validated
    op_preparation_year: Optional[int] = None           # Year 2070-2090
    sn_number: Optional[str] = None                     # regex validated
    province_guideline_year: Optional[int] = None       # default 2079

    # Section B
    province: Optional[str] = None
    division: Optional[str] = None
    sub_division: Optional[str] = None
    sub_division_chief: Optional[str] = None
    forest_management_section_chief: Optional[str] = None
    division_forest_officer: Optional[str] = None
    forest_municipality: Optional[str] = None
    municipality_type: Optional[str] = None
    forest_ward: Optional[str] = None

    # Section C
    cf_sn_number: Optional[int] = None
    constitution_approved_year: Optional[str] = None    # Nepali date
    user_group_reg_no: Optional[int] = None
    op_start_fy: Optional[str] = None                   # regex
    op_end_fy: Optional[str] = None                     # regex
    cf_code: Optional[str] = None                       # regex
    cf_name: Optional[str] = None

    # Section D — CF boundary
    cf_boundary_east: Optional[str] = None
    cf_boundary_south: Optional[str] = None
    cf_boundary_west: Optional[str] = None
    cf_boundary_north: Optional[str] = None

    # Section E
    physiography_zone: Optional[str] = None
    protected_area_status: Optional[str] = None
    cf_handover_date: Optional[str] = None              # Nepali date

    # Section F — UG location (pre-filled from Section B, independently editable)
    ug_province: Optional[str] = None
    ug_division: Optional[str] = None
    ug_sub_division: Optional[str] = None
    ug_municipality: Optional[str] = None
    ug_ward: Optional[str] = None
    ug_settlement: Optional[str] = None

    # Section G — UG boundary
    ug_boundary_east: Optional[str] = None
    ug_boundary_south: Optional[str] = None
    ug_boundary_west: Optional[str] = None
    ug_boundary_north: Optional[str] = None

    # Section H — Tech & forest
    technical_assistance_org: Optional[str] = None
    op_general_assembly_date: Optional[str] = None      # Nepali date
    forest_type: Optional[str] = "प्राकृतिक"
    forest_abundance: Optional[str] = "रुख"
    forest_avg_age: Optional[int] = 80
    main_non_timber_fp: Optional[str] = None
    avg_crown_density_pct: Optional[int] = None

    # Legacy fields (keep for backward compat)
    plan_year_start: Optional[int] = None
    plan_year_end: Optional[int] = None
    plan_duration_years: Optional[int] = None
    user_group_name: Optional[str] = None
    user_group_code: Optional[str] = None
    registration_date: Optional[str] = None
    registration_office: Optional[str] = None
    cf_area_provided: Optional[float] = None
    cf_total_households: Optional[int] = None
    cf_total_population: Optional[int] = None
    vdc_ward: Optional[str] = None
    contact_person: Optional[str] = None
    contact_designation: Optional[str] = None
    contact_phone: Optional[str] = None
    ranger_name: Optional[str] = None
    ranger_phone: Optional[str] = None
    prepared_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    approved_by: Optional[str] = None
    plan_language: Optional[str] = "NP"


class MetadataFormHybridOverrides(BaseModel):
    altitude_min_m: Optional[float] = None
    altitude_max_m: Optional[float] = None
    altitude_mean_m: Optional[float] = None
    dominant_slope: Optional[str] = None
    dominant_aspect: Optional[str] = None
    dominant_soil: Optional[str] = None
    crown_density_pct: Optional[int] = None
    trees_per_hectare: Optional[float] = None
    growing_stock_m3_per_ha: Optional[float] = None
    biomass_t_per_ha: Optional[float] = None
    carbon_stock_tc_per_ha: Optional[float] = None


class MetadataFormUpdate(BaseModel):
    user_inputs: MetadataFormUserInputs
    hybrid_overrides: Optional[MetadataFormHybridOverrides] = None
```

#### Modified: `backend/app/api/operational_plans.py`

**GET `/{plan_id}/metadata-form`** — Enhanced:

- Return cascading source data: `admin_nepal` lookup entries for province/division/subdivision/municipality/ward lists

- Return the `calculation.result_data` (for initial province/district/municipality auto-population)

- New response shape:
  
  ```json
  {
  "user_inputs": { ... },
  "hybrid_overrides": { ... },
  "admin_locations": {
    "provinces": [...],
    "divisions": [...],
    "sub_divisions": [...],
    "municipalities": [...],
    "wards": [...]
  }
  }
  ```

**PUT `/{plan_id}/metadata-form`** — Enhanced:

- Use the new `MetadataFormUpdate` Pydantic model for validation
- Add all new field validations (regex, year ranges, Nepali date formats)
- Keep backward compatibility with existing values in `plan_metadata`

#### New: `backend/app/services/metadata/admin_location_service.py`

- `get_provinces(db)` — `SELECT DISTINCT province_ne FROM admin.admin_nepal ORDER BY province_ne`
- `get_divisions(province, db)` — `SELECT DISTINCT division_n FROM admin.admin_nepal WHERE province_ne = :province ORDER BY division_n`
- `get_sub_divisions(province, division, db)` — filter chain
- `get_municipalities(province, division, sub_division, db)` — filter chain, also returns `type_nep`
- `get_wards(province, ..., municipality, db)` — filter chain
- Lookup functions to auto-populate fields from `admin_nepal` when a cascading parent changes
  - `physiography_ne` and `juridiction_ne` are also fetched from the same filtered row

#### New: `backend/app/utils/nepali_date.py`

- `is_valid_nepali_date(date_str: str) -> bool` — validate `YYYY/MM/DD` Nepali date (year 2000-2099, month 1-12, day 1-32)
- `is_valid_nepali_year(year_str: str) -> bool` — validate `YYYY/YYYY` fiscal year format
- `to_bs_display(date_str: str) -> str` — convert AD to BS display if needed

#### New: API Endpoint — Cascading Location Data

**GET `/api/operational-plans/locations/provinces`**
**GET `/api/operational-plans/locations/divisions?province=...`**
**GET `/api/operational-plans/locations/sub-divisions?province=...&division=...`**
**GET `/api/operational-plans/locations/municipalities?province=...&division=...&sub_division=...`**
**GET `/api/operational-plans/locations/wards?province=...&division=...&sub_division=...&municipality=...`**

These query `admin.admin_nepal` and return Nepali names + type_nep for municipalities.

### 4.2 Frontend: New Files & Modifications

#### Modified: `frontend/src/components/OperationalPlan/MetadataForm.tsx`

Complete rewrite of the form to include **10 sections** (A-H + legacy sections + settings):

**New UI Pattern — Sections as collapsible cards:**

```
┌─────────────────────────────────────────────────┐
│ ✏ Operational Plan Metadata (कार्य योजना सामान्य विवरण)       │
├─────────────────────────────────────────────────┤
│ Section A: Forest Registration & Identification │
│ ┌─────────────────────────────────────────────┐ │
│ │ [CF Registration No]  [OP Prep Year]        │ │
│ │ [SN Number]           [Guideline Year]      │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ Section B: Administrative Location (Cascading)  │
│ ┌─────────────────────────────────────────────┐ │
│ │ [Province ▾] → [Division ▾] → [SubDiv ▾]   │ │
│ │ [Municipality ▾] → [Ward ▾]                │ │
│ │ [SubDiv Chief]   [Section Chief]            │ │
│ │ [DFO Name]                                  │ │
│ └─────────────────────────────────────────────┘ │
│                                                 │
│ ... (all sections)                              │
│                                                 │
│ [Cancel]                              [Save]    │
└─────────────────────────────────────────────────┘
```

**Key frontend changes:**

1. Replace the simple modal with a **wider, scrollable form** (up to 900px)
2. Add **cascading Select** components for location hierarchy
3. Add **Nepali DatePicker** (or simple validated text inputs with proper format hints)
4. Add **readonly/auto-populated** fields that show values from admin_nepal but remain editable
5. Add **section collapsibility** using Ant Design Collapse for better UX with 41+ fields
6. Add **field-level validation feedback** matching all regex patterns

#### Modified: `frontend/src/services/api.ts`

- Add new API methods:
  - `getProvinces()`, `getDivisions(province)`, `getSubDivisions(province, division)`, `getMunicipalities(province, division, sub_division)`, `getWards(...)` — cascade endpoints
  - Update `getMetadataForm` to handle the new response shape with `admin_locations`

#### New: `frontend/src/components/OperationalPlan/NepaliDatePicker.tsx`

- Wrapper component for date input that validates Nepali BS format `YYYY/MM/DD`
- Visual indicator for BS dates (e.g., 🗓 icon with "BS" label)

---

## 5. Data Flow

### Section F Pre-Population Logic

Section F (उपभोक्ता समूहको स्थान) uses an independent copy of the cascading location hierarchy. On **first load** (when no Section F data exists in `plan_metadata`), all Section F fields are pre-populated from Section B values. Once the user saves Section F data, subsequent loads use the saved values and Section B changes do NOT cascade to Section F.

This is tracked with a `ug_prepopulated: true` flag in `plan_metadata.user_inputs` — set to `true` after first pre-population save, so subsequent loads skip re-copying from Section B.

### 5.1 Page Load / Open Metadata Form

```
User clicks "Metadata" button
  → Frontend: GET /api/operational-plans/{planId}/metadata-form
  → Backend:
      1. Reads plan_metadata from DB
      2. Reads admin.admin_nepal for cascading lists
      3. Reads calculation.result_data for auto-populated province/division
      4. Returns { user_inputs, hybrid_overrides, admin_locations }
  → Frontend:
      1. Populates form fields
      2. Populates cascading dropdown options
      3. Auto-selects province/division if found in calculation data
```

### 5.2 Cascading Dropdown Flow

```
User selects Province "बाग्मती"
  → Frontend: GET /api/operational-plans/locations/divisions?province=बाग्मती
  → Backend: SELECT DISTINCT division_n FROM admin.admin_nepal
             WHERE province_ne = 'बाग्मती' ORDER BY division_n
  → Response: ["काठमाण्डाै", "मकवानपुर", "धादिङ्", ...]
  → Frontend: Sets division options, clears sub_division+downstream

User selects Division "मकवानपुर"
  → Frontend: GET /locations/sub-divisions?province=बाग्मती&division=मकवानपुर
  → ... cascade continues ...
  → When municipality is selected, auto-fill municipality_type and
    physiography_zone from the same admin_nepal row
```

### 5.3 Save Flow

```
User clicks "Save Metadata"
  → Frontend: Form.validateFields() — client-side validation
  → Frontend: PUT /api/operational-plans/{planId}/metadata-form
              with body { user_inputs: {...}, hybrid_overrides: {...} }
  → Backend:
      1. Pydantic MetadataFormUpdate validates types & formats
      2. Custom validators check regex patterns, Nepali dates, year ranges
      3. Merges into plan_metadata JSONB
      4. Returns { status: "ok", plan_metadata: {...} }
  → Frontend: Shows success message, closes modal
```

---

## 6. Validation Rules — Complete Specification

| Field                        | Rule                               | Error Message                                   |
| ---------------------------- | ---------------------------------- | ----------------------------------------------- |
| `cf_registration_number`     | Regex: `^\d{3}/\d{4}/\d{2}/\d{2}$` | Must be format: ३२८/२०६६/०२/२०                  |
| `sn_number`                  | Regex: `^[\w/]+$`                  | Must be alphanumeric with / (e.g. MAK/PH/42/33) |
| `op_preparation_year`        | Integer, 2070-2090                 | Year must be between 2070-2090 BS               |
| `province_guideline_year`    | Integer, 2070-2090                 | Default 2079                                    |
| `op_start_fy`                | Regex: `^\d{4}/\d{4}$`             | Format: २०८१/२०८२                               |
| `op_end_fy`                  | Regex: `^\d{4}/\d{4}$`             | Format: २०९०/२०९१                               |
| `cf_code`                    | Regex: `^[\w/]+$`                  | Must match SN pattern                           |
| `constitution_approved_year` | Nepali date `YYYY/MM/DD` or `YYYY` | Valid Nepali date                               |
| `cf_handover_date`           | Nepali date `YYYY/MM/DD`           | Valid Nepali date                               |
| `op_general_assembly_date`   | Nepali date `YYYY/MM/DD`           | Valid Nepali date                               |
| `forest_type`                | Enum: प्राकृतिक, वृक्षारोपण        | Select from list                                |
| `forest_abundance`           | Enum: रुख, खाँवा, पुनरोत्पादन      | Select from list                                |
| `forest_avg_age`             | Integer >= 0                       | Default 80                                      |
| `avg_crown_density_pct`      | Integer 0-100                      | Must be 0-100                                   |
| `contact_phone`              | Digits 7-15                        | Must be 7-15 digits                             |
| `ranger_phone`               | Digits 7-15                        | Must be 7-15 digits                             |

---

## 7. Implementation Phases

### Phase 1: Backend Foundation (Days 1-2)

| Step | Description                                                              | Files                                                     |
| ---- | ------------------------------------------------------------------------ | --------------------------------------------------------- |
| 1.1  | Create `nepali_date.py` utility                                          | `backend/app/utils/nepali_date.py`                        |
| 1.2  | Create `MetadataFormUserInputs` Pydantic schema                          | `backend/app/schemas/metadata_form.py`                    |
| 1.3  | Create `admin_location_service.py` with cascading queries                | `backend/app/services/metadata/admin_location_service.py` |
| 1.4  | Add cascading location API endpoints                                     | `backend/app/api/operational_plans.py` (new routes)       |
| 1.5  | Enhance GET `/{plan_id}/metadata-form` to include `admin_locations`      | `backend/app/api/operational_plans.py`                    |
| 1.6  | Enhance PUT `/{plan_id}/metadata-form` with new schema + full validation | `backend/app/api/operational_plans.py`                    |

### Phase 2: Frontend Rewrite (Days 2-4)

| Step | Description                                              | Files                                                               |
| ---- | -------------------------------------------------------- | ------------------------------------------------------------------- |
| 2.1  | Create cascading Select helper hook (`useAdminLocation`) | `frontend/src/components/OperationalPlan/hooks/useAdminLocation.ts` |
| 2.2  | Create `NepaliDatePicker` component                      | `frontend/src/components/OperationalPlan/NepaliDatePicker.tsx`      |
| 2.3  | Rewrite `MetadataForm.tsx` with all 10 sections          | `frontend/src/components/OperationalPlan/MetadataForm.tsx`          |
| 2.4  | Update API client with new endpoints                     | `frontend/src/services/api.ts`                                      |

### Phase 3: Integration & Testing (Days 4-5)

| Step | Description                                                   | Files                                                        |
| ---- | ------------------------------------------------------------- | ------------------------------------------------------------ |
| 3.1  | Wire auto-population from `calculation.result_data` into form | `MetadataForm.tsx`                                           |
| 3.2  | Wire admin_nepal cascade into form                            | `MetadataForm.tsx` + `useAdminLocation.ts`                   |
| 3.3  | Update variable_registry.py for new metadata variables        | `backend/app/services/operational_plan/variable_registry.py` |
| 3.4  | Update DOCX builder to read new metadata fields               | `backend/app/services/operational_plan/op_docx_builder.py`   |
| 3.5  | Test all validation rules (frontend + backend)                | Manual / API tests                                           |
| 3.6  | Test cascading dropdown flow end-to-end                       | Manual                                                       |

---

## 8. Backward Compatibility

- **Existing OP documents** in draft status will NOT lose data — the old `user_inputs` keys are preserved in the `MetadataFormUserInputs` schema as optional fields
- The old keys (`plan_year_start`, `user_group_name`, `contact_person`, etc.) remain valid and editable
- `plan_metadata` structure remains `{ user_inputs: {...}, hybrid_overrides: {...} }` — only the internal keys expand
- API endpoints keep the same URL path — only the request/response shapes expand

---

## 9. Pre-Implementation Checklist

- [ ] Confirm admin_nepal table has `physiography_ne` and `juridiction_ne` populated for all records
- [ ] Confirm the Nepali date format convention (YYYY/MM/DD vs YYYY-MM-DD vs YYYY)
- [ ] Verify which fields should auto-populate from `calculation.result_data` vs `admin.admin_nepal`
- [ ] Confirm the fiscal year format pattern (e.g. २०८१/२०८२ with Nepali digits or 2081/2082 with English digits)
