from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import func
import uuid
from ..core.database import Base


class OPTemplate(Base):
    __tablename__ = "op_templates"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    tree = Column(JSONB, nullable=False, default=list)

    # Visibility & ownership
    visibility = Column(String(20), nullable=False, server_default="private")
    is_system = Column(Boolean, nullable=False, default=False)
    is_default = Column(Boolean, nullable=False, default=False)

    # Structured metadata (auto-generated)
    tags = Column(JSONB, nullable=True, default=list)
    sections_summary = Column(JSONB, nullable=True, default=list)
    variables_summary = Column(JSONB, nullable=True, default=list)

    # Approval workflow
    approval_status = Column(String(20), nullable=False, server_default="none")
    approval_note = Column(Text, nullable=True, default="")
    approved_by = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    source_calculation_id = Column(UUID(as_uuid=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<OPTemplate(id={self.id}, name={self.name}, visibility={self.visibility}, approval={self.approval_status})>"
