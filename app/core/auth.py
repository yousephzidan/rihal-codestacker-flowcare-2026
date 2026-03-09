"""
Authentication & Authorization

This module handles password hashing, HTTP Basic authentication,
and role-based access control (RBAC) for the FlowCare application.
"""

from datetime import datetime, timezone
from typing import Optional, List
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.models.models import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBasic()


def hash_password(password: str) -> str:
    """
    Hash a plain-text password using bcrypt.
    
    Args:
        password: Plain-text password to hash
        
    Returns:
        str: Hashed password string
        
    Raises:
        None
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a stored hash.
    
    Args:
        plain_password: Plain-text password to verify
        hashed_password: Stored hashed password
        
    Returns:
        bool: True if password matches, False otherwise
        
    Raises:
        None
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get the currently authenticated user from HTTP Basic Auth credentials.
    
    This is the main authentication dependency for protected endpoints.
    It validates credentials and returns the user object.
    
    Args:
        credentials: HTTP Basic Auth credentials (username/password)
        db: Database session
        
    Returns:
        User: User object if authentication successful
        
    Raises:
        HTTPException: 401 if credentials are invalid, 403 if account is disabled
    """
    user = db.query(User).filter(User.username == credentials.username).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user


def require_role(*allowed_roles: UserRole):
    """
    Create a dependency for role-based access control.
    
    Usage:
        @app.get("/admin/users")
        def get_users(current_user: User = Depends(require_role(UserRole.ADMIN))):
            ...
    
    Args:
        *allowed_roles: User roles permitted to access the endpoint
        
    Returns:
        Dependency function that checks user's role
        
    Raises:
        HTTPException: 403 if user role is not allowed
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    
    return role_checker


def require_branch_access(branch_id: str):
    """
    Create a dependency for branch-scoped access control.
    
    Ensures Branch Managers can only access data from their assigned branch.
    Admins have full access to all branches.
    
    Args:
        branch_id: ID of the branch being accessed
        
    Returns:
        Dependency function that checks branch access
        
    Raises:
        HTTPException: 403 if user doesn't have branch access
    """
    def branch_checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if current_user.role == UserRole.ADMIN:
            return current_user
        
        if current_user.role == UserRole.BRANCH_MANAGER:
            if current_user.branch_id != branch_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only access your assigned branch"
                )
            return current_user
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions for this operation"
        )
    
    return branch_checker


def can_manage_branch(user: User, branch_id: str) -> bool:
    """
    Check if user has permission to manage a specific branch.
    
    Args:
        user: User to check
        branch_id: ID of the branch
        
    Returns:
        bool: True if user can manage the branch
        
    Raises:
        None
    """
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.BRANCH_MANAGER and user.branch_id == branch_id:
        return True
    return False


def can_view_branch_audit_logs(user: User, branch_id: str) -> bool:
    """
    Check if user has permission to view audit logs for a branch.
    
    Args:
        user: User to check
        branch_id: ID of the branch
        
    Returns:
        bool: True if user can view audit logs
        
    Raises:
        None
    """
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.BRANCH_MANAGER and user.branch_id == branch_id:
        return True
    return False


def can_modify_appointment(user: User, appointment) -> bool:
    """
    Check if user has permission to modify an appointment.
    
    Business Rules:
    - Admins can modify any appointment
    - Branch Managers can modify appointments in their branch
    - Customers can only modify their own appointments
    
    Args:
        user: User to check
        appointment: Appointment object
        
    Returns:
        bool: True if user can modify the appointment
        
    Raises:
        None
    """
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.BRANCH_MANAGER and appointment.branch_id == user.branch_id:
        return True
    if user.role == UserRole.CUSTOMER and appointment.customer_id == user.id:
        return True
    return False

