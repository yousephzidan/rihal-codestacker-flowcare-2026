"""
File Retrieval API Endpoints

Handles:
- Retrieving customer ID images (admin only)
- Retrieving appointment attachments (authorized users)
"""

import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.models import User, UserRole, Appointment
from app.services.file_service import get_file_path

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/customer/{customer_id}/id-image")
def get_customer_id_image(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get customer ID image.
    
    Only admins can retrieve customer ID images.
    
    Args:
        customer_id: ID of the customer
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        FileResponse: Image file
        
    Raises:
        HTTPException: 403 if not admin, 404 if not found
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access customer ID images"
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    if not customer.id_image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ID image on file"
        )
    
    filepath = get_file_path(customer.id_image_path)
    
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    content_type = "image/jpeg"
    if filepath.endswith(".png"):
        content_type = "image/png"
    
    return FileResponse(
        filepath,
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename={os.path.basename(filepath)}"}
    )


@router.get("/appointments/{appointment_id}/attachment")
def get_appointment_attachment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get appointment attachment file.
    
    Access:
    - Admin: any attachment
    - Branch Manager: attachments in their branch
    - Staff: attachments for their appointments
    - Customer: their own appointment attachments
    
    Args:
        appointment_id: ID of the appointment
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        FileResponse: Attachment file
        
    Raises:
        HTTPException: 404 if not found, 403 if no access
    """
    from app.models.models import Appointment
    
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    if current_user.role == UserRole.CUSTOMER:
        if appointment.customer_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own appointment attachments"
            )
    
    elif current_user.role == UserRole.STAFF:
        if appointment.staff_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view attachments for your appointments"
            )
    
    elif current_user.role == UserRole.BRANCH_MANAGER:
        if appointment.branch_id != current_user.branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view attachments in your branch"
            )
    
    if not appointment.attachment_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No attachment on file"
        )
    
    filepath = get_file_path(appointment.attachment_path)
    
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if filepath.endswith(".pdf"):
        content_type = "application/pdf"
    elif filepath.endswith(".png"):
        content_type = "image/png"
    else:
        content_type = "image/jpeg"
    
    return FileResponse(
        filepath,
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename={os.path.basename(filepath)}"}
    )

