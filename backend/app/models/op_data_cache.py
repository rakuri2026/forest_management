"""
OP Data Cache model - caches collected operational plan data to avoid 35-50 queries on every export

Auto-invalidates whenever any model with calculation_id is changed (insert/update/delete).
This ensures the OP preview/export always reflects the latest data without manual cache clearing.
"""
from sqlalchemy import Column, DateTime, func, event
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Session
from datetime import datetime

from ..core.database import Base


class OpDataCache(Base):
    __tablename__ = "op_data_cache"
    __table_args__ = {"schema": "public"}

    calculation_id = Column(UUID(as_uuid=True), primary_key=True)
    data = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, server_default=func.now())


def _invalidate_op_cache_on_change(session: Session, flush_context):
    """Auto-invalidate OpDataCache when any model with calculation_id changes.

    Fires after flush but before commit — shares the same transaction, so a
    rollback also undoes the cache deletion. Catches insert/update/delete on
    ALL current and future models that have a calculation_id column.
    """
    calc_ids = set()
    for obj in list(session.dirty) + list(session.new) + list(session.deleted):
        if obj.__class__.__name__ == "OpDataCache":
            continue
        cid = getattr(obj, "calculation_id", None)
        if cid is not None:
            calc_ids.add(cid)
    if calc_ids:
        session.query(OpDataCache).filter(
            OpDataCache.calculation_id.in_(calc_ids)
        ).delete(synchronize_session=False)


event.listen(Session, "after_flush", _invalidate_op_cache_on_change)
