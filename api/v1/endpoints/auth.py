from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from api import deps
from schemas.user import UserLogin, Token, UserCreate, User, PasswordReset, PasswordChange
from schemas.common import SuccessResponse
from services.auth_service import AuthService
from core.config import settings

router = APIRouter()

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: Session = Depends(deps.get_db)
):
    """
    Register new user (clinic admin during tenant creation)
    """
    auth_service = AuthService(db)
    
    # Check if email already exists
    if auth_service.get_user_by_email(user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user = auth_service.create_user(user_in)
    return user

@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: Session = Depends(deps.get_db)
):
    """
    Login and get access token
    """
    auth_service = AuthService(db)
    
    user = auth_service.authenticate_user(credentials.email, credentials.password)
    
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
    
    # Create access token
    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(user)
    
    # Update last login
    auth_service.update_last_login(user.id)
    
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
    """
    auth_service = AuthService(db)
    
    try:
        new_access_token = auth_service.refresh_access_token(refresh_token)
        
        return Token(
            access_token=new_access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Logout (revoke refresh tokens)
    """
    auth_service = AuthService(db)
    auth_service.revoke_user_tokens(current_user.id)
    
    return SuccessResponse(
        success=True,
        message="Logged out successfully"
    )

@router.post("/password/reset-request", response_model=SuccessResponse)
async def request_password_reset(
    reset_request: PasswordReset,
    db: Session = Depends(deps.get_db)
):
    """
    Request password reset (sends email)
    """
    auth_service = AuthService(db)
    
    # Always return success to prevent email enumeration
    try:
        auth_service.create_password_reset_token(reset_request.email)
    except:
        pass
    
    return SuccessResponse(
        success=True,
        message="If the email exists, a password reset link has been sent"
    )

@router.post("/password/reset", response_model=SuccessResponse)
async def reset_password(
    token: str,
    new_password: str,
    db: Session = Depends(deps.get_db)
):
    """
    Reset password using token
    """
    auth_service = AuthService(db)
    
    success = auth_service.reset_password(token, new_password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token"
        )
    
    return SuccessResponse(
        success=True,
        message="Password reset successfully"
    )

@router.post("/password/change", response_model=SuccessResponse)
async def change_password(
    password_change: PasswordChange,
    current_user: User = Depends(deps.get_current_user),
    db: Session = Depends(deps.get_db)
):
    """
    Change password (requires authentication)
    """
    auth_service = AuthService(db)
    
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
    
    return SuccessResponse(
        success=True,
        message="Password changed successfully"
    )

@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user: User = Depends(deps.get_current_user)
):
    """
    Get current user information
    """
    return current_user

@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(
    token: str,
    db: Session = Depends(deps.get_db)
):
    """
    Verify user email
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