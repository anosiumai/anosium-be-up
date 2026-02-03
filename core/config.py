"""
Application Configuration
Handles all environment variables and settings
"""

from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Hospital Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/hospital_db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password Requirements
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Email (Optional - configure if using email features)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: Optional[str] = None
    SMTP_TLS: bool = True
    
    # SMS (Optional - configure if using SMS features)
    SMS_PROVIDER: Optional[str] = None  # twilio, aws_sns, etc.
    SMS_API_KEY: Optional[str] = None
    SMS_API_SECRET: Optional[str] = None
    SMS_FROM_NUMBER: Optional[str] = None
    
    # WhatsApp (Optional)
    WHATSAPP_API_KEY: Optional[str] = None
    WHATSAPP_API_URL: Optional[str] = None
    
    # File Storage
    UPLOAD_DIR: str = "/tmp/uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = [
        "jpg", "jpeg", "png", "gif", "pdf", "doc", "docx"
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or text
    LOG_FILE: Optional[str] = None
    
    # Redis (Optional - for caching and session management)
    REDIS_URL: Optional[str] = None
    REDIS_ENABLED: bool = False
    REDIS_CACHE_TTL: int = 300  # 5 minutes
    
    # Celery (Optional - for background tasks)
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    # Sentry (Optional - for error tracking)
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: Optional[str] = None
    
    # AI/ML Features
    AI_ENABLED: bool = False
    OPENAI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4"
    
    # Subscription Limits
    FREE_TIER_MAX_PATIENTS: int = 50
    FREE_TIER_MAX_DOCTORS: int = 2
    FREE_TIER_MAX_APPOINTMENTS_PER_MONTH: int = 100
    
    BASIC_TIER_MAX_PATIENTS: int = 500
    BASIC_TIER_MAX_DOCTORS: int = 5
    BASIC_TIER_MAX_APPOINTMENTS_PER_MONTH: int = 1000
    
    PREMIUM_TIER_MAX_PATIENTS: int = 5000
    PREMIUM_TIER_MAX_DOCTORS: int = 20
    PREMIUM_TIER_MAX_APPOINTMENTS_PER_MONTH: int = 10000
    
    # Audit and Compliance
    AUDIT_LOG_RETENTION_DAYS: int = 365
    DATA_RETENTION_DAYS: int = 2555  # ~7 years for medical records
    ENABLE_DATA_ACCESS_LOGGING: bool = True  # HIPAA compliance
    
    # Timezone
    DEFAULT_TIMEZONE: str = "UTC"
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v):
        if not v or v == "postgresql://user:password@localhost:5432/hospital_db":
            raise ValueError(
                "DATABASE_URL must be set in environment variables. "
                "Example: postgresql://username:password@host:port/database"
            )
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v, values):
        if values.get("ENVIRONMENT") == "production":
            if len(v) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")
            if v == "your-secret-key-change-in-production-min-32-chars":
                raise ValueError("SECRET_KEY must be changed from default value in production")
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create global settings instance
settings = Settings()


# Helper function to check if feature is enabled
def is_feature_enabled(feature: str) -> bool:
    """Check if a feature is enabled based on settings"""
    feature_flags = {
        "ai": settings.AI_ENABLED,
        "email": bool(settings.SMTP_HOST),
        "sms": bool(settings.SMS_API_KEY),
        "whatsapp": bool(settings.WHATSAPP_API_KEY),
        "redis": settings.REDIS_ENABLED,
        "celery": bool(settings.CELERY_BROKER_URL),
        "sentry": bool(settings.SENTRY_DSN),
    }
    return feature_flags.get(feature.lower(), False)


# Helper function to get tier limits
def get_tier_limits(tier: str) -> dict:
    """Get resource limits for a subscription tier"""
    tier_configs = {
        "FREE": {
            "max_patients": settings.FREE_TIER_MAX_PATIENTS,
            "max_doctors": settings.FREE_TIER_MAX_DOCTORS,
            "max_appointments_per_month": settings.FREE_TIER_MAX_APPOINTMENTS_PER_MONTH,
        },
        "BASIC": {
            "max_patients": settings.BASIC_TIER_MAX_PATIENTS,
            "max_doctors": settings.BASIC_TIER_MAX_DOCTORS,
            "max_appointments_per_month": settings.BASIC_TIER_MAX_APPOINTMENTS_PER_MONTH,
        },
        "PREMIUM": {
            "max_patients": settings.PREMIUM_TIER_MAX_PATIENTS,
            "max_doctors": settings.PREMIUM_TIER_MAX_DOCTORS,
            "max_appointments_per_month": settings.PREMIUM_TIER_MAX_APPOINTMENTS_PER_MONTH,
        },
        "ENTERPRISE": {
            "max_patients": -1,  # Unlimited
            "max_doctors": -1,
            "max_appointments_per_month": -1,
        },
    }
    return tier_configs.get(tier.upper(), tier_configs["FREE"])