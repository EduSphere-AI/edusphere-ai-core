from typing import Optional, List, Any, Dict
from datetime import datetime, timezone
from utils.firebase import get_firestore_client
from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)


class FirestoreDAO:

    def __init__(self):
        # We access the client lazily or ensure it is initialized
        self.documents_collection = "documents"

    @property
    def db(self):
        return get_firestore_client()

    # --- Document Operations ---

    async def create_document(self, doc_data: Dict[str, Any]) -> str:
        """Create a document record."""
        doc_id = doc_data.pop("id", None)
        if doc_data.get("upload_date") is None:
            doc_data["upload_date"] = datetime.now(timezone.utc)

        if doc_id:
            self.db.collection(
                self.documents_collection).document(doc_id).set(doc_data)
            return doc_id
        else:
            _, doc_ref = self.db.collection(
                self.documents_collection).add(doc_data)
            return doc_ref.id

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        doc_ref = self.db.collection(
            self.documents_collection).document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    async def get_all_documents(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve all documents ordered by upload_date desc."""
        docs_ref = self.db.collection(self.documents_collection)
        query = docs_ref.order_by(
            "upload_date", direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results

    async def update_document_status(self, doc_id: str, status: str):
        doc_ref = self.db.collection(
            self.documents_collection).document(doc_id)
        doc_ref.update({"status": status})

    # --- Job/Process Operations ---

    async def create_job(self, job_data: Dict[str, Any]) -> str:
        """Create a new processing job tracker."""
        job_id = job_data.pop("id", None)
        if job_data.get("created_at") is None:
            job_data["created_at"] = datetime.now(timezone.utc)

        if job_id:
            self.db.collection("jobs").document(job_id).set(job_data)
            return job_id
        else:
            _, doc_ref = self.db.collection("jobs").add(job_data)
            return doc_ref.id

    async def update_job(self, job_id: str, updates: Dict[str, Any]):
        """Update job status and results."""
        self.db.collection("jobs").document(job_id).update(updates)


# Global instance
db_dao = FirestoreDAO()


# Helper for dependency injection (placeholder)
def get_db():
    return db_dao


async def create_tables():
    pass  # No tables needed for Firestore


async def drop_tables():
    pass
