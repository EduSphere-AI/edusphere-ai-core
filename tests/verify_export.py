import asyncio
import logging
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import async_session_maker, Document, Chunk
from sqlalchemy import select

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def verify_export():
    async with async_session_maker() as db:
        # 1. Get the document
        result = await db.execute(select(Document).limit(1))
        doc = result.scalars().first()

        if not doc:
            logger.error("No document found.")
            return

        logger.info(f"Exporting data for Document ID: {doc.id}")

        # 2. Fetch chunks
        result = await db.execute(
            select(Chunk).where(Chunk.document_id == doc.id).order_by(
                Chunk.sequence_order))
        chunks = result.scalars().all()

        export_data = {
            "document_id": doc.id,
            "filename": doc.filename,
            "slides": []
        }

        for chunk in chunks:
            try:
                slide_content = json.loads(chunk.content)
            except json.JSONDecodeError:
                slide_content = {"raw_content": chunk.content}

            export_data["slides"].append({
                "id": chunk.id,
                "sequence": chunk.sequence_order,
                "type": chunk.chunk_type,
                "content": slide_content
            })

        # 3. Print JSON output
        print(json.dumps(export_data, indent=2))


if __name__ == "__main__":
    asyncio.run(verify_export())
