"""
Example of using authentication in your own routes.
This shows how to create protected endpoints that require authentication.
"""

from fastapi import APIRouter, Depends, HTTPException
from models import User
from utils.dependencies import get_current_user, get_current_verified_user

# Create a router for your feature
example_router = APIRouter(prefix="/api", tags=["Examples"])


@example_router.get("/public")
async def public_endpoint():
    """
    Public endpoint - no authentication required.
    Anyone can access this.
    """
    return {"message": "This is a public endpoint"}


@example_router.get("/protected")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    """
    Protected endpoint - requires authentication.
    User must include valid JWT token in Authorization header.
    
    Headers:
        Authorization: Bearer <jwt_token>
    """
    return {
        "message": f"Hello {current_user.full_name or current_user.email}!",
        "user_id": current_user.id,
        "email": current_user.email,
    }


@example_router.get("/verified-only")
async def verified_only_endpoint(
        current_user: User = Depends(get_current_verified_user)):
    """
    Protected endpoint - requires verified email.
    User must have is_verified=True in database.
    """
    return {
        "message": f"Welcome verified user {current_user.email}!",
        "verification_status": current_user.is_verified,
    }


@example_router.get("/user-data")
async def get_user_data(current_user: User = Depends(get_current_user)):
    """
    Example of accessing user-specific data.
    Returns information about the authenticated user.
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "auth_provider": current_user.auth_provider,
        "is_verified": current_user.is_verified,
        "created_at": current_user.created_at,
    }


@example_router.post("/admin-only")
async def admin_only_endpoint(current_user: User = Depends(get_current_user)):
    """
    Example of role-based access control.
    In a real app, you'd check user.role or similar.
    """
    # This is just an example - you'd implement actual role checking
    if current_user.email != "admin@example.com":
        raise HTTPException(status_code=403, detail="Admin access required")

    return {"message": "Admin-only data here"}


# To use this router, add it to main.py:
# from services.example import example_router
# app.include_router(example_router)
