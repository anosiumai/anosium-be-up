from typing import TypeVar, Generic, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar('T')

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    class Config:
        from_attributes = True

class SuccessResponse(BaseModel):
    """Standard success response"""
    success: bool = True
    message: str
    data: Optional[Any] = None

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Any] = None

class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    database: str
    redis: Optional[str] = None

class FileUpload(BaseModel):
    """File upload response"""
    filename: str
    url: str
    size: int
    content_type: str
    uploaded_at: datetime