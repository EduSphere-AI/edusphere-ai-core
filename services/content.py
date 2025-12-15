from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.database import get_db, Document, Chunk
from features.summarization import Summarizer
from features.extraction import Extraction
from features.chunking import Chunker
from services.websocket import manager
from config import settings
from utils.firebase import get_firestore_client
from utils.supabase_client import get_supabase
from pydantic import BaseModel
from firebase_admin import firestore

import asyncio
import logging
import json
import os
import requests
import uuid
import shutil

router = APIRouter(prefix="/content", tags=["content"])
logger = logging.getLogger(__name__)


def upload_image_to_supabase(file_path: str, destination_path: str) -> str:
    """Uploads an image to Supabase Storage and returns the public URL."""
    try:
        supabase = get_supabase()
        bucket = settings.supabase_bucket

        # Check if bucket exists, if not create? (Supabase usually pre-creates)
        # Just upload
        with open(file_path, 'rb') as f:
            supabase.storage.from_(bucket).upload(
                destination_path,
                f,
                file_options={"content-type": "image/png"})

        return supabase.storage.from_(bucket).get_public_url(destination_path)
    except Exception as e:
        logger.error(f"Failed to upload image {file_path} to Supabase: {e}")
        return ""


class UploadURLRequest(BaseModel):
    url: str
    user_id: str
    id: str | None = None  # Optional ID provided by client


@router.websocket("/ws/{document_id}")
async def websocket_endpoint(websocket: WebSocket, document_id: str):
    await manager.connect(websocket, document_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, document_id)


async def download_file(url: str, destination: str):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None,
                               lambda: _download_file_sync(url, destination))


def _download_file_sync(url: str, destination: str):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(destination, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


async def process_full_pipeline(document_id: str, file_path: str,
                                db_session_factory):
    """
    Full processing pipeline: Extraction -> Chunking -> Summarization
    """
    async with db_session_factory() as db:
        try:
            loop = asyncio.get_running_loop()
            await manager.broadcast(
                json.dumps({
                    "status": "processing",
                    "step": "starting",
                    "message": "Starting processing pipeline"
                }), document_id)

            # 1. Extraction
            await manager.broadcast(
                json.dumps({
                    "status": "processing",
                    "step": "extraction",
                    "message": "Extracting content from PDF"
                }), document_id)

            output_dir = os.path.join(settings.base_dir, "output",
                                      "extraction")
            os.makedirs(output_dir, exist_ok=True)
            extraction_output_file = os.path.join(
                output_dir, f"extraction_{document_id}.json")
            images_dir = os.path.join(settings.base_dir, "output", "images",
                                      str(document_id))
            os.makedirs(images_dir, exist_ok=True)

            # Run extraction in thread pool
            extractor = Extraction(inp_file_path=file_path,
                                   output_file_path=extraction_output_file,
                                   output_image_dir=images_dir,
                                   use_ollama=True,
                                   extract_images=True)
            await loop.run_in_executor(None, extractor.extract)

            with open(extraction_output_file, 'r') as f:
                extraction_data = json.load(f)

            # 1.1 Upload extracted images to Supabase & Save Extraction to Firestore
            firestore_db = get_firestore_client()
            doc_ref = firestore_db.collection("documents").document(
                str(document_id))

            # Process images in extraction data
            # Assuming extraction_data is a list of content items
            if isinstance(extraction_data, list):
                for item in extraction_data:
                    if item.get("type") == "Image" and item.get("image_path"):
                        local_path = item["image_path"]
                        if os.path.exists(local_path):
                            filename = os.path.basename(local_path)
                            supabase_path = f"{document_id}/{filename}"
                            public_url = upload_image_to_supabase(
                                local_path, supabase_path)
                            if public_url:
                                item["image_url"] = public_url
                                logger.info(f"Uploaded image to {public_url}")

            # Save Extraction Result to Firestore
            doc_ref.set(
                {
                    "status": "processing",
                    "current_step": "chunking",
                    "updated_at": firestore.SERVER_TIMESTAMP
                },
                merge=True)
            doc_ref.collection("results").document("extraction").set(
                {"content": extraction_data})

            # 2. Chunking
            await manager.broadcast(
                json.dumps({
                    "status": "processing",
                    "step": "chunking",
                    "message": "Chunking content"
                }), document_id)
            chunker = Chunker()
            chunks_data = await loop.run_in_executor(None, chunker.process,
                                                     extraction_data)

            # Save chunks to DB (optional, or just use for summarization)
            # For now, we'll skip saving raw chunks to DB to focus on slides,
            # but in a real RAG system you'd save them here.

            # 3. Summarization / Slide Generation
            await manager.broadcast(
                json.dumps({
                    "status": "processing",
                    "step": "summarization",
                    "message": "Generating slides"
                }), document_id)
            summarizer = Summarizer()
            slides = await loop.run_in_executor(None,
                                                summarizer.generate_slides,
                                                extraction_data)

            # 4. Save to DB & Firestore
            await manager.broadcast(
                json.dumps({
                    "status": "processing",
                    "step": "saving",
                    "message": "Saving results"
                }), document_id)

            # Save Generation Result to Firestore
            doc_ref.set(
                {
                    "status": "completed",
                    "current_step": "completed",
                    "updated_at": firestore.SERVER_TIMESTAMP
                },
                merge=True)
            doc_ref.collection("results").document("generation").set(
                {"slides": slides})

            for slide in slides:
                chunk = Chunk(document_id=document_id,
                              sequence_order=slide.get("sequence", 0),
                              title=slide.get("title", ""),
                              content=json.dumps(slide.get("content", {})),
                              chunk_type="slide")
                db.add(chunk)

            document = await db.get(Document, document_id)
            if document:
                document.status = "completed"
                db.add(document)

            await db.commit()

            await manager.broadcast(
                json.dumps({
                    "status": "completed",
                    "message": "Processing finished successfully"
                }), document_id)
            logger.info(f"Document {document_id} processing completed.")

        except Exception as e:
            logger.error(
                f"Error in processing pipeline for document {document_id}: {e}"
            )
            await manager.broadcast(
                json.dumps({
                    "status": "error",
                    "message": str(e)
                }), document_id)
            document = await db.get(Document, document_id)
            if document:
                document.status = "error"
                db.add(document)
                await db.commit()


@router.get("/documents/{document_id}")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status,
        "source_url": document.source_url,
        "upload_date": document.upload_date,
    }


@router.post("/upload-url")
async def upload_from_url(request: UploadURLRequest,
                          background_tasks: BackgroundTasks,
                          db: AsyncSession = Depends(get_db)):
    # Create Document record
    filename = request.url.split("/")[-1] or f"doc_{uuid.uuid4()}.pdf"

    # Use provided ID or generate new one
    document_id = request.id if request.id else str(uuid.uuid4())

    # Define local path
    upload_dir = os.path.join(settings.base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{document_id}_{filename}")

    # Download file
    try:
        await download_file(request.url, file_path)
    except Exception as e:
        raise HTTPException(status_code=400,
                            detail=f"Failed to download file: {str(e)}")

    new_doc = Document(id=document_id,
                       filename=filename,
                       file_path=file_path,
                       source_url=request.url,
                       user_id=request.user_id,
                       status="pending")
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)

    # Start background processing
    # We need a way to pass a session factory or handle session in background task
    # Since we can't easily pass the session factory from here without circular imports or complex setup,
    # we will use a workaround: import the sessionmaker from database.py
    from models.database import async_session_maker

    background_tasks.add_task(process_full_pipeline, new_doc.id, file_path,
                              async_session_maker)

    return {
        "message": "Document uploaded and processing started",
        "document_id": new_doc.id
    }


async def process_document_task(document_id: str, db: AsyncSession):
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
            chunk = Chunk(document_id=document_id,
                          sequence_order=slide.get("sequence", 0),
                          title=slide.get("title", ""),
                          content=json.dumps(slide.get("content", {})),
                          chunk_type="slide")
            db.add(chunk)

        await db.commit()

        # Update document status
        document = await db.get(Document, document_id)
        if document:
            document.status = "completed"
            await db.commit()
        logger.info(
            f"Document {document_id} processing completed. Generated {len(slides)} slides."
        )

    except Exception as e:
        logger.error(f"Error processing document {document_id}: {e}")
        document = await db.get(Document, document_id)
        if document:
            document.status = "error"
            await db.commit()


@router.post("/{document_id}/process")
async def process_document(document_id: str,
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
async def generate_slides(document_id: str,
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
