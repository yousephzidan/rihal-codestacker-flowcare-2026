"""
FlowCare - Queue & Appointment Booking System

Main FastAPI application entry point for FlowCare service branches in Oman.

Quick Start:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings, setup_directories
from app.core.database import init_db, SessionLocal
from app.api import public, auth, customers, management, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    
    Handles startup (setup directories, init DB, seed data) and shutdown.
    """
    settings = get_settings()
    
    setup_directories()
    
    init_db()
    
    from app.services.seed_service import seed_database
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    
    yield
    

app = FastAPI(
    title="FlowCare API",
    description="Queue & Appointment Booking System for FlowCare Service Branches",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(management.router)
app.include_router(files.router)


@app.get("/")
def root():
    """Root endpoint returning API info"""
    return {
        "name": "FlowCare API",
        "version": "1.0.0",
        "description": "Queue & Appointment Booking System"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

