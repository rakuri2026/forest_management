"""
DOCX builder for Operational Plan export
Walks the resolved tree and builds a .docx document with headings, text, charts, and tables.
"""
from typing import Dict, Any, Optional, List
from io import BytesIO
from uuid import UUID
from sqlalchemy.orm import Session

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

from app.models.op_table import OPTableData
from app.models.forest_block import ForestBlock
from app.models.calculation import Calculation
from app.services.operational_plan.tree_models import TreeNode
from app.services.operational_plan.variable_resolver import VariableResolver
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


def _set_cell_shading(cell, color_hex: str):
    shading = cell._tc.get_or_add_tcPr()
    elem = shading.makeelement(qn("w:shd"), {
        qn("w:fill"): color_hex,
        qn("w:val"): "clear",
    })
    shading.append(elem)


def _add_cover_page(doc: Document, plan: Dict[str, Any], metadata: Dict[str, Any]):
    for _ in range(6):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("सामुदायिक वन कार्य योजना")
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = _COVER_GREEN

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("COMMUNITY FOREST OPERATIONAL PLAN")
    run.font.size = Pt(16)
    run.font.color.rgb = _SUBTITLE_GRAY

    doc.add_paragraph()

    user_inputs = metadata.get("user_inputs", {})
    hybrid = metadata.get("hybrid_overrides", {})

    details = [
        ("सामुदायिक वनको नाम (Forest Name)", plan.get("forest_name", user_inputs.get("forest_name", "..............."))),
        ("क्रम संख्या (Serial No.)", user_inputs.get("serial_number", "...............")),
        ("सामुदायिक वनको कोड (CF Code)", hybrid.get("cf_code", user_inputs.get("cf_code", "..............."))),
        ("प्रदेश/डिभिजन/सब डिभिजन/पालिका",
         f"{user_inputs.get('province', '.....')} / {user_inputs.get('division', '..........')} / "
         f"{user_inputs.get('sub_division', '..............')} / {user_inputs.get('municipality', '.........')}"),
        ("उपभोक्ता समूहको नाम (Group Name)", user_inputs.get("user_group_name", "...............")),
        ("ठेगाना (Address)", user_inputs.get("address", "...............")),
    ]

    table = doc.add_table(rows=len(details), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, (label, value) in enumerate(details):
        c0, c1 = table.cell(i, 0), table.cell(i, 1)
        c0.text = label
        c1.text = str(value)
        for cell in (c0, c1):
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(11)
                    if cell == c0:
                        r.font.bold = True

    doc.add_paragraph()
    fy_start = user_inputs.get("fy_start", "२०../..")
    fy_end = user_inputs.get("fy_end", "२०../..")
    period = doc.add_paragraph()
    period.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = period.add_run(f"आ.व. {fy_start} देखि आ.व. {fy_end} सम्म")
    run.font.size = Pt(14)
    run.font.bold = True

    period_en = doc.add_paragraph()
    period_en.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = period_en.add_run(f"FY {fy_start} TO FY {fy_end}")
    run.font.size = Pt(12)
    run.font.color.rgb = _SUBTITLE_GRAY

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
    text = f"{num}{node.title_ne}"

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
        run = sub.add_run(node.title_en)
        run.font.size = Pt(10)
        run.font.italic = True
        run.font.color.rgb = RGBColor(120, 120, 120)
        sub.paragraph_format.space_after = Pt(12)


import re

_VARIABLE_PATTERN = re.compile(r"\{\{(\w+:?\w+)\}\}")

def _add_text_content(doc: Document, text: str, calculation_id: UUID = None, db: Session = None, raw_data: dict = None, table_cache: dict = None):
    parts = re.split(r"(\{\{chart:\w+\}\}|\{\{map:\w+\}\}|\{\{table:\w+\}\})", text)
    for part in parts:
        part = part.strip()
        if not part:
            continue

        chart_match = re.match(r"\{\{chart:(\w+)\}\}", part)
        map_match = re.match(r"\{\{map:(\w+)\}\}", part)
        table_match = re.match(r"\{\{table:(\w+)\}\}", part)

        if chart_match and raw_data:
            _add_chart_from_type(doc, chart_match.group(1), raw_data)
        elif map_match and calculation_id and db:
            _add_map_standard(doc, map_match.group(1), calculation_id, db)
        elif table_match and calculation_id:
            _add_table_inline(doc, table_match.group(1), table_cache)
        else:
            for para_text in part.split("\n"):
                para_text = para_text.strip()
                if not para_text:
                    continue
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.line_spacing = 1.15
                run = p.add_run(para_text)
                run.font.size = Pt(11)
                run.font.name = "Calibri"


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
    data_rows = [[str(r.get(h, "")) for h in headers] for r in rows] if headers else rows
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


def _add_chart_from_type(doc: Document, chart_type: str, raw_data: dict):
    forest_name = raw_data.get("basic_info", {}).get("forest_name", "")
    img_data = None

    if chart_type == "species_pie" or chart_type == "species_composition_pie":
        species = raw_data.get("species", {})
        if isinstance(species, dict):
            species = species.get("species_list", [])
        if isinstance(species, dict):
            species = species.get("species_list", [])
        img_data = generate_species_pie(species, forest_name, top_n=8)
    elif chart_type == "forest_type_pie" or chart_type == "forest_type":
        ra = raw_data.get("raster_analysis", {})
        ft = ra.get("forest_type", {}).get("percentages", {})
        img_data = generate_forest_type_pie(ft, forest_name)
    elif chart_type == "block_area_bar":
        blocks = raw_data.get("blocks", {}).get("blocks", [])
        img_data = generate_block_area_bar(blocks, forest_name)
    elif chart_type == "dbh_histogram":
        inv = raw_data.get("inventory", {})
        dbh = inv.get("dbh_summary", {}) or inv.get("dbh_distribution", {})
        img_data = generate_dbh_histogram(dbh, forest_name)
    elif chart_type == "biomass_bar":
        bi = raw_data.get("basic_info", {})
        agb = bi.get("above_ground_biomass_tons", 0) or bi.get("agb_total", 0)
        carbon = bi.get("carbon_stock_tc", 0) or bi.get("carbon_stock", 0)
        img_data = generate_biomass_bar(agb, carbon, forest_name)
    elif chart_type in ("slope_pie", "slope_bar"):
        ra = raw_data.get("raster_analysis", {})
        sp = ra.get("slope", {}).get("percentages", {})
        dom = ra.get("slope", {}).get("dominant_class", "")
        img_data = generate_slope_pie(sp, dom, forest_name)
    elif chart_type in ("canopy_pie", "canopy_bar"):
        ra = raw_data.get("raster_analysis", {})
        cp = ra.get("canopy", {}).get("percentages", {})
        dom = ra.get("canopy", {}).get("dominant_class", "")
        img_data = generate_canopy_pie(cp, dom, forest_name)
    elif chart_type == "landcover_pie":
        ra = raw_data.get("raster_analysis", {})
        lc = ra.get("landcover", {}).get("percentages", {})
        dom = ra.get("landcover", {}).get("dominant_class", "")
        img_data = generate_landcover_pie(lc, dom, forest_name)
    elif chart_type == "forest_health_pie":
        ra = raw_data.get("raster_analysis", {})
        fh = ra.get("forest_health", {}).get("percentages", {})
        if fh:
            img_data = _chart_from_data(list(fh.keys()), list(fh.values()), forest_name, "Forest Health")
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

    if img_data:
        try:
            if img_data.startswith("data:"):
                from base64 import b64decode
                encoded = img_data.split(",")[1]
                doc.add_picture(BytesIO(b64decode(encoded)), width=Inches(5.0))
            else:
                doc.add_picture(img_data, width=Inches(5.0))
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


def _chart_from_data(labels, values, forest_name, title, is_pie=True):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    if is_pie:
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))
        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors, textprops={'fontsize': 8})
        ax.set_title(f'{forest_name} - {title}', fontsize=11, fontweight='bold')
    else:
        colors = ['#2ecc71', '#3498db', '#e67e22', '#e74c3c', '#9b59b6', '#f1c40f']
        ax.bar(range(len(labels)), values, color=colors[:len(labels)], edgecolor='white')
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('Value', fontsize=10)
        ax.set_title(f'{forest_name} - {title}', fontsize=11, fontweight='bold')
        ax.yaxis.grid(True, alpha=0.3)

    fig.tight_layout()
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
    known_layers = {"boundary","forest_type","forest_health","slope","biomass","landcover","soil_texture","dem","aspect","canopy"}

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


def _add_chart(doc: Document, node: TreeNode, raw_data: Dict[str, Any]):
    forest_name = raw_data.get("basic_info", {}).get("forest_name", "")
    img_data = None

    if node.chart_type == "species_pie":
        species = raw_data.get("species", [])
        if isinstance(species, dict):
            species = species.get("species_list", [])
        img_data = generate_species_pie(species, forest_name, top_n=8)
    elif node.chart_type == "forest_type_pie":
        ra = raw_data.get("raster_analysis", {})
        ft = ra.get("forest_type", {}).get("percentages", {})
        img_data = generate_forest_type_pie(ft, forest_name)
    elif node.chart_type == "block_area_bar":
        blocks = raw_data.get("blocks", {}).get("blocks", [])
        img_data = generate_block_area_bar(blocks, forest_name)
    elif node.chart_type == "dbh_histogram":
        inv = raw_data.get("inventory", {}).get("dbh_distribution", {})
        img_data = generate_dbh_histogram(inv, forest_name)
    elif node.chart_type == "biomass_bar":
        bi = raw_data.get("basic_info", {})
        agb = bi.get("above_ground_biomass_tons", 0)
        carbon = bi.get("carbon_stock_tc", 0)
        img_data = generate_biomass_bar(agb, carbon, forest_name)
    elif node.chart_type == "slope_pie":
        ra = raw_data.get("raster_analysis", {})
        sp = ra.get("slope", {}).get("percentages", {})
        dom = ra.get("slope", {}).get("dominant_class", "")
        img_data = generate_slope_pie(sp, dom, forest_name)
    elif node.chart_type == "canopy_pie":
        ra = raw_data.get("raster_analysis", {})
        cp = ra.get("canopy", {}).get("percentages", {})
        dom = ra.get("canopy", {}).get("dominant_class", "")
        img_data = generate_canopy_pie(cp, dom, forest_name)
    elif node.chart_type == "landcover_pie":
        ra = raw_data.get("raster_analysis", {})
        lc = ra.get("landcover", {}).get("percentages", {})
        dom = ra.get("landcover", {}).get("dominant_class", "")
        img_data = generate_landcover_pie(lc, dom, forest_name)

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
    data_rows = [[str(r.get(h, "")) for h in headers] for r in rows] if headers else rows

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
        if node.hidden_in_export:
            continue

        has_content = node.content_type == "richtext" and node.content and node.content.strip()
        is_chart = node.content_type == "chart" and node.chart_type
        is_table = node.content_type == "table" and node.table_id
        is_map = node.content_type == "map"
        has_children = any(not c.hidden_in_export for c in node.children)

        if has_content or is_chart or is_table or is_map or has_children:
            _add_heading(doc, node)

        if has_content:
            _add_text_content(doc, node.content, calculation_id, db, raw_data, table_cache)

        if is_chart:
            _add_chart(doc, node, raw_data)

        if is_table:
            _add_table(doc, node, table_cache)

        if is_map:
            _add_map(doc, node, calculation_id, db, calc_cache)

        if has_children:
            _walk_tree(doc, node.children, calculation_id, raw_data, db, table_cache, calc_cache)

        if has_content or is_chart or is_table or is_map or has_children:
            doc.add_paragraph()


# ═══════════════════════════════════════════════════════
# HTML Preview Functions
# ═══════════════════════════════════════════════════════

def _walk_tree_html(nodes: List[TreeNode], calculation_id: UUID,
                    raw_data: Dict[str, Any], db: Session,
                    table_cache: dict = None) -> str:
    parts = []
    for node in nodes:
        if node.hidden_in_export:
            continue
        has_content = node.content_type == "richtext" and node.content and node.content.strip()
        is_chart = node.content_type == "chart" and node.chart_type
        is_table = node.content_type == "table" and node.table_id
        is_map = node.content_type == "map"
        has_children = any(not c.hidden_in_export for c in node.children)
        if not (has_content or is_chart or is_table or is_map or has_children):
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
            parts.append(f'<div class="section-content">{escaped}</div>')

        if is_chart:
            chart_labels = {
                "species_pie": "Species Composition Pie Chart",
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
    data_rows = [[str(r.get(h, "")) for h in headers] for r in rows] if headers else rows
    parts.append('<div class="table-preview"><table class="data"><thead><tr>')
    for h in headers:
        parts.append(f'<th>{_html_escape(h)}</th>')
    parts.append('</tr></thead><tbody>')
    for row in data_rows:
        parts.append('<tr>')
        for cell in row:
            parts.append(f'<td>{_html_escape(cell)}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div>')


def _html_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


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
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    for section in doc.sections:
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    metadata = plan.get("plan_metadata", {})
    _add_cover_page(doc, plan, metadata)
    _add_toc_field(doc)

    raw_data = resolver.get_raw_data()
    table_cache = _build_table_cache(calculation_id, db)
    calc_cache = _build_calc_cache(calculation_id, db)

    _walk_tree(doc, tree, calculation_id, raw_data, db, table_cache, calc_cache)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
