from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from api import deps
from schemas.user import UserLogin, Token, UserCreate, User, PasswordReset, PasswordChange
from schemas.common import SuccessResponse
from services.auth_service import AuthService
from core.config import settings
from core.limiter import limiter          # ← ADD 1

logger = logging.getLogger(__name__)
router = APIRouter()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "0.0.0.0"


def get_user_agent(request: Request) -> str:
    return request.headers.get("User-Agent", "Unknown")


@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")              # ← ADD 2
async def register(
    request: Request,                    # must be first param for slowapi
    user_in: UserCreate,
    db: Session = Depends(deps.get_db)
):
    auth_service = AuthService(db)
    try:
        user = auth_service.create_user(user_in)
        logger.info(f"New user registered: {user.email} from IP {get_client_ip(request)}")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")              # ← ADD 2
async def login(
    request: Request,                    # already first — no change needed
    credentials: UserLogin,
    db: Session = Depends(deps.get_db)
):
    auth_service = AuthService(db)
    ip_address = get_client_ip(request)
    user_agent = get_user_agent(request)

    is_locked, lockout_reason = auth_service.check_account_lockout(
        credentials.email, ip_address
    )
    if is_locked:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=lockout_reason)

    user = auth_service.authenticate_user(credentials.email, credentials.password, ip_address)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive")

    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(user, ip_address=ip_address, user_agent=user_agent)
    auth_service.update_last_login(user.id)

    logger.info(f"User logged in: {user.email} from IP {ip_address}")
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=Token)
@limiter.limit("30/minute")              # ← ADD 2
async def refresh_token(
    request: Request,                    # ← ADD 3: was missing, needed by slowapi
    refresh_token: str,
    db: Session = Depends(deps.get_db)
):
    auth_service = AuthService(db)
    try:
        new_access_token = auth_service.refresh_access_token(refresh_token)
        return Token(
            access_token=new_access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    # No rate limit — authenticated endpoint, abuse already prevented by token validation
    auth_service = AuthService(db)
    auth_service.revoke_user_tokens(current_user.id)
    logger.info(f"User logged out: {current_user.email}")
    return SuccessResponse(success=True, message="Logged out successfully from all devices")


@router.post("/logout-device", response_model=SuccessResponse)
async def logout_device(
    refresh_token: str,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    # No rate limit — authenticated endpoint
    auth_service = AuthService(db)
    success = auth_service.revoke_refresh_token(refresh_token)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refresh token not found")
    logger.info(f"User logged out from device: {current_user.email}")
    return SuccessResponse(success=True, message="Logged out successfully from this device")


@router.post("/password/reset-request", response_model=SuccessResponse)
@limiter.limit("5/minute")               # ← ADD 2 (stricter — this triggers email sends)
async def request_password_reset(
    request: Request,                    # already present — no change needed
    reset_request: PasswordReset,
    db: Session = Depends(deps.get_db)
):
    auth_service = AuthService(db)
    ip_address = get_client_ip(request)
    try:
        token = auth_service.create_password_reset_token(reset_request.email)
        if token:
            logger.info(f"Password reset requested for {reset_request.email} from IP {ip_address}")
    except Exception as e:
        logger.error(f"Error creating password reset token: {str(e)}")
    return SuccessResponse(success=True, message="If the email exists, a password reset link has been sent")


@router.post("/password/reset", response_model=SuccessResponse)
@limiter.limit("10/minute")              # ← ADD 2
async def reset_password(
    request: Request,                    # already present — no change needed
    token: str,
    new_password: str,
    db: Session = Depends(deps.get_db)
):
    auth_service = AuthService(db)
    ip_address = get_client_ip(request)
    try:
        success = auth_service.reset_password(token, new_password)
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
        logger.info(f"Password reset successful from IP {ip_address}")
        return SuccessResponse(success=True, message="Password reset successfully. Please login with your new password.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/password/change", response_model=SuccessResponse)
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    # No rate limit — authenticated, and brute force isn't the attack vector here
    auth_service = AuthService(db)
    try:
        success = auth_service.change_password(
            current_user.id, password_change.old_password, password_change.new_password
        )
        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
        logger.info(f"Password changed for user {current_user.email}")
        return SuccessResponse(success=True, message="Password changed successfully. Please login again.")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(deps.get_current_user)
):
    # No rate limit — cheap DB read, authenticated
    return current_user


@router.post("/verify-email", response_model=SuccessResponse)
@limiter.limit("10/minute")              # ← ADD 2
async def verify_email(
    request: Request,                    # ← ADD 3: was missing
    token: str,
    db: Session = Depends(deps.get_db)
):
    auth_service = AuthService(db)
    success = auth_service.verify_email(token)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired verification token")
    return SuccessResponse(success=True, message="Email verified successfully")


@router.get("/sessions")
async def get_active_sessions(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    # No rate limit — authenticated, read-only
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
            "token_suffix": token.token[-8:]
        })

    return {"success": True, "data": sessions}