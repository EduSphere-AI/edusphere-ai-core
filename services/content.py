from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from models.database import get_db, FirestoreDAO
from features.summarization import Summarizer
from features.extraction import Extraction
from features.chunking import Chunker
from services.websocket import manager
from datetime import datetime, timezone
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
import ollama
from typing import List, Dict, Any

router = APIRouter(prefix="/content", tags=["content"])
logger = logging.getLogger(__name__)


class SummarizeSlideRequest(BaseModel):
    result_id: str
    chapter_num: int
    slide_num: int
    strength: str = "standard"  # standard, strong


class ConfirmSummaryRequest(BaseModel):
    result_id: str
    chapter_num: int
    slide_num: int
    new_content: List[Dict[str, Any]]


async def summarize_slide_content(items: List[Dict[str, Any]],
                                  strength: str) -> List[Dict[str, Any]]:
    """
    Summarize text content within slide items using Ollama.
    Retains structure (items count and types).
    """
    # Filter text items
    text_indices = []
    text_parts = []

    for i, item in enumerate(items):
        if item.get("type") in ["paragraph", "bullet"]:
            text_indices.append(i)
            # Add label for context
            label = str(item.get("type", "unknown")).upper()
            content = item.get("text", "") or item.get("content", "")
            text_parts.append(f"[{label} {len(text_indices)}]: {content}")

    if not text_parts:
        return items

    combined_text = "\n\n".join(text_parts)

    strength_instruction = "Make it concise."
    if strength == "strong":
        strength_instruction = "Make it VERY concise. Use fewer words. Be direct."

    prompt = f"""You are an expert slide editor. Summarize the following content items.
    
    Instructions:
    1. Maintain the exact number of items ({len(text_parts)}).
    2. Maintain the type of each item (Paragraph vs Bullet).
    3. {strength_instruction}
    4. Do not lose critical data or numbers.
    5. Output strictly in the format:
       [PARAGRAPH 1]: <Summary>
       [BULLET 2]: <Summary>
       ...
    
    Original Content:
    {combined_text}
    """

    try:
        # Use asyncio to run blocking ollama call
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None, lambda: ollama.generate(model='llama3.2', prompt=prompt))
        response_text = response['response']

        # Parse response
        import re
        summarized_items = items.copy()

        # Regex to find [TYPE N]: Content
        # We iterate through our expected indices to find matches
        for idx_in_list, original_idx in enumerate(text_indices):
            # Construct expected tag roughly (allow loose matching)
            # Match [TYPE N]: ...
            # N is 1-based index in our text_parts list
            n = idx_in_list + 1
            pattern = re.compile(
                rf"\[(?:PARAGRAPH|BULLET) {n}\]:\s*(.*?)(?=\n\[(?:PARAGRAPH|BULLET) \d+\]:|$)",
                re.DOTALL | re.IGNORECASE)
            match = pattern.search(response_text)

            if match:
                new_text = match.group(1).strip()
                if "text" in summarized_items[original_idx]:
                    summarized_items[original_idx]["text"] = new_text
                elif "content" in summarized_items[original_idx]:
                    summarized_items[original_idx]["content"] = new_text

        return summarized_items

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        # Return original on failure
        return items


@router.post("/summarize/preview")
async def summarize_slide_preview(request: SummarizeSlideRequest,
                                  db: FirestoreDAO = Depends(get_db)):
    """
    Generates a summarized version of a slide's content.
    Returns the original and summarized content for preview.
    """
    if not db.db:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        # 1. Fetch generation results
        doc_ref = db.db.collection('documents').document(
            request.result_id).collection('results').document('generation')
        doc = doc_ref.get()
        if not doc.exists:
            # Fallback to job result if not in subcollection?
            # For now, assume standard path.
            raise HTTPException(status_code=404,
                                detail="Generation results not found")

        data = doc.to_dict()
        slides = data.get('slides', [])

        # 2. Find target slide
        target_slide = None
        for slide in slides:
            # Check matching logic
            # Support both 'slide_number' and 'sequence' keys
            s_num = slide.get('slide_number')
            if s_num is None:
                s_num = slide.get('sequence')

            if slide.get(
                    'chapter'
            ) == request.chapter_num and s_num == request.slide_num:
                target_slide = slide
                break

        if not target_slide:
            raise HTTPException(status_code=404, detail="Slide not found")

        # 3. Summarize
        original_content = target_slide.get('content', [])
        summarized_content = await summarize_slide_content(
            original_content, request.strength)

        return {
            "original_content": original_content,
            "summarized_content": summarized_content
        }

    except Exception as e:
        logger.error(f"Error in summarize_preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize/confirm")
async def confirm_summary(request: ConfirmSummaryRequest,
                          db: FirestoreDAO = Depends(get_db)):
    """
    Saves the confirmed summarized content to Firestore.
    """
    if not db.db:
        raise HTTPException(status_code=500, detail="Database not connected")

    try:
        doc_ref = db.db.collection('documents').document(
            request.result_id).collection('results').document('generation')

        # We need to read-modify-write.
        # Simplified non-transactional update for now to avoid linter issues with async/sync mixing
        snapshot = doc_ref.get()
        if not snapshot.exists:
            raise HTTPException(status_code=404, detail="Result not found")

        data = snapshot.to_dict()
        slides = data.get('slides', [])

        updated = False
        for i, slide in enumerate(slides):
            # Support both 'slide_number' and 'sequence' keys
            s_num = slide.get('slide_number')
            if s_num is None:
                s_num = slide.get('sequence')

            if slide.get(
                    'chapter'
            ) == request.chapter_num and s_num == request.slide_num:
                slides[i]['content'] = request.new_content
                updated = True
                break

        if updated:
            doc_ref.update({"slides": slides})
            return {
                "status": "success",
                "message": "Slide updated successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Slide not found")

    except Exception as e:
        logger.error(f"Error in confirm_summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def upload_image_to_supabase(file_path: str, destination_path: str) -> str:
    """Uploads an image to Supabase Storage and returns the public URL."""
    try:
        supabase = get_supabase()
        bucket = settings.supabase_bucket

        with open(file_path, 'rb') as f:
            supabase.storage.from_(bucket).upload(destination_path,
                                                  f,
                                                  file_options={
                                                      "content-type":
                                                      "image/png",
                                                      "upsert": "true"
                                                  })

        return supabase.storage.from_(bucket).get_public_url(destination_path)
    except Exception as e:
        logger.error(f"Failed to upload image {file_path} to Supabase: {e}")
        return ""


class UploadURLRequest(BaseModel):
    url: str
    user_id: str = "anonymous"  # Default to anonymous
    id: str | None = None  # Optional ID provided by client


# WebSocket endpoint for backward compatibility or direct notifications
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


async def process_full_pipeline(job_id: str, document_id: str, file_path: str,
                                db: FirestoreDAO):
    """
    Full processing pipeline: Extraction -> Chunking -> Summarization
    Updates Firestore 'jobs' collection at each step.
    """
    try:
        loop = asyncio.get_running_loop()

        # --- STARTED ---
        await db.update_job(
            job_id, {
                "status": "processing",
                "stage": "started",
                "message": "Starting processing pipeline",
                "updated_at": datetime.now(timezone.utc)
            })

        # --- 1. EXTRACTION ---
        await db.update_job(job_id, {
            "stage": "extraction",
            "message": "Extracting content from PDF"
        })

        output_dir = os.path.join(settings.base_dir, "output", "extraction")
        os.makedirs(output_dir, exist_ok=True)
        extraction_output_file = os.path.join(
            output_dir, f"extraction_{document_id}.json")

        images_dir = os.path.join(settings.base_dir, "output", "images",
                                  str(document_id))
        os.makedirs(images_dir, exist_ok=True)

        # Run extraction
        extractor = Extraction(inp_file_path=file_path,
                               output_file_path=extraction_output_file,
                               output_image_dir=images_dir,
                               use_ollama=True,
                               extract_images=True)
        await loop.run_in_executor(None, extractor.extract)

        with open(extraction_output_file, 'r') as f:
            extraction_data = json.load(f)

        # 1.1 Upload extracted images to Supabase
        image_urls = []

        # Helper to find items with images and upload them
        def process_image_items(items):
            for item in items:
                # Determine image path
                image_path = None
                img_context = None

                item_type = item.get("type", "").lower()
                if (item_type == "image"
                        or item_type == "figure") and item.get("image_path"):
                    image_path = item["image_path"]
                    img_context = item
                elif item.get("image_context") and item["image_context"].get(
                        "image_path"):
                    image_path = item["image_context"]["image_path"]
                    img_context = item["image_context"]

                if image_path and img_context:
                    # Resolve absolute path
                    local_path = image_path
                    if not os.path.isabs(local_path):
                        # Try relative to extraction file
                        candidate = os.path.join(
                            os.path.dirname(extraction_output_file),
                            local_path)
                        if os.path.exists(candidate):
                            local_path = candidate
                        else:
                            # Try relative to base output/images folder
                            # The item path is likely "images/filename.png", we want "filename.png"
                            filename_only = os.path.basename(local_path)
                            candidate_2 = os.path.join(images_dir,
                                                       filename_only)
                            if os.path.exists(candidate_2):
                                local_path = candidate_2

                    if os.path.exists(local_path):
                        filename = os.path.basename(local_path)
                        supabase_path = f"{document_id}/{filename}"
                        public_url = upload_image_to_supabase(
                            local_path, supabase_path)
                        if public_url:
                            # Update the item with the public URL
                            img_context["image_url"] = public_url
                            # Also set on main item for easier access if it's a figure
                            if item.get("type") in [
                                    "figure", "chart", "Image"
                            ]:
                                item["image_url"] = public_url

                            image_urls.append(public_url)
                            logger.info(f"Uploaded image to {public_url}")

        if isinstance(extraction_data, list):
            process_image_items(extraction_data)
        elif isinstance(extraction_data, dict) and "pages" in extraction_data:
            # Handle page-based structure
            for page in extraction_data["pages"]:
                if "elements" in page:
                    process_image_items(page["elements"])

        # Save Extraction to Subcollection (Classic Architecture Support)
        if extraction_data:
            try:
                # Use raw client to access subcollection
                if db.db:
                    results_ref = db.db.collection('documents').document(
                        document_id).collection('results')
                    results_ref.document('extraction').set({
                        "content":
                        extraction_data,
                        "image_urls":
                        image_urls,
                        "updated_at":
                        datetime.now(timezone.utc)
                    })
                    logger.info(
                        f"Saved extraction data to subcollection for {document_id}"
                    )
                else:
                    logger.warning(
                        f"Firestore client not available, skipping extraction save for {document_id}"
                    )
            except Exception as ex:
                logger.error(
                    f"Failed to save extraction data to subcollection: {ex}")

        # Update Job with Extraction Results
        # Note: We do NOT save the full 'extraction_data' to Firestore because it exceeds the 1MB limit
        # and may contain complex nested entities. The data is passed in-memory to the next steps.
        await db.update_job(
            job_id, {
                "stage": "extraction_done",
                "message": "Extraction completed",
                "stats": {
                    "items_extracted":
                    len(extraction_data)
                    if isinstance(extraction_data, list) else 0
                },
                "image_urls": image_urls
            })

        # --- 2. CHUNKING ---
        await db.update_job(job_id, {
            "stage": "chunking",
            "message": "Chunking content"
        })

        chunker = Chunker()
        chunks_data = await loop.run_in_executor(
            None, lambda: chunker.process(extraction_data))

        # --- 3. SUMMARIZATION / GENERATION ---
        await db.update_job(job_id, {
            "stage": "summarization",
            "message": "Generating slides with AI"
        })

        summarizer = Summarizer()

        # Now returns a dict with 'slides', 'chapters', 'summary'
        result_data = await loop.run_in_executor(
            None, lambda: summarizer.generate_slides(extraction_data))

        slides = result_data.get("slides", [])
        chapters = result_data.get("chapters", [])
        summary = result_data.get("summary", {})

        # Save Summary and Generation to Subcollections (Classic Architecture Support)
        try:
            if db.db:
                results_ref = db.db.collection('documents').document(
                    document_id).collection('results')

                # Save Summary
                results_ref.document('summarization').set(summary)

                # Save Generation (Slides & Chapters)
                results_ref.document('generation').set({
                    "slides":
                    slides,
                    "chapters":
                    chapters,
                    "updated_at":
                    datetime.now(timezone.utc)
                })
                logger.info(
                    f"Saved summary and generation data to subcollections for {document_id}"
                )
            else:
                logger.warning(
                    f"Firestore client not available, skipping summary/generation save for {document_id}"
                )
        except Exception as ex:
            logger.error(f"Failed to save summary/generation data: {ex}")

        # --- 4. COMPLETED ---

        # Save final result
        await db.update_job(
            job_id, {
                "status": "completed",
                "stage": "generation_done",
                "message": "Processing finished successfully",
                "result_json": {
                    "slides": slides,
                    "chapters": chapters
                },
                "updated_at": datetime.now(timezone.utc)
            })

        # Also update the Document record status if needed
        await db.update_document_status(document_id, "completed")

        logger.info(
            f"Job {job_id} / Document {document_id} processing completed.")

    except Exception as e:
        logger.error(f"Error in processing pipeline for job {job_id}: {e}")
        await db.update_job(
            job_id, {
                "status": "error",
                "message": str(e),
                "updated_at": datetime.now(timezone.utc)
            })
        await db.update_document_status(document_id, "error")


@router.get("/documents/{document_id}")
async def get_document(document_id: str, db: FirestoreDAO = Depends(get_db)):
    document = await db.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/documents")
async def list_documents(limit: int = 50, db: FirestoreDAO = Depends(get_db)):
    """List all recent documents (anonymous/stateless)."""
    return await db.get_all_documents(limit=limit)


@router.post("/process")
async def start_process(request: UploadURLRequest,
                        background_tasks: BackgroundTasks,
                        db: FirestoreDAO = Depends(get_db)):
    """
    Start the processing pipeline using the new Job-based architecture.
    """
    # 1. Create Document Record
    filename = request.url.split("/")[-1] or f"doc_{uuid.uuid4()}.pdf"
    document_id = request.id if request.id else str(uuid.uuid4())

    # Define local path for processing
    upload_dir = os.path.join(settings.base_dir, "data", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{document_id}_{filename}")

    # Download file locally for processing
    try:
        await download_file(request.url, file_path)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download file from Supabase: {str(e)}")

    # Save initial document record
    await db.create_document({
        "id": document_id,
        "filename": filename,
        "source_url": request.url,
        "user_id": request.user_id,  # Can be "anonymous" or ignored
        "status": "processing",
        "upload_date": datetime.now(timezone.utc)
    })

    # 2. Create Job Record
    job_id = f"job_{document_id}"
    await db.create_job({
        "id": job_id,
        "document_id": document_id,
        "user_id": request.user_id,  # Can be "anonymous" or ignored
        "file_url": request.url,
        "status": "processing",
        "stage": "started",
        "created_at": datetime.now(timezone.utc)
    })

    # 3. Start Background Worker
    background_tasks.add_task(process_full_pipeline, job_id, document_id,
                              file_path, db)

    return {
        "message": "Processing started",
        "job_id": job_id,
        "document_id": document_id
    }


# Backward compatibility (Upload from URL) - maps to start_process logic
@router.post("/upload-url")
async def upload_from_url(request: UploadURLRequest,
                          background_tasks: BackgroundTasks,
                          db: FirestoreDAO = Depends(get_db)):
    return await start_process(request, background_tasks, db)
