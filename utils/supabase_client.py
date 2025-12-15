from supabase import create_client, Client
from config import settings
import logging

logger = logging.getLogger(__name__)

_supabase: Client = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        try:
            _supabase = create_client(settings.supabase_url, settings.supabase_key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Supabase client: {e}")
            raise e
    return _supabase
