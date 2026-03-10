"""
Seed Data Service

Handles importing seed data from JSON file for initial database population.
Uses idempotent logic - running multiple times won't duplicate data.
"""

import json
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.models import (
    Branch, ServiceType, User, StaffServiceType, Slot, Appointment, 
    AuditLog, SystemConfig, UserRole, AppointmentStatus, ActionType
)
from app.core.auth import hash_password

settings = get_settings()


def load_seed_data() -> dict:
    """Load seed data from JSON file"""
    import os
    seed_file = os.path.join(os.path.dirname(__file__), "../example.json")
    
    if not os.path.exists(seed_file):
        seed_file = "../example.json"
    
    with open(seed_file, "r") as f:
        return json.load(f)


def seed_branches(db: Session, data: dict):
    """Seed branches"""
    for branch_data in data.get("branches", []):
        branch = db.query(Branch).filter(Branch.id == branch_data["id"]).first()
        
        if not branch:
            branch = Branch(
                id=branch_data["id"],
                name=branch_data["name"],
                city=branch_data["city"],
                address=branch_data["address"],
                timezone=branch_data.get("timezone", "Asia/Muscat"),
                is_active=branch_data.get("is_active", True)
            )
            db.add(branch)
        else:
            branch.name = branch_data["name"]
            branch.city = branch_data["city"]
            branch.address = branch_data["address"]
    
    db.commit()


def seed_service_types(db: Session, data: dict):
    """Seed service types"""
    for service_data in data.get("service_types", []):
        service = db.query(ServiceType).filter(ServiceType.id == service_data["id"]).first()
        
        if not service:
            service = ServiceType(
                id=service_data["id"],
                branch_id=service_data["branch_id"],
                name=service_data["name"],
                description=service_data.get("description"),
                duration_minutes=service_data["duration_minutes"],
                is_active=service_data.get("is_active", True)
            )
            db.add(service)
    
    db.commit()


def seed_users(db: Session, data: dict):
    """Seed all users (admin, managers, staff, customers)"""
    
    for user_data in data.get("users", {}).get("admin", []):
        seed_single_user(db, user_data)
    
    for user_data in data.get("users", {}).get("branch_managers", []):
        seed_single_user(db, user_data)
    
    for user_data in data.get("users", {}).get("staff", []):
        seed_single_user(db, user_data)
    
    for user_data in data.get("users", {}).get("customers", []):
        seed_single_user(db, user_data)
    
    db.commit()


def seed_single_user(db: Session, user_data: dict):
    """Seed a single user (idempotent)"""
    user = db.query(User).filter(User.id == user_data["id"]).first()
    
    if not user:
        user = User(
            id=user_data["id"],
            username=user_data["username"],
            password_hash=hash_password(user_data["password"]),
            role=UserRole(user_data["role"]),
            full_name=user_data["full_name"],
            email=user_data["email"],
            is_active=user_data.get("is_active", True),
            branch_id=user_data.get("branch_id")
        )
        db.add(user)


def seed_staff_service_types(db: Session, data: dict):
    """Seed staff-service type assignments"""
    for assignment_data in data.get("staff_service_types", []):
        assignment_id = f"sst_{assignment_data['staff_id']}_{assignment_data['service_type_id']}"
        
        assignment = db.query(StaffServiceType).filter(StaffServiceType.id == assignment_id).first()
        
        if not assignment:
            assignment = StaffServiceType(
                id=assignment_id,
                staff_id=assignment_data["staff_id"],
                service_type_id=assignment_data["service_type_id"]
            )
            db.add(assignment)
    
    db.commit()


def seed_slots(db: Session, data: dict):
    """Seed time slots"""
    from datetime import timedelta
    
    for i, slot_data in enumerate(data.get("slots", [])):
        slot = db.query(Slot).filter(Slot.id == slot_data["id"]).first()
        
        if not slot:
            base_date = datetime.now(timezone.utc) + timedelta(days=i%7)
            
            hour = 9 + (i * 2) % 8
            start_at = base_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            end_at = start_at + timedelta(minutes=15)
            
            from datetime import timedelta
            start_at = start_at + timedelta(hours=4)
            end_at = end_at + timedelta(hours=4)
            
            slot = Slot(
                id=slot_data["id"],
                branch_id=slot_data["branch_id"],
                service_type_id=slot_data["service_type_id"],
                staff_id=slot_data.get("staff_id"),
                start_at=start_at,
                end_at=end_at,
                capacity=slot_data.get("capacity", 1),
                is_active=slot_data.get("is_active", True)
            )
            db.add(slot)
    
    db.commit()


def seed_appointments(db: Session, data: dict):
    """Seed sample appointments"""
    for appt_data in data.get("appointments", []):
        appointment = db.query(Appointment).filter(Appointment.id == appt_data["id"]).first()
        
        if not appointment:
            slot = db.query(Slot).filter(Slot.id == appt_data["slot_id"]).first()
            if not slot:
                continue
            
            created_at = datetime.fromisoformat(appt_data["created_at"].replace("+04:00", "+04:00"))
            
            appointment = Appointment(
                id=appt_data["id"],
                customer_id=appt_data["customer_id"],
                branch_id=appt_data["branch_id"],
                service_type_id=appt_data["service_type_id"],
                slot_id=appt_data["slot_id"],
                staff_id=appt_data.get("staff_id"),
                status=AppointmentStatus(appt_data["status"]),
                created_at=created_at,
                updated_at=created_at
            )
            db.add(appointment)
    
    db.commit()


def seed_audit_logs(db: Session, data: dict):
    """Seed audit logs"""
    for log_data in data.get("audit_logs", []):
        log = db.query(AuditLog).filter(AuditLog.id == log_data["id"]).first()
        
        if not log:
            timestamp = datetime.fromisoformat(log_data["timestamp"].replace("+04:00", "+04:00"))
            
            log = AuditLog(
                id=log_data["id"],
                actor_id=log_data["actor_id"],
                actor_role=UserRole(log_data["actor_role"]),
                action_type=ActionType(log_data["action_type"]),
                entity_type=log_data["entity_type"],
                entity_id=log_data["entity_id"],
                timestamp=timestamp,
                metadata=json.dumps(log_data.get("metadata"))
            )
            db.add(log)
    
    db.commit()


def seed_system_config(db: Session):
    """Seed system configuration"""
    config = db.query(SystemConfig).filter(SystemConfig.key == "soft_delete_retention_days").first()
    
    if not config:
        config = SystemConfig(
            key="soft_delete_retention_days",
            value=str(settings.SOFT_DELETE_RETENTION_DAYS),
            description="Days to retain soft-deleted records"
        )
        db.add(config)
        db.commit()


def seed_database(db: Session):
    """
    Main seed function - imports all seed data.
    
    This is idempotent - running multiple times won't duplicate data.
    """
    print("Loading seed data...")
    data = load_seed_data()
    
    print("Seeding branches...")
    seed_branches(db, data)
    
    print("Seeding service types...")
    seed_service_types(db, data)
    
    print("Seeding users...")
    seed_users(db, data)
    
    print("Seeding staff-service type assignments...")
    seed_staff_service_types(db, data)
    
    print("Seeding slots...")
    seed_slots(db, data)
    
    print("Seeding appointments...")
    seed_appointments(db, data)
    
    print("Seeding audit logs...")
    seed_audit_logs(db, data)
    
    print("Seeding system config...")
    seed_system_config(db)
    
    print("Seed completed successfully!")

