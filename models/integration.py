from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import TypeDecorator
from core.database import Base
from core.config import settings
import base64
import hashlib
import json
from cryptography.fernet import Fernet

class EncryptedJSON(TypeDecorator):
    """
    Encrypts JSON data before storing it in the database and decrypts it when retrieving.
    Stores the data as an encrypted Text representation in the database.
    """
    impl = Text
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Derive a 32-byte key from settings.SECRET_KEY for Fernet cipher
        key_bytes = settings.SECRET_KEY.encode('utf-8')
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
        self.fernet = Fernet(derived_key)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        json_str = json.dumps(value)
        encrypted_bytes = self.fernet.encrypt(json_str.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            decrypted_bytes = self.fernet.decrypt(value.encode('utf-8'))
            return json.loads(decrypted_bytes.decode('utf-8'))
        except Exception:
            # Fallback if decryption fails (e.g. legacy data stored in plaintext)
            try:
                return json.loads(value)
            except Exception:
                return value

class APIKey(Base):
    """
    API keys for external integrations
    """
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Key Details
    name = Column(String(200), nullable=False)
    key_hash = Column(String(500), unique=True, nullable=False)  # Hashed API key
    prefix = Column(String(20), nullable=False)  # First few chars for identification
    
    # Permissions
    scopes = Column(JSON, default=[])  # List of allowed operations
    
    # Rate Limiting
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)
    
    # Status
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))
    
    # Tracking
    last_used_at = Column(DateTime(timezone=True))
    usage_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    
    # Relationships
    tenant = relationship("Tenant")

class WebhookEndpoint(Base):
    """
    Webhook endpoints for real-time events
    """
    __tablename__ = "webhook_endpoints"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Endpoint Details
    url = Column(String(500), nullable=False)
    secret = Column(String(500))  # For signature verification
    
    # Events to Subscribe
    subscribed_events = Column(JSON, default=[])  # appointment.created, payment.received
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Retry Config
    max_retries = Column(Integer, default=3)
    retry_delay_seconds = Column(Integer, default=60)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    deliveries = relationship("WebhookDelivery", back_populates="endpoint")

class WebhookDelivery(Base):
    """
    Track webhook delivery attempts
    """
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    endpoint_id = Column(Integer, ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False)
    
    # Event Details
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    
    # Delivery Status
    status = Column(String(20), default="pending")  # pending, success, failed
    http_status_code = Column(Integer)
    response_body = Column(Text)
    
    # Timing
    attempted_at = Column(DateTime(timezone=True), server_default=func.now())
    delivered_at = Column(DateTime(timezone=True))
    
    # Retries
    retry_count = Column(Integer, default=0)
    next_retry_at = Column(DateTime(timezone=True))
    
    # Relationships
    endpoint = relationship("WebhookEndpoint", back_populates="deliveries")

class ThirdPartyIntegration(Base):
    """
    Third-party service integrations (payment gateways, SMS, etc.)
    """
    __tablename__ = "third_party_integrations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Integration Details
    provider = Column(String(100), nullable=False)  # stripe, razorpay, twilio
    integration_type = Column(String(50), nullable=False)  # payment, sms, email
    
    # Credentials (encrypted)
    credentials = Column(EncryptedJSON, nullable=False)  # API keys, secrets
    
    # Configuration
    config = Column(JSON, default={})
    
    # Status
    is_active = Column(Boolean, default=True)
    is_test_mode = Column(Boolean, default=True)
    
    # Health Check
    last_health_check = Column(DateTime(timezone=True))
    health_status = Column(String(20), default="unknown")  # healthy, degraded, down
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())