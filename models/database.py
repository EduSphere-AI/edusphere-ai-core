from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, backref
from sqlalchemy import Column, Integer, String, DateTime, Boolean, func, ForeignKey, Text, JSON
import os

# Database URL - update with your PostgreSQL credentials
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/edusphere")

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True)

# Create session factory
async_session_maker = async_sessionmaker(engine,
                                         class_=AsyncSession,
                                         expire_on_commit=False)

# Base class for models
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String,
                             nullable=True)  # Nullable for Google auth users
    full_name = Column(String, nullable=True)
    firebase_uid = Column(String, unique=True, nullable=True,
                          index=True)  # For Google auth
    auth_provider = Column(String, default="email")  # "email" or "google"
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    documents = relationship("Document", back_populates="user")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(
        String, default="uploaded")  # uploaded, processing, completed, error

    user = relationship("User", back_populates="documents")
    extracted_content = relationship("ExtractedContent",
                                     back_populates="document",
                                     cascade="all, delete-orphan")
    chunks = relationship("Chunk",
                          back_populates="document",
                          cascade="all, delete-orphan")


class ExtractedContent(Base):
    __tablename__ = "extracted_content"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    content_type = Column(String,
                          nullable=False)  # header, paragraph, image, etc.
    text_content = Column(Text, nullable=True)
    metadata_info = Column(JSON, nullable=True)  # Position, style, etc.
    sequence_order = Column(Integer, nullable=False)
    parent_id = Column(Integer,
                       ForeignKey("extracted_content.id"),
                       nullable=True)  # For hierarchy

    document = relationship("Document", back_populates="extracted_content")
    children = relationship("ExtractedContent",
                            backref=backref("parent", remote_side=[id]))


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    sequence_order = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    content = Column(
        Text, nullable=False)  # The summarized/formatted content for the slide
    source_content_ids = Column(
        JSON, nullable=True)  # List of ExtractedContent IDs used
    chunk_type = Column(String, default="slide")  # slide, question_group

    document = relationship("Document", back_populates="chunks")
    learn_controls = relationship("LearnControl",
                                  back_populates="chunk",
                                  cascade="all, delete-orphan")


class LearnControl(Base):
    __tablename__ = "learn_controls"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("chunks.id"))
    question_text = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=True)  # Expected answer or key points
    question_type = Column(String, default="free_text")

    chunk = relationship("Chunk", back_populates="learn_controls")


# Dependency to get database session
async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Function to create all tables
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Function to drop all tables (use with caution)
async def drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
