"""
DOCX builder for Operational Plan export
Walks the resolved tree and builds a .docx document with headings, text, charts, and tables.
"""
import os
from typing import Dict, Any, Optional, List
from io import BytesIO
from uuid import UUID
from unicodedata import normalize as _norm
from sqlalchemy.orm import Session

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from app.models.op_table import OPTableData
from app.models.forest_block import ForestBlock
from app.models.calculation import Calculation
from app.services.operational_plan.tree_models import TreeNode
from app.services.operational_plan.variable_resolver import VariableResolver
from app.services.operational_plan.variable_registry import get_variable
from app.utils.number_format import format_devanagari

# ── Chart PNG cache ──
_CHART_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "charts_cache")

def _chart_cache_path(calculation_id: UUID, chart_key: str) -> str:
    sub = os.path.join(_CHART_CACHE_DIR, str(calculation_id))
    os.makedirs(sub, exist_ok=True)
    return os.path.join(sub, f"{chart_key}.png")

def _chart_cache_get(calculation_id: UUID, chart_key: str) -> Optional[BytesIO]:
    path = _chart_cache_path(calculation_id, chart_key)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return BytesIO(f.read())
        except Exception:
            pass
    return None

def _chart_cache_set(calculation_id: UUID, chart_key: str, buf: BytesIO):
    path = _chart_cache_path(calculation_id, chart_key)
    try:
        with open(path, "wb") as f:
            f.write(buf.getvalue())
    except Exception:
        pass

# ── Nepali font setup for matplotlib ──
_FONT_SETUP_DONE = False
def _ensure_dev_font():
    global _FONT_SETUP_DONE
    if _FONT_SETUP_DONE:
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
    for name in ['Nirmala UI', 'Mangal', 'Arial Unicode MS', 'Noto Sans Devanagari']:
        try:
            fp = fm.findfont(name, fallback_to_default=False)
            if fp:
                fm.fontManager.addfont(fp)
                plt.rcParams['font.family'] = name
                _FONT_SETUP_DONE = True
                return
        except Exception:
            continue
    _FONT_SETUP_DONE = True

# ── Chart color maps (consistent with frontend) ──
_HEALTH_COLORS_MAP = {
    "excellent": "#228B22", "healthy": "#90EE90", "moderate": "#FFD700",
    "poor": "#FF8C00", "stressed": "#DC143C",
}
_ASPECT_COLORS_MAP = {
    "N": "#1A5490", "NE": "#3498DB", "E": "#1ABC9C", "SE": "#F1C40F",
    "S": "#E74C3C", "SW": "#E67E22", "W": "#F39C12", "NW": "#9B59B6",
    "Flat": "#CCCCCC",
}
_NASA_FOREST_QUALITY_COLORS = {
    "Primary Forest": "#00FF00", "Young Secondary Forest": "#FF0000",
    "Old Secondary Forest": "#6666FF",
}
_SOIL_BAR_COLORS = ["#8B4513", "#A0522D", "#CD853F", "#D2691E", "#DEB887", "#D2B48C"]

from app.services.report.chart_generator import (
    generate_species_pie,
    generate_forest_type_pie,
    generate_block_area_bar,
    generate_dbh_histogram,
    generate_biomass_bar,
    generate_slope_pie,
    generate_canopy_pie,
    generate_landcover_pie,
)
from app.services.report.map_generator import generate_boundary_map
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping


_COVER_GREEN = RGBColor(0, 100, 0)
_SUBTITLE_GRAY = RGBColor(80, 80, 80)

import docx.document as _docx_doc

# Patch Document.add_table to auto-repeat header row on every page
_orig_add_table = _docx_doc.Document.add_table
def _patched_add_table(self, rows, cols, *args, **kwargs):
    tbl = _orig_add_table(self, rows, cols, *args, **kwargs)
    if rows > 0:
        trPr = tbl.rows[0]._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:tblHeader"))
    return tbl
_docx_doc.Document.add_table = _patched_add_table


def _set_cell_shading(cell, color_hex: str):
    shading = cell._tc.get_or_add_tcPr()
    elem = shading.makeelement(qn("w:shd"), {
        qn("w:fill"): color_hex,
        qn("w:val"): "clear",
    })
    shading.append(elem)


def _set_page_border(section):
    """Add double-line green page border to a section."""
    sectPr = section._sectPr
    pgBorders = OxmlElement("w:pgBorders")
    pgBorders.set(qn("w:offsetFrom"), "page")
    for side in ("top", "left", "bottom", "right"):
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "double")
        border.set(qn("w:sz"), "12")
        border.set(qn("w:space"), "18")
        border.set(qn("w:color"), "006400")
        pgBorders.append(border)
    sectPr.append(pgBorders)


def _add_cover_page(doc: Document, plan: Dict[str, Any], metadata: Dict[str, Any]):
    section = doc.sections[0]
    _set_page_border(section)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.2)
    section.right_margin = Cm(2.2)

    user_inputs = metadata.get("user_inputs", {})
    forest_name = plan.get("forest_name", user_inputs.get("forest_name", "..............."))
    sn_number = user_inputs.get("sn_number", "...............")
    division = user_inputs.get("division", "...........")
    sub_division = user_inputs.get("sub_division", "...........")
    forest_municipality = user_inputs.get("forest_municipality", "...........")
    forest_ward = user_inputs.get("forest_ward", "...........")
    op_prep_year = user_inputs.get("op_preparation_year", "...........")
    op_start_fy = user_inputs.get("op_start_fy", "२०../..")
    op_end_fy = user_inputs.get("op_end_fy", "२०../..")
    cf_reg_no = user_inputs.get("cf_registration_number", "")
    cf_handover = user_inputs.get("cf_handover_date", "")
    district = user_inputs.get("district", "")

    np = _fix

    # -- top spacer --
    for _ in range(2):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.space_before = Pt(0)

    # -- registration number (right) --
    if cf_reg_no:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(f"सामुदायिक वन द.नं. : {np(cf_reg_no)}")
        r.font.size = Pt(11)
        r.font.bold = True

    # -- main title --
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("सामुदायिक वन व्यवस्थापन कार्ययोजना")
    r.font.size = Pt(22)
    r.font.bold = True
    r.font.color.rgb = _COVER_GREEN

    # -- year --
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(np(str(op_prep_year)))
    r.font.size = Pt(18)
    r.font.bold = True
    r.font.color.rgb = _COVER_GREEN

    # -- divider --
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(8)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "006400")
    pBdr.append(bottom)
    pPr.append(pBdr)

    # -- details section --
    details = [
        ("क्रम संख्या :", np(str(sn_number))),
        ("डिभिजन / सव डिभिजन / स्थानिय तह / वडा :",
         f"{np(division)} / {np(sub_division)} / {np(forest_municipality)} / {np(forest_ward)}"),
    ]
    for label, value in details:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = Pt(20)
        r = p.add_run(label + " ")
        r.font.size = Pt(11)
        r.font.bold = True
        r2 = p.add_run(value)
        r2.font.size = Pt(11)

    # -- group name --
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(np(f"श्री {forest_name} सामुदायिक वन उपभोक्ता समूह"))
    r.font.size = Pt(12)
    r.font.bold = True
    r.font.color.rgb = _COVER_GREEN

    # -- address --
    mun_label = user_inputs.get("municipality_type", "")
    mun_display = f"{forest_municipality} {mun_label}" if mun_label else forest_municipality
    addr_parts = [f"{mun_display} वडा नं. {forest_ward}"]
    if district:
        addr_parts.append(district)
    address = ", ".join(addr_parts)

    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run(np(address))
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(60, 60, 60)

    # -- FY period --
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(np(f"आ.व. {op_start_fy} देखि आ.व. {op_end_fy} सम्म"))
    r.font.size = Pt(11)
    r.font.bold = True

    # -- English section (bordered) --
    en_table = doc.add_table(rows=1, cols=1)
    en_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    en_cell = en_table.cell(0, 0)

    # style the cell with double border
    tcPr = en_cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"), "double")
        border.set(qn("w:sz"), "6")
        border.set(qn("w:space"), "4")
        border.set(qn("w:color"), "006400")
        tcBorders.append(border)
    tcPr.append(tcBorders)

    # set cell paragraph alignment center
    for para in en_cell.paragraphs:
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    en_cell.paragraphs[0].paragraph_format.space_before = Pt(6)
    en_cell.paragraphs[0].paragraph_format.space_after = Pt(2)

    r = en_cell.paragraphs[0].add_run("COMMUNITY FORESTRY OPERATIONAL PLAN")
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = RGBColor(60, 60, 60)

    p2 = en_cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(0)
    p2.paragraph_format.space_after = Pt(4)
    r = p2.add_run(f"FY {op_start_fy} TO {op_end_fy}")
    r.font.size = Pt(10)
    r.font.color.rgb = _SUBTITLE_GRAY

    p3 = en_cell.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_before = Pt(1)
    p3.paragraph_format.space_after = Pt(1)
    r = p3.add_run(f"Serial No.: {sn_number}")
    r.font.size = Pt(10)
    r.font.bold = True

    p4 = en_cell.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p4.paragraph_format.space_before = Pt(0)
    p4.paragraph_format.space_after = Pt(1)
    r = p4.add_run(f"District/Sub Division/RM/Ward: {division} / {sub_division} / {forest_municipality} / {forest_ward}")
    r.font.size = Pt(10)

    p5 = en_cell.add_paragraph()
    p5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p5.paragraph_format.space_before = Pt(2)
    p5.paragraph_format.space_after = Pt(4)
    r = p5.add_run(f"Shree {forest_name} Community Forest User Group")
    r.font.size = Pt(10)
    r.font.bold = True

    # -- spacer to push bottom --
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(0)

    # -- handover date --
    if cf_handover:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(np(f"वन हस्तान्तरण मिति : {cf_handover}"))
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(60, 60, 60)

    # -- footer title --
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run(np(f"वन व्यवस्थापन कार्ययोजना {op_prep_year}"))
    r.font.size = Pt(14)
    r.font.bold = True
    r.font.color.rgb = _COVER_GREEN

    doc.add_page_break()


def _add_toc_field(doc: Document):
    heading = doc.add_heading("विषय सूची (Table of Contents)", level=1)
    for r in heading.runs:
        r.font.color.rgb = _COVER_GREEN

    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)

    from docx.oxml import OxmlElement

    def _make_run_with_fldchar(para, fldchar_type):
        run = OxmlElement("w:r")
        fld = OxmlElement("w:fldChar")
        fld.set(qn("w:fldCharType"), fldchar_type)
        run.append(fld)
        para._p.append(run)

    def _make_run_with_instr(para, text):
        run = OxmlElement("w:r")
        instr = OxmlElement("w:instrText")
        instr.text = text
        run.append(instr)
        para._p.append(run)

    def _make_run_with_text(para, text, italic=False, color=None, size=None):
        run_elem = OxmlElement("w:r")
        t_elem = OxmlElement("w:t")
        t_elem.text = text
        run_elem.append(t_elem)
        if italic or color or size:
            rpr = OxmlElement("w:rPr")
            if italic:
                rpr.append(OxmlElement("w:i"))
            if color:
                c = OxmlElement("w:color")
                c.set(qn("w:val"), color)
                rpr.append(c)
            if size:
                sz = OxmlElement("w:sz")
                sz.set(qn("w:val"), str(size))
                rpr.append(sz)
            run_elem.insert(0, rpr)
        para._p.append(run_elem)

    _make_run_with_fldchar(p, "begin")
    _make_run_with_instr(p, ' TOC \\o "1-3" \\h \\z \\u ')
    _make_run_with_fldchar(p, "separate")
    _make_run_with_text(p, "[Right-click here and select 'Update Field' to generate Table of Contents]",
                        italic=True, color="969696", size=20)
    _make_run_with_fldchar(p, "end")

    doc.add_page_break()


def _add_heading(doc: Document, node: TreeNode):
    num = f"{node.number}. " if node.number else ""
    text = f"{num}{_norm('NFC', node.title_ne)}"

    if node.type in ("section", "appendix"):
        heading = doc.add_heading(text, level=1)
    elif node.type == "subsection":
        heading = doc.add_heading(text, level=2)
    elif node.type == "preamble":
        heading = doc.add_heading(text, level=1)
    else:
        heading = doc.add_heading(text, level=1)

    for r in heading.runs:
        r.font.color.rgb = _COVER_GREEN

    if node.title_en and node.title_en != node.title_ne:
        sub = doc.add_paragraph()
        run = sub.add_run(_fix( node.title_en))
        run.font.size = Pt(10)
        run.font.italic = True
        run.font.color.rgb = RGBColor(120, 120, 120)
        sub.paragraph_format.space_after = Pt(12)


import re

_VARIABLE_PATTERN = re.compile(r"\{\{(\w+(?::\w+)*)\}\}")

# Devanagari text cleanup: common decomposed/wrong sequences → proper composed forms
_DEVANAGARI_FIXES = [
    ("\u093E\u0948", "\u094C"),  # ा+ै → ौ
    ("\u0947\u0947", "\u0947"),  # े+े → े (duplicate e)
    ("\u0948\u0948", "\u0948"),  # ै+ै → ै (duplicate ai)
]

_ARABIC_TO_DEV = str.maketrans("0123456789", "०१२३४५६७८९")

def _fix(text: str) -> str:
    """Normalize NFC + fix common Devanagari sequence errors + convert Arabic digits to Devanagari."""
    if text is None:
        return ""
    text = _norm("NFC", text)
    for wrong, correct in _DEVANAGARI_FIXES:
        text = text.replace(wrong, correct)
    text = text.translate(_ARABIC_TO_DEV)
    return text


def _set_header_repeat(tbl, row_index=0):
    """Mark a table row to repeat as header on each page when table spans multiple pages."""
    trPr = tbl.rows[row_index]._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:tblHeader"))

def _fmt_value(value, var_name=""):
    """Format a resolved variable value with Devanagari digits and correct precision."""
    if value is None:
        return "-"
    if isinstance(value, str) and any(c in "०१२३४५६७८९" for c in value):
        return _fix(value)
    val = get_variable(var_name)
    precision = val.precision if val else 2
    return _fix( format_devanagari(value, precision))


def _resolve_var_text(text: str, raw_data: dict) -> str:
    """Resolve {{variable}} patterns in a text string using raw_data."""
    def _replacer(m):
        var_name = m.group(1)
        if var_name.startswith("chart:") or var_name.startswith("map:") or var_name.startswith("table:") or var_name.endswith(":full"):
            return m.group(0)
        var_val = _resolve_var_from_raw(var_name, raw_data)
        if var_val is None:
            return ""
        if isinstance(var_val, (dict, list)):
            return ""
        return _fmt_value(var_val, var_name)
    return _fix( re.sub(r"\{\{(\w+(?::\w+)*)\}\}", _replacer, text))

# Alias mapping to look up unresolved list/dict variables from raw_data
_VAR_LOOKUP = {
    "uc_members": ("committees", "user_committee.members"),
    "ac_members": ("committees", "advisory_committee.members"),
    "fc_members": ("committees", "financial_committee.members"),
    "species_list": ("species", "species_list"),
    "bio_vegetation": ("biodiversity", "vegetation"),
    "bio_animals": ("biodiversity", "animals"),
    "activities_list": ("activities", "activities"),
    "ya_year_summary": ("yearly_plan", "year_summary"),
    "ya_plan_matrix": ("yearly_plan", "plan_matrix"),
    "ya_program_budget": ("yearly_plan", "program_budget"),
    "ya_total_budget_by_year": ("yearly_plan", "total_budget_by_year"),
    "ya_total_ten_year_budget": ("yearly_plan", "total_ten_year_budget"),
    "ya_activity_plan_detail": ("yearly_plan", "activity_plan_detail"),
    "ug_buildings": ("user_group", "buildings"),
    "hh_prosperity_distribution": ("households", "prosperity_distribution"),
    "hh_caste_distribution": ("households", "caste_distribution"),
    "inventory_species_summary": ("inventory", "species_summary"),
    "inventory_block_summary": ("inventory", "block_summary"),
    "blocks_count": ("blocks", "total_blocks"),
    "species_by_role": ("species", "by_role"),
    "kabuliyatnama_date": ("user_inputs", "kabuliyatnama_date"),
    "kabuliyatnama_date_year": ("user_inputs", "kabuliyatnama_date"),
    "kabuliyatnama_date_month": ("user_inputs", "kabuliyatnama_date"),
    "kabuliyatnama_date_day": ("user_inputs", "kabuliyatnama_date"),
    "kabuliyatnama_date_sentence": ("user_inputs", "kabuliyatnama_date"),

    # Sampling
    "sampling_type": ("sampling", "designs.0.sampling_type"),
    "sampling_block_summary": ("sampling", "sampling_block_summary"),
    "sampling_point_locations": ("sampling", "sampling_point_locations"),
    "sampling_total_points": ("sampling", "designs.0.total_points"),
    "sampling_total_blocks": ("sampling", "designs.0.total_blocks"),
    "sampling_requested_intensity": ("sampling", "designs.0.requested_intensity_percent"),
    "sampling_actual_intensity": ("sampling", "designs.0.sampling_percentage"),
    "sampling_forest_area_ha": ("sampling", "designs.0.forest_area_hectares"),
    "sampling_plot_area_sqm": ("sampling", "designs.0.plot_area_sqm"),
    "sampling_total_sampled_area_ha": ("sampling", "designs.0.total_sampled_area_hectares"),
    "sampling_available": ("sampling", "available"),
    "sampling_plot_shape": ("sampling", "designs.0.plot_shape"),
    "sampling_plot_radius_m": ("sampling", "designs.0.plot_radius_meters"),
    "sampling_intensity_per_ha": ("sampling", "designs.0.intensity_per_hectare"),

    # Fieldbook
    "fieldbook_total_points": ("fieldbook", "total_points"),
    "fieldbook_vertex_count": ("fieldbook", "vertex_count"),
    "fieldbook_interpolated_count": ("fieldbook", "interpolated_count"),
    "fieldbook_perimeter_m": ("fieldbook", "perimeter_m"),
    "fieldbook_avg_elevation_m": ("fieldbook", "avg_elevation_m"),
    "fieldbook_min_elevation_m": ("fieldbook", "min_elevation_m"),
    "fieldbook_max_elevation_m": ("fieldbook", "max_elevation_m"),
    "fieldbook_points": ("fieldbook", "points"),
    "fieldbook_block_summary": ("fieldbook", "block_summary"),
    "fieldbook_narration": ("section_generators", "section:fieldbook_narration"),
}

def _deep_get(data, path):
    if not path:
        return None
    current = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(key)
                current = current[idx] if 0 <= idx < len(current) else None
            except (ValueError, IndexError):
                return None
        else:
            return None
        if current is None:
            return None
    return current

def _resolve_var_from_raw(var_name: str, raw_data: dict) -> any:
    lookup = _VAR_LOOKUP.get(var_name)
    if lookup:
        section, path = lookup
        section_data = raw_data.get(section, {})
        result = _deep_get(section_data, path)
        if result is not None:
            if var_name == "kabuliyatnama_date_year":
                parts = str(result).split("/")
                return int(parts[0]) if len(parts) == 3 else result
            if var_name == "kabuliyatnama_date_month":
                parts = str(result).split("/")
                return int(parts[1]) if len(parts) == 3 else result
            if var_name == "kabuliyatnama_date_day":
                parts = str(result).split("/")
                return int(parts[2]) if len(parts) == 3 else result
            if var_name == "kabuliyatnama_date_sentence":
                return _format_kabuliyatnama_sentence(str(result))
            return result

    user_inputs = raw_data.get("user_inputs", {})
    if var_name in user_inputs and user_inputs[var_name] is not None:
        return user_inputs[var_name]

    for section_key in ("basic_info", "raster_analysis", "boundary", "blocks",
                        "species", "inventory", "field_inventory", "fieldbook",
                        "sampling", "households", "committees", "biodiversity",
                        "activities", "user_group", "section_generators",
                        "compartment", "yearly_plan"):
        section_data = raw_data.get(section_key, {})
        if var_name in section_data:
            return section_data[var_name]
    return None


def _format_kabuliyatnama_sentence(raw: str) -> str:
    parts = raw.split("/")
    if len(parts) != 3:
        return raw
    try:
        from nepali_datetime import date as nepali_date
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        nd = nepali_date(y, m, d)
        MONTH_NAMES_NP = (None, "वैशाख", "जेष्ठ", "असार", "श्रावण", "भदौ", "आश्विन", "कार्तिक", "मंसिर", "पौष", "माघ", "फाल्गुण", "चैत्र")
        DAY_NAMES_NP = ("आइतबार", "सोमबार", "मङ्गलबार", "बुधबार", "बिहिबार", "शुक्रबार", "शनिबार")
        month_name = MONTH_NAMES_NP[m] if 1 <= m <= 12 else str(m)
        day_name = DAY_NAMES_NP[nd.weekday()]
        return f"ईति सम्वत {_fix(str(y))} साल {month_name} महिना {_fix(str(d))} गते रोज {day_name} शुभम् ।"
    except Exception:
        return raw

def _render_list_value_as_text(val: any, var_name: str = "") -> str:
    if not val:
        return ""
    if isinstance(val, list):
        if all(isinstance(v, str) for v in val):
            return ", ".join(val)
        if all(isinstance(v, dict) for v in val):
            if var_name == "uc_members":
                headers, rows = _build_uc_members_data(val)
                col_widths = [max(len(cell) for cell in [h] + [r[i] for r in rows]) for i, h in enumerate(headers)]
                lines = []
                sep = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
                lines.append(sep)
                lines.append("-+-".join("-" * col_widths[i] for i in range(len(headers))))
                for row in rows:
                    lines.append(" | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)))
                return "\n".join(lines)
            lines = []
            for i, item in enumerate(val, 1):
                parts = [_fmt_value(item.get(k, ""), var_name) for k in ("name", "position", "gender") if k in item]
                clean = " — ".join(p for p in parts if p.strip())
                if clean:
                    lines.append(f"{i}. {clean}")
            return "\n".join(lines)
        return "\n".join(f"• {v}" for v in val if v)
    if isinstance(val, dict):
        return "\n".join(f"{k}: {_fmt_value(v, var_name)}" for k, v in val.items() if v)
    return _fmt_value(val, var_name)

def _add_list_table(doc: Document, val: list, var_name: str = ""):
    if not val or not isinstance(val, list):
        return None
    if all(isinstance(v, str) for v in val):
        for v in val:
            p = doc.add_paragraph(f"• {v}")
            p.paragraph_format.space_after = Pt(2)
        return True
    if all(isinstance(v, dict) for v in val):
        vdef = get_variable(var_name)
        if vdef and vdef.label_ne:
            p = doc.add_paragraph()
            run = p.add_run(vdef.label_ne)
            run.font.size = Pt(11)
            run.font.bold = True
        headers = list(val[0].keys())
        num_cols = len(headers)
        num_rows = len(val) + 1
        tbl = doc.add_table(rows=num_rows, cols=num_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.style = "Table Grid"
        for ci, h in enumerate(headers):
            cell = tbl.cell(0, ci)
            cell.text = h.replace("_", " ").title()
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.bold = True
                    r.font.color.rgb = RGBColor(255, 255, 255)
            _set_cell_shading(cell, "006400")
        for ri, row in enumerate(val, 1):
            for ci, h in enumerate(headers):
                cell = tbl.cell(ri, ci)
                cell.text = _fmt_value(row.get(h, ""), var_name)
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(9)
        doc.add_paragraph()
        return True
    return None


NP_HEADERS_ACTIVITY_PLAN = [
    ("s_no", "सि.नं."),
    ("activity", "कृयाकलाप"),
    ("program", "कार्यक्रम"),
    ("unit", "इकाइ"),
    ("quantity_years", "वार्षिक\nपरिमाण"),
    ("budget_years", "वार्षिक\nबजेट"),
    ("total_budget", "जम्मा\nबजेट\n(हजार)"),
    ("location_type", "स्थान\nप्रकार"),
    ("location_details", "स्थान\nविवरण"),
    ("spatial_features", "स्थानिक\nफिचर"),
]

NP_COL_WIDTHS_CM = [
    1.0,   # सि.नं.
    5.0,   # कृयाकलाप
    2.2,   # कार्यक्रम
    1.0,   # इकाइ
    2.5,   # वार्षिक परिमाण
    2.5,   # वार्षिक बजेट
    1.5,   # जम्मा बजेट (हजार) — narrow, 2-3 digit value
    1.5,   # स्थान प्रकार
    3.2,   # स्थान विवरण
    2.2,   # स्थानिक फिचर
]

def _add_activity_plan_detail_table(doc: Document, val: list):
    if not val or not isinstance(val, list):
        return
    keys = [eng_key for eng_key, _ in NP_HEADERS_ACTIVITY_PLAN if eng_key in val[0]]
    headers = [np_header for eng_key, np_header in NP_HEADERS_ACTIVITY_PLAN if eng_key in val[0]]
    widths = [NP_COL_WIDTHS_CM[i] for i, (eng_key, _) in enumerate(NP_HEADERS_ACTIVITY_PLAN) if eng_key in val[0]]
    num_cols = len(keys)
    num_rows = len(val) + 1
    tbl = doc.add_table(rows=num_rows, cols=num_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"
    tbl.autofit = False
    for ci, np_header in enumerate(headers):
        cell = tbl.cell(0, ci)
        cell.width = Cm(widths[ci])
        lines = np_header.split("\n")
        for li, line in enumerate(lines):
            if li == 0:
                cell.text = ""
            p = cell.add_paragraph() if li > 0 else cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(line)
            run.font.size = Pt(9)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
        _set_cell_shading(cell, "006400")
    for ri, row in enumerate(val, 1):
        for ci, key in enumerate(keys):
            cell = tbl.cell(ri, ci)
            cell.width = Cm(widths[ci])
            val_raw = row.get(key, "")
            if key == "total_budget":
                try:
                    val_raw = round(float(val_raw) / 1000)
                except (ValueError, TypeError):
                    pass
            cell.text = _fmt_value(val_raw, "ya_activity_plan_detail")
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    doc.add_paragraph()


def _add_text_content(doc: Document, text: str, calculation_id: UUID = None, db: Session = None, raw_data: dict = None, table_cache: dict = None):
    text = _fix( text)
    parts = re.split(r"(\{\{chart:\w+\}\}|\{\{map:\w+\}\}|\{\{table:\w+\}\})", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue

        chart_match = re.match(r"\{\{chart:(\w+)\}\}", part)
        map_match = re.match(r"\{\{map:(\w+)\}\}", part)
        table_match = re.match(r"\{\{table:(\w+)\}\}", part)

        if chart_match and raw_data:
            _add_chart_from_type(doc, chart_match.group(1), raw_data, calculation_id)
        elif map_match and calculation_id and db:
            _add_map_standard(doc, map_match.group(1), calculation_id, db)
        elif table_match and calculation_id:
            _add_table_inline(doc, table_match.group(1), table_cache)
        else:
            var_match = re.match(r"^\{\{(\w+(?::\w+)*)\}\}$", part)
            if var_match and raw_data:
                var_name = var_match.group(1)
                if var_name.endswith(":full"):
                    _add_section_full_docx(doc, var_name, raw_data, calculation_id)
                    continue
                if not var_name.startswith("chart:") and not var_name.startswith("map:") and not var_name.startswith("table:"):
                    var_val = _resolve_var_from_raw(var_name, raw_data)
                    if isinstance(var_val, list):
                        if var_name == "uc_members":
                            _add_uc_members_table(doc, var_val)
                            continue
                        if var_name == "ya_activity_plan_detail":
                            _add_activity_plan_detail_table(doc, var_val)
                            continue
                        _add_list_table(doc, var_val, var_name)
                        continue
                    if var_val is not None and not isinstance(var_val, (dict, list)):
                        p = doc.add_paragraph()
                        p.paragraph_format.space_after = Pt(6)
                        run = p.add_run(_fmt_value(var_val, var_name))
                        run.font.size = Pt(11)
                        continue

            for para_text in part.split("\n"):
                para_text = para_text.strip()
                if not para_text:
                    continue
                line_var_match = re.match(r"^\{\{(\w+(?::\w+)*)\}\}$", para_text)
                if line_var_match and raw_data:
                    var_name = line_var_match.group(1)
                    if var_name.endswith(":full"):
                        _add_section_full_docx(doc, var_name, raw_data, calculation_id)
                        continue
                    if not var_name.startswith("chart:") and not var_name.startswith("map:") and not var_name.startswith("table:"):
                        var_val = _resolve_var_from_raw(var_name, raw_data)
                        if isinstance(var_val, list):
                            if var_name == "uc_members":
                                _add_uc_members_table(doc, var_val)
                                continue
                            _add_list_table(doc, var_val, var_name)
                            continue
                        if var_val is not None and not isinstance(var_val, (dict, list)):
                            p = doc.add_paragraph()
                            p.paragraph_format.space_after = Pt(6)
                            run = p.add_run(_fmt_value(var_val, var_name))
                            run.font.size = Pt(11)
                            continue
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.line_spacing = 1.15
                if raw_data:
                    para_text = re.sub(r'\{\{(\w+(?::\w+)*)\}\}', lambda m: _resolve_var_text(m.group(0), raw_data) if not m.group(1).startswith(('chart:', 'map:', 'table:')) else m.group(0), para_text)
                run = p.add_run(_fix( para_text))
                run.font.size = Pt(11)
                run.font.name = "Nirmala UI"


def _add_section_full_docx(doc: Document, var_name: str, raw_data: dict, calculation_id: UUID = None):
    section_name = var_name.replace("section:", "").replace(":full", "")
    key = f"section:{section_name}"
    sections = raw_data.get("section_generators", {})
    narrative = sections.get(key, "")
    if not narrative:
        return
    title_np, title_en = _SECTION_TITLES.get(section_name, (section_name, section_name))
    heading = doc.add_heading(_fix(title_np), level=2)
    for r in heading.runs:
        r.font.color.rgb = _COVER_GREEN
    if title_en != title_np:
        sub = doc.add_paragraph()
        run = sub.add_run(_fix(title_en))
        run.font.size = Pt(10)
        run.font.italic = True
        run.font.color.rgb = RGBColor(120, 120, 120)
        sub.paragraph_format.space_after = Pt(6)
    for para_text in narrative.split("\n"):
        para_text = para_text.strip()
        if not para_text:
            continue
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(_fix(para_text))
        run.font.size = Pt(11)
        run.font.name = "Nirmala UI"
    chart_type = _SECTION_CHARTS.get(section_name)
    if chart_type:
        _add_chart_from_type(doc, chart_type, raw_data, calculation_id)


def _add_table_inline(doc: Document, table_id: str, table_cache: dict = None):
    table_data = (table_cache or {}).get(table_id)

    if not table_data or not table_data.rows:
        p = doc.add_paragraph()
        run = p.add_run(f"[Table data not available: {table_id}]")
        run.font.italic = True
        run.font.color.rgb = RGBColor(200, 0, 0)
        return

    rows = table_data.rows
    headers = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
    data_rows = [[_fix( format_devanagari(r.get(h, ""))) for h in headers] for r in rows] if headers else rows
    num_cols = len(headers) if headers else len(rows[0]) if rows else 1
    num_rows = len(rows) + 1

    tbl = doc.add_table(rows=num_rows, cols=num_cols)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = 'Table Grid'

    for ci, header in enumerate(headers):
        cell = tbl.cell(0, ci)
        cell.text = header.replace("_", " ").title()
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(9)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)
        _set_cell_shading(cell, "006400")

    for ri, row in enumerate(data_rows, 1):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = val
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)

    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap_p.add_run(table_id.replace("_", " ").title())
    run.font.size = Pt(9)
    run.font.italic = True
    doc.add_paragraph()


def _add_chart_from_type(doc: Document, chart_type: str, raw_data: dict, calculation_id: UUID = None):
    # Check cache first
    if calculation_id:
        cached = _chart_cache_get(calculation_id, chart_type)
        if cached:
            doc.add_picture(cached, width=Inches(5.0))
            cap_p = doc.add_paragraph()
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap_p.add_run(chart_type.replace("_", " ").title())
            run.font.size = Pt(9)
            run.font.italic = True
            run.font.color.rgb = RGBColor(100, 100, 100)
            doc.add_paragraph()
            return

    forest_name = raw_data.get("basic_info", {}).get("forest_name", "")
    language = raw_data.get("basic_info", {}).get("language", "NP")
    img_data = None

    if chart_type == "species_pie" or chart_type == "species_composition_pie":
        species = raw_data.get("species", {})
        if isinstance(species, dict):
            species = species.get("species_list", [])
        if isinstance(species, dict):
            species = species.get("species_list", [])
        img_data = generate_species_pie(species, forest_name, top_n=8)
    elif chart_type in ("species_composition_pie_fi",):
        fi = raw_data.get("field_inventory", {})
        comp = fi.get("fi_species_composition", {})
        if comp and isinstance(comp, dict):
            species_list = [
                {"scientific_name": k, "local_name": "", "availability_rank": i}
                for i, (k, _) in enumerate(
                    sorted(comp.items(), key=lambda x: x[1], reverse=True)
                )
            ]
            img_data = generate_species_pie(species_list, forest_name, top_n=8)
    elif chart_type == "forest_type_pie" or chart_type == "forest_type":
        ra = raw_data.get("raster_analysis", {})
        ft = ra.get("forest_type", {}).get("percentages", {})
        img_data = generate_forest_type_pie(ft, forest_name, language=language)
    elif chart_type == "block_area_bar":
        blocks = raw_data.get("blocks", {}).get("blocks", [])
        img_data = generate_block_area_bar(blocks, forest_name, language=language)
    elif chart_type == "dbh_histogram":
        inv = raw_data.get("inventory", {})
        dbh = inv.get("dbh_summary", {}) or inv.get("dbh_distribution", {})
        img_data = generate_dbh_histogram(dbh, forest_name)
    elif chart_type == "biomass_bar":
        bi = raw_data.get("basic_info", {})
        agb = bi.get("above_ground_biomass_tons", 0) or bi.get("agb_total", 0)
        carbon = bi.get("carbon_stock_tc", 0) or bi.get("carbon_stock", 0)
        img_data = generate_biomass_bar(agb, carbon, forest_name, language=language)
    elif chart_type in ("slope_pie", "slope_bar"):
        ra = raw_data.get("raster_analysis", {})
        sp = ra.get("slope", {}).get("percentages", {})
        dom = ra.get("slope", {}).get("dominant_class", "")
        img_data = generate_slope_pie(sp, dom, forest_name, language=language)
    elif chart_type in ("canopy_pie", "canopy_bar"):
        ra = raw_data.get("raster_analysis", {})
        cp = ra.get("canopy", {}).get("percentages", {})
        dom = ra.get("canopy", {}).get("dominant_class", "")
        img_data = generate_canopy_pie(cp, dom, forest_name, language=language)
    elif chart_type == "landcover_pie":
        ra = raw_data.get("raster_analysis", {})
        lc = ra.get("landcover", {}).get("percentages", {})
        dom = ra.get("landcover", {}).get("dominant_class", "")
        img_data = generate_landcover_pie(lc, dom, forest_name, language=language)
    elif chart_type == "forest_health_pie":
        ra = raw_data.get("raster_analysis", {})
        fh = ra.get("forest_health", {}).get("percentages", {})
        if fh:
            fh_colors = [_HEALTH_COLORS_MAP.get(k, "#95a5a6") for k in fh.keys()]
            img_data = _chart_from_data(list(fh.keys()), list(fh.values()), forest_name, "Forest Health", colors=fh_colors, legend_cols=2)
    elif chart_type == "aspect_rose":
        ra = raw_data.get("raster_analysis", {})
        ap = ra.get("aspect", {}).get("percentages", {})
        if ap:
            asp_colors = [_ASPECT_COLORS_MAP.get(k, "#95a5a6") for k in ap.keys()]
            img_data = _chart_from_data(list(ap.keys()), list(ap.values()), forest_name, "Aspect Distribution", colors=asp_colors, legend_cols=4)
    elif chart_type == "nasa_forest_2020_pie":
        rd = raw_data.get("result_data", {})
        pct = rd.get("whole_nasa_forest_2020_percentages", {})
        if pct and isinstance(pct, dict):
            items = {k: v for k, v in pct.items() if v > 0}
            if items:
                nasa_colors = [_NASA_FOREST_QUALITY_COLORS.get(k, "#95a5a6") for k in items.keys()]
                img_data = _chart_from_data(list(items.keys()), list(items.values()), forest_name, "Forest Quality", colors=nasa_colors)
    elif chart_type == "soil_bar":
        ra = raw_data.get("raster_analysis", {})
        sp = ra.get("soil", {}).get("percentages", {})
        if not sp:
            rd = raw_data.get("result_data", {})
            props = rd.get("soil_properties", {})
            if props and props.get("clay_pct") is not None:
                sp = {"Clay": props["clay_pct"], "Sand": props["sand_pct"], "Silt": props["silt_pct"]}
        if sp:
            img_data = _chart_from_data(list(sp.keys()), list(sp.values()), forest_name, "Soil Distribution", is_pie=False, colors=_SOIL_BAR_COLORS[:len(sp)])
    elif chart_type == "hh_prosperity_pie":
        hh = raw_data.get("households", {}).get("prosperity_distribution", {})
        if hh and isinstance(hh, dict):
            img_data = _chart_from_data(list(hh.keys()), list(hh.values()), forest_name, "Prosperity Distribution")
    elif chart_type == "hh_caste_bar":
        hh = raw_data.get("households", {}).get("caste_distribution", {})
        if hh and isinstance(hh, dict):
            img_data = _chart_from_data(list(hh.keys()), list(hh.values()), forest_name, "Caste Distribution", is_pie=False)
    elif chart_type == "budget_bar":
        acts = raw_data.get("activities", {})
        activities = acts.get("activities", [])
        if activities:
            labels = [f"Activity {a.get('activity_id', i+1)}" for i, a in enumerate(activities)]
            values = [a.get("default_quantity", 0) or sum(yd.get("budget", 0) for yd in a.get("yearly_details", [])) for a in activities]
            img_data = _chart_from_data(labels, values, forest_name, "Budget", is_pie=False)
    elif chart_type == "ya_budget_year_bar":
        yp = raw_data.get("yearly_plan", {})
        trend = yp.get("budget_year_trend", {})
        if trend and isinstance(trend, dict):
            labels = [f"Year {k}" for k in sorted(trend.keys(), key=int)]
            values = [trend[k] for k in sorted(trend.keys(), key=int)]
            year_colors = ["#2ecc71", "#27ae60", "#1abc9c", "#16a085", "#3498db",
                           "#2980b9", "#9b59b6", "#8e44ad", "#e67e22", "#d35400"]
            img_data = _chart_from_data(labels, values, forest_name,
                                         "वार्षिक बजेट वितरण (Year-wise Budget)",
                                         is_pie=False, colors=year_colors[:len(labels)])
    elif chart_type == "ya_program_pie":
        yp = raw_data.get("yearly_plan", {})
        pie_data = yp.get("program_pie_data", {})
        if pie_data and isinstance(pie_data, dict):
            prog_items = {k: v for k, v in pie_data.items() if v > 0}
            if prog_items:
                prog_colors = ["#27ae60", "#2980b9", "#e67e22", "#e74c3c",
                               "#9b59b6", "#f1c40f", "#1abc9c", "#2c3e50"]
                img_data = _chart_from_data(list(prog_items.keys()), list(prog_items.values()),
                                             forest_name, "कार्यक्रम अनुसार बजेट (Program Budget)",
                                             colors=prog_colors[:len(prog_items)])
    elif chart_type == "dbh_class_bar":
        cd = raw_data.get("field_inventory", {}).get("fi_dbh_class_chart_data", [])
        if cd:
            labels = [d["label"] for d in cd]
            values = [d["count_per_ha"] for d in cd]
            total = sum(values)
            pcts = [v / total * 100 if total > 0 else 0 for v in values]
            dbh_colors = ["#1a6e34", "#2d8f4e", "#45b068", "#6fc48a", "#99d8ae", "#c2ebd0"]
            img_data = _chart_from_data(labels, values, forest_name, "ब्यास क्लास अनुसार रूख संख्या (संख्या/हे.)",
                                         is_pie=False, colors=dbh_colors[:len(labels)], percentages=pcts)
    elif chart_type == "dbh_class_count_bar":
        cd = raw_data.get("field_inventory", {}).get("fi_dbh_class_chart_data", [])
        if cd:
            labels = [d["label"] for d in cd]
            values = [d["count_per_ha"] for d in cd]
            total = sum(values)
            pcts = [v / total * 100 if total > 0 else 0 for v in values]
            dbh_colors = ["#1a6e34", "#2d8f4e", "#45b068", "#6fc48a", "#99d8ae", "#c2ebd0"]
            img_data = _chart_from_data(labels, values, forest_name, "ब्यास क्लास अनुसार रूख संख्या (संख्या/हे.)",
                                         is_pie=False, colors=dbh_colors[:len(labels)], percentages=pcts)

    if img_data:
        try:
            if img_data.startswith("data:"):
                from base64 import b64decode
                encoded = img_data.split(",")[1]
                img_bytes = b64decode(encoded)
                doc.add_picture(BytesIO(img_bytes), width=Inches(5.0))
                if calculation_id:
                    _chart_cache_set(calculation_id, chart_type, BytesIO(img_bytes))
            else:
                with open(img_data, "rb") as _f:
                    img_bytes = _f.read()
                doc.add_picture(img_data, width=Inches(5.0))
                if calculation_id:
                    _chart_cache_set(calculation_id, chart_type, BytesIO(img_bytes))
            cap_p = doc.add_paragraph()
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap_p.add_run(chart_type.replace("_", " ").title())
            run.font.size = Pt(9)
            run.font.italic = True
            run.font.color.rgb = RGBColor(100, 100, 100)
            doc.add_paragraph()
            return
        except Exception:
            pass

    p = doc.add_paragraph()
    run = p.add_run(f"[Chart data not available: {chart_type}]")
    run.font.italic = True
    run.font.color.rgb = RGBColor(200, 0, 0)


def _dev_val(v):
    """Format a value with Devanagari digits + %."""
    return format_devanagari(v, 1) + "%"

def _chart_from_data(labels, values, forest_name, title, is_pie=True, colors=None, legend_cols=3, percentages=None):
    _ensure_dev_font()
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    if is_pie:
        if colors is None:
            colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        wedges, texts = ax.pie(
            values, labels=None, startangle=90,
            colors=colors,
        )
        legend_labels = [f"{l} ({_dev_val(v)})" for l, v in zip(labels, values)]
        ax.legend(
            wedges, legend_labels, loc='lower center',
            bbox_to_anchor=(0.5, -0.18), ncol=min(legend_cols, len(labels)),
            fontsize=7, frameon=False,
        )
        ax.set_title(f'{forest_name} - {title}', fontsize=11, fontweight='bold', pad=15)
    else:
        if colors is None:
            colors = ['#2ecc71', '#3498db', '#e67e22', '#e74c3c', '#9b59b6', '#f1c40f']
        bars = ax.bar(range(len(labels)), values, color=colors[:len(labels)], edgecolor='white')
        for i, (bar, val) in enumerate(zip(bars, values)):
            if percentages and i < len(percentages):
                label_text = f"{format_devanagari(val, 1)} ({format_devanagari(percentages[i], 1)}%)"
            else:
                label_text = format_devanagari(val, 1)
            ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + max(values)*0.01,
                    label_text, ha='center', va='bottom', fontsize=7)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('Value', fontsize=10)
        ax.set_title(f'{forest_name} - {title}', fontsize=11, fontweight='bold')
        ax.yaxis.grid(True, alpha=0.3)

    fig.tight_layout()
    if is_pie:
        fig.subplots_adjust(bottom=0.28)
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    from base64 import b64encode
    return f"data:image/png;base64,{b64encode(buf.read()).decode()}"


def _add_map_standard(doc: Document, map_type: str, calculation_id: UUID, db: Session, forest_name: str = "CF"):
    from app.services.management_plan_docx.plan_map_service import generate_standard_map, LAYER_LABELS

    alias_map = {"boundary_map": "boundary"}
    layer_name = alias_map.get(map_type, map_type)
    known_layers = {"boundary","forest_type","forest_health","slope","biomass","landcover","soil_texture","dem","aspect","canopy","sampling_plot","sampling_plot_topo","sampling_plot_satellite","fieldbook"}

    if layer_name not in known_layers:
        p = doc.add_paragraph()
        run = p.add_run(f"[Unknown map type: {map_type}]")
        run.font.italic = True
        run.font.color.rgb = RGBColor(200, 0, 0)
        return

    try:
        buf = generate_standard_map(db, calculation_id, layer_name, forest_name=forest_name)
        buf.seek(0)
        doc.add_picture(buf, width=Inches(5.5))
    except Exception:
        buf = None

    if buf:
        labels = LAYER_LABELS.get(layer_name, {"ne": layer_name, "en": layer_name})
        cap_p = doc.add_paragraph()
        cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cap_p.add_run(labels.get("en", layer_name))
        run.font.size = Pt(9)
        run.font.italic = True
        run.font.color.rgb = RGBColor(100, 100, 100)
        doc.add_paragraph()
    else:
        p = doc.add_paragraph()
        run = p.add_run(f"[Map: {map_type}] - data not available")
        run.font.italic = True
        run.font.color.rgb = RGBColor(200, 0, 0)


def _add_chart(doc: Document, node: TreeNode, raw_data: Dict[str, Any], calculation_id: UUID = None):
    # Check cache first
    if calculation_id and node.chart_type:
        cached = _chart_cache_get(calculation_id, node.chart_type)
        if cached:
            doc.add_picture(cached, width=Inches(5.5))
            cap_p = doc.add_paragraph()
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap_p.add_run(node.title_ne or "Chart")
            run.font.size = Pt(9)
            run.font.italic = True
            run.font.color.rgb = RGBColor(100, 100, 100)
            doc.add_paragraph()
            return

    forest_name = raw_data.get("basic_info", {}).get("forest_name", "")
    language = raw_data.get("basic_info", {}).get("language", "NP")
    img_data = None

    if node.chart_type == "species_pie":
        species = raw_data.get("species", [])
        if isinstance(species, dict):
            species = species.get("species_list", [])
        img_data = generate_species_pie(species, forest_name, top_n=8)
    elif node.chart_type == "species_composition_pie_fi":
        fi = raw_data.get("field_inventory", {})
        comp = fi.get("fi_species_composition", {})
        if comp and isinstance(comp, dict):
            species_list = [
                {"scientific_name": k, "local_name": "", "availability_rank": i}
                for i, (k, _) in enumerate(
                    sorted(comp.items(), key=lambda x: x[1], reverse=True)
                )
            ]
            img_data = generate_species_pie(species_list, forest_name, top_n=8)
    elif node.chart_type == "forest_type_pie":
        ra = raw_data.get("raster_analysis", {})
        ft = ra.get("forest_type", {}).get("percentages", {})
        img_data = generate_forest_type_pie(ft, forest_name, language=language)
    elif node.chart_type == "block_area_bar":
        blocks = raw_data.get("blocks", {}).get("blocks", [])
        img_data = generate_block_area_bar(blocks, forest_name, language=language)
    elif node.chart_type == "dbh_histogram":
        inv = raw_data.get("inventory", {}).get("dbh_distribution", {})
        img_data = generate_dbh_histogram(inv, forest_name)
    elif node.chart_type == "biomass_bar":
        bi = raw_data.get("basic_info", {})
        agb = bi.get("above_ground_biomass_tons", 0)
        carbon = bi.get("carbon_stock_tc", 0)
        img_data = generate_biomass_bar(agb, carbon, forest_name, language=language)
    elif node.chart_type == "slope_pie":
        ra = raw_data.get("raster_analysis", {})
        sp = ra.get("slope", {}).get("percentages", {})
        dom = ra.get("slope", {}).get("dominant_class", "")
        img_data = generate_slope_pie(sp, dom, forest_name, language=language)
    elif node.chart_type == "canopy_pie":
        ra = raw_data.get("raster_analysis", {})
        cp = ra.get("canopy", {}).get("percentages", {})
        dom = ra.get("canopy", {}).get("dominant_class", "")
        img_data = generate_canopy_pie(cp, dom, forest_name, language=language)
    elif node.chart_type == "landcover_pie":
        ra = raw_data.get("raster_analysis", {})
        lc = ra.get("landcover", {}).get("percentages", {})
        dom = ra.get("landcover", {}).get("dominant_class", "")
        img_data = generate_landcover_pie(lc, dom, forest_name, language=language)

    if img_data:
        try:
            if img_data.startswith("data:"):
                from base64 import b64decode
                encoded = img_data.split(",")[1]
                img_bytes = b64decode(encoded)
                doc.add_picture(BytesIO(img_bytes), width=Inches(5.5))
                if calculation_id and node.chart_type:
                    _chart_cache_set(calculation_id, node.chart_type, BytesIO(img_bytes))
            else:
                with open(img_data, "rb") as _f:
                    img_bytes = _f.read()
                doc.add_picture(img_data, width=Inches(5.5))
                if calculation_id and node.chart_type:
                    _chart_cache_set(calculation_id, node.chart_type, BytesIO(img_bytes))
            cap_p = doc.add_paragraph()
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap_p.add_run(node.title_ne or "Chart")
            run.font.size = Pt(9)
            run.font.italic = True
            run.font.color.rgb = RGBColor(100, 100, 100)
            doc.add_paragraph()
            return
        except Exception:
            pass

    p = doc.add_paragraph()
    run = p.add_run(f"[Chart: {node.title_ne}] - no data available")
    run.font.italic = True
    run.font.color.rgb = RGBColor(200, 0, 0)


def _add_table(doc: Document, node: TreeNode, table_cache: dict = None):
    table_id = node.table_id
    if not table_id:
        return

    table_data = (table_cache or {}).get(table_id)

    if not table_data or not table_data.rows:
        p = doc.add_paragraph()
        run = p.add_run(f"[Table: {table_id} — no data]")
        run.font.italic = True
        run.font.color.rgb = RGBColor(150, 150, 150)
        return

    rows = table_data.rows
    if not rows:
        return

    headers = list(rows[0].keys()) if isinstance(rows[0], dict) else []
    data_rows = [[format_devanagari(r.get(h, "")) for h in headers] for r in rows] if headers else rows

    tbl = doc.add_table(rows=1 + len(data_rows), cols=len(headers) if headers else len(data_rows[0]))
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, h in enumerate(headers):
        cell = tbl.cell(0, i)
        cell.text = h
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for r in p.runs:
                r.font.bold = True
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(255, 255, 255)
        _set_cell_shading(cell, "006400")

    for ri, row in enumerate(data_rows, 1):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.text = str(val)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)

    cap_p = doc.add_paragraph()
    cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap_p.add_run(node.title_ne or table_id)
    run.font.size = Pt(9)
    run.font.italic = True


def _build_uc_members_data(val: list) -> tuple:
    """Build uc_members table data with Nepali headers, chairperson-first layout."""
    if not val or not isinstance(val, list):
        return [], []
    headers = ["पदाधिकारीको नाम", "पद", "ठेगाना", "दाँया", "बाँया", "हस्ताक्षर"]
    chairperson = None
    others = []
    for m in val:
        pos = (m.get("position") or "").strip()
        if pos == "अध्यक्ष":
            chairperson = m
        else:
            others.append(m)
    rows = []
    if chairperson:
        rows.append([
            _fix( chairperson.get("name", "")),
            _fix( chairperson.get("position", "")),
            _fix( chairperson.get("address", "")),
            "", "", "",
        ])
    rows.append(["साक्षिहरू", "", "", "", "", ""])
    for m in others:
        rows.append([
            _fix( m.get("name", "")),
            _fix( m.get("position", "")),
            _fix( m.get("address", "")),
            "", "", "",
        ])
    return headers, rows


def _add_uc_members_table(doc: Document, val: list):
    headers, rows = _build_uc_members_data(val)
    if not headers or not rows:
        return
    num_rows = len(rows) + 1
    tbl = doc.add_table(rows=num_rows, cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"
    for ci, h in enumerate(headers):
        cell = tbl.cell(0, ci)
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(9)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)
        _set_cell_shading(cell, "006400")
    for ri, row in enumerate(rows):
        tr = tbl.rows[ri + 1]._tr
        trPr = tr.get_or_add_trPr()
        h_elem = OxmlElement("w:trHeight")
        h_elem.set(qn("w:val"), "900")
        h_elem.set(qn("w:hRule"), "atLeast")
        trPr.append(h_elem)
        is_separator = ri >= 1 and row[0] == "साक्षिहरू"
        for ci, val_str in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            cell.text = val_str
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
                    if is_separator:
                        r.font.bold = True
                if is_separator:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if is_separator:
                _set_cell_shading(cell, "f0f0f0")
    doc.add_paragraph()


def _add_uc_members_table_html(parts: list, val: list, var_name: str = ""):
    headers, rows = _build_uc_members_data(val)
    if not headers or not rows:
        return
    parts.append('<div class="table-preview"><table class="data" style="border-collapse:collapse;width:100%"><thead><tr>')
    for h in headers:
        parts.append(f'<th style="background:#006400;color:white;padding:8px;font-size:9pt;text-align:center;border:1px solid #006400">{_html_escape(h)}</th>')
    parts.append('</tr></thead><tbody>')
    for ri, row in enumerate(rows):
        is_separator = ri >= 1 and row[0] == "साक्षिहरू"
        bg = "#f0f0f0" if is_separator else "transparent"
        style = f'background:{bg};'
        parts.append(f'<tr style="{style}">')
        for ci, val_str in enumerate(row):
            align = "center" if is_separator and ci == 0 else "left"
            parts.append(f'<td style="padding:8px;font-size:9pt;border:1px solid #ddd;text-align:{align}">{_html_escape(val_str)}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')

def _add_activity_plan_detail_table_html(parts: list, val: list):
    if not val or not isinstance(val, list):
        return
    keys = [eng_key for eng_key, _ in NP_HEADERS_ACTIVITY_PLAN if eng_key in val[0]]
    headers = [np_header for eng_key, np_header in NP_HEADERS_ACTIVITY_PLAN if eng_key in val[0]]
    parts.append('<div class="table-preview"><table class="data" style="border-collapse:collapse;width:100%"><thead><tr>')
    for np_header in headers:
        display = _html_escape(np_header).replace("\n", "<br>")
        parts.append(f'<th style="background:#006400;color:white;padding:6px 8px;font-size:9pt;text-align:center;border:1px solid #006400;white-space:nowrap;">{display}</th>')
    parts.append('</tr></thead><tbody>')
    for row in val:
        parts.append('<tr>')
        for key in keys:
            val_raw = row.get(key, "")
            if key == "total_budget":
                try:
                    val_raw = round(float(val_raw) / 1000)
                except (ValueError, TypeError):
                    pass
            parts.append(f'<td style="padding:6px 8px;font-size:9pt;border:1px solid #ddd;">{_html_escape(_fmt_value(val_raw, "ya_activity_plan_detail"))}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')


def _add_static_table(doc: Document, node: TreeNode, raw_data: dict = None):
    data = node.static_table or {}
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    if not columns or not rows:
        p = doc.add_paragraph()
        run = p.add_run("[Static table — no data]")
        run.font.italic = True
        run.font.color.rgb = RGBColor(200, 0, 0)
        return
    tbl = doc.add_table(rows=1 + len(rows), cols=len(columns))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"
    for ci, h in enumerate(columns):
        cell = tbl.cell(0, ci)
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.font.size = Pt(9)
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)
        _set_cell_shading(cell, "006400")
    for ri, row in enumerate(rows, 1):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell_text = str(val) if val is not None else ""
            if raw_data and cell_text.startswith("{{") and cell_text.endswith("}}"):
                cell_text = _resolve_var_text(cell_text, raw_data)
            cell.text = _fix( cell_text)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
    doc.add_paragraph()


def _add_map(doc: Document, node: TreeNode, calculation_id: UUID, db: Session, calc_cache: dict = None):
    if node.map_type:
        forest_name = (calc_cache or {}).get("forest_name", "CF")
        _add_map_standard(doc, node.map_type, calculation_id, db, forest_name)
        return

    calc = calc_cache.get("calculation") if calc_cache else None
    if not calc:
        calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    if not calc:
        return

    forest_name = calc.forest_name or "CF"
    boundary_geojson = None
    blocks = []

    if calc.boundary_geom:
        try:
            shape = to_shape(calc.boundary_geom)
            boundary_geojson = mapping(shape)
        except Exception:
            pass

    cached_blocks = (calc_cache or {}).get("blocks")
    forest_blocks = cached_blocks if cached_blocks is not None else db.query(ForestBlock).filter(
        ForestBlock.calculation_id == calculation_id
    ).order_by(ForestBlock.index).all()

    for fb in forest_blocks:
        try:
            shape = to_shape(fb.geometry)
            geom = mapping(shape)
            centroid = {
                "lon": shape.centroid.x if hasattr(shape, 'centroid') else 0,
                "lat": shape.centroid.y if hasattr(shape, 'centroid') else 0,
            }
            blocks.append({
                "name": fb.name,
                "geometry": geom,
                "centroid": centroid,
                "area_hectares": fb.area_hectares,
            })
        except Exception:
            pass

    img_data = generate_boundary_map(boundary_geojson, forest_name, blocks if blocks else None)

    if img_data:
        try:
            if img_data.startswith("data:"):
                from base64 import b64decode
                encoded = img_data.split(",")[1]
                doc.add_picture(BytesIO(b64decode(encoded)), width=Inches(5.5))
            else:
                doc.add_picture(img_data, width=Inches(5.5))
            cap_p = doc.add_paragraph()
            cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap_p.add_run(node.title_ne or "Forest Boundary Map")
            run.font.size = Pt(9)
            run.font.italic = True
            run.font.color.rgb = RGBColor(100, 100, 100)
            doc.add_paragraph()
            return
        except Exception:
            pass

    p = doc.add_paragraph()
    run = p.add_run(f"[Map: {node.title_ne}] - no boundary or block data available")
    run.font.italic = True
    run.font.color.rgb = RGBColor(200, 0, 0)


def _walk_tree(doc: Document, nodes: List[TreeNode], calculation_id: UUID,
               raw_data: Dict[str, Any], db: Session,
               table_cache: dict = None, calc_cache: dict = None):
    for node in nodes:
        if node.hidden_in_export or node.deleted:
            continue

        has_content = node.content_type == "richtext" and node.content and node.content.strip()
        is_chart = node.content_type == "chart" and node.chart_type
        is_table = node.content_type == "table" and node.table_id
        is_static_table = node.content_type == "static_table"
        is_map = node.content_type == "map"
        has_children = any((not c.hidden_in_export and not c.deleted) for c in node.children)

        if has_content or is_chart or is_table or is_static_table or is_map or has_children:
            if node.type in ("section", "preamble", "appendix"):
                doc.add_page_break()
            _add_heading(doc, node)

        if has_content:
            _add_text_content(doc, node.content, calculation_id, db, raw_data, table_cache)

        if is_chart:
            _add_chart(doc, node, raw_data, calculation_id)

        if is_table:
            _add_table(doc, node, table_cache)

        if is_static_table:
            _add_static_table(doc, node, raw_data)

        if is_map:
            _add_map(doc, node, calculation_id, db, calc_cache)

        if has_children:
            _walk_tree(doc, node.children, calculation_id, raw_data, db, table_cache, calc_cache)

        if has_content or is_chart or is_table or is_static_table or is_map or has_children:
            doc.add_paragraph()


# ═══════════════════════════════════════════════════════
# HTML Preview Functions
# ═══════════════════════════════════════════════════════

def _walk_tree_html(nodes: List[TreeNode], calculation_id: UUID,
                    raw_data: Dict[str, Any], db: Session,
                    table_cache: dict = None) -> str:
    parts = []
    for node in nodes:
        if node.hidden_in_export or node.deleted:
            continue
        has_content = node.content_type == "richtext" and node.content and node.content.strip()
        is_chart = node.content_type == "chart" and node.chart_type
        is_table = node.content_type == "table" and node.table_id
        is_static_table = node.content_type == "static_table"
        is_map = node.content_type == "map"
        has_children = any((not c.hidden_in_export and not c.deleted) for c in node.children)
        if not (has_content or is_chart or is_table or is_static_table or is_map or has_children):
            continue

        num = f"{node.number}. " if node.number else ""
        tag = "h2" if node.type in ("subsection",) else "h1"
        parts.append(f'<div class="section" id="{node.id}">')
        parts.append(f'<{tag}>{num}{node.title_ne}</{tag}>')

        if has_content:
            escaped = _html_escape(node.content)
            escaped = re.sub(
                r'\{\{chart:(\w+)\}\}',
                r'<div class="chart-placeholder">📊 \1<br><small>Rendered as PNG in DOCX</small></div>',
                escaped
            )
            escaped = re.sub(
                r'\{\{map:(\w+)\}\}',
                r'<div class="chart-placeholder">🗺️ \1<br><small>Rendered as PNG in DOCX</small></div>',
                escaped
            )
            escaped = re.sub(
                r'\{\{table:(\w+)\}\}',
                r'<div class="chart-placeholder">📋 \1<br><small>Rendered as table in DOCX</small></div>',
                escaped
            )
            escaped = _render_html_list_vars(escaped, raw_data)
            escaped = re.sub(
                r'\{\{section:(\w+):full\}\}',
                lambda m: _render_section_full_html(m.group(1), raw_data, calculation_id),
                escaped
            )
            parts.append(f'<div class="section-content">{escaped}</div>')

        if is_chart:
            chart_labels = {
                "species_pie": "Species Composition Pie Chart",
                "species_composition_pie_fi": "प्रजाति संरचना पाई चार्ट (क्षेत्र सर्वेक्षण)",
                "forest_type_pie": "Forest Type Distribution Pie Chart",
                "block_area_bar": "Block-wise Area Bar Chart",
                "dbh_histogram": "DBH Class Distribution Histogram",
                "biomass_bar": "Biomass & Carbon Stock Bar Chart",
                "slope_pie": "Slope Classification Pie Chart",
                "canopy_pie": "Canopy Cover Pie Chart",
                "landcover_pie": "Landcover Distribution Pie Chart",
            }
            label = chart_labels.get(node.chart_type, "Chart")
            parts.append(f'<div class="chart-placeholder">📊 {label}<br><small>Rendered as PNG in DOCX</small></div>')

        if is_map:
            parts.append(f'<div class="chart-placeholder">🗺️ {node.title_ne}<br><small>Rendered as PNG in DOCX</small></div>')

        if is_table:
            _add_table_html(parts, node, table_cache)

        if is_static_table:
            _add_static_table_html(parts, node, raw_data)

        if has_children:
            parts.append(_walk_tree_html(node.children, calculation_id, raw_data, db, table_cache))

        parts.append('</div>')
    return "\n".join(parts)


def _add_table_html(parts: List[str], node: TreeNode, table_cache: dict = None):
    table_id = node.table_id
    if not table_id:
        return
    table_data = (table_cache or {}).get(table_id)
    if not table_data or not table_data.rows:
        parts.append(f'<div class="chart-placeholder">📋 {table_id} — no data</div>')
        return
    rows = table_data.rows
    if not rows:
        return
    headers = list(rows[0].keys()) if isinstance(rows[0], dict) else []
    parts.append('<div class="table-preview"><table class="data"><thead><tr>')
    for h in headers:
        parts.append(f'<th>{_html_escape(h)}</th>')
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        for h in headers:
            val = format_devanagari(row.get(h, ""))
            parts.append(f'<td>{_html_escape(val)}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')


def _add_static_table_html(parts: List[str], node: TreeNode, raw_data: dict = None):
    data = node.static_table or {}
    columns = data.get("columns", [])
    rows = data.get("rows", [])
    if not columns or not rows:
        parts.append('<div class="chart-placeholder">📋 Static table — no data</div>')
        return
    parts.append('<div class="table-preview"><table class="data"><thead><tr>')
    for h in columns:
        parts.append(f'<th>{_html_escape(h)}</th>')
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        for ci, val in enumerate(row):
            cell_text = str(val) if val is not None else ""
            if raw_data and cell_text.startswith("{{") and cell_text.endswith("}}"):
                cell_text = _resolve_var_text(cell_text, raw_data)
            parts.append(f'<td>{_html_escape(cell_text)}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')


_SECTION_TITLES = {
    "forest_summary": ("वन सारांश", "Forest Summary"),
    "slope_analysis": ("भिरालो विश्लेषण", "Slope Analysis"),
    "elevation_profile": ("उचाइ विवरण", "Elevation Profile"),
    "aspect_analysis": ("दिशा विश्लेषण", "Aspect Analysis"),
    "forest_health": ("वन स्वास्थ्य", "Forest Health"),
    "forest_type": ("वन प्रकार", "Forest Type"),
    "species_potential": ("सम्भावित प्रजातिहरू", "Potential Species"),
    "actual_species": ("वास्तविक प्रजातिहरू", "Actual Species"),
    "biodiversity": ("जैविक विविधता", "Biodiversity"),
    "canopy_structure": ("वन मुकुट", "Canopy Structure"),
    "biomass_carbon": ("जैविक पदार्थ तथा कार्बन", "Biomass & Carbon"),
    "climate_conditions": ("मौसम अवस्था", "Climate Conditions"),
    "land_cover": ("भू-आवरण", "Land Cover"),
    "forest_loss": ("वन क्षति", "Forest Loss"),
    "fire_loss": ("आगलागी क्षति", "Fire Loss"),
    "forest_quality": ("वन गुणस्तर (नासा)", "Forest Quality"),
    "soil_analysis": ("माटो विश्लेषण", "Soil Analysis"),
    "location_context": ("स्थान तथा सन्दर्भ", "Location & Context"),
    "species_distribution": ("प्रजाति वितरण", "Species Distribution"),
    "accessible_forest": ("पहुँचयोग्य वन क्षेत्र", "Accessible Forest"),
}

_SECTION_CHARTS = {
    "slope_analysis": "slope_bar",
    "aspect_analysis": "aspect_rose",
    "forest_health": "forest_health_pie",
    "forest_type": "forest_type_pie",
    "actual_species": "species_composition_pie_fi",
    "biodiversity": "species_composition_pie_fi",
    "canopy_structure": "canopy_bar",
    "land_cover": "landcover_pie",
    "forest_loss": None,
    "fire_loss": None,
    "forest_quality": "nasa_forest_2020_pie",
    "soil_analysis": "soil_bar",
}


def _render_section_full_html(section_name: str, raw_data: dict, calculation_id) -> str:
    key = f"section:{section_name}"
    sections = raw_data.get("section_generators", {})
    narrative = sections.get(key, "")
    if not narrative:
        return ""
    title_np, title_en = _SECTION_TITLES.get(section_name, (section_name, section_name))
    parts_html = [f'<div class="section-full" id="section-full-{section_name}">']
    parts_html.append(f'<h3>{_html_escape(title_np)}</h3>')
    parts_html.append(f'<p><small><em>{_html_escape(title_en)}</em></small></p>')
    parts_html.append(f'<div class="section-full-narrative"><p>{_html_escape(narrative)}</p></div>')
    chart_type = _SECTION_CHARTS.get(section_name)
    if chart_type:
        parts_html.append(
            f'<div class="chart-placeholder">📊 {chart_type}'
            f'<br><small>Rendered as PNG in DOCX</small></div>'
        )
    parts_html.append('</div>')
    return "\n".join(parts_html)


def _html_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _render_html_list_vars(text: str, raw_data: dict) -> str:
    def _replace_var(m):
        var_name = m.group(1)
        if var_name.startswith("chart:") or var_name.startswith("map:") or var_name.startswith("table:") or var_name.endswith(":full"):
            return m.group(0)
        var_val = _resolve_var_from_raw(var_name, raw_data)
        if var_val is None:
            return ""
        if isinstance(var_val, list):
            if all(isinstance(v, str) for v in var_val):
                items = "".join(f"<li>{_html_escape(v)}</li>" for v in var_val if v)
                return f"<ul>{items}</ul>" if items else ""
            if all(isinstance(v, dict) for v in var_val):
                if var_name == "uc_members":
                    parts = []
                    _add_uc_members_table_html(parts, var_val, var_name)
                    return "".join(parts)
                if var_name == "ya_activity_plan_detail":
                    parts = []
                    _add_activity_plan_detail_table_html(parts, var_val)
                    return "".join(parts)
                title_html = ""
                vdef = get_variable(var_name)
                if vdef and vdef.label_ne:
                    title_html = f'<h4 style="margin:12px 0 4px;font-size:14px;font-weight:700;">{_html_escape(vdef.label_ne)}</h4>'
                headers = list(var_val[0].keys())
                header_row = "".join(f"<th>{_html_escape(h.replace('_', ' ').title())}</th>" for h in headers)
                data_rows = ""
                for row in var_val:
                    cells = "".join(f"<td>{_html_escape(_fmt_value(row.get(h, ''), var_name))}</td>" for h in headers)
                    data_rows += f"<tr>{cells}</tr>"
                return f'{title_html}<div class="table-preview"><table class="data"><thead><tr>{header_row}</tr></thead><tbody>{data_rows}</tbody></table></div>'
            items = "".join(f"<li>{_html_escape(str(v))}</li>" for v in var_val if v)
            return f"<ul>{items}</ul>" if items else m.group(0)
        if isinstance(var_val, dict):
            items = "".join(f"<li><b>{_html_escape(k)}</b>: {_html_escape(_fmt_value(v, var_name))}</li>" for k, v in var_val.items() if v)
            return f"<ul>{items}</ul>" if items else m.group(0)
        return _html_escape(_fmt_value(var_val, var_name))
    return re.sub(r"\{\{(\w+(?::\w+)*)\}\}", _replace_var, text)


# ═══════════════════════════════════════════════════════
# DOCX Builder
# ═══════════════════════════════════════════════════════

def _build_table_cache(calculation_id: UUID, db: Session) -> dict:
    all_tables = db.query(OPTableData).filter(
        OPTableData.calculation_id == calculation_id
    ).all()
    return {t.table_id: t for t in all_tables}


def _build_calc_cache(calculation_id: UUID, db: Session) -> dict:
    calc = db.query(Calculation).filter(Calculation.id == calculation_id).first()
    blocks = db.query(ForestBlock).filter(
        ForestBlock.calculation_id == calculation_id
    ).order_by(ForestBlock.index).all()
    return {
        "calculation": calc,
        "blocks": blocks,
        "forest_name": calc.forest_name if calc else "CF",
    }


def build_op_document(
    plan: Dict[str, Any],
    tree: List[TreeNode],
    resolver: VariableResolver,
    calculation_id: UUID,
    db: Session,
) -> BytesIO:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Nirmala UI"
    style.font.size = Pt(11)

    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Nirmala UI")

    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    metadata = plan.get("plan_metadata", {})
    _add_cover_page(doc, plan, metadata)
    _add_toc_field(doc)

    raw_data = resolver.get_raw_data()
    raw_data["user_inputs"] = metadata.get("user_inputs", {})
    table_cache = _build_table_cache(calculation_id, db)
    calc_cache = _build_calc_cache(calculation_id, db)

    _walk_tree(doc, tree, calculation_id, raw_data, db, table_cache, calc_cache)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
