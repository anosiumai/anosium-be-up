"""
Hospital Management System - Main Application
Multi-tenant SaaS for healthcare management with AI automation
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time


from core.config import settings
from core.database import init_db, check_db_connection, engine

# ✅ CRITICAL FIX: Import and rebuild models BEFORE importing routers
# This must happen before api_router import to avoid Pydantic forward reference errors
from schemas import rebuild_all_models  
rebuild_all_models()  # Rebuild immediately to resolve forward references

# NOW safe to import routers (they reference Doctor and other models)
from api.v1.endpoints import api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown
    """
    # Startup
    logger.info("🚀 Starting Hospital Management System...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    # Models already rebuilt at module level - no need to rebuild again here
    logger.info("✅ Pydantic models rebuilt successfully")
    
    # Check database connection
    if not check_db_connection():
        logger.error("❌ Failed to connect to database")
        raise RuntimeError("Database connection failed")
    
    logger.info("✅ Database connection established")
    
    # Initialize database tables (only in development)
    if settings.ENVIRONMENT == "development":
        try:
            init_db()
            logger.info("✅ Database tables initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {str(e)}")
    
    logger.info("✅ Application started successfully")
    logger.info(f"📝 API Documentation: http://localhost:8000/docs")
    logger.info(f"📊 ReDoc Documentation: http://localhost:8000/redoc")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Hospital Management System...")
    engine.dispose()
    logger.info("✅ Database connections closed")
    logger.info("👋 Application shutdown complete")

# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## Hospital Management System API
    
    Multi-tenant SaaS platform for healthcare management with:
    
    * 🏥 **Multi-Clinic Management** - Complete tenant isolation
    * 👥 **Patient Management** - Comprehensive patient records
    * 👨‍⚕️ **Doctor Scheduling** - Smart appointment system
    * 💊 **Visit Management** - Clinical workflow automation
    * 💰 **Billing & Payments** - Revenue cycle management
    * 🤖 **AI Lead Capture** - Automated patient acquisition
    * 📧 **Notifications** - Multi-channel messaging
    * 📊 **Analytics** - Real-time insights and reporting
    * 🔐 **Security** - HIPAA/GDPR compliant
    
    ### Authentication
    
    All endpoints (except public registration) require JWT authentication.
    
    1. Register a tenant: `POST /api/v1/tenants`
    2. Login: `POST /api/v1/auth/login`
    3. Use the access token in Authorization header: `Bearer <token>`
    
    ### Multi-Tenancy
    
    Each clinic (tenant) has complete data isolation. Users can only access
    data within their tenant unless they have SUPER_ADMIN role.
    
    ### Rate Limiting
    
    API requests are rate-limited to prevent abuse. Current limit: 
    {0} requests per minute.
    
    ### Support
    
    For API support, contact: support@yourhospital.com
    """.format(settings.RATE_LIMIT_PER_MINUTE),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Authorization"],
)

# GZip Compression Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted Host Middleware (security)
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourhospital.com", "*.yourhospital.com"]
    )


# Request ID and Timing Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request ID and processing time to response headers"""
    request_id = request.headers.get("X-Request-ID", f"req-{int(time.time() * 1000)}")
    start_time = time.time()
    
    # Add request ID to request state for logging
    request.state.request_id = request_id
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)
    
    # Log slow requests
    if process_time > 1.0:
        logger.warning(
            f"Slow request: {request.method} {request.url.path} "
            f"took {process_time:.2f}s"
        )
    
    return response


# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(
        f"Request: {request.method} {request.url.path} "
        f"from {request.client.host if request.client else 'unknown'}"
    )
    
    response = await call_next(request)
    
    logger.info(
        f"Response: {request.method} {request.url.path} "
        f"status={response.status_code}"
    )
    
    return response


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "HTTPException"
            },
            "request_id": getattr(request.state, "request_id", None)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": 422,
                "message": "Validation error",
                "type": "ValidationError",
                "details": errors
            },
            "request_id": getattr(request.state, "request_id", None)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    # Don't expose internal error details in production
    if settings.ENVIRONMENT == "production":
        message = "An internal error occurred. Please try again later."
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": message,
                "type": "InternalServerError"
            },
            "request_id": getattr(request.state, "request_id", None)
        }
    )


# ============================================================================
# HEALTH CHECK ENDPOINTS
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns system health status including:
    - API status
    - Database connectivity
    - Version information
    """
    db_healthy = check_db_connection()
    
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {
            "database": "connected" if db_healthy else "disconnected",
            "api": "operational"
        },
        "timestamp": time.time()
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness check for Kubernetes/Docker
    
    Returns 200 if service is ready to accept traffic
    """
    if not check_db_connection():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "reason": "database unavailable"}
        )
    
    return {"status": "ready"}


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """
    Liveness check for Kubernetes/Docker
    
    Returns 200 if service is alive
    """
    return {"status": "alive"}


# ============================================================================
# API ROUTES
# ============================================================================

# Include all API v1 routes
app.include_router(
    api_router,
    prefix=settings.API_V1_PREFIX
)


# ============================================================================
# STARTUP MESSAGE
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("=" * 80)
    logger.info(f"🏥 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info("=" * 80)
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info("=" * 80)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )