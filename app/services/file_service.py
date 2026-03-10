"""
File Storage Service

Handles:
- Saving customer ID images
- Saving appointment attachments
- File validation and retrieval
- File deletion
"""

import os
import base64
import uuid
from typing import Optional

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import get_settings

settings = get_settings()


def validate_image_content_type(content_type: str) -> bool:
    """
    Check if content type is a valid image type.
    
    Args:
        content_type: MIME type string to validate
        
    Returns:
        bool: True if valid image type
        
    Raises:
        None
    """
    return content_type in settings.ALLOWED_IMAGE_TYPES


def validate_document_content_type(content_type: str) -> bool:
    """
    Check if content type is a valid document type.
    
    Args:
        content_type: MIME type string to validate
        
    Returns:
        bool: True if valid document type
        
    Raises:
        None
    """
    return content_type in settings.ALLOWED_DOCUMENT_TYPES


def validate_file_size(size_bytes: int) -> bool:
    """
    Check if file size is within limits.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        bool: True if within size limit
        
    Raises:
        None
    """
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    return size_bytes <= max_bytes


def save_customer_id_image(base64_data: str, customer_id: str) -> str:
    """
    Save a customer's ID image.
    
    Args:
        base64_data: Base64 encoded image data
        customer_id: ID of the customer
        
    Returns:
        str: Relative path to the saved file
        
    Raises:
        HTTPException: 400 if validation fails
    """
    try:
        if "," in base64_data:
            header, base64_data = base64_data.split(",", 1)
            content_type = header.split(";")[0].replace("data:", "")
        else:
            content_type = "image/jpeg"
        
        if not validate_image_content_type(content_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image type. Allowed: {settings.ALLOWED_IMAGE_TYPES}"
            )
        
        image_bytes = base64.b64decode(base64_data)
        
        if not validate_file_size(len(image_bytes)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        ext = ".jpg" if "jpeg" in content_type or "jpg" in content_type else ".png"
        
        filename = f"{customer_id}{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, "customer_ids", filename)
        
        with open(filepath, "wb") as f:
            f.write(image_bytes)
        
        return f"customer_ids/{filename}"
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to save image: {str(e)}"
        )


def save_appointment_attachment(base64_data: str, appointment_id: str) -> str:
    """
    Save an appointment attachment file.
    
    Args:
        base64_data: Base64 encoded file data
        appointment_id: ID of the appointment
        
    Returns:
        str: Relative path to the saved file
        
    Raises:
        HTTPException: 400 if validation fails
    """
    try:
        if "," in base64_data:
            header, base64_data = base64_data.split(",", 1)
            content_type = header.split(";")[0].replace("data:", "")
        else:
            content_type = "application/pdf"
        
        if not validate_image_content_type(content_type) and not validate_document_content_type(content_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Allowed: images and PDF"
            )
        
        file_bytes = base64.b64decode(base64_data)
        
        if not validate_file_size(len(file_bytes)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        if "pdf" in content_type:
            ext = ".pdf"
        elif "jpeg" in content_type or "jpg" in content_type:
            ext = ".jpg"
        elif "png" in content_type:
            ext = ".png"
        else:
            ext = ""
        
        filename = f"{appointment_id}{ext}"
        filepath = os.path.join(settings.UPLOAD_DIR, "attachments", filename)
        
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        
        return f"attachments/{filename}"
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to save attachment: {str(e)}"
        )


def get_file_path(relative_path: str) -> str:
    """
    Get absolute path for a relative file path.
    
    Args:
        relative_path: Relative path to the file
        
    Returns:
        str: Absolute file path
        
    Raises:
        None
    """
    return os.path.join(settings.UPLOAD_DIR, relative_path)


def file_exists(relative_path: str) -> bool:
    """
    Check if a file exists.
    
    Args:
        relative_path: Relative path to check
        
    Returns:
        bool: True if file exists
        
    Raises:
        None
    """
    filepath = get_file_path(relative_path)
    return os.path.exists(filepath)


def delete_file(relative_path: str) -> bool:
    """
    Delete a file.
    
    Args:
        relative_path: Relative path to the file
        
    Returns:
        bool: True if deleted, False if file didn't exist
        
    Raises:
        None
    """
    filepath = get_file_path(relative_path)
    if os.path.exists(filepath):
        os.remove(filepath)
        return True
    return False

