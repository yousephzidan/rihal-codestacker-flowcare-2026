"""
Audit Log Service

Handles:
- Creating audit log entries for sensitive actions
- Retrieving audit logs with filtering
- Branch-specific audit log retrieval
"""

import json
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from sqlalchemy.orm import Session

from app.models.models import AuditLog, UserRole, ActionType


def create_audit_log(
    db: Session,
    actor_id: str,
    actor_role: UserRole,
    action_type: ActionType,
    entity_type: str,
    entity_id: str,
    metadata: Optional[dict] = None
) -> AuditLog:
    """
    Create a new audit log entry.
    
    Args:
        db: Database session
        actor_id: ID of user who performed the action
        actor_role: Role of the user at time of action
        action_type: Type of action performed
        entity_type: Type of entity affected (e.g., "APPOINTMENT", "SLOT")
        entity_id: ID of the affected entity
        metadata: Optional additional data (dict, JSON serialized)
        
    Returns:
        AuditLog: The created audit log entry
        
    Raises:
        None
    """
    metadata_str = None
    if metadata:
        metadata_str = json.dumps(metadata)
    
    audit_log = AuditLog(
        id=f"aud_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{actor_id[:8]}",
        actor_id=actor_id,
        actor_role=actor_role,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        timestamp=datetime.now(timezone.utc),
        extra_data=metadata_str
    )
    
    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)
    
    return audit_log


def get_audit_logs(
    db: Session,
    actor_id: Optional[str] = None,
    action_type: Optional[ActionType] = None,
    entity_type: Optional[str] = None,
    branch_id: Optional[str] = None,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None
) -> Tuple[List[AuditLog], int]:
    """
    Get audit logs with filtering and pagination.
    
    Args:
        db: Database session
        actor_id: Filter by actor
        action_type: Filter by action type
        entity_type: Filter by entity type
        branch_id: Filter by branch
        page: Page number
        size: Items per page
        search: Search term
        
    Returns:
        Tuple[List[AuditLog], int]: Tuple of (audit logs list, total count)
        
    Raises:
        None
    """
    query = db.query(AuditLog)
    
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    
    if action_type:
        query = query.filter(AuditLog.action_type == action_type)
    
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    
    if search:
        query = query.filter(AuditLog.extra_data.ilike(f"%{search}%"))
    
    total = query.count()
    
    offset = (page - 1) * size
    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(size).all()
    
    return logs, total


def get_branch_audit_logs(
    db: Session,
    branch_id: str,
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None
) -> Tuple[List[AuditLog], int]:
    """
    Get audit logs for a specific branch.
    
    Used by Branch Managers to see logs for their branch.
    
    Args:
        db: Database session
        branch_id: Branch ID to filter by
        page: Page number
        size: Items per page
        search: Search term
        
    Returns:
        Tuple[List[AuditLog], int]: Tuple of (audit logs list, total count)
        
    Raises:
        None
    """
    query = db.query(AuditLog).filter(
        AuditLog.extra_data.ilike(f"%{branch_id}%")
    )
    
    if search:
        query = query.filter(AuditLog.extra_data.ilike(f"%{search}%"))
    
    total = query.count()
    
    offset = (page - 1) * size
    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(size).all()
    
    return logs, total

