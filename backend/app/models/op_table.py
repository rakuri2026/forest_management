from sqlalchemy import Column, String, Integer, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from ..core.database import Base


class OPTableDefinition(Base):
    __tablename__ = "op_table_definitions"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    table_id = Column(String(20), unique=True, nullable=False)  # "table_1" through "table_32"
    title_ne = Column(String(255), nullable=False)
    title_en = Column(String(255), nullable=False)
    auto_populatable = Column(Boolean, nullable=False, default=False)
    data_source = Column(String(100), nullable=True)
    column_config = Column(JSONB, nullable=True)

    def __repr__(self):
        return f"<OPTableDefinition(id={self.table_id}, title={self.title_en})>"


class OPTableData(Base):
    __tablename__ = "op_table_data"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calculation_id = Column(UUID(as_uuid=True), ForeignKey("public.calculations.id", ondelete="CASCADE"), nullable=False)
    table_id = Column(String(20), nullable=False)
    rows = Column(JSONB, nullable=False, default=list)
    auto_populated = Column(Boolean, nullable=False, default=False)
    created_at = Column(String(30), default=lambda: datetime.utcnow().isoformat())

    def __repr__(self):
        return f"<OPTableData(calc={self.calculation_id}, table={self.table_id}, rows={len(self.rows or [])})>"
