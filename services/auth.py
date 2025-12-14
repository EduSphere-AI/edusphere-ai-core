# Auth operations and auth utils

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from models import (
    User,
    get_db,
    UserCreate,
    UserLogin,
    UserResponse,
    GoogleAuthRequest,
    Token,
)
from utils.security import verify_password, get_password_hash, create_access_token
from utils.firebase import verify_firebase_token
from utils.dependencies import get_current_user

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Get a user by email."""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_firebase_uid(db: AsyncSession,
                                   firebase_uid: str) -> Optional[User]:
    """Get a user by Firebase UID."""
    result = await db.execute(
        select(User).filter(User.firebase_uid == firebase_uid))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    full_name: Optional[str] = None,
    password: Optional[str] = None,
    firebase_uid: Optional[str] = None,
    auth_provider: str = "email",
    is_verified: bool = False,
) -> User:
    """Create a new user in the database."""
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=get_password_hash(password) if password else None,
        firebase_uid=firebase_uid,
        auth_provider=auth_provider,
        is_verified=is_verified,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@auth_router.post("/register",
                  response_model=Token,
                  status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user with email and password.
    """
    logger.info(f"Registration attempt for email: {user_data.email}")

    # Check if user already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        logger.warning(
            f"Registration failed: Email already registered - {user_data.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = await create_user(
        db=db,
        email=user_data.email,
        full_name=user_data.full_name,
        password=user_data.password,
        auth_provider="email",
    )

    logger.info(f"User registered successfully: {user.email} (ID: {user.id})")

    # Create access token
    access_token = create_access_token(data={
        "sub": user.email,
        "user_id": user.id
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@auth_router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Login with email and password.
    """
    logger.info(f"Login attempt for email: {credentials.email}")

    # Get user by email
    user = await get_user_by_email(db, credentials.email)

    # Verify user exists and password is correct
    if not user or not user.hashed_password:
        logger.warning(
            f"Login failed: Invalid credentials for {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(credentials.password, user.hashed_password):
        logger.warning(
            f"Login failed: Incorrect password for {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Login failed: Inactive account - {credentials.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    logger.info(f"User logged in successfully: {user.email} (ID: {user.id})")

    # Create access token
    access_token = create_access_token(data={
        "sub": user.email,
        "user_id": user.id
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@auth_router.post("/google", response_model=Token)
async def google_auth(
        auth_data: GoogleAuthRequest,
        db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with Google via Firebase token.
    The client should get the Firebase ID token after Google sign-in and send it here.
    """
    logger.info("Google authentication attempt")

    # Verify Firebase token
    firebase_user = await verify_firebase_token(auth_data.firebase_token)

    if not firebase_user:
        logger.warning("Google auth failed: Invalid Firebase token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(
        f"Firebase token verified for email: {firebase_user['email']}")

    # Check if user exists by Firebase UID
    user = await get_user_by_firebase_uid(db, firebase_user["uid"])

    if not user:
        # Check if user exists by email
        user = await get_user_by_email(db, firebase_user["email"])

        if user:
            # User exists with email auth, link Google account
            logger.info(
                f"Linking Google account to existing user: {user.email}")
            user.firebase_uid = firebase_user["uid"]
            user.auth_provider = "google"
            user.is_verified = firebase_user.get("email_verified", False)
            if not user.full_name and firebase_user.get("name"):
                user.full_name = firebase_user["name"]
            await db.flush()
            await db.refresh(user)
        else:
            # Create new user
            logger.info(
                f"Creating new user from Google auth: {firebase_user['email']}"
            )
            user = await create_user(
                db=db,
                email=firebase_user["email"],
                full_name=auth_data.full_name or firebase_user.get("name"),
                firebase_uid=firebase_user["uid"],
                auth_provider="google",
                is_verified=firebase_user.get("email_verified", False),
            )
    else:
        logger.info(
            f"Google auth for existing user: {user.email} (ID: {user.id})")

    # Check if user is active
    if not user.is_active:
        logger.warning(f"Google auth failed: Inactive account - {user.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    logger.info(f"Google authentication successful for: {user.email}")

    # Create access token
    access_token = create_access_token(data={
        "sub": user.email,
        "user_id": user.id
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@auth_router.get("/test")
async def test_auth():
    """Test endpoint to verify auth router is working."""
    return {"message": "Auth router is working!"}


@auth_router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.
    Requires valid JWT token in Authorization header.
    
    Example:
        Authorization: Bearer <your_jwt_token>
    """
    return UserResponse.model_validate(current_user)
