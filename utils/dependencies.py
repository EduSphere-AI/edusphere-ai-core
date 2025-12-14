from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from models import User, get_db
from utils.security import decode_access_token

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI
security = HTTPBearer()


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    
    Usage:
        @app.get("/protected")
        async def protected_route(current_user: User = Depends(get_current_user)):
            return {"user": current_user.email}
    """
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("Failed to validate JWT token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user_id from token
    user_id: Optional[int] = payload.get("user_id")
    if user_id is None:
        logger.warning("JWT token missing user_id claim")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"User not found for user_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Inactive user attempted access: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    logger.debug(f"Authenticated user: {user.email} (ID: {user.id})")
    return user


async def get_current_active_user(
        current_user: User = Depends(get_current_user), ) -> User:
    """
    Dependency to get the current active user.
    This is an alias for get_current_user for clarity.
    """
    return current_user


async def get_current_verified_user(
        current_user: User = Depends(get_current_user), ) -> User:
    """
    Dependency to get the current verified user.
    Requires the user's email to be verified.
    """
    if not current_user.is_verified:
        logger.warning(
            f"Unverified user attempted access: {current_user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        )
    return current_user
