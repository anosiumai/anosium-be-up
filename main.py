"""
Main FastAPI Application
Multi-Clinic SaaS with AI Automation and Advanced Billing
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import logging

# Import routes
from routes.auth import router as auth_router
from routes.clinic import router as clinics_router
from routes.billing import router as billing_router
from routes.ai import router as ai_router

# Import database
from core.database import init_db, check_db_health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for startup and shutdown"""
    # Startup
    logger.info("Starting Clinic SaaS Application...")
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    # Check database health
    if check_db_health():
        logger.info("Database health check passed")
    else:
        logger.error("Database health check failed")
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Clinic SaaS Application...")


# Create FastAPI application
app = FastAPI(
    title="Clinic Management SaaS",
    description="""
    Multi-Clinic SaaS Platform with:
    - Multi-tenant architecture with complete clinic isolation
    - Advanced billing & invoicing system
    - AI-powered chatbot and lead management
    - Role-based access control
    - Subscription management
    
    Built with FastAPI, PostgreSQL, and optimized for high performance.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ==================== MIDDLEWARE ====================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip Middleware for response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add response time header to all requests"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"Status: {response.status_code}")
    return response


# ==================== ERROR HANDLERS ====================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": "Resource not found", "path": str(request.url)}
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Internal server error"}
    )


# ==================== ROUTES ====================

# Include routers
app.include_router(auth_router)
app.include_router(clinics_router)
app.include_router(billing_router)
app.include_router(ai_router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Clinic Management SaaS API",
        "version": "1.0.0",
        "features": [
            "Multi-Clinic Management",
            "Advanced Billing System",
            "AI-Powered Chatbot",
            "Lead Management",
            "Subscription Management"
        ],
        "docs": "/docs",
        "redoc": "/redoc",
        "status": "operational"
    }


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring"""
    db_healthy = check_db_health()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected",
        "timestamp": time.time()
    }


# System info endpoint
@app.get("/info", tags=["System"])
async def system_info():
    """System information endpoint"""
    return {
        "application": "Clinic Management SaaS",
        "version": "1.0.0",
        "python_version": "3.11+",
        "framework": "FastAPI",
        "database": "PostgreSQL",
        "features": {
            "multi_clinic": True,
            "ai_automation": True,
            "advanced_billing": True,
            "subscription_management": True
        }
    }


# ==================== DEMO DATA ENDPOINTS ====================

@app.post("/demo/setup", tags=["Demo"])
async def setup_demo_data():
    """
    Setup demo data for testing (Development only)
    Creates sample clinics, users, patients, etc.
    """
    from core.database import get_db_context
    from services.multi_clinic import MultiClinicService
    from core.security import AuthService
    from models.base import UserRole, SubscriptionTier
    from schemas.clinic import ClinicCreate
    
    try:
        with get_db_context() as db:
            # Create demo clinic
            clinic_data = ClinicCreate(
                name="Demo Medical Clinic",
                email="demo@clinic.com",
                phone="+1234567890",
                address="123 Medical Street, Healthcare City",
                subscription_tier=SubscriptionTier.PREMIUM
            )
            
            clinic = MultiClinicService.create_clinic(db, clinic_data)
            
            # Create admin user
            admin = AuthService.create_user(
                db=db,
                clinic_id=clinic.id,
                username="admin",
                email="admin@clinic.com",
                password="admin123",
                full_name="Admin User",
                role=UserRole.CLINIC_ADMIN,
                phone="+1234567890"
            )
            
            # Create doctor
            doctor = AuthService.create_user(
                db=db,
                clinic_id=clinic.id,
                username="doctor1",
                email="doctor1@clinic.com",
                password="doctor123",
                full_name="Dr. John Smith",
                role=UserRole.DOCTOR,
                phone="+1234567891",
                specialization="General Medicine",
                license_number="MD12345"
            )
            
            return {
                "message": "Demo data created successfully",
                "clinic": {
                    "id": clinic.id,
                    "code": clinic.clinic_code,
                    "name": clinic.name
                },
                "users": {
                    "admin": {
                        "username": "admin",
                        "password": "admin123"
                    },
                    "doctor": {
                        "username": "doctor1",
                        "password": "doctor123"
                    }
                }
            }
    except Exception as e:
        logger.error(f"Demo setup failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": f"Demo setup failed: {str(e)}"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )