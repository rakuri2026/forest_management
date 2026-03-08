"""
Location search API for administrative boundaries.
Helps users find areas to digitize by searching province/district/municipality/ward.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db

router = APIRouter()


# Response models
class Province(BaseModel):
    code: str
    name: str
    name_nepali: Optional[str] = None


class District(BaseModel):
    code: str
    name: str
    name_nepali: Optional[str] = None
    province_code: str


class Municipality(BaseModel):
    code: str
    name: str
    name_nepali: Optional[str] = None
    district_code: str
    type: Optional[str] = None  # Metropolitan, Municipality, Rural Municipality


class Ward(BaseModel):
    id: int
    ward_no: int
    municipality_code: str
    province: str
    district: str
    municipality: str
    geometry: Optional[dict] = None
    bounds: Optional[List[float]] = None  # [minLon, minLat, maxLon, maxLat]


class LocationSearchResult(BaseModel):
    """Search result for text-based location search"""
    id: int
    display_name: str
    province: str
    district: str
    municipality: str
    ward_no: int
    bounds: List[float]


@router.get("/provinces", response_model=List[Province])
async def get_provinces(db: Session = Depends(get_db)):
    """Get all provinces"""
    query = text("""
        SELECT DISTINCT
            province_code as code,
            province_name as name,
            province_name_nepali as name_nepali
        FROM admin.wards
        WHERE province_code IS NOT NULL
        ORDER BY province_name
    """)

    result = db.execute(query)
    provinces = [
        Province(
            code=row.code or "",
            name=row.name or "",
            name_nepali=row.name_nepali
        )
        for row in result
    ]

    return provinces


@router.get("/districts", response_model=List[District])
async def get_districts(
    province_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get districts, optionally filtered by province"""
    query_text = """
        SELECT DISTINCT
            district_code as code,
            district_name as name,
            district_name_nepali as name_nepali,
            province_code
        FROM admin.wards
        WHERE district_code IS NOT NULL
    """

    if province_code:
        query_text += " AND province_code = :province_code"

    query_text += " ORDER BY district_name"

    query = text(query_text)

    if province_code:
        result = db.execute(query, {"province_code": province_code})
    else:
        result = db.execute(query)

    districts = [
        District(
            code=row.code or "",
            name=row.name or "",
            name_nepali=row.name_nepali,
            province_code=row.province_code or ""
        )
        for row in result
    ]

    return districts


@router.get("/municipalities", response_model=List[Municipality])
async def get_municipalities(
    district_code: Optional[str] = None,
    province_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get municipalities, optionally filtered by district/province"""
    query_text = """
        SELECT DISTINCT
            municipality_code as code,
            municipality_name as name,
            municipality_name_nepali as name_nepali,
            district_code,
            municipality_type as type
        FROM admin.wards
        WHERE municipality_code IS NOT NULL
    """

    params = {}
    if province_code:
        query_text += " AND province_code = :province_code"
        params["province_code"] = province_code
    if district_code:
        query_text += " AND district_code = :district_code"
        params["district_code"] = district_code

    query_text += " ORDER BY municipality_name"

    query = text(query_text)
    result = db.execute(query, params) if params else db.execute(query)

    municipalities = [
        Municipality(
            code=row.code or "",
            name=row.name or "",
            name_nepali=row.name_nepali,
            district_code=row.district_code or "",
            type=row.type
        )
        for row in result
    ]

    return municipalities


@router.get("/wards", response_model=List[Ward])
async def get_wards(
    municipality_code: Optional[str] = None,
    district_code: Optional[str] = None,
    province_code: Optional[str] = None,
    include_geometry: bool = False,
    db: Session = Depends(get_db)
):
    """Get wards, optionally filtered by municipality/district/province"""

    # Build geometry selection
    geom_select = ""
    if include_geometry:
        geom_select = """
            , ST_AsGeoJSON(geom)::json as geometry
            , ARRAY[
                ST_XMin(geom), ST_YMin(geom),
                ST_XMax(geom), ST_YMax(geom)
              ] as bounds
        """

    query_text = f"""
        SELECT
            id,
            ward_no,
            municipality_code,
            province_name as province,
            district_name as district,
            municipality_name as municipality
            {geom_select}
        FROM admin.wards
        WHERE id IS NOT NULL
    """

    params = {}
    if province_code:
        query_text += " AND province_code = :province_code"
        params["province_code"] = province_code
    if district_code:
        query_text += " AND district_code = :district_code"
        params["district_code"] = district_code
    if municipality_code:
        query_text += " AND municipality_code = :municipality_code"
        params["municipality_code"] = municipality_code

    query_text += " ORDER BY municipality_name, ward_no"

    query = text(query_text)
    result = db.execute(query, params) if params else db.execute(query)

    wards = []
    for row in result:
        ward_data = {
            "id": row.id,
            "ward_no": row.ward_no,
            "municipality_code": row.municipality_code or "",
            "province": row.province or "",
            "district": row.district or "",
            "municipality": row.municipality or ""
        }

        if include_geometry:
            ward_data["geometry"] = row.geometry if hasattr(row, 'geometry') else None
            ward_data["bounds"] = list(row.bounds) if hasattr(row, 'bounds') and row.bounds else None

        wards.append(Ward(**ward_data))

    return wards


@router.get("/search", response_model=List[LocationSearchResult])
async def search_location(
    q: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Text search across all administrative levels.
    Searches province, district, municipality, and ward names.
    """
    search_term = f"%{q}%"

    query = text("""
        SELECT
            id,
            province_name || ', ' || district_name || ', ' ||
            municipality_name || ', Ward ' || ward_no as display_name,
            province_name as province,
            district_name as district,
            municipality_name as municipality,
            ward_no,
            ARRAY[
                ST_XMin(geom), ST_YMin(geom),
                ST_XMax(geom), ST_YMax(geom)
            ] as bounds
        FROM admin.wards
        WHERE
            LOWER(province_name) LIKE LOWER(:search)
            OR LOWER(district_name) LIKE LOWER(:search)
            OR LOWER(municipality_name) LIKE LOWER(:search)
            OR LOWER(province_name_nepali) LIKE LOWER(:search)
            OR LOWER(district_name_nepali) LIKE LOWER(:search)
            OR LOWER(municipality_name_nepali) LIKE LOWER(:search)
        ORDER BY
            CASE
                WHEN LOWER(municipality_name) LIKE LOWER(:search) THEN 1
                WHEN LOWER(district_name) LIKE LOWER(:search) THEN 2
                WHEN LOWER(province_name) LIKE LOWER(:search) THEN 3
                ELSE 4
            END,
            municipality_name, ward_no
        LIMIT :limit
    """)

    result = db.execute(query, {"search": search_term, "limit": limit})

    results = [
        LocationSearchResult(
            id=row.id,
            display_name=row.display_name,
            province=row.province or "",
            district=row.district or "",
            municipality=row.municipality or "",
            ward_no=row.ward_no,
            bounds=list(row.bounds) if row.bounds else [0, 0, 0, 0]
        )
        for row in result
    ]

    return results


@router.get("/ward/{ward_id}/geometry")
async def get_ward_geometry(ward_id: int, db: Session = Depends(get_db)):
    """Get ward boundary geometry for display on map"""
    query = text("""
        SELECT
            ST_AsGeoJSON(geom)::json as geometry,
            ARRAY[ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)] as bounds,
            province_name, district_name, municipality_name, ward_no
        FROM admin.wards
        WHERE id = :ward_id
    """)

    result = db.execute(query, {"ward_id": ward_id}).first()

    if not result:
        raise HTTPException(status_code=404, detail="Ward not found")

    return {
        "geometry": result.geometry,
        "bounds": list(result.bounds) if result.bounds else None,
        "province": result.province_name,
        "district": result.district_name,
        "municipality": result.municipality_name,
        "ward_no": result.ward_no
    }
