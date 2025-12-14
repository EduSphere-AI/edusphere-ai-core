from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging

from utils.logging_config import setup_logging
from utils.firebase import initialize_firebase
from services import auth_router
from models import create_tables

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Starting up application...")
    initialize_firebase()
    await create_tables()
    logger.info("Database tables created/verified")
    yield
    # Shutdown
    logger.info("Shutting down application...")


app = FastAPI(
    title="EduSphere AI Core",
    description="Services for EduSphere AI",
    version="0.1.0",
    lifespan=lifespan,
)


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


app.include_router(auth_router)
