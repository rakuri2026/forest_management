"""
Export functionality for fieldbook and sampling data.
Supports CSV, Excel, GPX, GeoJSON, and KML formats.
"""
from sqlalchemy.orm import Session
from uuid import UUID
import csv
import io
from typing import List, Dict, Any
from xml.etree import ElementTree as ET

from app.models.fieldbook import Fieldbook
from app.models.sampling import SamplingDesign


# ===========================
# Fieldbook Export Functions
# ===========================

def export_fieldbook_csv(db: Session, calculation_id: UUID) -> bytes:
    """
    Export fieldbook to CSV format.
    """
    points = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).order_by(Fieldbook.point_number).all()

    if not points:
        raise ValueError("No fieldbook points found for this calculation")

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'Point No',
        'Type',
        'Block No',
        'Block Name',
        'Longitude',
        'Latitude',
        'Easting UTM',
        'Northing UTM',
        'UTM Zone',
        'Azimuth (deg)',
        'Distance (m)',
        'Elevation (m)',
        'Verified',
        'Remarks'
    ])

    # Write data rows
    for point in points:
        writer.writerow([
            f'P{point.point_number}',
            point.point_type,
            point.block_number if point.block_number else '',
            point.block_name if point.block_name else '',
            f'{point.longitude:.7f}' if point.longitude else '',
            f'{point.latitude:.7f}' if point.latitude else '',
            f'{point.easting_utm:.2f}' if point.easting_utm else '',
            f'{point.northing_utm:.2f}' if point.northing_utm else '',
            point.utm_zone if point.utm_zone else '',
            f'{point.azimuth_to_next:.2f}' if point.azimuth_to_next else '',
            f'{point.distance_to_next:.2f}' if point.distance_to_next else '',
            f'{point.elevation:.2f}' if point.elevation else '',
            'Yes' if point.is_verified else 'No',
            point.remarks if point.remarks else ''
        ])

    return output.getvalue().encode('utf-8')


def export_fieldbook_excel(db: Session, calculation_id: UUID) -> bytes:
    """
    Export fieldbook to Excel format.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")

    points = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).order_by(Fieldbook.point_number).all()

    if not points:
        raise ValueError("No fieldbook points found for this calculation")

    # Create workbook
    wb = Workbook()

    # Summary sheet
    ws_summary = wb.active
    ws_summary.title = "Summary"

    ws_summary['A1'] = "Fieldbook Summary"
    ws_summary['A1'].font = Font(size=14, bold=True)

    summary_data = [
        ['Total Points', len(points)],
        ['Vertices', sum(1 for p in points if p.point_type == 'vertex')],
        ['Interpolated Points', sum(1 for p in points if p.point_type == 'interpolated')],
        ['Total Perimeter (m)', sum(p.distance_to_next or 0 for p in points)],
        ['Min Elevation (m)', min((p.elevation for p in points if p.elevation), default=None)],
        ['Max Elevation (m)', max((p.elevation for p in points if p.elevation), default=None)],
        ['Avg Elevation (m)', sum(p.elevation or 0 for p in points) / len(points) if points else None],
        ['Verified Points', sum(1 for p in points if p.is_verified)]
    ]

    for i, (label, value) in enumerate(summary_data, start=3):
        ws_summary[f'A{i}'] = label
        ws_summary[f'A{i}'].font = Font(bold=True)
        if value is not None:
            ws_summary[f'B{i}'] = round(value, 2) if isinstance(value, float) else value

    # Points sheet
    ws_points = wb.create_sheet("Points")

    # Header row
    headers = [
        'Point No', 'Type', 'Longitude', 'Latitude',
        'Easting UTM', 'Northing UTM', 'UTM Zone',
        'Azimuth (deg)', 'Distance (m)', 'Elevation (m)',
        'Verified', 'Remarks'
    ]

    for col, header in enumerate(headers, start=1):
        cell = ws_points.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        cell.alignment = Alignment(horizontal='center')

    # Data rows
    for row, point in enumerate(points, start=2):
        ws_points.cell(row=row, column=1, value=f'P{point.point_number}')
        ws_points.cell(row=row, column=2, value=point.point_type)
        ws_points.cell(row=row, column=3, value=round(point.longitude, 7) if point.longitude else '')
        ws_points.cell(row=row, column=4, value=round(point.latitude, 7) if point.latitude else '')
        ws_points.cell(row=row, column=5, value=round(point.easting_utm, 2) if point.easting_utm else '')
        ws_points.cell(row=row, column=6, value=round(point.northing_utm, 2) if point.northing_utm else '')
        ws_points.cell(row=row, column=7, value=point.utm_zone if point.utm_zone else '')
        ws_points.cell(row=row, column=8, value=round(point.azimuth_to_next, 2) if point.azimuth_to_next else '')
        ws_points.cell(row=row, column=9, value=round(point.distance_to_next, 2) if point.distance_to_next else '')
        ws_points.cell(row=row, column=10, value=round(point.elevation, 2) if point.elevation else '')
        ws_points.cell(row=row, column=11, value='Yes' if point.is_verified else 'No')
        ws_points.cell(row=row, column=12, value=point.remarks if point.remarks else '')

        # Highlight verified points
        if point.is_verified:
            for col in range(1, 13):
                ws_points.cell(row=row, column=col).fill = PatternFill(
                    start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"
                )

    # Adjust column widths
    for col in range(1, 13):
        ws_points.column_dimensions[chr(64 + col)].width = 15

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def export_fieldbook_gpx(db: Session, calculation_id: UUID) -> bytes:
    """
    Export fieldbook to GPX format (GPS Exchange Format).
    """
    points = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).order_by(Fieldbook.point_number).all()

    if not points:
        raise ValueError("No fieldbook points found for this calculation")

    # Create GPX XML
    gpx = ET.Element('gpx', {
        'version': '1.1',
        'creator': 'Community Forest Management System',
        'xmlns': 'http://www.topografix.com/GPX/1/1',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:schemaLocation': 'http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd'
    })

    metadata = ET.SubElement(gpx, 'metadata')
    ET.SubElement(metadata, 'name').text = f'Fieldbook - Calculation {calculation_id}'
    ET.SubElement(metadata, 'desc').text = f'Boundary fieldbook with {len(points)} points'

    for point in points:
        if point.latitude and point.longitude:
            wpt = ET.SubElement(gpx, 'wpt', {
                'lat': f'{point.latitude:.7f}',
                'lon': f'{point.longitude:.7f}'
            })

            ET.SubElement(wpt, 'name').text = f'P{point.point_number}'
            ET.SubElement(wpt, 'type').text = point.point_type

            if point.elevation:
                ET.SubElement(wpt, 'ele').text = f'{point.elevation:.2f}'

            desc_parts = []
            if point.azimuth_to_next:
                desc_parts.append(f'Azimuth: {point.azimuth_to_next:.2f}°')
            if point.distance_to_next:
                desc_parts.append(f'Distance: {point.distance_to_next:.2f}m')
            if point.remarks:
                desc_parts.append(f'Remarks: {point.remarks}')

            if desc_parts:
                ET.SubElement(wpt, 'desc').text = ' | '.join(desc_parts)

    # Convert to bytes
    tree = ET.ElementTree(gpx)
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    output.seek(0)
    return output.read()


def export_fieldbook_geojson(db: Session, calculation_id: UUID) -> Dict[str, Any]:
    """
    Export fieldbook to GeoJSON format.
    """
    points = db.query(Fieldbook).filter(
        Fieldbook.calculation_id == calculation_id
    ).order_by(Fieldbook.point_number).all()

    if not points:
        raise ValueError("No fieldbook points found for this calculation")

    features = []
    for point in points:
        if point.latitude and point.longitude:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(point.longitude), float(point.latitude)]
                },
                "properties": {
                    "point_number": point.point_number,
                    "point_type": point.point_type,
                    "elevation": round(float(point.elevation), 2) if point.elevation else None,
                    "azimuth_to_next": round(float(point.azimuth_to_next), 2) if point.azimuth_to_next else None,
                    "distance_to_next": round(float(point.distance_to_next), 2) if point.distance_to_next else None,
                    "easting_utm": round(float(point.easting_utm), 2) if point.easting_utm else None,
                    "northing_utm": round(float(point.northing_utm), 2) if point.northing_utm else None,
                    "utm_zone": point.utm_zone,
                    "is_verified": point.is_verified,
                    "remarks": point.remarks
                }
            }
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features
    }


# ===========================
# Sampling Export Functions
# ===========================

def export_sampling_csv(db: Session, design_id: UUID) -> bytes:
    """
    Export sampling points to CSV format.
    """
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design or not design.points_geometry:
        raise ValueError("Sampling design not found or has no points")

    # Get geometry as WKT using PostGIS
    from sqlalchemy import text
    wkt_query = text("""
        SELECT ST_AsText(points_geometry) as wkt
        FROM public.sampling_designs
        WHERE id = :design_id
    """)
    result = db.execute(wkt_query, {"design_id": str(design_id)}).first()

    if not result or not result.wkt:
        raise ValueError("Failed to retrieve geometry as WKT")

    # Parse MultiPoint geometry
    from shapely import wkt
    multipoint = wkt.loads(result.wkt)

    # Get block assignment
    block_assignment = design.points_block_assignment or []

    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(['Plot No', 'Longitude', 'Latitude', 'Block No', 'Block Name'])

    # Write points
    for i, point in enumerate(multipoint.geoms):
        # Find block assignment for this point
        block_info = next((b for b in block_assignment if b.get('point_index') == i), None)
        block_number = block_info.get('block_number', '') if block_info else ''
        block_name = block_info.get('block_name', '') if block_info else ''

        writer.writerow([
            i + 1,  # Plot number starts at 1
            f'{point.x:.7f}',
            f'{point.y:.7f}',
            block_number,
            block_name
        ])

    return output.getvalue().encode('utf-8')


def export_sampling_gpx(db: Session, design_id: UUID) -> bytes:
    """
    Export sampling points to GPX format.
    """
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design or not design.points_geometry:
        raise ValueError("Sampling design not found or has no points")

    # Get geometry as WKT using PostGIS
    from sqlalchemy import text
    wkt_query = text("""
        SELECT ST_AsText(points_geometry) as wkt
        FROM public.sampling_designs
        WHERE id = :design_id
    """)
    result = db.execute(wkt_query, {"design_id": str(design_id)}).first()

    if not result or not result.wkt:
        raise ValueError("Failed to retrieve geometry as WKT")

    # Parse MultiPoint geometry
    from shapely import wkt
    multipoint = wkt.loads(result.wkt)

    # Create GPX XML
    gpx = ET.Element('gpx', {
        'version': '1.1',
        'creator': 'Community Forest Management System',
        'xmlns': 'http://www.topografix.com/GPX/1/1'
    })

    metadata = ET.SubElement(gpx, 'metadata')
    ET.SubElement(metadata, 'name').text = f'Sampling Points - {design.sampling_type}'
    ET.SubElement(metadata, 'desc').text = f'{design.total_points} sampling plots'

    for i, point in enumerate(multipoint.geoms, start=1):
        wpt = ET.SubElement(gpx, 'wpt', {
            'lat': f'{point.y:.7f}',
            'lon': f'{point.x:.7f}'
        })
        ET.SubElement(wpt, 'name').text = f'Plot {i}'
        ET.SubElement(wpt, 'type').text = 'sampling_plot'

        if design.plot_shape:
            desc = f'{design.plot_shape} plot'
            if design.plot_radius_meters:
                desc += f' (r={design.plot_radius_meters}m)'
            ET.SubElement(wpt, 'desc').text = desc

    # Convert to bytes
    tree = ET.ElementTree(gpx)
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    output.seek(0)
    return output.read()


def export_sampling_kml(db: Session, design_id: UUID) -> bytes:
    """
    Export sampling points to KML format (Google Earth).
    """
    design = db.query(SamplingDesign).filter(SamplingDesign.id == design_id).first()

    if not design or not design.points_geometry:
        raise ValueError("Sampling design not found or has no points")

    # Get geometry as WKT using PostGIS
    from sqlalchemy import text
    wkt_query = text("""
        SELECT ST_AsText(points_geometry) as wkt
        FROM public.sampling_designs
        WHERE id = :design_id
    """)
    result = db.execute(wkt_query, {"design_id": str(design_id)}).first()

    if not result or not result.wkt:
        raise ValueError("Failed to retrieve geometry as WKT")

    # Parse MultiPoint geometry
    from shapely import wkt
    multipoint = wkt.loads(result.wkt)

    # Create KML XML
    kml = ET.Element('kml', {'xmlns': 'http://www.opengis.net/kml/2.2'})
    document = ET.SubElement(kml, 'Document')

    ET.SubElement(document, 'name').text = f'Sampling Points - {design.sampling_type}'
    ET.SubElement(document, 'description').text = (
        f'Sampling design with {design.total_points} plots. '
        f'Type: {design.sampling_type}. '
        f'Intensity: {design.intensity_per_hectare}/ha.'
    )

    # Add style for sampling points
    style = ET.SubElement(document, 'Style', {'id': 'samplingPlot'})
    icon_style = ET.SubElement(style, 'IconStyle')
    ET.SubElement(icon_style, 'scale').text = '1.2'
    icon = ET.SubElement(icon_style, 'Icon')
    ET.SubElement(icon, 'href').text = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'

    # Add folder for points
    folder = ET.SubElement(document, 'Folder')
    ET.SubElement(folder, 'name').text = 'Sampling Plots'

    for i, point in enumerate(multipoint.geoms, start=1):
        placemark = ET.SubElement(folder, 'Placemark')
        ET.SubElement(placemark, 'name').text = f'Plot {i}'
        ET.SubElement(placemark, 'styleUrl').text = '#samplingPlot'

        if design.plot_shape:
            desc = f'Shape: {design.plot_shape}<br/>'
            if design.plot_radius_meters:
                # Calculate plot area for circular plots: π * r²
                import math
                plot_area = math.pi * float(design.plot_radius_meters) ** 2
                desc += f'Radius: {design.plot_radius_meters}m<br/>'
                desc += f'Area: {plot_area:.2f} m²'
            elif design.plot_length_meters and design.plot_width_meters:
                # Calculate plot area for rectangular plots
                plot_area = float(design.plot_length_meters) * float(design.plot_width_meters)
                desc += f'Length: {design.plot_length_meters}m x Width: {design.plot_width_meters}m<br/>'
                desc += f'Area: {plot_area:.2f} m²'
            ET.SubElement(placemark, 'description').text = desc

        point_elem = ET.SubElement(placemark, 'Point')
        ET.SubElement(point_elem, 'coordinates').text = f'{point.x:.7f},{point.y:.7f},0'

    # Convert to bytes
    tree = ET.ElementTree(kml)
    output = io.BytesIO()
    tree.write(output, encoding='utf-8', xml_declaration=True)
    output.seek(0)
    return output.read()
