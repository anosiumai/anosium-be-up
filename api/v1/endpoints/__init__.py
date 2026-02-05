"""
API v1 Endpoints Package
"""
from fastapi import APIRouter

# Create main API router
api_router = APIRouter()

# For now, just a simple test endpoint
@api_router.get("/test")
async def test_endpoint():
    return {"message": "API is working!", "status": "ok"}

# Export
__all__ = ["api_router"]
