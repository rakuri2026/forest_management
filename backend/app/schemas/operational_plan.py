"""
Pydantic schemas for Operational Plan
"""
from pydantic import BaseModel, Field, UUID4
from typing import Optional, Dict, Any, List
from datetime import datetime


class OperationalPlanSection(BaseModel):
    """Single section (परिच्छेद) content"""
    section_number: str  # e.g., "१", "२", "३"
    title: str  # e.g., "परिचय", "भौगोलिक अवस्थिति"
    content: Optional[str] = None  # User editable content
    auto_data: Optional[Dict[str, Any]] = {}  # System populated data
    is_auto_generated: bool = False
    last_modified: Optional[datetime] = None


class OperationalPlanCreate(BaseModel):
    """Create new operational plan"""
    calculation_id: UUID4
    forest_name: Optional[str] = None


class OperationalPlanUpdate(BaseModel):
    """Update operational plan sections"""
    sections: Optional[Dict[str, OperationalPlanSection]] = None
    status: Optional[str] = None
    plan_metadata: Optional[Dict[str, Any]] = None


class OperationalPlanSectionUpdate(BaseModel):
    """Update single section"""
    content: str
    auto_data: Optional[Dict[str, Any]] = None


class OperationalPlanResponse(BaseModel):
    """Operational plan response"""
    id: UUID
    calculation_id: UUID
    forest_name: Optional[str] = None
    sections: Dict[str, Any] = {}
    plan_metadata: Dict[str, Any] = {}
    status: str
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OperationalPlanListResponse(BaseModel):
    """List view of operational plans"""
    id: UUID4
    calculation_id: UUID4
    forest_name: Optional[str] = None
    status: str
    updated_at: datetime

    class Config:
        from_attributes = True
