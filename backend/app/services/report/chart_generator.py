"""
Chart generator for report generation
Creates chart images (PNG) from analysis data
"""
import base64
from typing import Dict, Any, List, Optional
from io import BytesIO

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def _save_or_base64(fig, output_path: str = None) -> str:
    """Save figure to file or return base64 string"""
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        return output_path

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return f"data:image/png;base64,{base64.b64encode(buf.read()).decode()}"


def generate_species_pie(species_list: List[Dict], forest_name: str = "", top_n: int = 8, output_path: str = None) -> str:
    """Species composition pie chart"""
    if not species_list:
        return ""

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)

    # Sort by rank and take top N
    sorted_species = sorted(species_list, key=lambda x: x.get('availability_rank', 999))[:top_n]

    labels = [s.get('scientific_name', 'Unknown')[:20] for s in sorted_species]
    sizes = [1] * len(sorted_species)

    colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct='', startangle=90,
        colors=colors, textprops={'fontsize': 8}
    )

    title = f'{forest_name} - Species Composition (Top {top_n})' if forest_name else f'Species Composition (Top {top_n})'
    ax.set_title(title, fontsize=11, fontweight='bold')

    return _save_or_base64(fig, output_path)


def generate_forest_type_pie(forest_type_percentages: Dict, forest_name: str = "", output_path: str = None) -> str:
    """Forest type distribution pie chart"""
    if not forest_type_percentages:
        return ""

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)

    labels = list(forest_type_percentages.keys())
    sizes = list(forest_type_percentages.values())

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct='%1.1f%%', startangle=90,
        colors=plt.cm.Greens(np.linspace(0.3, 0.9, len(labels))),
        textprops={'fontsize': 9}
    )

    title = f'{forest_name} - Forest Type Distribution' if forest_name else 'Forest Type Distribution'
    ax.set_title(title, fontsize=11, fontweight='bold')

    return _save_or_base64(fig, output_path)


def generate_slope_pie(slope_percentages: Dict, dominant: str = "", forest_name: str = "", output_path: str = None) -> str:
    """Slope class distribution pie chart"""
    if not slope_percentages:
        return ""

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)

    labels = list(slope_percentages.keys())
    sizes = list(slope_percentages.values())

    # Color gradient: green (flat) to red (steep)
    color_map = {'Flat': '#27ae60', 'Gentle': '#f1c40f', 'Moderate': '#e67e22', 'Steep': '#e74c3c', 'Very Steep': '#c0392b'}
    colors = [color_map.get(l, '#95a5a6') for l in labels]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90,
        textprops={'fontsize': 9}
    )

    dom_text = f' (Dominant: {dominant})' if dominant else ''
    title = f'{forest_name} - Slope Classification{dom_text}' if forest_name else f'Slope Classification{dom_text}'
    ax.set_title(title, fontsize=11, fontweight='bold')

    return _save_or_base64(fig, output_path)


def generate_canopy_pie(canopy_percentages: Dict, dominant: str = "", forest_name: str = "", output_path: str = None) -> str:
    """Canopy cover distribution pie chart"""
    if not canopy_percentages:
        return ""

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)

    labels = list(canopy_percentages.keys())
    sizes = list(canopy_percentages.values())

    color_map = {'Open': '#d5f5e3', 'Medium': '#82e0aa', 'Dense': '#27ae60', 'Very Dense': '#1a5c2e'}
    colors = [color_map.get(l, '#95a5a6') for l in labels]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct='%1.1f%%', colors=colors, startangle=90,
        textprops={'fontsize': 9}
    )

    dom_text = f' (Dominant: {dominant})' if dominant else ''
    title = f'{forest_name} - Canopy Cover{dom_text}' if forest_name else f'Canopy Cover{dom_text}'
    ax.set_title(title, fontsize=11, fontweight='bold')

    return _save_or_base64(fig, output_path)


def generate_landcover_pie(landcover_percentages: Dict, dominant: str = "", forest_name: str = "", top_n: int = 6, output_path: str = None) -> str:
    """Land cover distribution pie chart"""
    if not landcover_percentages:
        return ""

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)

    # Sort and take top N
    sorted_lc = sorted(landcover_percentages.items(), key=lambda x: x[1], reverse=True)[:top_n]
    labels = [lc[0] for lc in sorted_lc]
    sizes = [lc[1] for lc in sorted_lc]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct='%1.1f%%', startangle=90,
        colors=plt.cm.terrain(np.linspace(0.2, 0.9, len(labels))),
        textprops={'fontsize': 8}
    )

    dom_text = f' (Dominant: {dominant})' if dominant else ''
    title = f'{forest_name} - Land Cover{dom_text}' if forest_name else f'Land Cover{dom_text}'
    ax.set_title(title, fontsize=11, fontweight='bold')

    return _save_or_base64(fig, output_path)


def generate_aspect_rose(aspect_percentages: Dict, forest_name: str = "", output_path: str = None) -> str:
    """Aspect distribution rose diagram"""
    if not aspect_percentages:
        return ""

    fig = plt.figure(figsize=(6, 5), dpi=150)
    ax = fig.add_subplot(111, projection='polar')

    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    angles = np.linspace(0, 2 * np.pi, 8, endpoint=False)

    sizes = [aspect_percentages.get(d, 0) for d in directions]

    width = 2 * np.pi / 8

    bars = ax.bar(angles, sizes, width=width, bottom=0.0,
                  color=plt.cm.RdYlGn(np.linspace(0.3, 0.9, 8)), edgecolor='white')

    ax.set_xticks(angles)
    ax.set_xticklabels(directions, fontsize=10)
    ax.set_title(f'{forest_name} - Aspect Distribution' if forest_name else 'Aspect Distribution',
                 fontsize=11, fontweight='bold', pad=20)

    return _save_or_base64(fig, output_path)


def generate_block_area_bar(blocks: List[Dict], forest_name: str = "", output_path: str = None) -> str:
    """Block-wise area bar chart"""
    if not blocks:
        return ""

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)

    names = [b.get('name', f'Block {i+1}')[:15] for i, b in enumerate(blocks)]
    areas = [b.get('area_hectares', 0) for b in blocks]
    colors = ['#2ecc71', '#3498db', '#e67e22', '#e74c3c', '#9b59b6', '#f1c40f', '#1abc9c'][:len(blocks)]

    bars = ax.bar(names, areas, color=colors, edgecolor='white', linewidth=1.5)

    for bar, area in zip(bars, areas):
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.1,
                f'{area:.1f} ha', ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_ylabel('Area (hectares)', fontsize=11)
    title = f'{forest_name} - Block-wise Area' if forest_name else 'Block-wise Area'
    ax.set_title(title, fontsize=11, fontweight='bold')

    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    return _save_or_base64(fig, output_path)


def generate_dbh_histogram(dbh_summary: Dict, forest_name: str = "", output_path: str = None) -> str:
    """DBH class distribution histogram"""
    if not dbh_summary:
        return ""

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)

    classes = list(dbh_summary.keys())
    counts = list(dbh_summary.values())

    bars = ax.bar(range(len(classes)), counts, color='#3498db', edgecolor='white', linewidth=1.5)

    ax.set_xticks(range(len(classes)))
    ax.set_xticklabels(classes, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Number of Trees', fontsize=11)
    ax.set_xlabel('DBH Class (cm)', fontsize=11)

    title = f'{forest_name} - DBH Class Distribution' if forest_name else 'DBH Class Distribution'
    ax.set_title(title, fontsize=11, fontweight='bold')

    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    return _save_or_base64(fig, output_path)


def generate_biomass_bar(agb_total: float, carbon_stock: float, forest_name: str = "", output_path: str = None) -> str:
    """Biomass and carbon stock bar chart"""
    if agb_total == 0 and carbon_stock == 0:
        return ""

    fig, ax = plt.subplots(figsize=(5, 4), dpi=150)

    labels = ['Above Ground\nBiomass (tons)', 'Carbon Stock\n(tons)']
    values = [agb_total, carbon_stock]
    colors = ['#27ae60', '#2980b9']

    bars = ax.bar(labels, values, color=colors, edgecolor='white', linewidth=1.5)

    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2., val + 0.5,
                f'{val:.1f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

    title = f'{forest_name} - Biomass & Carbon Stock' if forest_name else 'Biomass & Carbon Stock'
    ax.set_title(title, fontsize=11, fontweight='bold')
    ax.set_ylabel('Amount (tons)', fontsize=10)

    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    return _save_or_base64(fig, output_path)
