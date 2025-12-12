from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db, Document, Chunk
from features.summarization import Summarizer
from config import settings

import logging
import json
import os

router = APIRouter(prefix="/content", tags=["content"])
logger = logging.getLogger(__name__)


async def process_document_task(document_id: int, db: AsyncSession):
    try:
        # 1. Extraction (Assuming this is done previously and saved to disk)
        # In a real pipeline, we might call the extraction service here.
        # For now, we assume extraction_result.json exists at the path defined in settings.
        
        extraction_path = settings.extraction_output_path
        if not os.path.exists(extraction_path):
            logger.error(f"Extraction result not found at {extraction_path}")
            # Potentially trigger extraction here
            return

        with open(extraction_path, 'r') as f:
            extraction_data = json.load(f)

        # 2. Slide Generation using Enhanced Summarizer
        logger.info(f"Starting slide generation for document {document_id}")
        
        summarizer = Summarizer()
        slides = summarizer.generate_slides(extraction_data)
        
        # 3. Save slides to database as Chunks
        # First, clear existing chunks for this document to avoid duplicates if re-running
        # (Optional, but good for idempotency)
        # await db.execute(delete(Chunk).where(Chunk.document_id == document_id))
        
        for slide in slides:
            chunk = Chunk(
                document_id=document_id,
                sequence_order=slide.get("sequence", 0),
                title=slide.get("title", ""),
                content=json.dumps(slide.get("content", {})),
                chunk_type="slide"
            )
            db.add(chunk)
        
        await db.commit()

        # Update document status
        document = await db.get(Document, document_id)
        if document:
            document.status = "completed"
            await db.commit()
        logger.info(f"Document {document_id} processing completed. Generated {len(slides)} slides.")

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        document = await db.get(Document, document_id)
        if document:
            document.status = "error"
            await db.commit()


@router.post("/{document_id}/process")
async def process_document(document_id: int,
                           background_tasks: BackgroundTasks,
                           db: AsyncSession = Depends(get_db)):
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    document.status = "processing"
    await db.commit()

    # Run in background
    background_tasks.add_task(process_document_task, document_id, db)

    return {"message": "Document processing started"}


@router.post("/{document_id}/generate-slides")
async def generate_slides(document_id: int,
                          db: AsyncSession = Depends(get_db)):
    """
    Manually trigger slide generation for a document.
    """
    await process_document_task(document_id, db)
    return {"message": "Slide generation completed"}


@router.get("/{document_id}/export")
async def export_content(document_id: int, db: AsyncSession = Depends(get_db)):
    """
    Export the generated content (slides) for a document in JSON format.
    """
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Fetch chunks
    result = await db.execute(
        select(Chunk).where(Chunk.document_id == document_id).order_by(
            Chunk.sequence_order))
    chunks = result.scalars().all()

    export_data = {
        "document_id": document.id,
        "filename": document.filename,
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
            "title": chunk.title,
            "content": slide_content
        })

    return export_data
