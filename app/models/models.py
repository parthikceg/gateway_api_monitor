"""Database models"""
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.db.database import Base


class Snapshot(Base):
    """Stores API schema snapshots"""
    __tablename__ = "snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway = Column(String(50), nullable=False, index=True)
    endpoint_path = Column(String(255), nullable=False, index=True)
    spec_type = Column(String(50), nullable=False, default='primary', index=True)
    schema_data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    changes = relationship("Change", back_populates="snapshot", cascade="all, delete-orphan")


class Change(Base):
    """Stores detected API changes"""
    __tablename__ = "changes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=False)
    change_type = Column(String(50), nullable=False, index=True)
    field_path = Column(String(500), nullable=False)
    old_value = Column(JSONB)
    new_value = Column(JSONB)
    ai_summary = Column(Text)
    severity = Column(String(20), index=True)
    change_category = Column(String(50), index=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    snapshot = relationship("Snapshot", back_populates="changes")


class AlertSubscription(Base):
    """Email alert subscriptions"""
    __tablename__ = "alert_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    gateway = Column(String(50))  # None = all gateways
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
