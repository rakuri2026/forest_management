"""
Operational Plan API endpoints — Tree Document Model
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime

from ..core.database import get_db
from ..models.user import User, UserRole
from ..models.calculation import Calculation
from ..models.operational_plan import OperationalPlan
from ..models.op_template import OPTemplate
from ..models.forest_block import ForestBlock
from ..models.op_table import OPTableData
from ..schemas.operational_plan import (
    OperationalPlanCreate,
    OperationalPlanUpdate,
    OperationalPlanSectionUpdate,
    OperationalPlanResponse,
    TreeNodeCreate,
    TreeNodeUpdate,
    TreeNodeReorder,
    TreeNodeSchema,
    VariableDefResponse,
    TemplateCreate,
    TemplateUpdate,
    TemplateApprove,
    TemplateResponse,
    TemplateSummary,
)
from ..schemas.metadata_form import MetadataFormUpdate
from ..services.metadata.admin_location_service import (
    get_provinces,
    get_districts,
    get_divisions,
    get_sub_divisions,
    get_municipalities,
    get_municipalities_by_district,
    get_wards,
    get_wards_by_district_municipality,
    get_physiography_and_jurisdiction,
    get_physiography_by_district_municipality,
    get_location_by_centroid,
    resolve_from_resolved_vars,
)
from ..services.operational_plan.template_utils import generate_template_summaries
from ..utils.auth import get_current_active_user
from ..services.operational_plan.tree_models import TreeNode, TreeOperations, DocumentTree
from ..services.operational_plan.auto_numbering import recompute_numbers
from ..services.operational_plan.seed_data import get_full_seed_document
from ..services.operational_plan.variable_registry import (
    VARIABLE_REGISTRY,
    get_variable,
    get_variables_by_category,
    search_variables,
    get_all_variables,
    VariableDef,
)
from ..services.operational_plan.variable_resolver import VariableResolver
from ..services.operational_plan.op_docx_builder import build_op_document
from ..utils.file_export import build_disposition
from ..utils.number_format import format_devanagari
from nepali_datetime import date as nepali_date

router = APIRouter(tags=["operational-plans"])


def _tree_to_dict_list(tree: list) -> list:
    return [n.model_dump() for n in tree]


def _dict_list_to_tree(data: list) -> list:
    return [TreeNode.from_dict(n) if isinstance(n, dict) else n for n in data]


def plan_to_dict(plan: OperationalPlan) -> Dict[str, Any]:
    tree_data = plan.sections.get("tree", []) if plan.sections else []
    return {
        "id": str(plan.id),
        "calculation_id": str(plan.calculation_id),
        "forest_name": plan.forest_name,
        "sections": plan.sections or {},
        "tree": tree_data,
        "plan_metadata": plan.plan_metadata or {},
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "submitted_at": plan.submitted_at.isoformat() if plan.submitted_at else None,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
    }


def _check_calc_access(calculation_id: UUID, current_user: User, db: Session) -> Calculation:
    calculation = db.execute(
        select(Calculation).where(Calculation.id == calculation_id)
    ).scalar_one_or_none()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")
    if calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    return calculation


def _check_plan_access(plan_id: UUID, current_user: User, db: Session) -> OperationalPlan:
    plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.id == plan_id)
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Operational plan not found")
    _check_calc_access(plan.calculation_id, current_user, db)
    return plan


def _save_tree(plan: OperationalPlan, tree: list, db: Session) -> None:
    sections = plan.sections or {}
    sections["tree"] = _tree_to_dict_list(tree)
    plan.sections = dict(sections)
    flag_modified(plan, "sections")
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_operational_plan(
    plan_data: OperationalPlanCreate,
    template_id: Optional[UUID] = Query(None, description="Template ID to use instead of the default seed tree"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    calculation = _check_calc_access(plan_data.calculation_id, current_user, db)

    existing_plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.calculation_id == plan_data.calculation_id)
    ).scalar_one_or_none()
    if existing_plan:
        raise HTTPException(status_code=400, detail="Operational plan already exists for this calculation")

    if template_id:
        tmpl = db.execute(
            select(OPTemplate).where(OPTemplate.id == template_id)
        ).scalar_one_or_none()
        if not tmpl:
            raise HTTPException(status_code=404, detail="Template not found")
        tree_list = [TreeNode.from_dict(n) for n in tmpl.tree]
    else:
        use_default = db.execute(
            select(OPTemplate).where(OPTemplate.is_default == True, OPTemplate.is_system == True)
        ).scalar_one_or_none()
        if use_default:
            tree_list = [TreeNode.from_dict(n) for n in use_default.tree]
        else:
            tree_list = get_full_seed_document()

    recompute_numbers(tree_list, language="NP")

    sections = {"tree": _tree_to_dict_list(tree_list)}

    plan = OperationalPlan(
        calculation_id=plan_data.calculation_id,
        forest_name=plan_data.forest_name or calculation.forest_name,
        created_by=current_user.id,
        sections=sections,
        plan_metadata={"version": "2.0", "language": "NP", "auto_populated": False}
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    # Auto-populate variables so the plan is ready-to-print immediately
    try:
        resolver = VariableResolver(db, plan.calculation_id, plan)
        tree_list = _dict_list_to_tree(sections.get("tree", []))
        resolved = resolver.resolve_all()
        for node in TreeOperations.flatten(tree_list):
            if node.content:
                node.content = resolver.resolve_node_content(node.content)
        plan.sections["tree"] = _tree_to_dict_list(tree_list)
        plan.plan_metadata["auto_populated"] = True
        plan.plan_metadata["auto_populated_at"] = datetime.utcnow().isoformat()
        flag_modified(plan, "sections")
        plan.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(plan)
    except Exception:
        pass

    return plan_to_dict(plan)


@router.get("/calculation/{calculation_id}")
async def get_operational_plan_by_calculation(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.calculation_id == calculation_id)
    ).scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="Operational plan not found")
    _check_calc_access(calculation_id, current_user, db)

    sections = plan.sections or {}
    if not sections.get("tree"):
        seed_tree = get_full_seed_document()
        recompute_numbers(seed_tree, language="NP")
        sections["tree"] = _tree_to_dict_list(seed_tree)
        plan.sections = dict(sections)
        flag_modified(plan, "sections")
        db.commit()
        db.refresh(plan)

    return plan_to_dict(plan)


@router.put("/{plan_id}")
async def update_operational_plan(
    plan_id: UUID,
    plan_data: OperationalPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)

    if plan_data.tree is not None:
        tree = _dict_list_to_tree([t.model_dump() for t in plan_data.tree])
        recompute_numbers(tree, language=(plan.plan_metadata or {}).get("language", "NP"))
        _save_tree(plan, tree, db)

    if plan_data.sections is not None:
        plan.sections = plan_data.sections

    if plan_data.status is not None:
        plan.status = plan_data.status
        if plan_data.status == "submitted" and not plan.submitted_at:
            plan.submitted_at = datetime.utcnow()
        elif plan_data.status == "approved" and not plan.approved_at:
            plan.approved_at = datetime.utcnow()
            plan.approved_by = current_user.id

    if plan_data.plan_metadata is not None:
        plan.plan_metadata = plan_data.plan_metadata

    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    return plan_to_dict(plan)


# ═══════════════════════════════════════════════════════════
# Tree CRUD Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("/{plan_id}/tree")
async def get_tree(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    sections = plan.sections or {}
    tree_data = sections.get("tree", [])
    return {"tree": tree_data}


@router.post("/{plan_id}/tree/nodes", status_code=status.HTTP_201_CREATED)
async def add_tree_node(
    plan_id: UUID,
    node_data: TreeNodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    sections = plan.sections or {}
    tree_list = _dict_list_to_tree(sections.get("tree", []))

    new_node = TreeNode(
        type=node_data.type,
        title_ne=node_data.title_ne,
        title_en=node_data.title_en or node_data.title_ne,
        content=node_data.content,
        content_type=node_data.content_type,
        chart_type=node_data.chart_type,
        table_id=node_data.table_id,
        static_table=node_data.static_table,
    )

    tree_list = TreeOperations.add_node(tree_list, node_data.parent_id, new_node, node_data.position)
    recompute_numbers(tree_list, language=(plan.plan_metadata or {}).get("language", "NP"))
    _save_tree(plan, tree_list, db)

    return {"node": new_node.model_dump(), "tree": _tree_to_dict_list(tree_list)}


@router.put("/{plan_id}/tree/nodes/{node_id}")
async def update_tree_node(
    plan_id: UUID,
    node_id: str,
    node_data: TreeNodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    sections = plan.sections or {}
    tree_list = _dict_list_to_tree(sections.get("tree", []))

    updates = {k: v for k, v in node_data.model_dump(exclude_none=True).items()}
    tree_list = TreeOperations.update_node(tree_list, node_id, updates)
    _save_tree(plan, tree_list, db)

    updated = TreeOperations.find_node(tree_list, node_id)
    return {"node": updated.model_dump() if updated else None}


@router.delete("/{plan_id}/tree/nodes/{node_id}")
async def delete_tree_node(
    plan_id: UUID,
    node_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    sections = plan.sections or {}
    tree_list = _dict_list_to_tree(sections.get("tree", []))

    try:
        tree_list = TreeOperations.delete_node(tree_list, node_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    recompute_numbers(tree_list, language=(plan.plan_metadata or {}).get("language", "NP"))
    _save_tree(plan, tree_list, db)

    return {"tree": _tree_to_dict_list(tree_list)}


@router.put("/{plan_id}/tree/reorder")
async def reorder_tree(
    plan_id: UUID,
    reorder_data: TreeNodeReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    sections = plan.sections or {}
    tree_list = _dict_list_to_tree(sections.get("tree", []))

    try:
        tree_list = TreeOperations.move_node(tree_list, reorder_data.node_id, reorder_data.new_parent_id, reorder_data.new_position)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    recompute_numbers(tree_list, language=(plan.plan_metadata or {}).get("language", "NP"))
    _save_tree(plan, tree_list, db)

    return {"tree": _tree_to_dict_list(tree_list)}


# ═══════════════════════════════════════════════════════════
# Auto-Populate Endpoint
# ═══════════════════════════════════════════════════════════

@router.post("/{plan_id}/auto-populate")
async def auto_populate_sections(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)

    resolver = VariableResolver(db, plan.calculation_id, plan)
    resolved = resolver.resolve_all()

    sections = plan.sections or {}
    tree_list = _dict_list_to_tree(sections.get("tree", []))

    for node in TreeOperations.flatten(tree_list):
        if node.content:
            node.content = resolver.resolve_node_content(node.content)

    sections["tree"] = _tree_to_dict_list(tree_list)
    plan.sections = dict(sections)
    plan.plan_metadata = {
        **(plan.plan_metadata or {}),
        "auto_populated": True,
        "auto_populated_at": datetime.utcnow().isoformat(),
        "resolved_variables": {k: v for k, v in resolved.items() if isinstance(v, (str, int, float, bool))},
    }
    flag_modified(plan, "sections")
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    return plan_to_dict(plan)


# ═══════════════════════════════════════════════════════════
# Variable Registry Endpoints
# ═══════════════════════════════════════════════════════════

@router.get("/variables")
async def list_variables(
    category: Optional[str] = Query(None, description="Filter by category (A-F)"),
    search: Optional[str] = Query(None, description="Search by name or label"),
):
    if search:
        vars_list = search_variables(search)
    elif category:
        vars_list = get_variables_by_category(category.upper())
    else:
        vars_list = get_all_variables()

    return {
        "total": len(vars_list),
        "variables": [
            VariableDefResponse(
                key=v.key,
                category=v.category,
                label_ne=v.label_ne,
                label_en=v.label_en,
                var_type=v.var_type,
                source=v.source,
                auto_populate=v.auto_populate,
                description=v.description,
            )
            for v in vars_list
        ],
    }


@router.get("/variables/{key}")
async def get_variable_detail(key: str):
    var = get_variable(key)
    if not var:
        raise HTTPException(status_code=404, detail=f"Variable '{key}' not found")
    return VariableDefResponse(
        key=var.key,
        category=var.category,
        label_ne=var.label_ne,
        label_en=var.label_en,
        var_type=var.var_type,
        source=var.source,
        auto_populate=var.auto_populate,
        description=var.description,
    )


@router.get("/{calculation_id}/variable-catalog")
async def get_variable_catalog(
    calculation_id: UUID,
    category: Optional[str] = Query(None, description="Filter by category (A-F)"),
    search: Optional[str] = Query(None, description="Search by key or label"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Returns ALL variables with their resolved values for a given calculation.
    This is the complete variable catalog — shows variable key, type, sample output,
    and whether the data is available for the current forest calculation."""
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc:
        raise HTTPException(status_code=404, detail="Calculation not found")

    plan = db.query(OperationalPlan).filter(
        OperationalPlan.calculation_id == calculation_id
    ).first()
    if not plan:
        plan = OperationalPlan(
            calculation_id=calculation_id,
            forest_name=calc.forest_name or "",
            plan_metadata={},
            status="draft",
        )

    resolver = VariableResolver(db, calculation_id, plan)
    all_resolved = resolver.resolve_all()

    if search:
        vars_list = search_variables(search)
    elif category:
        vars_list = get_variables_by_category(category.upper())
    else:
        vars_list = get_all_variables()

    catalog = []
    for var_def in vars_list:
        resolved = all_resolved.get(var_def.key)

        data_status = "available"
        sample_value = resolved
        if resolved is None:
            data_status = "empty"
            sample_value = None
        elif isinstance(resolved, dict):
            if "datasets" in resolved:
                sample_value = f"[Chart: {resolved.get('type', 'pie')}, {len(resolved.get('labels', []))} categories]"
            elif "rows" in resolved:
                sample_value = f"[Table: {len(resolved.get('rows', []))} rows]"
            elif len(str(resolved)) > 200:
                sample_value = str(resolved)[:200] + "..."
        elif isinstance(resolved, list):
            if len(resolved) > 5:
                sample_value = f"[List: {len(resolved)} items]"
            elif all(isinstance(v, dict) for v in resolved):
                sample_value = f"[Table: {len(resolved)} rows, columns: {list(resolved[0].keys())}]" if resolved else "[]"
        elif isinstance(resolved, bool):
            sample_value = str(resolved)

        catalog.append({
            "key": var_def.key,
            "category": var_def.category,
            "label_ne": var_def.label_ne,
            "label_en": var_def.label_en,
            "var_type": var_def.var_type,
            "source": var_def.source,
            "auto_populate": var_def.auto_populate,
            "data_status": data_status,
            "sample_value": sample_value,
        })

    return {"total": len(catalog), "variables": catalog}


# ═══════════════════════════════════════════════════════════
# Cascading Location Data Endpoints (from admin.admin_nepal)
# ═══════════════════════════════════════════════════════════

@router.get("/locations/provinces")
async def list_provinces(db: Session = Depends(get_db)):
    return get_provinces(db)


@router.get("/locations/districts")
async def list_districts(
    province: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_districts(db, province)


@router.get("/locations/municipalities-by-district")
async def list_municipalities_by_district(
    province: str = Query(...),
    district: str = Query(...),
    db: Session = Depends(get_db),
):
    return get_municipalities_by_district(db, province, district)


@router.get("/locations/wards-by-district")
async def list_wards_by_district(
    province: str = Query(...),
    district: str = Query(...),
    municipality: str = Query(...),
    db: Session = Depends(get_db),
):
    return get_wards_by_district_municipality(db, province, district, municipality)


@router.get("/locations/physiography-by-district")
async def get_physiography_by_district(
    province: str = Query(...),
    district: str = Query(...),
    municipality: str = Query(...),
    db: Session = Depends(get_db),
):
    return get_physiography_by_district_municipality(db, province, district, municipality)


@router.get("/locations/divisions")
async def list_divisions(
    province: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_divisions(db, province)


@router.get("/locations/sub-divisions")
async def list_sub_divisions(
    province: Optional[str] = Query(None),
    division: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_sub_divisions(db, province, division)


@router.get("/locations/municipalities")
async def list_municipalities(
    province: Optional[str] = Query(None),
    division: Optional[str] = Query(None),
    sub_division: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_municipalities(db, province, division, sub_division)


@router.get("/locations/wards")
async def list_wards(
    province: Optional[str] = Query(None),
    division: Optional[str] = Query(None),
    sub_division: Optional[str] = Query(None),
    municipality: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_wards(db, province, division, sub_division, municipality)


@router.get("/locations/physiography-jurisdiction")
async def get_location_physiography(
    province: Optional[str] = Query(None),
    division: Optional[str] = Query(None),
    sub_division: Optional[str] = Query(None),
    municipality: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return get_physiography_and_jurisdiction(db, province, division, sub_division, municipality)


# ═══════════════════════════════════════════════════════════
# Metadata Form Endpoint
# ═══════════════════════════════════════════════════════════

@router.get("/{plan_id}/metadata-form")
async def get_metadata_form(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    user_inputs = (plan.plan_metadata or {}).get("user_inputs", {})
    hybrid_overrides = (plan.plan_metadata or {}).get("hybrid_overrides", {})

    # Backward compat: map old municipality_type → forest_municipality_type
    if user_inputs.get("municipality_type") and not user_inputs.get("forest_municipality_type"):
        user_inputs["forest_municipality_type"] = user_inputs["municipality_type"]

    system_defaults = {}
    try:
        resolver = VariableResolver(db, plan.calculation_id, plan)
        for key, var_def in VARIABLE_REGISTRY.items():
            if var_def.resolver == "resolve_hybrid":
                val = resolver._resolve_category_a(var_def)
                if val is not None:
                    system_defaults[key] = val
    except Exception:
        pass

    has_location = bool(user_inputs.get("province"))
    if not has_location:
        loc = get_location_by_centroid(plan.calculation_id, db)
        if not loc:
            resolved = (plan.plan_metadata or {}).get("resolved_variables", {})
            loc = resolve_from_resolved_vars(resolved, db)
        if loc:
            loc["forest_municipality"] = loc.get("forest_municipality") or loc.get("municipality")
            loc["forest_ward"] = loc.get("forest_ward") or loc.get("ward")
            loc["forest_district"] = loc.get("forest_district") or loc.get("district")
            loc["forest_municipality_type"] = loc.get("forest_municipality_type") or loc.get("municipality_type")
            loc["municipality"] = loc["forest_municipality"]
            loc["ward"] = loc["forest_ward"]
            loc["district"] = loc["forest_district"]
            loc["municipality_type"] = loc["forest_municipality_type"]
            loc["ug_prepopulated"] = True
            loc["ug_province"] = loc.get("province")
            loc["ug_district"] = loc.get("forest_district")
            loc["ug_division"] = loc.get("division")
            loc["ug_sub_division"] = loc.get("sub_division")
            loc["ug_municipality"] = loc.get("forest_municipality")
            loc["ug_municipality_type"] = loc.get("forest_municipality_type")
            loc["ug_ward"] = loc.get("forest_ward")
            loc = {k: v for k, v in loc.items() if v is not None}
            user_inputs = {**user_inputs, **loc}
            metadata = plan.plan_metadata or {}
            metadata["user_inputs"] = user_inputs
            plan.plan_metadata = metadata
            flag_modified(plan, "plan_metadata")
            db.commit()

    if not user_inputs.get("kabuliyatnama_date"):
        today_bs = nepali_date.today()
        user_inputs["kabuliyatnama_date"] = today_bs.strftime("%Y/%m/%d")
        metadata = plan.plan_metadata or {}
        metadata["user_inputs"] = user_inputs
        plan.plan_metadata = metadata
        flag_modified(plan, "plan_metadata")
        db.commit()

    admin_locations = {
        "provinces": get_provinces(db),
        "districts": [],
        "divisions": [],
        "sub_divisions": [],
        "municipalities": [],
        "wards": [],
    }

    province = user_inputs.get("province")
    forest_district = user_inputs.get("forest_district")
    division = user_inputs.get("division")
    sub_division = user_inputs.get("sub_division")

    if province:
        admin_locations["districts"] = get_districts(db, province)
        admin_locations["divisions"] = get_divisions(db, province)
    if province and forest_district:
        admin_locations["municipalities"] = get_municipalities_by_district(db, province, forest_district)
    if province and forest_district:
        mun = user_inputs.get("forest_municipality")
        if mun:
            admin_locations["wards"] = get_wards_by_district_municipality(db, province, forest_district, mun)
    if province and division:
        admin_locations["sub_divisions"] = get_sub_divisions(db, province, division)

    return {
        "user_inputs": user_inputs,
        "hybrid_overrides": hybrid_overrides,
        "system_defaults": system_defaults,
        "admin_locations": admin_locations,
    }


@router.put("/{plan_id}/metadata-form")
async def update_metadata_form(
    plan_id: UUID,
    form_data: MetadataFormUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)

    user_inputs = form_data.user_inputs.model_dump(exclude_none=True) if form_data.user_inputs else {}
    hybrid = form_data.hybrid_overrides.model_dump(exclude_none=True) if form_data.hybrid_overrides else {}

    metadata = plan.plan_metadata or {}
    metadata["user_inputs"] = user_inputs
    metadata["hybrid_overrides"] = hybrid
    plan.plan_metadata = metadata
    flag_modified(plan, "plan_metadata")
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    admin_locations = {
        "provinces": get_provinces(db),
        "districts": [],
        "divisions": [],
        "sub_divisions": [],
        "municipalities": [],
        "wards": [],
    }

    province = user_inputs.get("province")
    forest_district = user_inputs.get("forest_district")
    division = user_inputs.get("division")
    sub_division = user_inputs.get("sub_division")

    if province:
        admin_locations["districts"] = get_districts(db, province)
        admin_locations["divisions"] = get_divisions(db, province)
    if province and forest_district:
        admin_locations["municipalities"] = get_municipalities_by_district(db, province, forest_district)
    if province and forest_district:
        mun = user_inputs.get("forest_municipality")
        if mun:
            admin_locations["wards"] = get_wards_by_district_municipality(db, province, forest_district, mun)
    if province and division:
        admin_locations["sub_divisions"] = get_sub_divisions(db, province, division)

    return {
        "status": "ok",
        "plan_metadata": plan.plan_metadata,
        "admin_locations": admin_locations,
    }


# ═══════════════════════════════════════════════════════════
# HTML Preview Endpoint
# ═══════════════════════════════════════════════════════════

from fastapi.responses import HTMLResponse
from app.services.operational_plan.op_docx_builder import _walk_tree_html

@router.get("/{plan_id}/preview")
async def preview_operational_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    sections = plan.sections or {}
    tree_list = _dict_list_to_tree(sections.get("tree", []))
    resolver = VariableResolver(db, plan.calculation_id, plan)

    for node in TreeOperations.flatten(tree_list):
        if node.content:
            node.content = resolver.resolve_node_content(node.content)

    raw_data = resolver.get_raw_data()
    metadata = plan.plan_metadata or {}
    raw_data["user_inputs"] = metadata.get("user_inputs", {})
    all_tables = db.query(OPTableData).filter(
        OPTableData.calculation_id == plan.calculation_id
    ).all()
    table_cache = {t.table_id: t for t in all_tables}
    body_html = _walk_tree_html(tree_list, plan.calculation_id, raw_data, db, table_cache)
    metadata = plan.plan_metadata or {}
    user_inputs = metadata.get("user_inputs", {})

    _dev = format_devanagari
    fn = plan.forest_name or user_inputs.get('forest_name', '')
    sn = user_inputs.get('sn_number', '')
    div = user_inputs.get('division', '')
    sdiv = user_inputs.get('sub_division', '')
    mun = user_inputs.get('forest_municipality', '')
    wd = user_inputs.get('forest_ward', '')
    py = user_inputs.get('op_preparation_year', '')
    sf = user_inputs.get('op_start_fy', '')
    ef = user_inputs.get('op_end_fy', '')
    reg = user_inputs.get('cf_registration_number', '')
    hd = user_inputs.get('cf_handover_date', '')
    dst = user_inputs.get('forest_district', '') or user_inputs.get('district', '')
    mun_type = user_inputs.get('municipality_type', '')
    mun_disp = f"{mun} {mun_type}" if mun_type else mun
    addr_parts = [f"{mun_disp} वडा नं. {wd}"]
    if dst:
        addr_parts.append(dst)

    html = f"""<!DOCTYPE html>
<html lang="ne">
<head>
<meta charset="UTF-8">
<title>{fn or 'CF'} — Operational Plan Preview</title>
<style>
  body {{ font-family: 'Noto Sans', 'Segoe UI', sans-serif; max-width: 21cm; margin: 0 auto; padding: 0; line-height: 1.7; color: #222; background: #eee; }}
  .page {{ background: white; width: 21cm; min-height: 29.7cm; margin: 0 auto; padding: 0; position: relative; box-sizing: border-box; }}
  .border-outer {{ position: absolute; top: 12px; left: 12px; right: 12px; bottom: 12px; border: 2px solid #006400; pointer-events: none; }}
  .border-inner {{ position: absolute; top: 16px; left: 16px; right: 16px; bottom: 16px; border: 1px solid #006400; pointer-events: none; }}
  .content {{ padding: 36px 32px 24px 32px; display: flex; flex-direction: column; min-height: 29.7cm; box-sizing: border-box; position: relative; z-index: 1; }}
  .inner {{ display: flex; flex-direction: column; min-height: calc(29.7cm - 60px); }}
  .reg-no {{ text-align: right; font-size: 11pt; margin-bottom: 16px; }}
  .main-title {{ text-align: center; margin: 0; padding-top: 12px; }}
  .main-title h1 {{ font-size: 22pt; font-weight: bold; color: #006400; margin: 0 0 4px; border: none; padding: 0; }}
  .main-title .year {{ font-size: 18pt; font-weight: bold; color: #006400; margin: 0; }}
  .divider {{ border: none; border-top: 2.5px solid #006400; margin: 12px 0 14px; }}
  .details {{ font-size: 11pt; line-height: 2; flex: 1; display: flex; flex-direction: column; justify-content: center; padding: 4px 0; }}
  .details .label {{ font-weight: 600; }}
  .details .group {{ font-size: 12pt; font-weight: bold; color: #006400; margin: 8px 0 3px; }}
  .details .addr {{ color: #444; }}
  .details .period {{ font-weight: 600; margin-top: 6px; }}
  .en-box {{ text-align: center; border: 2px double #006400; padding: 10px 14px; margin: 0; }}
  .en-box .t {{ font-size: 13pt; font-weight: bold; color: #333; }}
  .en-box .sub {{ font-size: 10pt; color: #666; margin: 2px 0 6px; }}
  .en-box .d {{ font-size: 10pt; color: #444; line-height: 1.8; margin: 0; }}
  .bottom {{ text-align: center; margin-top: auto; padding-top: 10px; }}
  .bottom .h {{ font-size: 11pt; color: #444; margin: 0 0 4px; }}
  .bottom .f {{ font-size: 14pt; font-weight: bold; color: #006400; margin: 0; }}

  h2 {{ color: #006400; margin-top: 24px; }}
  h3 {{ color: #333; }}
  .toc {{ margin-bottom: 30px; }}
  .toc a {{ color: #006400; text-decoration: none; }}
  .section {{ margin-bottom: 20px; }}
  .section-content {{ white-space: pre-wrap; font-size: 13px; }}
  .chart-placeholder {{ background: #f5f5f5; border: 2px dashed #ccc; border-radius: 8px; padding: 20px; text-align: center; margin: 12px 0; color: #999; }}
  .table-preview {{ overflow-x: auto; margin: 12px 0; }}
  table.data {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  table.data th {{ background: #006400; color: white; padding: 6px 8px; text-align: center; }}
  table.data td {{ padding: 4px 8px; border: 1px solid #ddd; }}
  table.data tr:nth-child(even) {{ background: #f9f9f9; }}
  .hidden {{ display: none; }}
</style>
</head>
<body>
<div class="page">
  <div class="border-outer"></div>
  <div class="border-inner"></div>
  <div class="content">
    <div class="inner">

      <div class="reg-no">{'सामुदायिक वन द.नं. : ' + _dev(reg) if reg else ''}</div>

      <div class="main-title">
        <h1>सामुदायिक वन व्यवस्थापन कार्ययोजना</h1>
        <div class="year">{_dev(str(py)) if py else ''}</div>
      </div>

      <hr class="divider">

      <div class="details">
        <div><span class="label">क्रम संख्या :</span> {sn or '-'}</div>
        <div><span class="label">डिभिजन / सव डिभिजन / स्थानिय तह / वडा :</span> {_dev(div) if div else '-'} / {_dev(sdiv) if sdiv else '-'} / {_dev(mun) if mun else '-'} / {_dev(wd) if wd else '-'}</div>

        <div class="group">श्री {fn} सामुदायिक वन उपभोक्ता समूह</div>
        <div class="addr">{addr_parts[0] + (', ' + dst if dst else '')}</div>
        <div class="period">आ.व. {_dev(sf) if sf else '-'} देखि आ.व. {_dev(ef) if ef else '-'} सम्म</div>
      </div>

      <div class="en-box">
        <div class="t">COMMUNITY FORESTRY OPERATIONAL PLAN</div>
        <div class="sub">FY {sf} TO {ef}</div>
        <div class="d"><strong>Serial No.:</strong> {sn} &nbsp;|&nbsp; <strong>District/Sub Division/RM/Ward:</strong> {div} / {sdiv} / {mun} / {wd}</div>
        <div class="d"><strong>Shree {fn} Community Forest User Group</strong><br>{'Bagmati RM' if mun else ''} Ward No. {wd}{', ' + dst if dst else ''}</div>
      </div>

      <div class="bottom">
        <div class="h">{'वन हस्तान्तरण मिति : ' + _dev(hd) if hd else ''}</div>
        <div class="f">वन व्यवस्थापन कार्ययोजना {_dev(str(py)) if py else ''}</div>
      </div>

    </div>
  </div>
</div>
<h2>विषय सूची</h2>
<div class="toc">{_build_toc_html(tree_list)}</div>
<hr>
{body_html}
</body>
</html>"""
    return HTMLResponse(content=html)


def _build_toc_html(tree: List[TreeNode]) -> str:
    lines = []
    for node in tree:
        if node.hidden_in_export or node.deleted:
            continue
        num = f"{node.number}. " if node.number else ""
        lines.append(f'<div style="padding-left:{node.level * 20}px"><a href="#{node.id}">{num}{node.title_ne}</a></div>')
        if node.children:
            lines.append(_build_toc_html(node.children))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# DOCX Export Endpoint
# ═══════════════════════════════════════════════════════════

from fastapi.responses import StreamingResponse, JSONResponse

# ═══════════════════════════════════════════════════════════
# Chart Data Endpoint (for live Chart.js preview)
# ═══════════════════════════════════════════════════════════

@router.get("/{plan_id}/chart-data/{chart_type}")
async def get_chart_data(
    plan_id: UUID,
    chart_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)
    resolver = VariableResolver(db, plan.calculation_id, plan)
    raw_data = resolver.get_raw_data()
    forest_name = raw_data.get("basic_info", {}).get("forest_name", "")

    chart_configs = {
        "species_pie": {
            "chart_type": "pie",
            "title": f"{forest_name} - Species Composition (Top 8)",
            "get_data": lambda rd: _chart_species_pie(rd, forest_name),
        },
        "forest_type_pie": {
            "chart_type": "pie",
            "title": f"{forest_name} - Forest Type Distribution",
            "get_data": lambda rd: _chart_forest_type_pie(rd, forest_name),
        },
        "block_area_bar": {
            "chart_type": "bar",
            "title": f"{forest_name} - Block-wise Area",
            "get_data": lambda rd: _chart_block_area_bar(rd, forest_name),
        },
        "dbh_histogram": {
            "chart_type": "bar",
            "title": f"{forest_name} - DBH Class Distribution",
            "get_data": lambda rd: _chart_dbh_histogram(rd, forest_name),
        },
        "biomass_bar": {
            "chart_type": "bar",
            "title": f"{forest_name} - Biomass & Carbon Stock",
            "get_data": lambda rd: _chart_biomass_bar(rd, forest_name),
        },
        "slope_pie": {
            "chart_type": "pie",
            "title": f"{forest_name} - Slope Classification",
            "get_data": lambda rd: _chart_slope_pie(rd, forest_name),
        },
        "canopy_pie": {
            "chart_type": "pie",
            "title": f"{forest_name} - Canopy Cover",
            "get_data": lambda rd: _chart_canopy_pie(rd, forest_name),
        },
        "landcover_pie": {
            "chart_type": "pie",
            "title": f"{forest_name} - Land Cover Distribution",
            "get_data": lambda rd: _chart_landcover_pie(rd, forest_name),
        },
        "species_composition_pie_fi": {
            "chart_type": "pie",
            "title": f"{forest_name} - प्रजाति संरचना (Species Composition)",
            "get_data": lambda rd: _chart_species_composition_pie_fi(rd, forest_name),
        },
    }

    if chart_type not in chart_configs:
        raise HTTPException(status_code=404, detail=f"Unknown chart type: {chart_type}")

    config = chart_configs[chart_type]
    result = config["get_data"](raw_data)
    if not result:
        raise HTTPException(status_code=404, detail=f"No data available for chart: {chart_type}")

    return {
        "chart_type": config["chart_type"],
        "title": config["title"],
        "labels": result["labels"],
        "datasets": result["datasets"],
    }


def _chart_species_pie(raw: dict, forest_name: str) -> dict:
    species = raw.get("species", {})
    if isinstance(species, dict):
        species = species.get("species_list", [])
    if isinstance(species, dict):
        species = species.get("species_list", [])
    if not species or not isinstance(species, list):
        return None
    sorted_sp = sorted(species, key=lambda x: x.get("availability_rank", 999))[:8]
    labels = [s.get("scientific_name", "Unknown")[:25] for s in sorted_sp]
    colors = ["#2ecc71", "#3498db", "#e67e22", "#9b59b6", "#f1c40f", "#1abc9c", "#e74c3c", "#95a5a6"]
    return {
        "labels": labels,
        "datasets": [{
            "label": "Species Composition",
            "data": [1] * len(labels),
            "backgroundColor": colors[:len(labels)],
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


def _chart_forest_type_pie(raw: dict, forest_name: str) -> dict:
    ra = raw.get("raster_analysis", {})
    ft = ra.get("forest_type", {}).get("percentages", {})
    if not ft:
        return None
    labels = list(ft.keys())
    values = list(ft.values())
    return {
        "labels": labels,
        "datasets": [{
            "label": "Forest Type",
            "data": values,
            "backgroundColor": ["#1a5c2e", "#27ae60", "#82e0aa", "#d5f5e3", "#2ecc71"],
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


def _chart_block_area_bar(raw: dict, forest_name: str) -> dict:
    blocks = raw.get("blocks", {}).get("blocks", [])
    if not blocks:
        return None
    labels = [b.get("name", f"Block {i+1}")[:15] for i, b in enumerate(blocks)]
    values = [b.get("area_hectares", 0) for b in blocks]
    colors = ["#2ecc71", "#3498db", "#e67e22", "#e74c3c", "#9b59b6", "#f1c40f", "#1abc9c"]
    return {
        "labels": labels,
        "datasets": [{
            "label": "Area (hectares)",
            "data": values,
            "backgroundColor": colors[:len(blocks)],
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


def _chart_dbh_histogram(raw: dict, forest_name: str) -> dict:
    inv = raw.get("inventory", {})
    dbh = inv.get("dbh_summary", {}) or inv.get("dbh_distribution", {})
    if not dbh or not isinstance(dbh, dict):
        return None
    labels = list(dbh.keys())
    values = list(dbh.values())
    return {
        "labels": labels,
        "datasets": [{
            "label": "Number of Trees",
            "data": values,
            "backgroundColor": "#3498db",
            "borderColor": "#2980b9",
            "borderWidth": 1,
        }],
    }


def _chart_biomass_bar(raw: dict, forest_name: str) -> dict:
    bi = raw.get("basic_info", {})
    agb = bi.get("above_ground_biomass_tons", 0) or bi.get("agb_total", 0)
    carbon = bi.get("carbon_stock_tc", 0) or bi.get("carbon_stock", 0)
    if not agb and not carbon:
        return None
    return {
        "labels": ["Above Ground\nBiomass (tons)", "Carbon Stock\n(tons)"],
        "datasets": [{
            "label": "Amount (tons)",
            "data": [float(agb or 0), float(carbon or 0)],
            "backgroundColor": ["#27ae60", "#2980b9"],
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


def _chart_slope_pie(raw: dict, forest_name: str) -> dict:
    ra = raw.get("raster_analysis", {})
    sp = ra.get("slope", {}).get("percentages", {})
    if not sp:
        return None
    labels = list(sp.keys())
    values = list(sp.values())
    color_map = {
        "Flat": "#27ae60", "Gentle": "#f1c40f", "Moderate": "#e67e22",
        "Steep": "#e74c3c", "Very Steep": "#c0392b",
    }
    colors = [color_map.get(l, "#95a5a6") for l in labels]
    return {
        "labels": labels,
        "datasets": [{
            "label": "Slope Classification",
            "data": values,
            "backgroundColor": colors,
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


def _chart_canopy_pie(raw: dict, forest_name: str) -> dict:
    ra = raw.get("raster_analysis", {})
    cp = ra.get("canopy", {}).get("percentages", {})
    if not cp:
        return None
    labels = list(cp.keys())
    values = list(cp.values())
    color_map = {"Open": "#d5f5e3", "Medium": "#82e0aa", "Dense": "#27ae60", "Very Dense": "#1a5c2e"}
    colors = [color_map.get(l, "#95a5a6") for l in labels]
    return {
        "labels": labels,
        "datasets": [{
            "label": "Canopy Cover",
            "data": values,
            "backgroundColor": colors,
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


def _chart_landcover_pie(raw: dict, forest_name: str) -> dict:
    ra = raw.get("raster_analysis", {})
    lc = ra.get("landcover", {}).get("percentages", {})
    if not lc or not isinstance(lc, dict):
        return None
    sorted_lc = sorted(lc.items(), key=lambda x: x[1], reverse=True)[:6]
    labels = [x[0] for x in sorted_lc]
    values = [x[1] for x in sorted_lc]
    return {
        "labels": labels,
        "datasets": [{
            "label": "Land Cover",
            "data": values,
            "backgroundColor": ["#27ae60", "#3498db", "#f39c12", "#e74c3c", "#95a5a6", "#9b59b6"],
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


def _chart_species_composition_pie_fi(raw: dict, forest_name: str) -> dict:
    fi = raw.get("field_inventory", {})
    comp = fi.get("fi_species_composition", {})
    if not comp or not isinstance(comp, dict):
        return None
    sorted_items = sorted(comp.items(), key=lambda x: x[1], reverse=True)[:10]
    labels = [x[0] for x in sorted_items]
    values = [x[1] for x in sorted_items]
    colors = ["#2ecc71", "#3498db", "#e67e22", "#9b59b6", "#f1c40f",
              "#1abc9c", "#e74c3c", "#95a5a6", "#27ae60", "#2980b9"]
    return {
        "labels": labels,
        "datasets": [{
            "label": "Species Composition (%)",
            "data": values,
            "backgroundColor": colors[:len(labels)],
            "borderColor": "#fff",
            "borderWidth": 1,
        }],
    }


# ═══════════════════════════════════════════════════════════
# Map GeoJSON Endpoint (for live Leaflet preview)
# ═══════════════════════════════════════════════════════════

from geoalchemy2.shape import to_shape
from shapely.geometry import mapping

@router.get("/{plan_id}/map-geojson")
async def get_map_geojson(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)

    calculation = db.query(Calculation).filter(Calculation.id == plan.calculation_id).first()
    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    features = []

    # Forest boundary
    if calculation.boundary_geom:
        try:
            shape = to_shape(calculation.boundary_geom)
            boundary_geojson = mapping(shape)
            features.append({
                "type": "Feature",
                "properties": {"name": "Forest Boundary", "type": "boundary", "color": "#27ae60"},
                "geometry": boundary_geojson,
            })
        except Exception:
            pass

    # Blocks
    blocks = db.query(ForestBlock).filter(
        ForestBlock.calculation_id == plan.calculation_id
    ).order_by(ForestBlock.index).all()

    block_colors = ["#2ecc71", "#3498db", "#e67e22", "#e74c3c", "#9b59b6", "#f1c40f", "#1abc9c", "#e91e63"]
    for i, block in enumerate(blocks):
        try:
            shape = to_shape(block.geometry)
            block_geojson = mapping(shape)
            features.append({
                "type": "Feature",
                "properties": {
                    "name": block.name,
                    "type": "block",
                    "area_hectares": block.area_hectares,
                    "color": block_colors[i % len(block_colors)],
                },
                "geometry": block_geojson,
            })
        except Exception:
            pass

    return {
        "type": "FeatureCollection",
        "features": features,
        "forest_name": calculation.forest_name or plan.forest_name or "CF",
    }


@router.post("/{plan_id}/clear-map-cache")
async def clear_plan_map_cache(
    plan_id: UUID,
    layer: Optional[str] = Query(None, description="Specific layer or all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.management_plan_docx.plan_map_service import clear_map_cache
    plan = _check_plan_access(plan_id, current_user, db)
    clear_map_cache(calculation_id=plan.calculation_id, layer_name=layer)
    return {"message": f"Map cache cleared for {layer or 'all layers'}"}


@router.post("/{plan_id}/reset-tree")
async def reset_plan_tree(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Reset the plan document tree to the default seed/default template."""
    plan = _check_plan_access(plan_id, current_user, db)

    use_default = db.execute(
        select(OPTemplate).where(OPTemplate.is_default == True, OPTemplate.is_system == True)
    ).scalar_one_or_none()
    if use_default:
        tree_list = [TreeNode.from_dict(n) for n in use_default.tree]
    else:
        tree_list = get_full_seed_document()

    recompute_numbers(tree_list, language=(plan.plan_metadata or {}).get("language", "NP"))
    plan.sections = {"tree": _tree_to_dict_list(tree_list)}
    flag_modified(plan, "sections")
    db.commit()
    db.refresh(plan)

    return {"tree": plan.sections.get("tree", [])}


@router.get("/{plan_id}/export")
async def export_operational_plan(
    plan_id: UUID,
    refresh_cache: bool = Query(False, description="Regenerate all cached maps"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.management_plan_docx.plan_map_service import clear_map_cache

    plan = _check_plan_access(plan_id, current_user, db)
    if refresh_cache:
        clear_map_cache(calculation_id=plan.calculation_id)

    sections = plan.sections or {}
    tree_list = _dict_list_to_tree(sections.get("tree", []))
    resolver = VariableResolver(db, plan.calculation_id, plan)

    for node in TreeOperations.flatten(tree_list):
        if node.content:
            node.content = resolver.resolve_node_content(node.content)

    buffer = build_op_document(
        plan=plan_to_dict(plan),
        tree=tree_list,
        resolver=resolver,
        calculation_id=plan.calculation_id,
        db=db,
    )

    forest_name = plan.forest_name or "CF"
    filename, disposition = build_disposition(forest_name, "OP", "DOCX", "docx")

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": disposition},
    )


# ═══════════════════════════════════════════════════════════
# Template Management Endpoints
# ═══════════════════════════════════════════════════════════


@router.get("/templates", summary="List templates (user's own + globally available)")
async def list_templates(
    scope: str = Query("mine", description="Filter: mine, shared, global, all"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    conditions = []

    if scope == "mine":
        conditions.append(OPTemplate.created_by == current_user.id)
    elif scope == "shared":
        conditions.append(OPTemplate.visibility.in_(["shared", "global"]))
        conditions.append(OPTemplate.approval_status == "approved")
    elif scope == "global":
        conditions.append(OPTemplate.visibility == "global")
        conditions.append(OPTemplate.approval_status == "approved")
    else:
        conditions.append(
            sa.or_(
                OPTemplate.created_by == current_user.id,
                sa.and_(
                    OPTemplate.visibility.in_(["shared", "global"]),
                    OPTemplate.approval_status == "approved",
                ),
            )
        )

    if tag:
        conditions.append(OPTemplate.tags.contains(tag))

    templates = db.execute(
        select(OPTemplate).where(sa.and_(*conditions))
        .order_by(OPTemplate.is_system.desc(), OPTemplate.is_default.desc(), OPTemplate.updated_at.desc())
    ).scalars().all()

    return {
        "total": len(templates),
        "templates": [TemplateSummary.model_validate(t) for t in templates],
    }


@router.get("/templates/public", summary="Browse all publicly available templates")
async def list_public_templates(
    tag: Optional[str] = Query(None, description="Filter by tag"),
    search: Optional[str] = Query(None, description="Search name or description"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    conditions = [
        OPTemplate.visibility.in_(["shared", "global"]),
        OPTemplate.approval_status == "approved",
    ]
    if tag:
        conditions.append(OPTemplate.tags.contains(tag))
    if search:
        conditions.append(
            sa.or_(
                OPTemplate.name.ilike(f"%{search}%"),
                OPTemplate.description.ilike(f"%{search}%"),
            )
        )

    templates = db.execute(
        select(OPTemplate).where(sa.and_(*conditions))
        .order_by(OPTemplate.is_default.desc(), OPTemplate.updated_at.desc())
    ).scalars().all()

    return {
        "total": len(templates),
        "templates": [TemplateSummary.model_validate(t) for t in templates],
    }


@router.get("/templates/pending-approval", summary="Super admin: list templates pending approval")
async def list_pending_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can view pending approval")

    templates = db.execute(
        select(OPTemplate).where(OPTemplate.approval_status == "pending")
        .order_by(OPTemplate.updated_at.asc())
    ).scalars().all()

    return {
        "total": len(templates),
        "templates": [TemplateSummary.model_validate(t) for t in templates],
    }


@router.post("/templates", status_code=status.HTTP_201_CREATED, summary="Save a new template")
async def create_template(
    tmpl_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if tmpl_data.is_default:
        db.execute(
            sa.update(OPTemplate).where(OPTemplate.created_by == current_user.id).values(is_default=False)
        )

    tree_dicts = [n.model_dump() for n in tmpl_data.tree]
    summaries = generate_template_summaries(tree_dicts)

    tmpl = OPTemplate(
        name=tmpl_data.name,
        description=tmpl_data.description or "",
        tree=tree_dicts,
        visibility=tmpl_data.visibility or "private",
        tags=list(tmpl_data.tags) if tmpl_data.tags else [],
        sections_summary=summaries["sections_summary"],
        variables_summary=summaries["variables_summary"],
        is_system=False,
        is_default=tmpl_data.is_default,
        created_by=current_user.id,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)

    return TemplateResponse.model_validate(tmpl)


@router.get("/templates/{template_id}", summary="Get full template details")
async def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tmpl = db.execute(
        select(OPTemplate).where(OPTemplate.id == template_id)
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.visibility == "private" and tmpl.created_by != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    return TemplateResponse.model_validate(tmpl)


@router.put("/templates/{template_id}", summary="Update a template")
async def update_template(
    template_id: UUID,
    tmpl_data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tmpl = db.execute(
        select(OPTemplate).where(OPTemplate.id == template_id)
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.is_system:
        raise HTTPException(status_code=400, detail="Cannot edit system templates")
    if tmpl.created_by != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")

    if tmpl_data.name is not None:
        tmpl.name = tmpl_data.name
    if tmpl_data.description is not None:
        tmpl.description = tmpl_data.description
    if tmpl_data.tree is not None:
        tree_dicts = [n.model_dump() for n in tmpl_data.tree]
        tmpl.tree = tree_dicts
        summaries = generate_template_summaries(tree_dicts)
        tmpl.sections_summary = summaries["sections_summary"]
        tmpl.variables_summary = summaries["variables_summary"]
    if tmpl_data.is_default is not None:
        if tmpl_data.is_default:
            db.execute(
                sa.update(OPTemplate).where(
                    OPTemplate.created_by == current_user.id, OPTemplate.id != template_id
                ).values(is_default=False)
            )
        tmpl.is_default = tmpl_data.is_default
    if tmpl_data.visibility is not None:
        tmpl.visibility = tmpl_data.visibility
    if tmpl_data.tags is not None:
        tmpl.tags = list(tmpl_data.tags)

    tmpl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tmpl)

    return TemplateResponse.model_validate(tmpl)


@router.delete("/templates/{template_id}", summary="Delete a user template")
async def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tmpl = db.execute(
        select(OPTemplate).where(OPTemplate.id == template_id)
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system templates")
    if tmpl.created_by != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")

    db.delete(tmpl)
    db.commit()

    return {"status": "ok", "message": "Template deleted"}


@router.post("/templates/{template_id}/submit", summary="Submit a private template for global approval")
async def submit_template_for_approval(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    tmpl = db.execute(
        select(OPTemplate).where(OPTemplate.id == template_id)
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only submit your own templates")
    if tmpl.approval_status == "pending":
        raise HTTPException(status_code=400, detail="Template is already pending approval")
    if tmpl.approval_status == "approved":
        raise HTTPException(status_code=400, detail="Template is already approved")

    tmpl.approval_status = "pending"
    tmpl.approval_note = ""
    tmpl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tmpl)

    return TemplateResponse.model_validate(tmpl)


@router.post("/templates/{template_id}/review", summary="Super admin: approve or reject a template")
async def review_template(
    template_id: UUID,
    review: TemplateApprove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admins can review templates")

    tmpl = db.execute(
        select(OPTemplate).where(OPTemplate.id == template_id)
    ).scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.approval_status != "pending":
        raise HTTPException(status_code=400, detail="Template is not pending approval")

    if review.action == "approve":
        tmpl.approval_status = "approved"
        tmpl.visibility = "global"
        tmpl.approved_by = current_user.id
        tmpl.approved_at = datetime.utcnow()
        tmpl.approval_note = review.note or ""
    else:
        tmpl.approval_status = "rejected"
        tmpl.approval_note = review.note or "No reason provided"

    tmpl.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tmpl)

    return TemplateResponse.model_validate(tmpl)


@router.post("/{plan_id}/save-as-template", summary="Save current operational plan as a template")
async def save_plan_as_template(
    plan_id: UUID,
    tmpl_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    plan = _check_plan_access(plan_id, current_user, db)

    if tmpl_data.tree:
        tree_list = [n.model_dump() for n in tmpl_data.tree]
    else:
        sections = plan.sections or {}
        tree_list = sections.get("tree", [])

    if not tree_list:
        raise HTTPException(status_code=400, detail="Plan has no document tree to save")

    if tmpl_data.is_default:
        db.execute(
            sa.update(OPTemplate).where(OPTemplate.created_by == current_user.id).values(is_default=False)
        )

    summaries = generate_template_summaries(tree_list)

    tmpl = OPTemplate(
        name=tmpl_data.name,
        description=tmpl_data.description or "",
        tree=tree_list,
        visibility=tmpl_data.visibility or "private",
        tags=list(tmpl_data.tags) if tmpl_data.tags else [],
        sections_summary=summaries["sections_summary"],
        variables_summary=summaries["variables_summary"],
        is_system=False,
        is_default=tmpl_data.is_default,
        source_calculation_id=plan.calculation_id,
        created_by=current_user.id,
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)

    return TemplateResponse.model_validate(tmpl)
