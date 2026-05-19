from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any, List


class OPTableDefinitionResponse(BaseModel):
    table_id: str
    title_ne: str
    title_en: str
    auto_populatable: bool
    data_source: Optional[str] = None
    column_config: Optional[Dict[str, Any]] = None


class OPTableDataUpdate(BaseModel):
    rows: List[Dict[str, Any]]
    auto_populated: Optional[bool] = False


class OPTableDataResponse(BaseModel):
    table_id: str
    rows: List[Dict[str, Any]] = []
    auto_populated: bool = False


class OPTableCatalogResponse(BaseModel):
    tables: List[OPTableDefinitionResponse]
