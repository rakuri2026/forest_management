"""
Operational Plan API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from ..core.database import get_db
from ..models.user import User, UserRole
from ..models.calculation import Calculation
from ..models.operational_plan import OperationalPlan
from ..schemas.operational_plan import (
    OperationalPlanCreate,
    OperationalPlanUpdate,
    OperationalPlanSectionUpdate,
)
from ..utils.auth import get_current_active_user

router = APIRouter(tags=["operational-plans"])


def plan_to_dict(plan: OperationalPlan) -> Dict[str, Any]:
    """Convert OperationalPlan to dict to avoid Pydantic validation issues"""
    return {
        "id": str(plan.id),
        "calculation_id": str(plan.calculation_id),
        "forest_name": plan.forest_name,
        "sections": plan.sections or {},
        "plan_metadata": plan.plan_metadata or {},
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "submitted_at": plan.submitted_at.isoformat() if plan.submitted_at else None,
        "approved_at": plan.approved_at.isoformat() if plan.approved_at else None,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_operational_plan(
    plan_data: OperationalPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new operational plan for a calculation"""
    # Check if calculation exists
    calculation = db.execute(
        select(Calculation).where(Calculation.id == plan_data.calculation_id)
    ).scalar_one_or_none()

    if not calculation:
        raise HTTPException(status_code=404, detail="Calculation not found")

    # Check if user owns the calculation or is super admin
    if calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if plan already exists
    existing_plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.calculation_id == plan_data.calculation_id)
    ).scalar_one_or_none()

    if existing_plan:
        raise HTTPException(status_code=400, detail="Operational plan already exists for this calculation")

    # Create new plan with TOC template
    plan = OperationalPlan(
        calculation_id=plan_data.calculation_id,
        forest_name=plan_data.forest_name or calculation.forest_name,
        created_by=current_user.id,
        sections=get_toc_template(),
        plan_metadata={"version": "1.0", "auto_populated": False}
    )

    db.add(plan)
    db.commit()
    db.refresh(plan)

    return plan_to_dict(plan)


@router.get("/calculation/{calculation_id}")
async def get_operational_plan_by_calculation(
    calculation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get operational plan for a calculation"""
    plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.calculation_id == calculation_id)
    ).scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Operational plan not found")

    # Check access
    calculation = db.execute(
        select(Calculation).where(Calculation.id == calculation_id)
    ).scalar_one_or_none()

    if not calculation or (calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied")

    # Ensure all template sections exist (toc_*, section_*, etc.)
    sections = plan.sections or {}
    template = get_toc_template()

    print(f"DEBUG: Plan {plan.id} has {len(sections)} sections before update")
    print(f"DEBUG: Current sections: {list(sections.keys())}")

    updated = False

    # Migrate old 'toc' format to new 'toc_*' format if needed
    if 'toc' in sections and isinstance(sections['toc'], dict) and 'items' in sections['toc']:
        print(f"DEBUG: Migrating old 'toc' format to new 'toc_*' format")
        old_toc_items = sections['toc'].get('items', [])
        print(f"DEBUG: Old TOC items: {old_toc_items}")

        # Map old items to new format
        toc_mapping = {
            'कबुलियतनामा': 'toc_kabuliyat',
            'शव्दावली परिचय': 'toc_shabdawali',
            'वन कार्ययोजना स्वीकृति': 'toc_approval',
            'प्रस्तावना': 'toc_intro',
            'कार्ययोजनाको सारांश': 'toc_summary'
        }

        for item in old_toc_items:
            key = toc_mapping.get(item)
            if key and key not in sections:
                sections[key] = template[key]
                updated = True
                print(f"DEBUG: Migrated '{item}' to '{key}'")

        # Remove old 'toc' key
        del sections['toc']
        updated = True
        print(f"DEBUG: Removed old 'toc' key")

    # Add any missing template sections
    for key, value in template.items():
        if key not in sections:
            sections[key] = value
            updated = True
            print(f"DEBUG: Added missing section: {key}")

    if updated:
        # Force JSONB update by creating a new dict
        plan.sections = dict(sections)
        flag_modified(plan, "sections")  # Tell SQLAlchemy the JSONB changed
        db.commit()
        print(f"DEBUG: Committed plan with {len(sections)} sections")
        db.refresh(plan)
        print(f"DEBUG: After refresh, sections keys: {list(plan.sections.keys())}")

    # Convert to dict
    result = plan_to_dict(plan)
    print(f"DEBUG: Returning plan with {len(result.get('sections', {}))} sections")
    print(f"DEBUG: Section keys: {list((result.get('sections', {}) or {}).keys())}")

    return result


@router.put("/{plan_id}")
async def update_operational_plan(
    plan_id: UUID,
    plan_data: OperationalPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update operational plan"""
    plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.id == plan_id)
    ).scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Operational plan not found")

    # Check access
    calculation = db.execute(
        select(Calculation).where(Calculation.id == plan.calculation_id)
    ).scalar_one_or_none()

    if not calculation or (calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied")

    # Update fields
    if plan_data.sections is not None:
        plan.sections = plan_data.sections
    if plan_data.status is not None:
        plan.status = plan_data.status
        if plan_data.status == 'submitted' and not plan.submitted_at:
            plan.submitted_at = datetime.utcnow()
        elif plan_data.status == 'approved' and not plan.approved_at:
            plan.approved_at = datetime.utcnow()
            plan.approved_by = current_user.id
    if plan_data.plan_metadata is not None:
        plan.plan_metadata = plan_data.plan_metadata

    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    return plan_to_dict(plan)


@router.put("/{plan_id}/sections/{section_key}")
async def update_section(
    plan_id: UUID,
    section_key: str,
    section_data: OperationalPlanSectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update a specific section (परिच्छेद)"""
    plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.id == plan_id)
    ).scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Operational plan not found")

    # Check access
    calculation = db.execute(
        select(Calculation).where(Calculation.id == plan.calculation_id)
    ).scalar_one_or_none()

    if not calculation or (calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied")

    # Update section
    sections = plan.sections or {}
    if section_key not in sections:
        raise HTTPException(status_code=404, detail=f"Section {section_key} not found")

    sections[section_key]["content"] = section_data.content
    sections[section_key]["last_modified"] = datetime.utcnow().isoformat()

    if section_data.auto_data is not None:
        sections[section_key]["auto_data"] = section_data.auto_data

    # Force JSONB update - create new dict and flag as modified
    plan.sections = dict(sections)
    flag_modified(plan, "sections")
    plan.updated_at = datetime.utcnow()

    print(f"DEBUG: Saving section '{section_key}' with content length: {len(section_data.content)}")
    db.commit()
    print(f"DEBUG: Committed successfully")

    # Re-fetch to confirm save
    plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.id == plan_id)
    ).scalar_one_or_none()
    saved_content = plan.sections.get(section_key, {}).get('content', '')
    print(f"DEBUG: Verified saved content length: {len(saved_content)}")

    return plan_to_dict(plan)


@router.post("/{plan_id}/auto-populate")
async def auto_populate_sections(
    plan_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Auto-populate sections with system data"""
    plan = db.execute(
        select(OperationalPlan).where(OperationalPlan.id == plan_id)
    ).scalar_one_or_none()

    if not plan:
        raise HTTPException(status_code=404, detail="Operational plan not found")

    # Check access
    calculation = db.execute(
        select(Calculation).where(Calculation.id == plan.calculation_id)
    ).scalar_one_or_none()

    if not calculation or (calculation.user_id != current_user.id and current_user.role != UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Access denied")

    # Auto-populate from system
    sections = plan.sections or {}
    sections = auto_populate_from_system(sections, calculation, db)

    plan.sections = sections
    plan.plan_metadata = {**(plan.plan_metadata or {}), "auto_populated": True, "auto_populated_at": datetime.utcnow().isoformat()}
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    return plan_to_dict(plan)


def get_toc_template() -> Dict[str, Any]:
    """Return the TOC template with all sections (परिच्छेद)"""
    return {
        # TOC Items (editable sections)
        "toc_kabuliyat": {
            "section_number": "कबुलियतनामा",
            "title": "कबुलियतनामा",
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "toc_shabdawali": {
            "section_number": "शब्दावली परिचय",
            "title": "शब्दावली परिचय",
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "toc_approval": {
            "section_number": "वन कार्ययोजना स्वीकृति",
            "title": "वन कार्ययोजना स्वीकृति",
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "toc_intro": {
            "section_number": "प्रस्तावना",
            "title": "प्रस्तावना",
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "toc_summary": {
            "section_number": "कार्ययोजनाको सारांश",
            "title": "कार्ययोजनाको सारांश",
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_1": {
            "section_number": "१",
            "title": "परिचय",
            "subsections": ["१.१ संक्षिप्त नाम र प्रारम्भ", "१.२ परिभाषा"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_2": {
            "section_number": "२",
            "title": "सामुदायिक वन र समूहको भौगोलिक अवस्थिति",
            "subsections": ["२.१ समुहको परिचय", "२.२ वनको भौगोलिक अवस्था", "२.३ वनको ऐतिहासिक पृष्ठभूमि", "२.४ सामुदायिक वनको सिमाना (चारकिल्ला)", "२.५ वनको क्षेत्रफल र नक्सा", "२.६ भू-उपयोग"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": True
        },
        "section_3": {
            "section_number": "३",
            "title": "वनको किसिम र मुख्य प्रजाती",
            "subsections": ["३.१ वन श्रोत मापन विधी", "३.२ कम्पार्टमेण्ट अनुसारको वनको मौज्दात", "३.३ वार्षिक रूपमा उत्पादन हुने काठ दाउराको परिमाण", "३.४ व्यवस्थापनको हिसाबले मुख्य प्रजातीहरु"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": True
        },
        "section_4": {
            "section_number": "४",
            "title": "वन पैदावरको माग र अपुर्तीको अवस्था",
            "subsections": ["४.१ वन पैदावारको माग र आपुर्ति आँकलन विधि", "४.२ वन पैदावारको माग तथा आपूर्तिको अवस्था", "४.२.१ सन्तुलनका उपायहरु"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_5": {
            "section_number": "५",
            "title": "समुहको आर्थिक तथा सामाजिक अवस्था",
            "subsections": ["५.१ समूहको सामाजिक र आर्थिक अवस्था"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_6": {
            "section_number": "६",
            "title": "विगतका वन व्यवस्थापन कार्ययोजनाको समीक्षा",
            "subsections": ["६.१ वन श्रोतको अवस्था विश्लेषण", "६.२ पुरानो कार्ययोजनाको अवधिमा हासिल गरेका प्रमुख उपलब्धिहरु", "६.३ आर्थिक विश्लेषण", "६.४ सकरात्मक पक्षहरु", "६.५ चुनौतीहरु", "६.६ सुधार गर्नुपर्ने पक्षहरु", "६.७ वन व्यवस्थापनको संक्षिप्त समिक्षा"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_7": {
            "section_number": "७",
            "title": "वनस्रोत सर्वेक्षण, विश्लेषण, वन संवर्द्धन प्रणाली तथा व्यवस्थापन",
            "subsections": ["७.१ भू-उपयोग", "७.२ ब्लक/कम्पार्टमेण्ट विभाजन", "७.३ वन संवर्द्धन प्रणाली छनोटको आधार", "७.४ वन संवर्द्धन प्रणाली तथा क्रियाकलाप", "७.५ वन पैदावार सङ्कलन चक्र तथा पुनरोत्पादन तरिका"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": True
        },
        "section_8": {
            "section_number": "८",
            "title": "वन पैदावार उत्पादन र आपूर्तिको तरिका",
            "content": "",
            "auto_data": {},
            "is_auto_generated": True
        },
        "section_9": {
            "section_number": "९",
            "title": "संरक्षण तथा संवर्द्धन कार्य व्यवस्थापन",
            "subsections": ["९.१ वन डढेलो तथा चरिचरन नियन्त्रण", "९.२ एकीकृत रोग किरा तथा मिचाहा प्रजाति नियन्त्रण", "९.३ वन अतिक्रमण, चोरी शिकार तथा कटानी नियन्त्रण", "९.४ वन्यजन्तु तथा जैविक मार्ग संरक्षण", "९.५ वातावरणीय सेवा मूलप्रवाहीकरण", "९.६ पानीका मुहान, खोला किनार, सिमसार, जलाधार संरक्षण", "९.७ जलवायुजन्य जोखिम न्यूनीकरण", "९.८ वन संवर्द्धनका क्रियाकलापहरू", "९.९ वन सम्बन्धी परम्परागत ज्ञान"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_10": {
            "section_number": "१०",
            "title": "वन पैदावारमा आधारित आय-आर्जन, सिप विकास, उद्योग तथा पर्यापर्यटन सम्बन्धी व्यवस्था",
            "subsections": ["१०.१ सामाजिक तथा आर्थिक विकासका कार्यक्रम", "१०.२ सामुदायिक विकास कार्यक्रम", "१०.३ वैकल्पिक उर्जा प्रवर्द्धन कार्यक्रम", "१०.४ संस्थागत तथा मानविय विकास", "१०.५ वनमा आधारित उद्यम विकास कार्यक्रम", "१०.६ पर्या-पर्यटन सम्बन्धी व्यवस्था"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_11": {
            "section_number": "११",
            "title": "वार्षिक बजेट तथा कार्यक्रम तर्जुमा, कार्यान्वयन, अनुगमन र प्रतिवेदन सम्बन्धी व्यवस्था",
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_12": {
            "section_number": "१२",
            "title": "व्यवस्थापन कार्ययोजना अवधिको लागि वार्षिक क्रियाकलाप तथा बजेट",
            "subsections": ["१२.१ दश वर्षे कार्यक्रम"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_13": {
            "section_number": "१३",
            "title": "छिमेकी समूहसँग सहकार्य तथा साझेदारीको व्यवस्था",
            "subsections": ["१३.१ छिमेकी समूहलाई वन पैदावर उपलब्ध गराउने व्यवस्था", "१३.२ समुह बाहिर लिलाम बिक्री गर्दा पुरा गर्नु पर्ने प्रक्रियाहरु"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_14": {
            "section_number": "१४",
            "title": "व्यवस्थापन कार्ययोजनाको वित्तीय विश्लेषण",
            "subsections": ["१४.१ वित्तिय विश्लेषणको अवस्था"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": True
        },
        "section_15": {
            "section_number": "१५",
            "title": "व्यवस्थापन कार्ययोजनाको पुनरावलोकन, अनुगमन, मूल्याङ्कन",
            "subsections": ["१५.१ स्वःअनूगमन तथा मूल्यांकन", "१५.२ सार्वजनिक सुनुवाई/सार्वजनिक लेखापरिक्षण", "१५.३ लेखापरिक्षण", "१५.४ अनुगमन र लेखापरिक्षण", "१५.५ समिक्षा", "१५.६ सम्बन्धीत कार्यालयहरुबाट गरिने अनुगमनमा सहयोग", "१५.७ भत्ता सम्बन्धीत व्यवस्था"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_16": {
            "section_number": "१६",
            "title": "सामुदायिक वनमा निषेधित कार्यहरु",
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_17": {
            "section_number": "१७",
            "title": "वन अपराध र दण्ड जरिवाना",
            "subsections": ["१७.१ वन अपराध र दण्ड जरिवाना सम्बन्धी व्यवस्था", "१७.२ दण्ड जरिवाना"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        },
        "section_18": {
            "section_number": "१८",
            "title": "विविध",
            "subsections": ["१८.१ विविध जानकारी", "१८.२ सोच तालिका (Logical Framework)"],
            "content": "",
            "auto_data": {},
            "is_auto_generated": False
        }
    }


def auto_populate_from_system(sections: Dict[str, Any], calculation: Calculation, db: Session) -> Dict[str, Any]:
    """Auto-populate sections with data from the system"""
    # Section 2: Geographic info - area from calculation
    if "section_2" in sections:
        area_ha = 0
        if calculation.result_data and "area_hectares" in calculation.result_data:
            area_ha = calculation.result_data["area_hectares"]

        sections["section_2"]["auto_data"] = {
            "forest_name": calculation.forest_name,
            "area_hectares": area_ha,
            "boundary_info": "Auto-populated from system"
        }
        sections["section_2"]["content"] = f"यस सामुदायिक वनको क्षेत्रफल {area_ha:.2f} हेक्टर रहेको छ।"

    # Section 3: Species info - from inventory
    if "section_3" in sections:
        sections["section_3"]["auto_data"] = {
            "species_count": 0,
            "main_species": []
        }

    # Section 7: Block/compartment info
    if "section_7" in sections:
        sections["section_7"]["auto_data"] = {
            "blocks": [],
            "compartments": []
        }

    # Section 14: Financial analysis
    if "section_14" in sections:
        sections["section_14"]["auto_data"] = {
            "budget": {},
            "expenses": {}
        }

    return sections
