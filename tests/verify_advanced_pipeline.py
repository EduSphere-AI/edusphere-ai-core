import asyncio
import logging
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import async_session_maker, Document, Chunk, LearnControl, ExtractedContent
from sqlalchemy import select, delete

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def verify_advanced_pipeline():
    async with async_session_maker() as db:
        # 1. Get the document
        result = await db.execute(select(Document).limit(1))
        doc = result.scalars().first()

        if not doc:
            logger.error("No document found. Please run extraction first.")
            return

        logger.info(f"Testing with Document ID: {doc.id} ({doc.filename})")

        # 2. Clean up previous results (Chunks and LearnControls)
        logger.info("Cleaning up previous chunks and questions...")
        await db.execute(
            delete(LearnControl).where(
                LearnControl.chunk_id.in_(
                    select(Chunk.id).where(Chunk.document_id == doc.id))))
        await db.execute(delete(Chunk).where(Chunk.document_id == doc.id))
        await db.commit()


if __name__ == "__main__":
    asyncio.run(verify_advanced_pipeline())
