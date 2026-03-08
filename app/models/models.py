from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Enum as SQLEnum, Text, UniqueConstraint, Index
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    BRANCH_MANAGER = "BRANCH_MANAGER"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


class AppointmentStatus(str, Enum):
    BOOKED = "BOOKED"
    CHECKED_IN = "CHECKED_IN"
    NO_SHOW = "NO_SHOW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ActionType(str, Enum):
    APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
    APPOINTMENT_RESCHEDULED = "APPOINTMENT_RESCHEDULED"
    APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
    APPOINTMENT_STATUS_CHANGED = "APPOINTMENT_STATUS_CHANGED"
    SLOT_CREATED = "SLOT_CREATED"
    SLOT_UPDATED = "SLOT_UPDATED"
    SLOT_SOFT_DELETED = "SLOT_SOFT_DELETED"
    SLOT_HARD_DELETED = "SLOT_HARD_DELETED"
    STAFF_ASSIGNED = "STAFF_ASSIGNED"
    SEED_IMPORT = "SEED_IMPORT"
    CUSTOMER_REGISTERED = "CUSTOMER_REGISTERED"


class Branch(Base):
    __tablename__ = "branches"

    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    address = Column(Text, nullable=False)
    timezone = Column(String(50), default="Asia/Muscat")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    service_types = relationship("ServiceType", back_populates="branch", cascade="all, delete-orphan")
    staff_members = relationship("User", back_populates="branch", foreign_keys="User.branch_id")
    slots = relationship("Slot", back_populates="branch", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="branch")


class ServiceType(Base):
    __tablename__ = "service_types"

    id = Column(String(50), primary_key=True)
    branch_id = Column(String(50), ForeignKey("branches.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="service_types")
    staff = relationship("StaffServiceType", back_populates="service_type", cascade="all, delete-orphan")
    slots = relationship("Slot", back_populates="service_type")
    appointments = relationship("Appointment", back_populates="service_type")


class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.CUSTOMER)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20))
    id_image_path = Column(String(500))
    is_active = Column(Boolean, default=True)
    branch_id = Column(String(50), ForeignKey("branches.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="staff_members", foreign_keys=[branch_id])
    service_types = relationship("StaffServiceType", back_populates="staff", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="customer", foreign_keys="Appointment.customer_id")
    staff_appointments = relationship("Appointment", back_populates="staff", foreign_keys="Appointment.staff_id")


class StaffServiceType(Base):
    __tablename__ = "staff_service_types"

    id = Column(String(50), primary_key=True)
    staff_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    service_type_id = Column(String(50), ForeignKey("service_types.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    staff = relationship("User", back_populates="service_types")
    service_type = relationship("ServiceType", back_populates="staff")

    __table_args__ = (UniqueConstraint('staff_id', 'service_type_id', name='unique_staff_service'),)


class Slot(Base):
    __tablename__ = "slots"

    id = Column(String(50), primary_key=True)
    branch_id = Column(String(50), ForeignKey("branches.id"), nullable=False)
    service_type_id = Column(String(50), ForeignKey("service_types.id"), nullable=False)
    staff_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    capacity = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    branch = relationship("Branch", back_populates="slots")
    service_type = relationship("ServiceType", back_populates="slots")
    staff = relationship("User", foreign_keys=[staff_id])
    appointment = relationship("Appointment", back_populates="slot", uselist=False)

    __table_args__ = (
        Index('idx_slot_branch_time', 'branch_id', 'start_at', 'end_at'),
        Index('idx_slot_service', 'service_type_id'),
        Index('idx_slot_deleted', 'deleted_at'),
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(50), primary_key=True)
    customer_id = Column(String(50), ForeignKey("users.id"), nullable=False)
    branch_id = Column(String(50), ForeignKey("branches.id"), nullable=False)
    service_type_id = Column(String(50), ForeignKey("service_types.id"), nullable=False)
    slot_id = Column(String(50), ForeignKey("slots.id"), nullable=False)
    staff_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    status = Column(SQLEnum(AppointmentStatus), default=AppointmentStatus.BOOKED)
    attachment_path = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    customer = relationship("User", back_populates="appointments", foreign_keys=[customer_id])
    branch = relationship("Branch", back_populates="appointments")
    service_type = relationship("ServiceType", back_populates="appointments")
    slot = relationship("Slot", back_populates="appointment")
    staff = relationship("User", back_populates="staff_appointments", foreign_keys=[staff_id])

    __table_args__ = (
        Index('idx_appointment_customer', 'customer_id'),
        Index('idx_appointment_branch', 'branch_id'),
        Index('idx_appointment_slot', 'slot_id'),
        Index('idx_appointment_status', 'status'),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(50), primary_key=True)
    actor_id = Column(String(50), nullable=False)
    actor_role = Column(SQLEnum(UserRole), nullable=False)
    action_type = Column(SQLEnum(ActionType), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    extra_data = Column(Text)

    __table_args__ = (
        Index('idx_audit_actor', 'actor_id'),
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_timestamp', 'timestamp'),
        Index('idx_audit_action', 'action_type'),
    )


class SystemConfig(Base):
    __tablename__ = "system_config"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

