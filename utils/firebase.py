import firebase_admin
from firebase_admin import credentials, firestore
from config import settings
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
_firebase_initialized = False
_db = None


def initialize_firebase():
    """Initialize Firebase Admin SDK."""
    global _firebase_initialized, _db

    if _firebase_initialized:
        return

    try:
        if os.path.exists(settings.firebase_credentials_path):
            cred = credentials.Certificate(settings.firebase_credentials_path)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            _db = firestore.client()
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


def get_firestore_client():
    """Get the Firestore client."""
    if not _firebase_initialized:
        initialize_firebase()
    return _db
