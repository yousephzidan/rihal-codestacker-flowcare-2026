"""
Customer & Appointment API Endpoints

Handles customer operations:
- Book appointments
- List own appointments
- View appointment details
- Cancel appointments
- Reschedule appointments
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import User, UserRole, Appointment, AppointmentStatus, Slot, ActionType
from app.schemas.schemas import (
    AppointmentCreate, AppointmentResponse, AppointmentUpdate, 
    AppointmentReschedule, PaginatedResponse
)
from app.services.file_service import file_exists, get_file_path
from app.services.audit_service import create_audit_log
from app.services.file_service import save_appointment_attachment

router = APIRouter(prefix="/customers", tags=["Customer"])


@router.post("/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def book_appointment(
    appointment_data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Book a new appointment.
    
    Validates slot availability, branch, and service type matching.
    Creates an audit log entry for tracking.
    
    Args:
        appointment_data: Appointment booking data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        AppointmentResponse: Created appointment
        
    Raises:
        HTTPException: 403 if not customer, 404 if slot not found, 400 for validation errors
    """
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can book appointments"
        )
    
    slot = db.query(Slot).filter(Slot.id == appointment_data.slot_id).first()
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found"
        )
    
    if slot.start_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot book a slot in the past"
        )
    
    if not slot.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot is not active"
        )
    
    if slot.deleted_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot is no longer available"
        )
    
    if slot.appointment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot is already booked"
        )
    
    if slot.branch_id != appointment_data.branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot does not belong to the specified branch"
        )
    
    if slot.service_type_id != appointment_data.service_type_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot does not match the specified service type"
        )
    
    appointment_id = f"appt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
    
    attachment_path = None
    if appointment_data.attachment:
        attachment_path = save_appointment_attachment(appointment_data.attachment, appointment_id)
    
    appointment = Appointment(
        id=appointment_id,
        customer_id=current_user.id,
        branch_id=appointment_data.branch_id,
        service_type_id=appointment_data.service_type_id,
        slot_id=appointment_data.slot_id,
        staff_id=slot.staff_id,
        status=AppointmentStatus.BOOKED,
        attachment_path=attachment_path
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    create_audit_log(
        db=db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action_type=ActionType.APPOINTMENT_BOOKED,
        entity_type="APPOINTMENT",
        entity_id=appointment.id,
        metadata={
            "slot_id": slot.id,
            "branch_id": appointment.branch_id,
            "service_type_id": appointment.service_type_id
        }
    )
    
    return appointment


@router.get("/appointments", response_model=PaginatedResponse)
def list_my_appointments(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100)
):
    """
    List authenticated customer's own appointments.
    
    Supports pagination and optional status filtering.
    
    Args:
        status_filter: Optional status filter
        current_user: Current authenticated user
        db: Database session
        page: Page number
        size: Items per page
        
    Returns:
        PaginatedResponse: List of appointments
        
    Raises:
        HTTPException: 403 if not customer
    """
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can view their own appointments"
        )
    
    query = db.query(Appointment).filter(Appointment.customer_id == current_user.id)
    
    if status_filter:
        try:
            status_enum = AppointmentStatus(status_filter)
            query = query.filter(Appointment.status == status_enum)
        except ValueError:
            pass
    
    total = query.count()
    
    offset = (page - 1) * size
    appointments = query.order_by(Appointment.created_at.desc()).offset(offset).limit(size).all()
    
    return PaginatedResponse(
        results=[{
            "id": a.id,
            "branch_id": a.branch_id,
            "service_type_id": a.service_type_id,
            "slot_id": a.slot_id,
            "staff_id": a.staff_id,
            "status": a.status.value,
            "created_at": a.created_at.isoformat()
        } for a in appointments],
        total=total,
        page=page,
        size=size
    )


@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
def get_appointment_details(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific appointment.
    
    Access restricted to the customer who booked, assigned staff, manager, or admin.
    
    Args:
        appointment_id: ID of the appointment
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        AppointmentResponse: Appointment details
        
    Raises:
        HTTPException: 404 if not found, 403 if no access
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if (current_user.role == UserRole.CUSTOMER and 
        appointment.customer_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own appointments"
        )
    
    if (current_user.role == UserRole.STAFF and 
        appointment.staff_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your assigned appointments"
        )
    
    return appointment


@router.delete("/appointments/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel customer's own appointment.
    
    Only the customer who booked can cancel.
    Cannot cancel already completed or cancelled appointments.
    
    Args:
        appointment_id: ID of the appointment
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        None
        
    Raises:
        HTTPException: 404 if not found, 403 if no access, 400 if cannot cancel
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if appointment.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own appointments"
        )
    
    if appointment.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel this appointment"
        )
    
    appointment.status = AppointmentStatus.CANCELLED
    appointment.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    create_audit_log(
        db=db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action_type=ActionType.APPOINTMENT_CANCELLED,
        entity_type="APPOINTMENT",
        entity_id=appointment.id,
        metadata={"branch_id": appointment.branch_id}
    )
    
    return None


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentResponse)
def reschedule_appointment(
    appointment_id: str,
    reschedule_data: AppointmentReschedule,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reschedule an appointment to a different slot.
    
    Validates ownership, appointment status, and new slot availability.
    
    Args:
        appointment_id: ID of the appointment
        reschedule_data: Reschedule request data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        AppointmentResponse: Updated appointment
        
    Raises:
        HTTPException: 404 if not found, 403 if no access, 400 if cannot reschedule
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if appointment.customer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only reschedule your own appointments"
        )
    
    if appointment.status in [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reschedule this appointment"
        )
    
    new_slot = db.query(Slot).filter(Slot.id == reschedule_data.new_slot_id).first()
    if not new_slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="New slot not found"
        )
    
    if new_slot.appointment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New slot is already booked"
        )
    
    if new_slot.start_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reschedule to a past slot"
        )
    
    old_slot_id = appointment.slot_id
    
    appointment.slot_id = new_slot.id
    appointment.staff_id = new_slot.staff_id
    appointment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(appointment)
    
    create_audit_log(
        db=db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action_type=ActionType.APPOINTMENT_RESCHEDULED,
        entity_type="APPOINTMENT",
        entity_id=appointment.id,
        metadata={
            "old_slot_id": old_slot_id,
            "new_slot_id": new_slot.id
        }
    )
    
    return appointment

