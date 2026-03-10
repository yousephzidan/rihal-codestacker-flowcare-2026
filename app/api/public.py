"""
Public API Endpoints

Accessible endpoints that don't require authentication:
- List branches
- List services by branch
- List available slots
"""

from typing import Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import PaginatedResponse
from app.models.models import Branch, ServiceType, Slot

router = APIRouter(prefix="", tags=["Public"])


@router.get("/branches", response_model=PaginatedResponse)
def list_branches(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term (name, city)")
):
    """
    List all active branches (public endpoint).
    
    Returns paginated list of branches with optional search.
    
    Args:
        db: Database session
        page: Page number (default: 1)
        size: Items per page (default: 10, max: 100)
        search: Optional search term for name or city
        
    Returns:
        PaginatedResponse: Paginated list of branches
        
    Raises:
        None
    """
    query = db.query(Branch).filter(Branch.is_active == True)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Branch.name.ilike(search_term)) | 
            (Branch.city.ilike(search_term))
        )
    
    total = query.count()
    
    offset = (page - 1) * size
    branches = query.order_by(Branch.name).offset(offset).limit(size).all()
    
    return PaginatedResponse(
        results=[{
            "id": b.id,
            "name": b.name,
            "city": b.city,
            "address": b.address,
            "timezone": b.timezone
        } for b in branches],
        total=total,
        page=page,
        size=size
    )


@router.get("/branches/{branch_id}/services", response_model=PaginatedResponse)
def list_services_by_branch(
    branch_id: str,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None)
):
    """
    List services offered by a branch (public endpoint).
    
    Returns active service types available at the specified branch.
    
    Args:
        branch_id: ID of the branch
        db: Database session
        page: Page number (default: 1)
        size: Items per page (default: 10, max: 100)
        search: Optional search term for service name
        
    Returns:
        PaginatedResponse: Paginated list of services
        
    Raises:
        HTTPException: 404 if branch not found
    """
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    query = db.query(ServiceType).filter(
        ServiceType.branch_id == branch_id,
        ServiceType.is_active == True
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(ServiceType.name.ilike(search_term))
    
    total = query.count()
    
    offset = (page - 1) * size
    services = query.order_by(ServiceType.name).offset(offset).limit(size).all()
    
    return PaginatedResponse(
        results=[{
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "duration_minutes": s.duration_minutes
        } for s in services],
        total=total,
        page=page,
        size=size
    )


@router.get("/branches/{branch_id}/slots", response_model=PaginatedResponse)
def list_available_slots(
    branch_id: str,
    service_type_id: Optional[str] = Query(None, description="Filter by service type"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    """
    List available slots at a branch (public endpoint).
    
    Returns slots that are:
    - In the future (not past)
    - Active (not disabled)
    - Not soft-deleted
    - Not already booked
    
    Supports filtering by service_type_id and date.
    
    Args:
        branch_id: ID of the branch
        service_type_id: Optional filter by service type
        date: Optional filter by date (YYYY-MM-DD format)
        db: Database session
        page: Page number (default: 1)
        size: Items per page (default: 20, max: 100)
        
    Returns:
        PaginatedResponse: Paginated list of available slots
        
    Raises:
        HTTPException: 404 if branch not found, 400 if invalid date format
    """
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Branch not found"
        )
    
    now = datetime.now(timezone.utc)
    query = db.query(Slot).filter(
        Slot.branch_id == branch_id,
        Slot.is_active == True,
        Slot.deleted_at == None,
        Slot.start_at > now
    )
    
    if service_type_id:
        query = query.filter(Slot.service_type_id == service_type_id)
    
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(
                Slot.start_at >= filter_date,
                Slot.start_at < filter_date.replace(day=filter_date.day + 1)
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    
    total = query.count()
    
    offset = (page - 1) * size
    slots = query.order_by(Slot.start_at).offset(offset).limit(size).all()
    
    available_slots = []
    for slot in slots:
        if not slot.appointment:
            available_slots.append({
                "id": slot.id,
                "service_type_id": slot.service_type_id,
                "staff_id": slot.staff_id,
                "start_at": slot.start_at.isoformat(),
                "end_at": slot.end_at.isoformat(),
                "capacity": slot.capacity
            })
    
    return PaginatedResponse(
        results=available_slots,
        total=len(available_slots),
        page=page,
        size=size
    )

