"""
Organization model - maps to existing organizations table
"""
from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from ..core.database import Base


class SubscriptionType(str, enum.Enum):
    """Organization subscription types"""
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class Organization(Base):
    """
    Organization model - maps to public.organizations table
    Represents community forest user groups or organizations
    """
    __tablename__ = "organizations"
    __table_args__ = {"schema": "public"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(20), nullable=True)
    subscription_type = Column(SQLEnum(SubscriptionType), nullable=False, default=SubscriptionType.BASIC)
    max_users = Column(Integer, nullable=False, default=5)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    users = relationship("User", back_populates="organization")

    def __repr__(self):
        return f"<Organization(id={self.id}, name={self.name})>"
