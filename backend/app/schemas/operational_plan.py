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
    content_type: Literal["richtext", "chart", "table", "map", "static_table"] = "richtext"
    content: str = ""
    chart_type: Optional[str] = None
    table_id: Optional[str] = None
    static_table: Optional[dict] = None
    children: List["TreeNodeSchema"] = []
    is_locked: bool = False
    hidden_in_export: bool = False
    deleted: bool = False
    last_modified: Optional[str] = None


class OperationalPlanCreate(BaseModel):
    calculation_id: UUID4
    forest_name: Optional[str] = None
    custom_notes: Optional[str] = None


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
    content_type: Literal["richtext", "chart", "table", "map", "static_table"] = "richtext"
    chart_type: Optional[str] = None
    table_id: Optional[str] = None
    map_type: Optional[str] = None
    static_table: Optional[dict] = None
    position: int = -1


class TreeNodeUpdate(BaseModel):
    title_ne: Optional[str] = None
    title_en: Optional[str] = None
    content: Optional[str] = None
    content_type: Optional[Literal["richtext", "chart", "table", "map", "static_table"]] = None
    chart_type: Optional[str] = None
    table_id: Optional[str] = None
    map_type: Optional[str] = None
    static_table: Optional[dict] = None
    hidden_in_export: Optional[bool] = None
    deleted: Optional[bool] = None


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
    description_ne: str = ""
    table_columns: List[str] = []
    mock_rows: List[Dict[str, Any]] = []


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


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    tree: List[TreeNodeSchema]
    is_default: bool = False
    is_system: bool = False
    visibility: Literal["private", "shared"] = "private"
    tags: Optional[List[str]] = None
    template_category: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tree: Optional[List[TreeNodeSchema]] = None
    is_default: Optional[bool] = None
    visibility: Optional[Literal["private", "shared"]] = None
    tags: Optional[List[str]] = None
    template_category: Optional[str] = None
    changelog: Optional[str] = None


class TemplatePublish(BaseModel):
    is_active: bool


class TemplateClone(BaseModel):
    name: Optional[str] = None


class TemplateApprove(BaseModel):
    action: Literal["approve", "reject"]
    note: Optional[str] = ""


class TemplateSummary(BaseModel):
    id: UUID4
    name: str
    description: str = ""
    is_system: bool = False
    is_default: bool = False
    is_active: bool = True
    version: int = 1
    visibility: str = "private"
    approval_status: str = "none"
    tags: List[str] = []
    template_category: Optional[str] = None
    sections_summary: List[str] = []
    variables_summary: List[str] = []
    created_by: Optional[UUID4] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TemplateResponse(TemplateSummary):
    tree: List[TreeNodeSchema] = []
    approval_note: str = ""
    approved_by: Optional[UUID4] = None
    approved_at: Optional[datetime] = None
    source_calculation_id: Optional[UUID4] = None
    source_template_id: Optional[UUID4] = None
    changelog: Optional[str] = None


class TemplateVersionResponse(BaseModel):
    id: UUID4
    template_id: UUID4
    version: int
    name: str
    description: str = ""
    changelog: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateRollbackRequest(BaseModel):
    version: int


class CategoryCreate(BaseModel):
    key: str = Field(..., min_length=1, max_length=50)
    label_ne: str = Field(..., min_length=1, max_length=255)
    label_en: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    color: Optional[str] = "purple"
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    label_ne: Optional[str] = None
    label_en: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    sort_order: Optional[int] = None


class CategoryResponse(BaseModel):
    id: UUID4
    key: str
    label_ne: str
    label_en: str
    description: str = ""
    color: str = "purple"
    sort_order: int = 0
    created_at: datetime

    class Config:
        from_attributes = True
