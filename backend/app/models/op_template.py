from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
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

    visibility = Column(String(20), nullable=False, server_default="private")
    is_system = Column(Boolean, nullable=False, default=False)
    is_default = Column(Boolean, nullable=False, default=False)

    version = Column(Integer, nullable=False, server_default="1")
    is_active = Column(Boolean, nullable=False, server_default="false")
    changelog = Column(Text, nullable=True, default="")
    template_category = Column(String(100), nullable=True)
    preview_image_url = Column(Text, nullable=True)
    source_template_id = Column(UUID(as_uuid=True), nullable=True)

    tags = Column(JSONB, nullable=True, default=list)
    sections_summary = Column(JSONB, nullable=True, default=list)
    variables_summary = Column(JSONB, nullable=True, default=list)

    approval_status = Column(String(20), nullable=False, server_default="none")
    approval_note = Column(Text, nullable=True, default="")
    approved_by = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    source_calculation_id = Column(UUID(as_uuid=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("public.users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<OPTemplate(id={self.id}, name={self.name}, version={self.version})>"


class OPTemplateVersion(Base):
    __tablename__ = "op_template_versions"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("public.op_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    tree = Column(JSONB, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    changelog = Column(Text, nullable=True, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    template = relationship("OPTemplate", backref="versions")

    def __repr__(self):
        return f"<OPTemplateVersion(template_id={self.template_id}, version={self.version})>"


class OPTemplateCategory(Base):
    __tablename__ = "op_template_categories"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(50), unique=True, nullable=False, index=True)
    label_ne = Column(String(255), nullable=False)
    label_en = Column(String(255), nullable=False)
    description = Column(Text, nullable=True, default="")
    color = Column(String(20), nullable=True, default="purple")
    sort_order = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<OPTemplateCategory(key={self.key}, label_en={self.label_en})>"
