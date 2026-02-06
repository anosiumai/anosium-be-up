from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from api import deps
from schemas.user import UserLogin, Token, UserCreate, User, PasswordReset, PasswordChange
from schemas.common import SuccessResponse
from services.auth_service import AuthService
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ✅ Helper to extract real IP address
def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request
    Handles proxy headers (X-Forwarded-For, X-Real-IP)
    """
    # Check for proxy headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first (client IP)
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct connection IP
    return request.client.host if request.client else "0.0.0.0"


def get_user_agent(request: Request) -> str:
    """Extract user agent from request"""
    return request.headers.get("User-Agent", "Unknown")


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    """
    Register new user (clinic admin during tenant creation)
    
    - **email**: User email (must be unique)
    - **password**: Password (min 8 chars, must contain uppercase, lowercase, digit)
    - **first_name**: User first name
    - **last_name**: User last name
    - **role**: User role (CLINIC_ADMIN, DOCTOR, etc.)
    - **tenant_id**: Tenant ID (clinic identifier)
    """
    auth_service = AuthService(db)
    
    try:
        user = auth_service.create_user(user_in)
        
        logger.info(
            f"New user registered: {user.email} from IP {get_client_ip(request)}"
        )
        
        return user
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    """
    Login and get access token
    
    - **email**: User email
    - **password**: User password
    
    Returns:
    - **access_token**: JWT access token (30min expiry)
    - **refresh_token**: Refresh token (7 days expiry)
    - **token_type**: Bearer
    - **expires_in**: Token expiration in seconds
    """
    auth_service = AuthService(db)
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)
    
    # ✅ Check for account lockout
    is_locked, lockout_reason = auth_service.check_account_lockout(
        credentials.email,
        ip_address
    )
    
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=lockout_reason
        )
    
    # Authenticate user
    user = auth_service.authenticate_user(
        credentials.email,
        credentials.password,
        ip_address
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # ✅ Create tokens with device info
    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(
        user,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    # Update last login
    auth_service.update_last_login(user.id)
    
    logger.info(f"User logged in: {user.email} from IP {ip_address}")
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(deps.get_db)
):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Refresh token from login response
    
    Returns new access token while keeping the same refresh token
    """
    auth_service = AuthService(db)
    
    try:
        new_access_token = auth_service.refresh_access_token(refresh_token)
        
        return Token(
            access_token=new_access_token,
            refresh_token=refresh_token,  # Keep same refresh token
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Logout current user (revokes all refresh tokens)
    
    This logs the user out from all devices.
    """
    auth_service = AuthService(db)
    auth_service.revoke_user_tokens(current_user.id)
    
    logger.info(f"User logged out: {current_user.email}")
    
    return SuccessResponse(
        success=True,
        message="Logged out successfully from all devices"
    )


@router.post("/logout-device", response_model=SuccessResponse)
async def logout_device(
    refresh_token: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Logout from specific device (revokes specific refresh token)
    
    - **refresh_token**: The refresh token to revoke
    
    This logs the user out from only the current device.
    """
    auth_service = AuthService(db)
    
    success = auth_service.revoke_refresh_token(refresh_token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh token not found"
        )
    
    logger.info(f"User logged out from device: {current_user.email}")
    
    return SuccessResponse(
        success=True,
        message="Logged out successfully from this device"
    )


@router.post("/password/reset-request", response_model=SuccessResponse)
async def request_password_reset(
    reset_request: PasswordReset,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    """
    Request password reset (sends email with reset link)
    
    - **email**: User email
    
    Always returns success to prevent email enumeration attacks.
    If the email exists, a reset link will be sent.
    """
    auth_service = AuthService(db)
    ip_address = get_client_ip(request)
    
    # Always return success to prevent email enumeration
    try:
        token = auth_service.create_password_reset_token(reset_request.email)
        
        if token:
            logger.info(
                f"Password reset requested for {reset_request.email} from IP {ip_address}"
            )
            # TODO: Send email with reset link
            # send_password_reset_email(reset_request.email, token)
    except Exception as e:
        logger.error(f"Error creating password reset token: {str(e)}")
    
    return SuccessResponse(
        success=True,
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/password/reset", response_model=SuccessResponse)
async def reset_password(
    token: str,
    new_password: str,
    request: Request,
    db: Session = Depends(deps.get_db)
):
    """
    Reset password using token from email
    
    - **token**: Reset token from email
    - **new_password**: New password (must meet strength requirements)
    """
    auth_service = AuthService(db)
    ip_address = get_client_ip(request)
    
    try:
        success = auth_service.reset_password(token, new_password)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired token"
            )
        
        logger.info(f"Password reset successful from IP {ip_address}")
        
        return SuccessResponse(
            success=True,
            message="Password reset successfully. Please login with your new password."
        )
        
    except ValueError as e:
        # Password validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/password/change", response_model=SuccessResponse)
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Change password (requires authentication)
    
    - **old_password**: Current password
    - **new_password**: New password (must meet strength requirements)
    
    This will log you out from all devices for security.
    """
    auth_service = AuthService(db)
    
    try:
        success = auth_service.change_password(
            current_user.id,
            password_change.old_password,
            password_change.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        logger.info(f"Password changed for user {current_user.email}")
        
        return SuccessResponse(
            success=True,
            message="Password changed successfully. Please login again with your new password."
        )
        
    except ValueError as e:
        # Password validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get current user information
    
    Returns full user profile of the authenticated user.
    """
    return current_user


@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(
    token: str,
    db: Session = Depends(deps.get_db)
):
    """
    Verify user email using verification token
    
    - **token**: Email verification token from email
    """
    auth_service = AuthService(db)
    
    success = auth_service.verify_email(token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    return SuccessResponse(
        success=True,
        message="Email verified successfully"
    )


# ✅ NEW: Get active sessions
@router.get("/sessions")
async def get_active_sessions(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Get list of active login sessions (refresh tokens)
    
    Shows all devices where the user is currently logged in.
    """
    from models.security import RefreshToken
    from datetime import datetime
    
    active_tokens = db.query(RefreshToken).filter(
        RefreshToken.user_id == current_user.id,
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    ).all()
    
    sessions = []
    for token in active_tokens:
        sessions.append({
            "device_name": token.device_name or "Unknown Device",
            "ip_address": token.ip_address,
            "last_used": token.last_used_at or token.created_at,
            "created_at": token.created_at,
            "token": token.token  # For logout-device endpoint
        })
    
    return {
        "success": True,
        "data": sessions
    }