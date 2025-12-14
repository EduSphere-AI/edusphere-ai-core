import firebase_admin
from firebase_admin import credentials, auth
from config import settings
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
_firebase_initialized = False


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_initialized

    if _firebase_initialized:
        return

    try:
        if os.path.exists(settings.firebase_credentials_path):
            cred = credentials.Certificate(settings.firebase_credentials_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin SDK initialized successfully")
        else:
            logger.warning(
                f"Firebase credentials file not found at {settings.firebase_credentials_path}"
            )
            logger.warning(
                "Google authentication will not work until credentials are provided"
            )
    except Exception as e:
        logger.error(f"Error initializing Firebase: {e}")


async def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verify a Firebase ID token and return the decoded claims.
    
    Args:
        token: The Firebase ID token to verify
        
    Returns:
        Dict containing user info (uid, email, name, etc.) or None if verification fails
    """
    try:
        if not _firebase_initialized:
            initialize_firebase()

        decoded_token = auth.verify_id_token(token)
        logger.debug(
            f"Firebase token verified for user: {decoded_token.get('email')}")
        return {
            "uid": decoded_token.get("uid"),
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
            "email_verified": decoded_token.get("email_verified", False),
        }
    except Exception as e:
        logger.error(f"Error verifying Firebase token: {e}")
        return None
