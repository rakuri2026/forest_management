from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime


class TreeNodeSchema(BaseModel):
    id: str
    type: Literal["preamble", "toc", "section", "subsection", "appendix"] = "section"
    title_ne: str = ""
    title_en: str = ""
    number: Optional[str] = None
    level: int = 0
    content_type: Literal["richtext", "chart", "table", "map"] = "richtext"
    content: str = ""
    chart_type: Optional[str] = None
    table_id: Optional[str] = None
    children: List["TreeNodeSchema"] = []
    is_locked: bool = False
    hidden_in_export: bool = False
    last_modified: Optional[str] = None


class OperationalPlanCreate(BaseModel):
    calculation_id: UUID4
    forest_name: Optional[str] = None


class OperationalPlanUpdate(BaseModel):
    sections: Optional[Dict[str, Any]] = None
    tree: Optional[List[TreeNodeSchema]] = None
    status: Optional[str] = None
    plan_metadata: Optional[Dict[str, Any]] = None


class OperationalPlanSectionUpdate(BaseModel):
    content: str
    auto_data: Optional[Dict[str, Any]] = None


class TreeNodeCreate(BaseModel):
    parent_id: Optional[str] = None
    type: Literal["preamble", "toc", "section", "subsection", "appendix"] = "section"
    title_ne: str = ""
    title_en: str = ""
    content: str = ""
    content_type: Literal["richtext", "chart", "table", "map"] = "richtext"
    chart_type: Optional[str] = None
    table_id: Optional[str] = None
    position: int = -1


class TreeNodeUpdate(BaseModel):
    title_ne: Optional[str] = None
    title_en: Optional[str] = None
    content: Optional[str] = None
    content_type: Optional[Literal["richtext", "chart", "table", "map"]] = None
    chart_type: Optional[str] = None
    table_id: Optional[str] = None
    hidden_in_export: Optional[bool] = None


class TreeNodeReorder(BaseModel):
    node_id: str
    new_parent_id: Optional[str] = None
    new_position: int = -1


class VariableDefResponse(BaseModel):
    key: str
    category: str
    label_ne: str
    label_en: str
    var_type: str
    source: str
    auto_populate: bool
    description: str


class OperationalPlanResponse(BaseModel):
    id: UUID4
    calculation_id: UUID4
    forest_name: Optional[str] = None
    sections: Dict[str, Any] = {}
    tree: List[TreeNodeSchema] = []
    plan_metadata: Dict[str, Any] = {}
    status: str
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OperationalPlanListResponse(BaseModel):
    id: UUID4
    calculation_id: UUID4
    forest_name: Optional[str] = None
    status: str
    updated_at: datetime

    class Config:
        from_attributes = True
