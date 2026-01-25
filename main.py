from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from utils.logging_config import setup_logging
from utils.firebase import initialize_firebase
from services import content_router

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Starting up application...")
    initialize_firebase()
    logger.info("Firebase initialized")
    yield
    # Shutdown
    logger.info("Shutting down application...")


app = FastAPI(
    title="EduSphere AI Core",
    description="Services for EduSphere AI",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,
)

# Include routers
app.include_router(content_router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to EduSphere AI Core API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/check")
async def health_check(name: str):
    return {"message": "Hello World!"}
