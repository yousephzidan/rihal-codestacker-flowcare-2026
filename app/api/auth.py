"""
Authentication API Endpoints

Handles customer registration and user info retrieval.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user, hash_password
from app.models.models import User, UserRole
from app.schemas.schemas import CustomerRegister, UserResponse, PaginatedResponse
from app.services.file_service import save_customer_id_image, file_exists, get_file_path

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_customer(
    registration: CustomerRegister,
    db: Session = Depends(get_db)
):
    """
    Register a new customer.
    
    Requires:
    - Unique username and email
    - Phone number
    - ID image (base64 encoded)
    - Password meeting strength requirements
    
    Args:
        registration: Customer registration data
        db: Database session
        
    Returns:
        UserResponse: Created user profile
        
    Raises:
        HTTPException: 400 if username/email already exists
    """
    if db.query(User).filter(User.username == registration.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    if db.query(User).filter(User.email == registration.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user_id = f"usr_cust_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    
    id_image_path = save_customer_id_image(registration.id_image, user_id)
    
    user = User(
        id=user_id,
        username=registration.username,
        password_hash=hash_password(registration.password),
        full_name=registration.full_name,
        email=registration.email,
        phone=registration.phone,
        role=UserRole.CUSTOMER,
        id_image_path=id_image_path,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    Requires authentication (HTTP Basic Auth).
    
    Args:
        current_user: Current authenticated user (injected by dependency)
        
    Returns:
        UserResponse: Current user's profile
        
    Raises:
        None
    """
    return current_user

