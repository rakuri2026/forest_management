"""
OP Data Cache model - caches collected operational plan data to avoid 35-50 queries on every export
"""
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime

from ..core.database import Base


class OpDataCache(Base):
    __tablename__ = "op_data_cache"
    __table_args__ = {"schema": "public"}

    calculation_id = Column(UUID(as_uuid=True), primary_key=True)
    data = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())
