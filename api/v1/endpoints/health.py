"""
Health Check Endpoint
Simple endpoint for testing the API
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping():
    """Simple ping endpoint"""
    return {"message": "pong", "status": "ok"}


@router.get("/test")
async def test():
    """Test endpoint"""
    return {
        "message": "Hospital Management System API is running!",
        "version": "1.0.0",
        "status": "operational"
    }