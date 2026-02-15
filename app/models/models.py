from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, JSON, Enum as SQLEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
import enum

from app.db.database import Base

class SpecType(enum.Enum):
    """Specification maturity levels"""
    STABLE = "stable"        # spec3.json - General Availability
    PREVIEW = "preview"      # spec3.sdk.json - Preview features
    BETA = "beta"           # spec3.beta.sdk.json - Beta experiments

class ChangeMaturity(enum.Enum):
    """Change maturity classification"""
    # Within-tier temporal changes (current vs previous snapshot)
    STABLE_CHANGE = "stable_change"           # Change in GA version
    PREVIEW_CHANGE = "preview_change"         # Change in preview version
    BETA_CHANGE = "beta_change"               # Change in beta version
    # Cross-tier static differences (what's different between tiers)
    CROSS_TIER_PREVIEW = "cross_tier_preview" # In preview but not stable
    CROSS_TIER_BETA = "cross_tier_beta"       # In beta but not stable
    # Legacy values (kept for DB compatibility)
    PREVIEW_TO_STABLE = "preview_to_stable"   # Preview feature going GA
    BETA_TO_PREVIEW = "beta_to_preview"       # Beta moving to preview
    NEW_PREVIEW = "new_preview"               # Legacy: use CROSS_TIER_PREVIEW
    NEW_BETA = "new_beta"                     # Legacy: use CROSS_TIER_BETA

class Snapshot(Base):
    __tablename__ = "snapshots"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gateway = Column(String, nullable=False)
    endpoint_path = Column(String, nullable=False)
    spec_type = Column(SQLEnum(SpecType), nullable=False, default=SpecType.STABLE)
    spec_url = Column(String, nullable=True)
    schema_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    changes = relationship("Change", back_populates="snapshot", cascade="all, delete-orphan")

class Change(Base):
    __tablename__ = "changes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey('snapshots.id'), nullable=False)  # FIXED: Added ForeignKey
    change_type = Column(String, nullable=False)
    field_path = Column(String, nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    severity = Column(String, nullable=False)
    change_category = Column(String, nullable=True)
    change_maturity = Column(String, nullable=True)
    ai_summary = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    snapshot = relationship("Snapshot", back_populates="changes")

class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    gateway = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)