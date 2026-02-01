"""
Common Pydantic Schemas
Shared response schemas across the application
"""

from pydantic import BaseModel
from typing import List, Any, Optional

class MessageResponse(BaseModel):
    message: str
    success: bool = True

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int