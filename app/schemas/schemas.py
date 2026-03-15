"""
Pydantic Schemas for Request/Response Models

This module defines all data validation and serialization models
using Pydantic for the FlowCare API.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, EmailStr, Field, validator


class UserRoleEnum(str, Enum):
    """User roles available in the system"""
    ADMIN = "ADMIN"
    BRANCH_MANAGER = "BRANCH_MANAGER"
    STAFF = "STAFF"
    CUSTOMER = "CUSTOMER"


class AppointmentStatusEnum(str, Enum):
    """Appointment status values"""
    BOOKED = "BOOKED"
    CHECKED_IN = "CHECKED_IN"
    NO_SHOW = "NO_SHOW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ActionTypeEnum(str, Enum):
    """Action types for audit logging"""
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


class PaginatedResponse(BaseModel):
    """Standard paginated response format"""
    results: List[dict] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 10


class BranchBase(BaseModel):
    """Base branch schema with shared fields"""
    name: str = Field(..., min_length=1, max_length=255)
    city: str = Field(..., min_length=1, max_length=100)
    address: str = Field(..., min_length=1)
    timezone: str = "Asia/Muscat"


class BranchCreate(BranchBase):
    """Schema for creating a new branch"""
    id: str = Field(..., pattern=r"^br_[a-z0-9_]+$")


class BranchResponse(BranchBase):
    """Schema for branch response data"""
    id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ServiceTypeBase(BaseModel):
    """Base service type schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    duration_minutes: int = Field(..., gt=0)
    is_active: bool = True


class ServiceTypeCreate(ServiceTypeBase):
    """Schema for creating a new service type"""
    id: str = Field(..., pattern=r"^svc_[a-z0-9_]+$")
    branch_id: str


class ServiceTypeResponse(ServiceTypeBase):
    """Schema for service type response data"""
    id: str
    branch_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    """Base user schema with shared fields"""
    username: str = Field(..., min_length=3, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class UserCreate(UserBase):
    """
    Schema for user registration
    
    Password must be at least 8 characters with uppercase,
    lowercase, and digit.
    """
    password: str = Field(..., min_length=8)
    role: UserRoleEnum = UserRoleEnum.CUSTOMER
    phone: Optional[str] = None
    branch_id: Optional[str] = None
    
    @validator('password')
    def password_strength(cls, v):
        """Validate password meets strength requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserResponse(BaseModel):
    """Schema for user response (excludes sensitive data)"""
    id: str
    username: str
    full_name: str
    email: str
    role: UserRoleEnum
    phone: Optional[str] = None
    branch_id: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerRegister(BaseModel):
    """
    Schema for customer self-registration
    
    Requires ID image for verification.
    """
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(..., min_length=5)
    id_image: str = Field(..., description="Base64 encoded ID image")
    
    @validator('password')
    def password_strength(cls, v):
        """Validate password meets strength requirements"""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class SlotBase(BaseModel):
    """Base slot schema"""
    start_at: datetime
    end_at: datetime
    capacity: int = 1


class SlotCreate(SlotBase):
    """Schema for creating a new slot"""
    id: str
    branch_id: str
    service_type_id: str
    staff_id: Optional[str] = None


class SlotUpdate(BaseModel):
    """Schema for updating a slot"""
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    capacity: Optional[int] = Field(None, gt=0)
    is_active: Optional[bool] = None


class SlotResponse(SlotBase):
    """Schema for slot response data"""
    id: str
    branch_id: str
    service_type_id: str
    staff_id: Optional[str] = None
    is_active: bool
    deleted_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AppointmentBase(BaseModel):
    """Base appointment schema"""
    branch_id: str
    service_type_id: str
    slot_id: str


class AppointmentCreate(AppointmentBase):
    """
    Schema for creating an appointment
    
    Validates slot availability and branch/service type matching.
    """
    attachment: Optional[str] = Field(None, description="Base64 encoded attachment")


class AppointmentUpdate(BaseModel):
    """Schema for updating an appointment"""
    status: Optional[AppointmentStatusEnum] = None
    notes: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Schema for appointment response data"""
    id: str
    customer_id: str
    branch_id: str
    service_type_id: str
    slot_id: str
    staff_id: Optional[str] = None
    status: AppointmentStatusEnum
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentReschedule(BaseModel):
    """Schema for rescheduling an appointment to a new slot"""
    new_slot_id: str = Field(..., description="ID of the new slot to move to")


class AuditLogResponse(BaseModel):
    """Schema for audit log response data"""
    id: str
    actor_id: str
    actor_role: UserRoleEnum
    action_type: ActionTypeEnum
    entity_type: str
    entity_id: str
    timestamp: datetime
    metadata: Optional[str] = None

    class Config:
        from_attributes = True


class StaffServiceTypeCreate(BaseModel):
    """Schema for assigning a staff member to a service type"""
    staff_id: str
    service_type_id: str


class StaffServiceTypeResponse(BaseModel):
    """Schema for staff service type assignment response"""
    id: str
    staff_id: str
    service_type_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class SystemConfigResponse(BaseModel):
    """Schema for system configuration response"""
    key: str
    value: str
    description: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class RetentionPeriodUpdate(BaseModel):
    """Schema for updating data retention period"""
    days: int = Field(..., gt=0, description="Number of days to retain soft-deleted records")


class StaffListItem(BaseModel):
    """Schema for staff list item response"""
    id: str
    username: str
    full_name: str
    email: str
    role: UserRoleEnum
    branch_id: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerListItem(BaseModel):
    """Schema for customer list item response"""
    id: str
    username: str
    full_name: str
    email: str
    phone: Optional[str] = None
    role: UserRoleEnum
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

