from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from routes.projects import router as projects_router

app = FastAPI(title="Project Service", version="1.0.0")

# Setup CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include project router
app.include_router(projects_router)

# Startup and shutdown events to manage DB connection
from db import db_manager

@app.on_event("startup")
async def startup_event():
    await db_manager.connect_to_database()

@app.on_event("shutdown")
async def shutdown_event():
    await db_manager.close_database_connection()
