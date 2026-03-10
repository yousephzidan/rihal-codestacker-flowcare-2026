"""
Staff & Manager API Endpoints

Handles:
- Listing appointments (role-based)
- Updating appointment status
- Managing slots (create, update, soft-delete)
- Viewing audit logs
- System configuration
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
import csv
import io

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user, can_manage_branch
from app.models.models import (
    User, UserRole, Appointment, AppointmentStatus, Slot, 
    ServiceType, ActionType, SystemConfig, Branch
)
from app.schemas.schemas import (
    SlotCreate, SlotUpdate, SlotResponse, AppointmentUpdate,
    AppointmentResponse, PaginatedResponse, RetentionPeriodUpdate, 
    SystemConfigResponse
)
from app.services.audit_service import create_audit_log, get_audit_logs, get_branch_audit_logs

router = APIRouter(prefix="/management", tags=["Management"])


@router.get("/appointments", response_model=PaginatedResponse)
def list_appointments(
    branch_id: Optional[str] = Query(None, description="Filter by branch"),
    staff_id: Optional[str] = Query(None, description="Filter by staff"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Search term")
):
    """
    List appointments based on user role.
    
    - ADMIN: All appointments (optional branch filter)
    - BRANCH_MANAGER: Appointments in their branch
    - STAFF: Appointments assigned to them
    
    Args:
        branch_id: Optional filter by branch (admin only)
        staff_id: Optional filter by staff
        status_filter: Optional filter by status
        current_user: Current authenticated user
        db: Database session
        page: Page number
        size: Items per page
        search: Optional search term
        
    Returns:
        PaginatedResponse: List of appointments
        
    Raises:
        HTTPException: 403 if insufficient permissions
    """
    query = db.query(Appointment)
    
    if current_user.role == UserRole.ADMIN:
        if branch_id:
            query = query.filter(Appointment.branch_id == branch_id)
    
    elif current_user.role == UserRole.BRANCH_MANAGER:
        query = query.filter(Appointment.branch_id == current_user.branch_id)
    
    elif current_user.role == UserRole.STAFF:
        query = query.filter(Appointment.staff_id == current_user.id)
    
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    if staff_id:
        query = query.filter(Appointment.staff_id == staff_id)
    
    if status_filter:
        try:
            query = query.filter(Appointment.status == AppointmentStatus(status_filter))
        except ValueError:
            pass
    
    total = query.count()
    
    offset = (page - 1) * size
    appointments = query.order_by(Appointment.created_at.desc()).offset(offset).limit(size).all()
    
    return PaginatedResponse(
        results=[{
            "id": a.id,
            "customer_id": a.customer_id,
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


@router.patch("/appointments/{appointment_id}", response_model=AppointmentResponse)
def update_appointment_status(
    appointment_id: str,
    update_data: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update appointment status or notes.
    
    Staff can update their assigned appointments.
    Managers can update appointments in their branch.
    
    Args:
        appointment_id: ID of the appointment
        update_data: Update data (status, notes)
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        AppointmentResponse: Updated appointment
        
    Raises:
        HTTPException: 404 if not found, 403 if no access
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if current_user.role == UserRole.STAFF:
        if appointment.staff_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your assigned appointments"
            )
    
    elif current_user.role == UserRole.BRANCH_MANAGER:
        if appointment.branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update appointments in your branch"
            )
    
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    if update_data.status:
        old_status = appointment.status
        appointment.status = update_data.status
    
    if update_data.notes is not None:
        appointment.notes = update_data.notes
    
    appointment.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(appointment)
    
    if update_data.status:
        create_audit_log(
            db=db,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action_type=ActionType.APPOINTMENT_STATUS_CHANGED,
            entity_type="APPOINTMENT",
            entity_id=appointment.id,
            metadata={
                "old_status": old_status.value,
                "new_status": update_data.status.value
            }
        )
    
    return appointment


@router.post("/slots", response_model=SlotResponse, status_code=status.HTTP_201_CREATED)
def create_slot(
    slot_data: SlotCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new time slot.
    
    ADMIN can create in any branch.
    BRANCH_MANAGER can only create in their branch.
    
    Args:
        slot_data: Slot creation data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        SlotResponse: Created slot
        
    Raises:
        HTTPException: 403 if no access, 404 if branch/service not found, 400 for validation errors
    """
    if current_user.role == UserRole.BRANCH_MANAGER:
        if slot_data.branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create slots in your branch"
            )
    elif current_user.role not in [UserRole.ADMIN, UserRole.BRANCH_MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    branch = db.query(Branch).filter(Branch.id == slot_data.branch_id).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    service = db.query(ServiceType).filter(
        ServiceType.id == slot_data.service_type_id,
        ServiceType.branch_id == slot_data.branch_id
    ).first()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service type not found in this branch"
        )
    
    if slot_data.staff_id:
        staff = db.query(User).filter(
            User.id == slot_data.staff_id,
            User.branch_id == slot_data.branch_id
        ).first()
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Staff not found in this branch"
            )
    
    overlapping = db.query(Slot).filter(
        Slot.branch_id == slot_data.branch_id,
        Slot.staff_id == slot_data.staff_id,
        Slot.start_at < slot_data.end_at,
        Slot.end_at > slot_data.start_at,
        Slot.deleted_at == None
    ).first()
    
    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slot overlaps with existing slot"
        )
    
    slot = Slot(
        id=slot_data.id,
        branch_id=slot_data.branch_id,
        service_type_id=slot_data.service_type_id,
        staff_id=slot_data.staff_id,
        start_at=slot_data.start_at,
        end_at=slot_data.end_at,
        capacity=slot_data.capacity,
        is_active=True
    )
    
    db.add(slot)
    db.commit()
    db.refresh(slot)
    
    create_audit_log(
        db=db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action_type=ActionType.SLOT_CREATED,
        entity_type="SLOT",
        entity_id=slot.id,
        metadata={
            "branch_id": slot.branch_id,
            "service_type_id": slot.service_type_id,
            "start_at": slot.start_at.isoformat()
        }
    )
    
    return slot


@router.patch("/slots/{slot_id}", response_model=SlotResponse)
def update_slot(
    slot_id: str,
    update_data: SlotUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a slot's details.
    
    Can update start time, end time, capacity, or active status.
    
    Args:
        slot_id: ID of the slot
        update_data: Update data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        SlotResponse: Updated slot
        
    Raises:
        HTTPException: 404 if not found, 403 if no access
    """
    slot = db.query(Slot).filter(Slot.id == slot_id).first()
    
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found"
        )
    
    if current_user.role == UserRole.BRANCH_MANAGER:
        if slot.branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update slots in your branch"
            )
    elif current_user.role not in [UserRole.ADMIN, UserRole.BRANCH_MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    if update_data.start_at:
        slot.start_at = update_data.start_at
    if update_data.end_at:
        slot.end_at = update_data.end_at
    if update_data.capacity is not None:
        slot.capacity = update_data.capacity
    if update_data.is_active is not None:
        slot.is_active = update_data.is_active
    
    db.commit()
    db.refresh(slot)
    
    create_audit_log(
        db=db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action_type=ActionType.SLOT_UPDATED,
        entity_type="SLOT",
        entity_id=slot.id,
        metadata={"branch_id": slot.branch_id}
    )
    
    return slot


@router.delete("/slots/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_slot(
    slot_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Soft delete a slot.
    
    Sets deleted_at timestamp but keeps the record for audit purposes.
    
    Args:
        slot_id: ID of the slot
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        None
        
    Raises:
        HTTPException: 404 if not found, 403 if no access
    """
    slot = db.query(Slot).filter(Slot.id == slot_id).first()
    
    if not slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Slot not found"
        )
    
    if current_user.role == UserRole.BRANCH_MANAGER:
        if slot.branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete slots in your branch"
            )
    elif current_user.role not in [UserRole.ADMIN, UserRole.BRANCH_MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    slot.deleted_at = datetime.now(timezone.utc)
    db.commit()
    
    create_audit_log(
        db=db,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action_type=ActionType.SLOT_SOFT_DELETED,
        entity_type="SLOT",
        entity_id=slot.id,
        metadata={
            "branch_id": slot.branch_id,
            "deleted_at": slot.deleted_at.isoformat()
        }
    )
    
    return None


@router.get("/audit-logs", response_model=PaginatedResponse)
def list_audit_logs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    """
    View audit logs.
    
    ADMIN can see all logs.
    BRANCH_MANAGER can only see logs for their branch.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        page: Page number
        size: Items per page
        search: Optional search term
        
    Returns:
        PaginatedResponse: List of audit logs
        
    Raises:
        HTTPException: 403 if insufficient permissions
    """
    if current_user.role == UserRole.ADMIN:
        logs, total = get_audit_logs(
            db=db,
            page=page,
            size=size,
            search=search
        )
    elif current_user.role == UserRole.BRANCH_MANAGER:
        logs, total = get_branch_audit_logs(
            db=db,
            branch_id=current_user.branch_id,
            page=page,
            size=size,
            search=search
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    return PaginatedResponse(
        results=[{
            "id": log.id,
            "actor_id": log.actor_id,
            "actor_role": log.actor_role.value,
            "action_type": log.action_type.value,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "timestamp": log.timestamp.isoformat(),
            "metadata": log.extra_data
        } for log in logs],
        total=total,
        page=page,
        size=size
    )


@router.get("/audit-logs/export")
def export_audit_logs_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export audit logs as CSV file.
    
    Only admins can export audit logs.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        StreamingResponse: CSV file download
        
    Raises:
        HTTPException: 403 if not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can export audit logs"
        )
    
    logs, _ = get_audit_logs(db=db, page=1, size=10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Actor ID", "Actor Role", "Action Type", "Entity Type", "Entity ID", "Timestamp", "Metadata"])
    
    for log in logs:
        writer.writerow([
            log.id,
            log.actor_id,
            log.actor_role.value,
            log.action_type.value,
            log.entity_type,
            log.entity_id,
            log.timestamp.isoformat(),
            log.extra_data or ""
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"}
    )


@router.get("/config/retention-period", response_model=SystemConfigResponse)
def get_retention_period(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get soft delete retention period.
    
    Only admins can view this setting.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        SystemConfigResponse: Retention period configuration
        
    Raises:
        HTTPException: 403 if not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view this"
        )
    
    config = db.query(SystemConfig).filter(SystemConfig.key == "soft_delete_retention_days").first()
    if not config:
        return SystemConfigResponse(
            key="soft_delete_retention_days",
            value="30",
            description="Days to retain soft-deleted records"
        )
    
    return config


@router.put("/config/retention-period", response_model=SystemConfigResponse)
def update_retention_period(
    data: RetentionPeriodUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update soft delete retention period.
    
    Only admins can modify this setting.
    
    Args:
        data: Update data with new retention days
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        SystemConfigResponse: Updated configuration
        
    Raises:
        HTTPException: 403 if not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can update this"
        )
    
    config = db.query(SystemConfig).filter(SystemConfig.key == "soft_delete_retention_days").first()
    
    if not config:
        config = SystemConfig(
            key="soft_delete_retention_days",
            value=str(data.days),
            description="Days to retain soft-deleted records"
        )
        db.add(config)
    else:
        config.value = str(data.days)
    
    db.commit()
    db.refresh(config)
    
    return config


@router.delete("/slots/cleanup", status_code=status.HTTP_204_NO_CONTENT)
def cleanup_soft_deleted_slots(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete soft-deleted slots past retention period.
    
    Only admins can run this cleanup operation.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        None
        
    Raises:
        HTTPException: 403 if not admin
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can run cleanup"
        )
    
    config = db.query(SystemConfig).filter(SystemConfig.key == "soft_delete_retention_days").first()
    retention_days = int(config.value) if config else 30
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
    
    expired_slots = db.query(Slot).filter(
        Slot.deleted_at != None,
        Slot.deleted_at < cutoff_date
    ).all()
    
    for slot in expired_slots:
        slot_info = {
            "branch_id": slot.branch_id,
            "service_type_id": slot.service_type_id,
            "start_at": slot.start_at.isoformat()
        }
        
        db.query(Appointment).filter(Appointment.slot_id == slot.id).delete()
        
        db.delete(slot)
        
        create_audit_log(
            db=db,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action_type=ActionType.SLOT_HARD_DELETED,
            entity_type="SLOT",
            entity_id=slot.id,
            metadata=slot_info
        )
    
    db.commit()
    
    return None

