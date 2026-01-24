from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DocumentBase(BaseModel):
    filename: str
    file_path: str


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: int
    user_id: int
    upload_date: datetime
    status: str

    class Config:
        from_attributes = True


class ExtractedContentBase(BaseModel):
    content_type: str
    text_content: Optional[str] = None
    metadata_info: Optional[Dict[str, Any]] = None
    sequence_order: int
    parent_id: Optional[int] = None


class ExtractedContentCreate(ExtractedContentBase):
    document_id: int


class ExtractedContentResponse(ExtractedContentBase):
    id: int
    document_id: int

    class Config:
        from_attributes = True


class LearnControlBase(BaseModel):
    question_text: str
    answer_text: Optional[str] = None
    question_type: str = "free_text"


class LearnControlCreate(LearnControlBase):
    chunk_id: int


class LearnControlResponse(LearnControlBase):
    id: int
    chunk_id: int

    class Config:
        from_attributes = True


class ChunkBase(BaseModel):
    sequence_order: int
    title: Optional[str] = None
    content: str
    source_content_ids: Optional[List[int]] = None
    chunk_type: str = "slide"


class ChunkCreate(ChunkBase):
    document_id: int


class ChunkResponse(ChunkBase):
    id: int
    document_id: int
    learn_controls: List[LearnControlResponse] = []

    class Config:
        from_attributes = True
